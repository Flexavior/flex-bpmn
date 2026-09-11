"""Swimlane normalization — infer lanes and assign nodes to owners."""

from __future__ import annotations

from app.schemas.process_json import NodeType, ProcessLane, ProcessModel, ProcessNode

PREFERRED_LANE_ORDER = ("student", "teacher", "admin", "system", "general")

DEFAULT_LABELS = {
    "student": "Student",
    "teacher": "Teacher",
    "admin": "Admin Staff",
    "system": "System",
    "general": "General",
}

KEYWORD_HINTS: dict[str, tuple[str, ...]] = {
    "student": ("student", "learner", "pupil", "trainee"),
    "teacher": ("teacher", "instructor", "faculty", "grader", "trainer"),
    "admin": ("admin", "staff", "registrar", "finance", "manager", "hr"),
    "candidate": ("candidate", "applicant", "job seeker", "interviewee"),
    "employer": ("employer", "hiring manager", "recruiter", "company"),
    "regulator": ("regulator", "compliance", "auditor", "inspection", "authority"),
    "trainer": ("trainer", "coach", "mentor", "skills trainer"),
    "system": ("automated", "batch", "integration", "api"),
}


def _lane_keywords(lane: ProcessLane) -> tuple[str, ...]:
    parts = [lane.id.replace("_", " "), lane.name.lower()]
    parts.extend(actor.replace("_", " ") for actor in lane.actors)
    return tuple(p for p in parts if p)


def _guess_lane_from_text(text: str, lanes: list[ProcessLane]) -> str | None:
    lower = text.lower()
    for lane in lanes:
        for keyword in _lane_keywords(lane):
            if keyword and keyword in lower:
                return lane.id
    for lane_id, keywords in KEYWORD_HINTS.items():
        if any(keyword in lower for keyword in keywords):
            return lane_id
    return None


def _guess_lane_for_node(node: ProcessNode, lanes: list[ProcessLane]) -> str:
    if node.node_type == NodeType.SERVICE_TASK:
        return "system"
    from_name = _guess_lane_from_text(node.name, lanes)
    if from_name:
        return from_name
    if node.node_type == NodeType.USER_TASK:
        return "general"
    return "system"


def _build_incoming(model: ProcessModel) -> dict[str, list[str]]:
    incoming: dict[str, list[str]] = {node.id: [] for node in model.nodes}
    for flow in model.flows:
        if flow.to in incoming:
            incoming[flow.to].append(flow.from_id)
    return incoming


def _build_outgoing(model: ProcessModel) -> dict[str, list[str]]:
    outgoing: dict[str, list[str]] = {node.id: [] for node in model.nodes}
    for flow in model.flows:
        if flow.from_id in outgoing:
            outgoing[flow.from_id].append(flow.to)
    return outgoing


def _resolve_lanes(model: ProcessModel) -> dict[str, str]:
    lane_by_node: dict[str, str] = {}
    for node in model.nodes:
        if node.lane:
            lane_by_node[node.id] = node.lane

    incoming = _build_incoming(model)
    outgoing = _build_outgoing(model)

    for node in model.nodes:
        if node.id in lane_by_node:
            continue
        lane_by_node[node.id] = _guess_lane_for_node(node, model.lanes)

    changed = True
    while changed:
        changed = False
        for node in model.nodes:
            if node.node_type not in (
                NodeType.EXCLUSIVE_GATEWAY,
                NodeType.PARALLEL_GATEWAY,
                NodeType.END_EVENT,
                NodeType.START_EVENT,
            ):
                continue
            sources = incoming.get(node.id, [])
            if not sources:
                continue
            upstream = lane_by_node.get(sources[0], "system")
            for src in sources[1:]:
                if lane_by_node.get(src) != upstream:
                    upstream = "system"
                    break
            if lane_by_node.get(node.id) != upstream:
                lane_by_node[node.id] = upstream
                changed = True

    for node in model.nodes:
        if node.node_type != NodeType.START_EVENT:
            continue
        targets = outgoing.get(node.id, [])
        if targets:
            lane_by_node[node.id] = lane_by_node.get(targets[0], "general")

    return lane_by_node


def _lane_sort_key(lane_id: str) -> tuple[int, str]:
    try:
        return (PREFERRED_LANE_ORDER.index(lane_id), lane_id)
    except ValueError:
        return (len(PREFERRED_LANE_ORDER), lane_id)


def _lane_display_name(lane_id: str) -> str:
    return DEFAULT_LABELS.get(lane_id, lane_id.replace("_", " ").title())


def _default_actors(lane_id: str, explicit: list[str] | None = None) -> list[str]:
    if explicit:
        return explicit
    if lane_id == "system":
        return ["system"]
    return [lane_id]


def normalize_lanes(model: ProcessModel) -> ProcessModel:
    """Ensure every node belongs to a swimlane; lanes list matches assignments."""
    known_lane_ids = {lane.id for lane in model.lanes}
    lane_by_node = _resolve_lanes(model)

    for node in model.nodes:
        if node.lane and node.lane not in known_lane_ids:
            known_lane_ids.add(node.lane)

    used_lane_ids = set(lane_by_node.values())
    lane_defs = {lane.id: lane for lane in model.lanes}

    for lane_id in used_lane_ids:
        if lane_id not in lane_defs:
            lane_defs[lane_id] = ProcessLane(
                id=lane_id,
                name=_lane_display_name(lane_id),
                actors=_default_actors(lane_id),
            )
        elif not lane_defs[lane_id].actors and lane_id != "system":
            lane_defs[lane_id] = lane_defs[lane_id].model_copy(
                update={"actors": _default_actors(lane_id)}
            )

    lanes = sorted(lane_defs.values(), key=lambda lane: _lane_sort_key(lane.id))
    lanes = [lane for lane in lanes if lane.id in used_lane_ids]

    nodes = []
    nodes_changed = False
    for node in model.nodes:
        lane_id = lane_by_node[node.id]
        if node.lane != lane_id:
            nodes.append(node.model_copy(update={"lane": lane_id}))
            nodes_changed = True
        else:
            nodes.append(node)

    lanes_changed = lanes != model.lanes
    if not lanes_changed and not nodes_changed:
        return model
    return model.model_copy(update={"lanes": lanes, "nodes": nodes})
