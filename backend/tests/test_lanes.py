from __future__ import annotations

import json
from pathlib import Path

from app.schemas.process_json import ProcessModel
from app.services import bpmn_generator
from app.utils.lane_util import normalize_lanes

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "examples"


def _load(name: str) -> ProcessModel:
    return ProcessModel.model_validate(json.loads((EXAMPLES / name).read_text(encoding="utf-8")))


def test_normalize_assigns_lanes_to_legacy_example() -> None:
    model = _load("lms_student_enrollment.json")
    assert model.lanes == []
    fixed = normalize_lanes(model)
    assert len(fixed.lanes) >= 2
    assert all(node.lane for node in fixed.nodes)
    student_nodes = [n.id for n in fixed.nodes if n.lane == "student"]
    assert "submit_request" in student_nodes


def test_bpmn_xml_contains_swimlanes() -> None:
    model = normalize_lanes(_load("lms_exam_appeal.json"))
    xml = bpmn_generator.generate_bpmn(model)
    assert "<bpmn:laneSet" in xml
    assert "<bpmn:lane " in xml
    assert "flowNodeRef" in xml
    assert 'isHorizontal="true"' in xml
    assert "candidateGroups" in xml


def test_user_task_gets_lane_candidate_group() -> None:
    model = normalize_lanes(_load("lms_exam_attempt.json"))
    xml = bpmn_generator.generate_bpmn(model)
    assert 'candidateGroups="student"' in xml or 'candidateGroups="teacher"' in xml


def test_custom_domain_lanes_from_llm_shape() -> None:
    model = ProcessModel.model_validate(
        {
            "process": {"id": "skill_training_flow", "name": "Skills Training Accreditation"},
            "lanes": [
                {"id": "trainee", "name": "Trainee", "actors": ["trainee"]},
                {"id": "employer", "name": "Employer", "actors": ["employer"]},
                {"id": "regulator", "name": "Regulator", "actors": ["regulator"]},
                {"id": "system", "name": "System", "actors": ["system"]},
            ],
            "nodes": [
                {"id": "start", "nodeType": "startEvent", "name": "Start", "lane": "trainee"},
                {
                    "id": "submit_application",
                    "nodeType": "userTask",
                    "name": "Employer submits training plan",
                    "lane": "employer",
                },
                {
                    "id": "regulator_review",
                    "nodeType": "userTask",
                    "name": "Regulator reviews accreditation",
                    "lane": "regulator",
                },
                {"id": "notify", "nodeType": "serviceTask", "name": "Notify parties", "lane": "system"},
                {"id": "end", "nodeType": "endEvent", "name": "End", "lane": "trainee"},
            ],
            "flows": [
                {"from": "start", "to": "submit_application"},
                {"from": "submit_application", "to": "regulator_review"},
                {"from": "regulator_review", "to": "notify"},
                {"from": "notify", "to": "end"},
            ],
        }
    )
    xml = bpmn_generator.generate_bpmn(model)
    assert '<bpmn:lane id="employer"' in xml
    assert '<bpmn:lane id="regulator"' in xml
    assert 'candidateGroups="employer"' in xml
    assert 'candidateGroups="regulator"' in xml


def test_explicit_lanes_validate() -> None:
    model = ProcessModel.model_validate(
        {
            "process": {"id": "lane_demo", "name": "Lane Demo"},
            "lanes": [
                {"id": "student", "name": "Student", "actors": ["student"]},
                {"id": "system", "name": "System", "actors": ["system"]},
            ],
            "nodes": [
                {"id": "start", "nodeType": "startEvent", "name": "Start", "lane": "student"},
                {"id": "pay", "nodeType": "userTask", "name": "Student pays", "lane": "student"},
                {"id": "notify", "nodeType": "serviceTask", "name": "Send receipt", "lane": "system"},
                {"id": "end", "nodeType": "endEvent", "name": "End", "lane": "student"},
            ],
            "flows": [
                {"from": "start", "to": "pay"},
                {"from": "pay", "to": "notify"},
                {"from": "notify", "to": "end"},
            ],
        }
    )
    xml = bpmn_generator.generate_bpmn(model)
    assert '<bpmn:lane id="student"' in xml
    assert '<bpmn:lane id="system"' in xml
    assert 'candidateGroups="student"' in xml
