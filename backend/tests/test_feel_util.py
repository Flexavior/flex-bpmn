from __future__ import annotations

import json
from pathlib import Path

from app.schemas.process_json import ProcessModel
from app.services import bpmn_generator
from app.utils.feel_util import normalize_feel_condition, normalize_process_model

ROOT = Path(__file__).resolve().parents[2]
GENERATED = ROOT / "backend" / "app" / "generated"


def test_normalize_feel_replaces_double_equals() -> None:
    assert normalize_feel_condition("decision == 'approved'") == "decision = 'approved'"
    assert normalize_feel_condition("decision -- 'rejected'") == "decision = 'rejected'"
    assert normalize_feel_condition("amount >= 500") == "amount >= 500"


def test_normalize_strips_default_flow_condition() -> None:
    model = ProcessModel.model_validate(
        {
            "process": {"id": "gw_test", "name": "GW"},
            "nodes": [
                {"id": "start", "nodeType": "startEvent", "name": "Start"},
                {"id": "gw", "nodeType": "exclusiveGateway", "name": "GW"},
                {"id": "end", "nodeType": "endEvent", "name": "End"},
            ],
            "flows": [
                {"from": "start", "to": "gw"},
                {"from": "gw", "to": "end", "condition": "decision == 'approved'"},
                {"from": "gw", "to": "end", "condition": "decision == 'rejected'", "default": True},
            ],
        }
    )
    fixed = normalize_process_model(model)
    assert fixed.flows[1].condition == "decision = 'approved'"
    assert fixed.flows[2].condition is None
    assert fixed.flows[2].is_default is True


def test_student_payment_approval_xml_is_camunda_feel() -> None:
    path = GENERATED / "student_course_payment_approval_20260822_212304.json"
    if not path.exists():
        return
    model = ProcessModel.model_validate(json.loads(path.read_text(encoding="utf-8")))
    xml = bpmn_generator.generate_bpmn(model)
    assert "= decision = 'approved'" in xml
    assert "==" not in xml
    assert 'default="Flow_6"' in xml or 'default="Flow_5"' in xml
