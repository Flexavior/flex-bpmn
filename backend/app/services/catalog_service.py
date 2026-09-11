"""PRD-backed process catalog (no LLM)."""

from __future__ import annotations

import json
from app.config import CATALOG_PATH, EXAMPLES_DIR
from app.schemas.process_json import ProcessModel
from app.services import bpmn_generator, validator


def list_catalog() -> list[dict]:
    if not CATALOG_PATH.exists():
        return []
    items = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return items if isinstance(items, list) else []


def load_example(process_id: str) -> ProcessModel:
    allowed = {item["id"]: item["file"] for item in list_catalog() if "id" in item and "file" in item}
    if process_id not in allowed:
        # Fall back to any examples/*.json with matching process.id after schema check.
        path = EXAMPLES_DIR / f"{process_id}.json"
        if not path.exists() or path.resolve().parent != EXAMPLES_DIR.resolve():
            raise FileNotFoundError(f"Unknown catalog process: {process_id}")
    else:
        path = EXAMPLES_DIR / allowed[process_id]
        if path.resolve().parent != EXAMPLES_DIR.resolve():
            raise FileNotFoundError(f"Unknown catalog process: {process_id}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return ProcessModel.model_validate(data)


def render_catalog_item(process_id: str) -> tuple[ProcessModel, str]:
    model = load_example(process_id)
    report = validator.validate_process(model)
    if not report.valid:
        raise ValueError("; ".join(i.message for i in report.issues if i.severity == "error"))
    return model, bpmn_generator.generate_bpmn(model)
