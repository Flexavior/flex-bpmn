"""Chat API — provider discovery and natural language -> process JSON."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.config import CHAT_RATE_LIMIT, CHAT_RATE_WINDOW_S, TRUST_PROXY
from app.schemas.request import ChatRequest
from app.schemas.response import ChatResponse
from app.services.llm_gateway import LLMConnectionError, LLMError, LLMTimeoutError
from app.services.workflow_service import WorkflowError, WorkflowService
from app.utils.logger import get_logger
from app.utils.rate_limit import RateLimiter

log = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["Chat"])
workflow = WorkflowService()
_limiter = RateLimiter(CHAT_RATE_LIMIT, CHAT_RATE_WINDOW_S)


def _client_key(request: Request) -> str:
    if TRUST_PROXY:
        forwarded = request.headers.get("x-forwarded-for", "")
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"


@router.get("/ping")
def ping() -> dict:
    return {"message": "Chat API is working."}


@router.get("/providers")
def providers() -> dict:
    """List configured, reachable LLM providers without exposing credentials."""
    return {"providers": workflow.llm.provider_statuses()}


@router.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, request: Request) -> ChatResponse:
    if not _limiter.allow(_client_key(request)):
        raise HTTPException(status_code=429, detail="Too many generation requests. Wait a minute and retry.")
    try:
        return workflow.generate_process(
            req.prompt,
            model_override=req.model,
            provider=req.provider,
        )
    except LLMConnectionError as exc:
        log.warning("LLM unreachable: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMTimeoutError as exc:
        log.warning("LLM timeout: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMError as exc:
        log.warning("LLM error: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except WorkflowError as exc:
        log.warning("Chat failed: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        log.exception("Unexpected error in /api/chat")
        raise HTTPException(status_code=500, detail="Internal error generating the process.") from None
