"""Ollama LLM provider — the only service that talks to Ollama."""

from __future__ import annotations

import time

import requests

from app.config import OLLAMA_MODEL, OLLAMA_URL
from app.utils.logger import get_logger

log = get_logger(__name__)

CONNECT_TIMEOUT = 10
READ_TIMEOUT = 600

HINT_START = (
    "Start Ollama with `ollama serve` (or run `ollama run {model}` once to "
    "pre-load the model), then retry."
)


class OllamaError(Exception):
    """Base class for Ollama provider failures."""


class OllamaConnectionError(OllamaError):
    """Ollama is not reachable."""


class OllamaTimeoutError(OllamaError):
    """Ollama accepted the request but timed out before producing output."""


class OllamaService:
    """Thin client around Ollama's ``/api/chat`` endpoint."""

    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        self.base_url = (base_url or OLLAMA_URL or "http://127.0.0.1:11434").rstrip("/")
        self.model = model or OLLAMA_MODEL or "qwen3.5:9b"
        self._last_resolved = self.model

    def is_available(self, timeout: float = 5.0) -> bool:
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=timeout)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def list_models(self) -> list[str]:
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=CONNECT_TIMEOUT)
            resp.raise_for_status()
            names = [tag.get("name", "") for tag in resp.json().get("models", [])]
            return [n for n in names if n]
        except requests.RequestException as exc:
            raise OllamaConnectionError(
                f"Cannot list Ollama models at {self.base_url}."
            ) from exc

    def is_model_loaded(self, timeout: float = 5.0) -> bool:
        try:
            names = self.list_models()
        except OllamaError:
            return False
        return any(name == self.model or name.startswith(f"{self.model}:") for name in names)

    def chat(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.2,
        model: str | None = None,
    ) -> str:
        use_model = model or self.model
        self._last_resolved = use_model
        payload = {
            "model": use_model,
            "stream": False,
            "options": {"temperature": temperature},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        url = f"{self.base_url}/api/chat"
        log.info("Calling Ollama: %s model=%s", url, use_model)
        started = time.monotonic()
        try:
            resp = requests.post(
                url,
                json=payload,
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            )
        except requests.ConnectionError as exc:
            raise OllamaConnectionError(
                f"Cannot reach Ollama at {self.base_url}. "
                f"{HINT_START.format(model=use_model)}"
            ) from exc
        except requests.Timeout as exc:
            raise OllamaTimeoutError(
                f"Ollama did not answer within {READ_TIMEOUT}s "
                f"(model '{use_model}' may still be loading, or generation "
                f"is slow). {HINT_START.format(model=use_model)}"
            ) from exc
        except requests.RequestException as exc:
            raise OllamaError(f"Ollama request failed: {exc}") from exc

        elapsed = time.monotonic() - started
        log.info("Ollama responded in %.1fs (status=%s)", elapsed, resp.status_code)

        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            if resp.status_code == 404:
                raise OllamaError(
                    f"Model '{use_model}' was not found in Ollama. "
                    f"Pull it with `ollama pull {use_model}` and retry."
                ) from exc
            raise OllamaError(
                f"Ollama returned HTTP {resp.status_code}: {resp.text[:300]}"
            ) from exc

        data = resp.json()
        content = data.get("message", {}).get("content")
        if not content:
            raise OllamaError("Ollama response missing 'message.content'.")
        return str(content)
