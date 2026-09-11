"""Normalize gateway conditions to Camunda FEEL syntax."""

from __future__ import annotations

import re

from app.schemas.process_json import ProcessModel

_DASH_EQ = re.compile(r"\s--\s+")


def normalize_feel_condition(condition: str) -> str:
    """Convert common JS-style operators to Camunda FEEL (= not ==)."""
    text = condition.strip()
    text = _DASH_EQ.sub(" = ", text)
    text = text.replace("===", "=")
    text = text.replace("==", "=")
    return text


def normalize_process_model(model: ProcessModel) -> ProcessModel:
    """Repair LLM quirks before BPMN generation (FEEL ops, default flows)."""
    flows = []
    changed = False
    for flow in model.flows:
        cond = normalize_feel_condition(flow.condition) if flow.condition else None
        if flow.is_default and cond:
            cond = None
        if cond != flow.condition:
            changed = True
            flows.append(flow.model_copy(update={"condition": cond}))
        else:
            flows.append(flow)
    if not changed:
        return model
    return model.model_copy(update={"flows": flows})
