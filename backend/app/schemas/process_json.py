"""Pydantic models — the single source of truth for a BPMN process."""

from __future__ import annotations

import re
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")


class NodeType(str, Enum):
    START_EVENT = "startEvent"
    END_EVENT = "endEvent"
    TASK = "task"
    USER_TASK = "userTask"
    SERVICE_TASK = "serviceTask"
    EXCLUSIVE_GATEWAY = "exclusiveGateway"
    PARALLEL_GATEWAY = "parallelGateway"


class ProcessLane(BaseModel):
    id: str = Field(..., description="Unique snake_case lane id.")
    name: str = Field(default="", max_length=80, description="Swimlane label shown on the diagram.")
    actors: list[str] = Field(
        default_factory=list,
        max_length=8,
        description="Roles that own this lane, e.g. student, teacher, admin.",
    )

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("id")
    @classmethod
    def _id_shape(cls, value: str) -> str:
        if not ID_RE.fullmatch(value):
            raise ValueError("lane id must be a short snake_case identifier")
        return value

    @field_validator("actors")
    @classmethod
    def _actor_shape(cls, actors: list[str]) -> list[str]:
        for actor in actors:
            if not ID_RE.fullmatch(actor):
                raise ValueError(f"lane actor must be snake_case: {actor}")
        return actors


class ProcessNode(BaseModel):
    id: str = Field(..., description="Unique snake_case node id.")
    node_type: NodeType = Field(alias="nodeType", description="BPMN node kind.")
    name: str = Field(default="", max_length=120, description="Human-readable node label.")
    lane: Optional[str] = Field(
        default=None,
        description="Lane id that owns this step (swimlane).",
    )

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("id")
    @classmethod
    def _id_shape(cls, value: str) -> str:
        if not ID_RE.fullmatch(value):
            raise ValueError("node id must be a short snake_case identifier")
        return value


class ProcessFlow(BaseModel):
    id: Optional[str] = Field(default=None, max_length=64)
    from_id: str = Field(alias="from", description="Source node id.")
    to: str = Field(description="Target node id.")
    condition: Optional[str] = Field(default=None, max_length=240)
    is_default: bool = Field(default=False, alias="default")

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("from_id", "to")
    @classmethod
    def _ref_shape(cls, value: str) -> str:
        if not ID_RE.fullmatch(value):
            raise ValueError("flow endpoints must be snake_case identifiers")
        return value

    @field_validator("id")
    @classmethod
    def _optional_id(cls, value: Optional[str]) -> Optional[str]:
        if value is None or value == "":
            return None
        if not ID_RE.fullmatch(value):
            raise ValueError("flow id must be a short snake_case identifier")
        return value

    @field_validator("condition")
    @classmethod
    def _no_markup(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if re.search(r"</?[A-Za-z][^>]*>", value):
            raise ValueError("condition cannot contain markup")
        return value


class ProcessInfo(BaseModel):
    id: str = Field(description="Process id (snake_case).")
    name: str = Field(default="", max_length=160)

    @field_validator("id")
    @classmethod
    def _id_shape(cls, value: str) -> str:
        if not ID_RE.fullmatch(value):
            raise ValueError("process.id must be a short snake_case identifier")
        return value


class ProcessModel(BaseModel):
    process: ProcessInfo
    lanes: list[ProcessLane] = Field(
        default_factory=list,
        max_length=12,
        description="Swimlanes showing who owns each part of the process.",
    )
    nodes: list[ProcessNode] = Field(default_factory=list, max_length=80)
    flows: list[ProcessFlow] = Field(default_factory=list, max_length=160)

    @field_validator("lanes")
    @classmethod
    def _unique_lane_ids(cls, lanes: list[ProcessLane]) -> list[ProcessLane]:
        ids = [lane.id for lane in lanes]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate lane id(s) in lanes list.")
        return lanes

    @field_validator("nodes")
    @classmethod
    def _unique_node_ids(cls, nodes: list[ProcessNode]) -> list[ProcessNode]:
        ids = [n.id for n in nodes]
        seen: set[str] = set()
        dupes = [i for i in ids if i in seen or seen.add(i)]
        if dupes:
            raise ValueError(f"Duplicate node id(s): {', '.join(sorted(set(dupes)))}")
        return nodes
