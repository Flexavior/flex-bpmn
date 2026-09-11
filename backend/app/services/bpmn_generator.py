"""Deterministic JSON(ProcessModel) -> BPMN 2.0 XML generator."""

from __future__ import annotations

from collections import defaultdict

from lxml import etree

from app.schemas.process_json import NodeType, ProcessModel
from app.utils import feel_util
from app.utils import lane_util
from app.utils import xml_util
from app.utils.logger import get_logger

log = get_logger(__name__)

NS_BPMN = xml_util.NS_BPMN
NS_BPMNDI = xml_util.NS_BPMNDI
NS_DC = xml_util.NS_DC
NS_DI = xml_util.NS_DI
NS_XSI = xml_util.NS_XSI
NS_ZEEBE = xml_util.NS_ZEEBE

_ELEMENT = {
    NodeType.START_EVENT: "startEvent",
    NodeType.END_EVENT: "endEvent",
    NodeType.TASK: "task",
    NodeType.USER_TASK: "userTask",
    NodeType.SERVICE_TASK: "serviceTask",
    NodeType.EXCLUSIVE_GATEWAY: "exclusiveGateway",
    NodeType.PARALLEL_GATEWAY: "parallelGateway",
}

_SIZE = {
    NodeType.START_EVENT: (36, 36),
    NodeType.END_EVENT: (36, 36),
    NodeType.EXCLUSIVE_GATEWAY: (50, 50),
    NodeType.PARALLEL_GATEWAY: (50, 50),
}

LANE_HEIGHT = 160.0
COL_W = 220.0
ORIGIN_X = 180.0
ORIGIN_Y = 80.0
LANE_X = 60.0


def _qn(ns: str, tag: str) -> str:
    return f"{{{ns}}}{tag}"


def _flow_ids(model: ProcessModel) -> dict[int, str]:
    out: dict[int, str] = {}
    for idx, flow in enumerate(model.flows):
        if flow.id:
            out[idx] = xml_util.safe_id(flow.id, prefix=f"Flow_{idx}")
        else:
            out[idx] = f"Flow_{idx + 1}"
    return out


def _feel(condition: str) -> str:
    text = condition.strip()
    return text if text.startswith("=") else f"= {text}"


def _is_exclusive(model: ProcessModel, node_id: str) -> bool:
    for n in model.nodes:
        if n.id == node_id:
            return n.node_type == NodeType.EXCLUSIVE_GATEWAY
    return False


def _compute_ranks(model: ProcessModel) -> dict[str, int]:
    outgoing: dict[str, list[str]] = defaultdict(list)
    for flow in model.flows:
        outgoing[flow.from_id].append(flow.to)

    starts = [n.id for n in model.nodes if n.node_type == NodeType.START_EVENT]
    rank: dict[str, int] = {sid: 0 for sid in starts}
    if not rank:
        return {n.id: 0 for n in model.nodes}

    # Relax ranks up to N times so cyclic flows (e.g. rework loops) converge.
    for _ in range(len(model.nodes)):
        changed = False
        for flow in model.flows:
            if flow.from_id not in rank:
                continue
            nxt_rank = rank[flow.from_id] + 1
            if flow.to not in rank or nxt_rank > rank[flow.to]:
                rank[flow.to] = nxt_rank
                changed = True
        if not changed:
            break

    for node in model.nodes:
        rank.setdefault(node.id, max(rank.values(), default=0) + 1)
    return rank


def _lane_index(model: ProcessModel) -> dict[str, int]:
    return {lane.id: idx for idx, lane in enumerate(model.lanes)}


def _layout_swimlanes(
    model: ProcessModel,
) -> tuple[dict[str, tuple[float, float, float, float]], dict[str, tuple[float, float, float, float]]]:
    """Lay out nodes inside horizontal swimlanes; return node boxes and lane boxes."""
    ranks = _compute_ranks(model)
    lane_idx = _lane_index(model)
    types = {n.id: n.node_type for n in model.nodes}

    node_boxes: dict[str, tuple[float, float, float, float]] = {}
    for node in model.nodes:
        if not node.lane or node.lane not in lane_idx:
            continue
        li = lane_idx[node.lane]
        w, h = _SIZE.get(types[node.id], (100, 80))
        x = ORIGIN_X + ranks[node.id] * COL_W
        y = ORIGIN_Y + li * LANE_HEIGHT + (LANE_HEIGHT - h) / 2
        node_boxes[node.id] = (x, y, w, h)

    max_rank = max(ranks.values()) if ranks else 0
    total_width = ORIGIN_X + (max_rank + 1) * COL_W + 80
    lane_boxes: dict[str, tuple[float, float, float, float]] = {}
    for lane in model.lanes:
        li = lane_idx[lane.id]
        lane_boxes[lane.id] = (LANE_X, ORIGIN_Y + li * LANE_HEIGHT, total_width - LANE_X, LANE_HEIGHT)

    return node_boxes, lane_boxes


def _anchor(box: tuple[float, float, float, float], side: str) -> tuple[float, float]:
    x, y, w, h = box
    if side == "right":
        return x + w, y + h / 2
    return x, y + h / 2


def _lane_actors(model: ProcessModel, lane_id: str | None) -> list[str]:
    if not lane_id:
        return []
    for lane in model.lanes:
        if lane.id == lane_id:
            return lane.actors
    return []


def generate_bpmn(model: ProcessModel) -> str:
    model = feel_util.normalize_process_model(model)
    model = lane_util.normalize_lanes(model)
    _validate_model(model)

    root = xml_util.build_root(model.process.id)
    proc_id = xml_util.safe_id(model.process.id, "Process_")
    proc = etree.SubElement(root, _qn(NS_BPMN, "process"))
    proc.set("id", proc_id)
    if model.process.name:
        proc.set("name", model.process.name)
    proc.set("isExecutable", "true")

    flow_ids = _flow_ids(model)
    node_elems: dict[str, etree._Element] = {}
    safe_node: dict[str, str] = {}
    safe_lane: dict[str, str] = {}

    lane_set = etree.SubElement(proc, _qn(NS_BPMN, "laneSet"))
    lane_set.set("id", f"LaneSet_{proc_id}")
    lane_elems: dict[str, etree._Element] = {}
    for lane in model.lanes:
        lane_el = etree.SubElement(lane_set, _qn(NS_BPMN, "lane"))
        lid = xml_util.safe_id(lane.id, "Lane_")
        safe_lane[lane.id] = lid
        lane_el.set("id", lid)
        lane_el.set("name", lane.name or lane.id)
        lane_elems[lane.id] = lane_el

    for node in model.nodes:
        tag = _ELEMENT[node.node_type]
        el = etree.SubElement(proc, _qn(NS_BPMN, tag))
        nid = xml_util.safe_id(node.id, "node_")
        safe_node[node.id] = nid
        el.set("id", nid)
        if node.name:
            el.set("name", node.name)
        if node.lane and node.lane in lane_elems:
            ref = etree.SubElement(lane_elems[node.lane], _qn(NS_BPMN, "flowNodeRef"))
            ref.text = nid
        if node.node_type == NodeType.USER_TASK:
            ext = etree.SubElement(el, _qn(NS_BPMN, "extensionElements"))
            actors = _lane_actors(model, node.lane)
            user_task = etree.SubElement(ext, _qn(NS_ZEEBE, "userTask"))
            if actors:
                assign = etree.SubElement(ext, _qn(NS_ZEEBE, "assignmentDefinition"))
                assign.set("candidateGroups", ",".join(actors))
        elif node.node_type == NodeType.SERVICE_TASK:
            ext = etree.SubElement(el, _qn(NS_BPMN, "extensionElements"))
            job = etree.SubElement(ext, _qn(NS_ZEEBE, "taskDefinition"))
            job.set("type", f"fxv.{proc_id}.{nid}")
        node_elems[node.id] = el

    inbound: dict[str, list[int]] = {n.id: [] for n in model.nodes}
    outbound: dict[str, list[int]] = {n.id: [] for n in model.nodes}
    for idx, f in enumerate(model.flows):
        if f.from_id in outbound:
            outbound[f.from_id].append(idx)
        if f.to in inbound:
            inbound[f.to].append(idx)

    for nid, el in node_elems.items():
        for idx in inbound.get(nid, []):
            etree.SubElement(el, _qn(NS_BPMN, "incoming")).text = flow_ids[idx]
        for idx in outbound.get(nid, []):
            etree.SubElement(el, _qn(NS_BPMN, "outgoing")).text = flow_ids[idx]

    for idx, f in enumerate(model.flows):
        sf = etree.SubElement(proc, _qn(NS_BPMN, "sequenceFlow"))
        sf.set("id", flow_ids[idx])
        sf.set("sourceRef", safe_node[f.from_id])
        sf.set("targetRef", safe_node[f.to])
        if f.condition and _is_exclusive(model, f.from_id) and not f.is_default:
            cond = etree.SubElement(sf, _qn(NS_BPMN, "conditionExpression"))
            cond.set(_qn(NS_XSI, "type"), "bpmn:tFormalExpression")
            cond.text = _feel(f.condition)
        if f.is_default and _is_exclusive(model, f.from_id):
            src = node_elems.get(f.from_id)
            if src is not None and not src.get("default"):
                src.set("default", flow_ids[idx])

    node_boxes, lane_boxes = _layout_swimlanes(model)
    diagram = etree.SubElement(root, _qn(NS_BPMNDI, "BPMNDiagram"))
    diagram.set("id", f"BPMNDiagram_{proc_id}")
    plane = etree.SubElement(diagram, _qn(NS_BPMNDI, "BPMNPlane"))
    plane.set("id", f"BPMNPlane_{proc_id}")
    plane.set("bpmnElement", proc_id)

    for lane in model.lanes:
        lx, ly, lw, lh = lane_boxes[lane.id]
        lane_shape = etree.SubElement(plane, _qn(NS_BPMNDI, "BPMNShape"))
        lane_shape.set("id", f"{safe_lane[lane.id]}_di")
        lane_shape.set("bpmnElement", safe_lane[lane.id])
        lane_shape.set("isHorizontal", "true")
        bounds = etree.SubElement(lane_shape, _qn(NS_DC, "Bounds"))
        bounds.set("x", f"{lx:.0f}")
        bounds.set("y", f"{ly:.0f}")
        bounds.set("width", f"{lw:.0f}")
        bounds.set("height", f"{lh:.0f}")

    for node in model.nodes:
        if node.id not in node_boxes:
            continue
        x, y, w, h = node_boxes[node.id]
        shape = etree.SubElement(plane, _qn(NS_BPMNDI, "BPMNShape"))
        shape.set("id", f"{safe_node[node.id]}_di")
        shape.set("bpmnElement", safe_node[node.id])
        bounds = etree.SubElement(shape, _qn(NS_DC, "Bounds"))
        bounds.set("x", f"{x:.0f}")
        bounds.set("y", f"{y:.0f}")
        bounds.set("width", f"{w:.0f}")
        bounds.set("height", f"{h:.0f}")

    for idx, f in enumerate(model.flows):
        if f.from_id not in node_boxes or f.to not in node_boxes:
            continue
        edge = etree.SubElement(plane, _qn(NS_BPMNDI, "BPMNEdge"))
        edge.set("id", f"{flow_ids[idx]}_di")
        edge.set("bpmnElement", flow_ids[idx])
        sx, sy = _anchor(node_boxes[f.from_id], "right")
        tx, ty = _anchor(node_boxes[f.to], "left")
        for px, py in ((sx, sy), (tx, ty)):
            wp = etree.SubElement(edge, _qn(NS_DI, "waypoint"))
            wp.set("x", f"{px:.0f}")
            wp.set("y", f"{py:.0f}")

    return xml_util.pretty_xml(root)


def _validate_model(model: ProcessModel) -> None:
    starts = [n for n in model.nodes if n.node_type == NodeType.START_EVENT]
    if len(starts) != 1:
        raise ValueError("BPMN generation requires exactly one startEvent.")
    if not any(n.node_type == NodeType.END_EVENT for n in model.nodes):
        raise ValueError("BPMN generation requires at least one endEvent.")
    node_ids = {n.id for n in model.nodes}
    for f in model.flows:
        if f.from_id not in node_ids or f.to not in node_ids:
            raise ValueError(f"Flow references unknown node: {f.from_id} -> {f.to}")
