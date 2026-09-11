from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.api import chat as chat_api
from app.main import app
from app.services.workflow_service import WorkflowService

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def _load(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


class FakeGateway:
    last_result = ("test", "test-model")

    def chat(self, system, user, *, temperature=0.2, model=None, provider=None):
        return json.dumps(_load("lms_student_enrollment.json"))

    def provider_statuses(self):
        return [
            {
                "name": "ollama",
                "configured": True,
                "available": True,
                "models": ["test-model"],
                "reason": "ok",
            },
            {
                "name": "openai",
                "configured": False,
                "available": False,
                "models": [],
                "reason": "no_api_key",
            },
        ]


def test_health_and_ready() -> None:
    client = TestClient(app)
    assert client.get("/healthz").json()["status"] == "ok"
    assert client.get("/readyz").json()["status"] == "ready"


def test_catalog_and_item() -> None:
    client = TestClient(app)
    listing = client.get("/api/catalog")
    assert listing.status_code == 200
    ids = [i["id"] for i in listing.json()["items"]]
    assert "lms_exam_attempt" in ids
    item = client.get("/api/catalog/lms_exam_attempt")
    assert item.status_code == 200
    body = item.json()
    assert "BPMNDiagram" in body["bpmn"]
    assert body["process"]["process"]["id"] == "lms_exam_attempt"


def test_provider_status_has_no_secret_fields() -> None:
    client = TestClient(app)
    previous = chat_api.workflow
    chat_api.workflow = WorkflowService(llm=FakeGateway())
    try:
        res = client.get("/api/providers")
        assert res.status_code == 200
        body = res.json()
        assert body["providers"][0]["name"] == "ollama"
        assert body["providers"][1]["reason"] == "no_api_key"
        for provider in body["providers"]:
            keys = {key.lower() for key in provider}
            assert "api_key" not in keys
            assert "authorization" not in keys
            assert "token" not in keys
    finally:
        chat_api.workflow = previous


def test_validate_and_generate() -> None:
    client = TestClient(app)
    payload = {"process": _load("lms_admin_provisioning.json")}
    assert client.post("/api/validate", json=payload).json()["valid"] is True
    rendered = client.post("/api/generate-bpmn", json=payload)
    assert rendered.status_code == 200
    assert "http://www.omg.org/spec/BPMN/20100524/MODEL" in rendered.json()["bpmn"]


def test_chat_with_fake_gateway() -> None:
    client = TestClient(app)
    previous = chat_api.workflow
    chat_api.workflow = WorkflowService(llm=FakeGateway())
    try:
        res = client.post(
            "/api/chat",
            json={
                "prompt": "Create the student enrollment workflow from the LMS PRD",
                "provider": "ollama",
                "model": "test-model",
            },
        )
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["process"]["process"]["id"] == "lms_student_enrollment"
        assert body["validation"]["valid"] is True
        assert body["bpmn"] is None
        assert body["bpmn_path"] is None
        assert body["llm_model"] == "test-model"

        rendered = client.post(
            "/api/generate-bpmn",
            json={"process": body["process"]},
        )
        assert rendered.status_code == 200
        xml = rendered.json()["bpmn"]
        assert "http://www.omg.org/spec/BPMN/20100524/MODEL" in xml
        assert "BPMNDiagram" in xml
        assert "zeebe:userTask" in xml
        assert "zeebe:taskDefinition" in xml
    finally:
        chat_api.workflow = previous


def test_invalid_draft_cannot_be_drawn() -> None:
    client = TestClient(app)
    broken = {
        "process": {"id": "broken_process", "name": "Broken process"},
        "nodes": [
            {"id": "start", "nodeType": "startEvent", "name": "Start"},
            {"id": "orphan", "nodeType": "userTask", "name": "Orphan"},
            {"id": "finish", "nodeType": "endEvent", "name": "End"},
        ],
        "flows": [{"from": "start", "to": "finish"}],
    }
    validation = client.post("/api/validate", json={"process": broken})
    assert validation.status_code == 200
    assert validation.json()["valid"] is False

    rendered = client.post("/api/generate-bpmn", json={"process": broken})
    assert rendered.status_code == 422


def test_deploy_disabled_by_default(monkeypatch) -> None:
    from app.services import camunda_service

    monkeypatch.setattr(camunda_service, "CAMUNDA_DEPLOY_ENABLED", False)
    client = TestClient(app)
    xml = client.get("/api/catalog/lms_exam_appeal").json()["bpmn"]
    res = client.post("/api/deploy", json={"process_id": "lms_exam_appeal", "bpmn": xml})
    assert res.status_code == 503
    assert "disabled" in res.json()["detail"].lower()


def test_docs_hidden_contract_in_dev() -> None:
    client = TestClient(app)
    assert client.get("/docs").status_code in (200, 404)
