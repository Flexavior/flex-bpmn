"""Response payloads returned by the HTTP API."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.process_json import ProcessModel


class ValidationIssue(BaseModel):
    """A single validation finding."""

    severity: Literal["error", "warning"]
    code: str
    message: str


class ValidationReport(BaseModel):
    """Semantic validation outcome for a process model."""

    valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)


class ChatResponse(BaseModel):
    """LLM-generated process JSON and its validation report."""

    process: ProcessModel
    validation: ValidationReport
    bpmn: Optional[str] = Field(default=None, description="Always null until user draws.")
    json_path: Optional[str] = Field(default=None, description="Saved JSON file path.")
    bpmn_path: Optional[str] = Field(default=None, description="Always null until user draws.")
    llm_model: str
    latency_ms: int = 0


class GenerateBpmnResponse(BaseModel):
    """Result of rendering a ProcessModel into BPMN XML."""

    bpmn: str
    bpmn_path: Optional[str] = None