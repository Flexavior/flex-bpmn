"""Semantic validation of a ProcessModel and of generated BPMN."""

from __future__ import annotations

from app.schemas.process_json import NodeType, ProcessModel
from app.schemas.response import ValidationIssue, ValidationReport


def validate_process(model: ProcessModel) -> ValidationReport:
    issues: list[ValidationIssue] = []
    types = {n.id: n.node_type for n in model.nodes}
    node_ids = list(types)

    seen: set[str] = set()
    for nid in node_ids:
        if nid in seen:
            issues.append(ValidationIssue(severity="error", code="DUP_ID", message=f"Duplicate node id: {nid}"))
        seen.add(nid)

    starts = [nid for nid, t in types.items() if t == NodeType.START_EVENT]
    ends = [nid for nid, t in types.items() if t == NodeType.END_EVENT]
    if len(starts) != 1:
        issues.append(
            ValidationIssue(
                severity="error",
                code="START_EVENT",
                message=f"Expected exactly 1 startEvent, found {len(starts)}.",
            )
        )
    if len(ends) < 1:
        issues.append(
            ValidationIssue(severity="error", code="END_EVENT", message="Process has no endEvent.")
        )

    incoming: dict[str, list[str]] = {nid: [] for nid in node_ids}
    outgoing: dict[str, list[str]] = {nid: [] for nid in node_ids}

    for flow in model.flows:
        if flow.from_id not in types:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="BAD_FLOW_SRC",
                    message=f"Flow from unknown node: {flow.from_id}",
                )
            )
        elif flow.to not in types:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="BAD_FLOW_TGT",
                    message=f"Flow to unknown node: {flow.to}",
                )
            )
        if flow.from_id in types and flow.to in types:
            incoming[flow.to].append(flow.from_id)
            outgoing[flow.from_id].append(flow.to)
            src_type = types[flow.from_id]
            if src_type == NodeType.PARALLEL_GATEWAY and flow.condition:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="PARALLEL_CONDITION",
                        message=f"Parallel gateway {flow.from_id} cannot carry a condition.",
                    )
                )
            if src_type == NodeType.EXCLUSIVE_GATEWAY and flow.is_default and flow.condition:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        code="DEFAULT_WITH_CONDITION",
                        message=f"Default flow {flow.from_id}->{flow.to} should not carry a condition (auto-fixed when drawing).",
                    )
                )
            if flow.condition and ("==" in flow.condition or " -- " in flow.condition):
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        code="INVALID_FEEL_OP",
                        message=(
                            f"Condition on {flow.from_id}->{flow.to} uses JS-style operators; "
                            "Camunda FEEL requires single = (auto-fixed when drawing)."
                        ),
                    )
                )

    lane_ids = {lane.id for lane in model.lanes}
    for node in model.nodes:
        if node.lane and node.lane not in lane_ids:
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="UNKNOWN_LANE",
                    message=f"Node '{node.id}' references unknown lane '{node.lane}'.",
                )
            )
        elif not node.lane and model.lanes:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="MISSING_LANE",
                    message=f"Node '{node.id}' has no lane (auto-assigned when drawing).",
                )
            )

    if not model.lanes:
        issues.append(
            ValidationIssue(
                severity="warning",
                code="NO_LANES",
                message="Process has no swimlanes; lanes will be inferred from task owners when drawing.",
            )
        )

    for lane in model.lanes:
        assigned = [n.id for n in model.nodes if n.lane == lane.id]
        if not assigned:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    code="EMPTY_LANE",
                    message=f"Lane '{lane.id}' has no flow nodes.",
                )
            )

    for nid, t in types.items():
        if t == NodeType.EXCLUSIVE_GATEWAY:
            out = [f for f in model.flows if f.from_id == nid]
            if len(out) < 1:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="GATEWAY_NO_OUT",
                        message=f"Gateway {nid} has no outgoing flow.",
                    )
                )
            has_default = any(f.is_default for f in out)
            for f in out:
                if not f.condition and not f.is_default and not has_default and len(out) > 1:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            code="MISSING_CONDITION",
                            message=f"Gateway {nid} branch -> {f.to} has no condition.",
                        )
                    )

    for nid, t in types.items():
        if t == NodeType.START_EVENT:
            if not outgoing.get(nid):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        code="START_NO_OUT",
                        message="startEvent has no outgoing flow.",
                    )
                )
            continue
        if not incoming.get(nid):
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="ORPHAN_NODE",
                    message=f"Node '{nid}' has no incoming flow.",
                )
            )
        if t != NodeType.END_EVENT and not outgoing.get(nid):
            issues.append(
                ValidationIssue(
                    severity="error",
                    code="DEAD_END",
                    message=f"Node '{nid}' has no outgoing flow.",
                )
            )

    valid = not any(i.severity == "error" for i in issues)
    return ValidationReport(valid=valid, issues=issues)
