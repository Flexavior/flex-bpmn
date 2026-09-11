"""Request payloads accepted by the HTTP API."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.config import PROMPT_MAX_CHARS
from app.schemas.process_json import ProcessModel


class ChatRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=PROMPT_MAX_CHARS)
    model: Optional[str] = Field(
        default=None,
        max_length=80,
        pattern=r"^[A-Za-z0-9_.:/-]+$",
        description="Optional per-request model id.",
    )
    provider: Optional[str] = Field(
        default=None,
        pattern=r"^(ollama|omniroute|openrouter|openai|gemini)$",
    )
    continue_conversation: bool = Field(default=False)


class GenerateBpmnRequest(BaseModel):
    process: ProcessModel


class ValidateRequest(BaseModel):
    process: ProcessModel


class DeployRequest(BaseModel):
    process_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
    bpmn: str = Field(min_length=40, max_length=400_000)
