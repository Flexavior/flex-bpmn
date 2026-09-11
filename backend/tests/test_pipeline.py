from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.process_json import ProcessModel
from app.services import bpmn_generator, catalog_service, validator
from app.utils import xml_util

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples"
MODEL_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"


def _load(name: str) -> ProcessModel:
    return ProcessModel.model_validate(json.loads((EXAMPLES / name).read_text(encoding="utf-8")))


@pytest.mark.parametrize(
    "name",
    [
        "employee.json",
        "expense.json",
        "invoice.json",
        "lms_student_enrollment.json",
        "lms_exam_authoring.json",
        "lms_exam_attempt.json",
        "lms_admin_provisioning.json",
        "lms_exam_appeal.json",
    ],
)
def test_examples_validate_and_render(name: str) -> None:
    model = _load(name)
    report = validator.validate_process(model)
    assert report.valid, [i.message for i in report.issues]
    xml = bpmn_generator.generate_bpmn(model)
    assert MODEL_NS in xml
    assert "BPMNDiagram" in xml
    assert "BPMNShape" in xml
    assert "<bpmn:laneSet" in xml
    assert "<bpmn:process" in xml or "process " in xml
    root = xml_util.parse_xml(xml)
    assert root is not None
    assert root.tag == f"{{{MODEL_NS}}}definitions"


def test_lms_enrollment_is_camunda_ready() -> None:
    xml = bpmn_generator.generate_bpmn(_load("lms_student_enrollment.json"))
    assert "zeebe:userTask" in xml or "{http://camunda.org/schema/zeebe/1.0}userTask" in xml
    assert "taskDefinition" in xml
    assert "= eligible = false" in xml
    assert "isExecutable=\"true\"" in xml


def test_feel_prefix_and_no_parallel_condition() -> None:
    xml = bpmn_generator.generate_bpmn(_load("lms_exam_attempt.json"))
    assert "= passed = true" in xml
    assert "grade_fork" in xml
    # parallel edges must not grow conditionExpression
    assert 1 <= xml.count("conditionExpression") <= 2


def test_catalog_prd_items_render() -> None:
    items = catalog_service.list_catalog()
    assert len(items) == 5
    for item in items:
        model, xml = catalog_service.render_catalog_item(item["id"])
        assert model.process.id == item["id"]
        assert MODEL_NS in xml


def test_unknown_catalog_is_rejected() -> None:
    with pytest.raises(FileNotFoundError):
        catalog_service.load_example("../secret")


def test_process_id_rejects_path_chars() -> None:
    with pytest.raises(ValidationError):
        ProcessModel.model_validate(
            {
                "process": {"id": "../etc/passwd", "name": "Bad"},
                "nodes": [
                    {"id": "start", "nodeType": "startEvent", "name": "Start"},
                    {"id": "end", "nodeType": "endEvent", "name": "End"},
                ],
                "flows": [{"from": "start", "to": "end"}],
            }
        )


def test_orphan_is_error() -> None:
    model = ProcessModel.model_validate(
        {
            "process": {"id": "broken_orphan", "name": "Broken"},
            "nodes": [
                {"id": "start", "nodeType": "startEvent", "name": "Start"},
                {"id": "lonely", "nodeType": "userTask", "name": "Orphan"},
                {"id": "end", "nodeType": "endEvent", "name": "End"},
            ],
            "flows": [{"from": "start", "to": "end"}],
        }
    )
    report = validator.validate_process(model)
    assert report.valid is False
    assert any(i.code == "ORPHAN_NODE" for i in report.issues)


def test_output_file_cannot_escape(tmp_path: Path) -> None:
    path = xml_util.output_file(tmp_path, "../../secret", ".bpmn")
    path.relative_to(tmp_path.resolve())
    assert path.suffix == ".bpmn"
