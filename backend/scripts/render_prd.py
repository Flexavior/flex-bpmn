"""Render catalog JSON models to examples/*.bpmn (no LLM)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services import catalog_service  # noqa: E402


def main() -> int:
    examples = ROOT / "examples"
    for item in catalog_service.list_catalog():
        model, xml = catalog_service.render_catalog_item(item["id"])
        path = examples / f"{model.process.id}.bpmn"
        path.write_text(xml, encoding="utf-8")
        print(f"wrote {path.name} ({len(xml)} chars)")
    for legacy in ("employee", "expense", "invoice"):
        model, xml = catalog_service.render_catalog_item(legacy) if False else _legacy(legacy)
        if xml:
            (examples / f"{legacy}.bpmn").write_text(xml, encoding="utf-8")
            print(f"wrote {legacy}.bpmn ({len(xml)} chars)")
    return 0


def _legacy(name: str):
    from app.schemas.process_json import ProcessModel
    from app.services import bpmn_generator, validator
    import json

    data = json.loads((ROOT / "examples" / f"{name}.json").read_text(encoding="utf-8"))
    model = ProcessModel.model_validate(data)
    report = validator.validate_process(model)
    if not report.valid:
        raise SystemExit(report.issues)
    return model, bpmn_generator.generate_bpmn(model)


if __name__ == "__main__":
    raise SystemExit(main())
