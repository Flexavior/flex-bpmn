"""LLM gateway — multi-provider chat routing with key-driven model selection.

Supported providers:

* ``ollama``     — local Ollama (no key)
* ``omniroute``  — remote OpenAI-compatible router
* ``openrouter`` — remote OpenAI-compatible router
* ``openai``     — remote OpenAI-compatible API
* ``gemini``     — Google Gemini (generativelanguage API, free tier works)

**Key-availability model selector** — every remote provider implements
:meth:`list_models`, which queries the provider's ``/models`` endpoint with
the configured API key. The actual models visible in the dropdown are exactly
the ones that key can access.

**Auto model selection** — set ``*_MODEL=auto`` and the provider resolves the
model at runtime from ``/models``, preferring `*_PREFERRED_MODELS` first.

**Routing** — ``LLM_PROVIDER=auto`` (default) tries configured remote
providers first (omniroute -> openrouter -> openai -> gemini), then local
Ollama as a last resort. Pin to one provider with ``LLM_PROVIDER=<name>``,
or per-request via ``provider``.
"""

from __future__ import annotations

import time
from typing import Optional

import requests

from app.config import (
    LLM_PROVIDER,
    OLLAMA_MODEL,
    OLLAMA_URL,
    OMNIROUTE_API_KEY,
    OMNIROUTE_BASE_URL,
    OMNIROUTE_MODEL,
    OMNIROUTE_PREFERRED_MODELS,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_MODEL,
    OPENROUTER_PREFERRED_MODELS,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
    OPENAI_PREFERRED_MODELS,
    GEMINI_API_KEY,
    GEMINI_BASE_URL,
    GEMINI_MODEL,
    GEMINI_PREFERRED_MODELS,
)
from app.services.ollama_service import (
    OllamaConnectionError,
    OllamaError,
    OllamaService,
    OllamaTimeoutError,
)
from app.utils.logger import get_logger

log = get_logger(__name__)

CONNECT_TIMEOUT = 10
READ_TIMEOUT = 120
AUTO_MODEL_CACHE_TTL = 300.0  # seconds


class LLMError(Exception):
    """Base class for any LLM provider failure."""


class LLMConnectionError(LLMError):
    """Provider is unreachable / not configured."""


class LLMTimeoutError(LLMError):
    """Provider accepted the request but timed out."""
class OpenAICompatProvider:
    """OpenAI-compatible ``/chat/completions`` remote provider.

    Used for OmniRoute, OpenRouter and OpenAI. Derives the
    ``/chat/completions`` and ``/models`` endpoints from ``base_url``
    (which should end in ``/v1``).
    """

    def __init__(
        self,
        name: str,
        api_key: str,
        base_url: str,
        model: str = "auto",
        preferred_models: list[str] | tuple[str, ...] = (),
    ) -> None:
        self.name = name
        self.api_key = (api_key or "").strip()
        self.base_url = (base_url or "").rstrip("/")
        self.model = (model or "auto").strip()
        self.preferred_models = list(preferred_models)
        self._model_cache: tuple[float, Optional[str]] = (0.0, None)
        self._last_resolved: Optional[str] = None

    # ------------------------------------------------------------------ #
    def is_configured(self) -> bool:
        return bool(self.api_key) and bool(self.base_url)

    def is_available(self, timeout: float = 5.0) -> bool:
        if not self.is_configured():
            return False
        try:
            resp = requests.get(
                f"{self.base_url}/models",
                headers=self._headers(),
                timeout=timeout,
            )
            return resp.status_code == 200
        except requests.RequestException:
            return False

    # ------------------------------------------------------------------ #
    # Key-availability model listing
    # ------------------------------------------------------------------ #
    def list_models(self) -> list[str]:
        """Return model ids the configured API key can access."""
        if not self.is_configured():
            raise LLMConnectionError(
                f"{self.name}: API key not configured. "
                f"Add {self.name.upper()}_API_KEY to backend/.env"
            )
        try:
            resp = requests.get(
                f"{self.base_url}/models",
                headers=self._headers(),
                timeout=CONNECT_TIMEOUT,
            )
        except requests.ConnectionError as exc:
            raise LLMConnectionError(
                f"{self.name}: cannot reach {self.base_url}."
            ) from exc
        except requests.RequestException as exc:
            raise LLMError(f"{self.name}: failed to list models: {exc}") from exc

        if resp.status_code in (401, 403):
            raise LLMError(
                f"{self.name}: the API key is invalid or lacks access (HTTP "
                f"{resp.status_code}). Check {self.name.upper()}_API_KEY."
            )
        if resp.status_code != 200:
            raise LLMError(
                f"{self.name}: GET /models returned HTTP {resp.status_code}: "
                f"{resp.text[:300]}"
            )
        ids = [m.get("id", "") for m in resp.json().get("data", []) if m.get("id")]
        if not ids:
            raise LLMError(f"{self.name}: /models returned no models for this key.")
        return ids

    # ------------------------------------------------------------------ #
    # Auto model resolution
    # ------------------------------------------------------------------ #
    def resolve_model(self, override: Optional[str] = None) -> str:
        if override and override != "auto":
            self._last_resolved = override
            return override
        if self.model != "auto":
            self._last_resolved = self.model
            return self.model

        cached = self._model_cache[1]
        if cached and (time.monotonic() - self._model_cache[0]) < AUTO_MODEL_CACHE_TTL:
            self._last_resolved = cached
            return cached

        ids = self.list_models()
        for pref in self.preferred_models:
            if pref in ids:
                model = pref
                break
        else:
            model = ids[0]
        self._model_cache = (time.monotonic(), model)
        self._last_resolved = model
        log.info("Auto-selected model for %s: %s", self.name, model)
        return model
# ------------------------------------------------------------------ #
    # Chat
    # ------------------------------------------------------------------ #
    def chat(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.2,
        model: Optional[str] = None,
    ) -> str:
        resolved = self.resolve_model(model)
        payload = {
            "model": resolved,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "stream": False,
        }
        url = f"{self.base_url}/chat/completions"
        log.info("Calling %s: %s model=%s", self.name, url, resolved)
        started = time.monotonic()
        try:
            resp = requests.post(
                url,
                json=payload,
                headers=self._headers(),
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            )
        except requests.ConnectionError as exc:
            raise LLMConnectionError(
                f"{self.name}: cannot reach {self.base_url}. "
                "Check the base URL and your network."
            ) from exc
        except requests.Timeout as exc:
            raise LLMTimeoutError(
                f"{self.name}: did not answer within {READ_TIMEOUT}s."
            ) from exc
        except requests.RequestException as exc:
            raise LLMError(f"{self.name}: request failed: {exc}") from exc

        elapsed = time.monotonic() - started
        log.info("%s responded in %.1fs (status=%s)", self.name, elapsed, resp.status_code)

        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            if resp.status_code in (401, 403):
                raise LLMError(
                    f"{self.name}: authentication failed (HTTP {resp.status_code}). "
                    f"Check your {self.name.upper()}_API_KEY."
                ) from exc
            raise LLMError(
                f"{self.name}: HTTP {resp.status_code}: {resp.text[:300]}"
            ) from exc

        try:
            content = resp.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            raise LLMError(
                f"{self.name}: unexpected response shape: {resp.text[:300]}"
            ) from exc
        if not content:
            raise LLMError(f"{self.name}: empty content in response.")
        return str(content)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }


class GeminiProvider:
    """Google Gemini provider (generativelanguage API).

    System prompt is sent via the API's top-level ``systemInstruction``.
    Free-tier keys (Google AI Studio) work with the Flash models, e.g.
    ``gemini-2.0-flash`` / ``gemini-2.5-flash`` — no credit card required,
    subject to per-minute rate limits.
    """

    CHAT_ENDPOINT = ":generateContent"

    def __init__(
        self,
        name: str = "gemini",
        api_key: str = "",
        base_url: str = "",
        model: str = "auto",
        preferred_models: list[str] | tuple[str, ...] = (),
    ) -> None:
        self.name = name
        self.api_key = (api_key or "").strip()
        self.base_url = (base_url or "").rstrip("/")
        self.model = (model or "auto").strip()
        self.preferred_models = list(preferred_models)
        self._model_cache: tuple[float, Optional[str]] = (0.0, None)
        self._last_resolved: Optional[str] = None

    # ------------------------------------------------------------------ #
    def is_configured(self) -> bool:
        return bool(self.api_key) and bool(self.base_url)

    def is_available(self, timeout: float = 5.0) -> bool:
        if not self.is_configured():
            return False
        try:
            resp = requests.get(
                f"{self.base_url}/models",
                params={"pageSize": 1000},
                headers=self._headers(),
                timeout=timeout,
            )
            return resp.status_code == 200
        except requests.RequestException:
            return False

    # ------------------------------------------------------------------ #
    def list_models(self) -> list[str]:
        """Return model names the key can access (strips ``models/`` prefix)."""
        if not self.is_configured():
            raise LLMConnectionError(
                f"gemini: API key not configured. Add GEMINI_API_KEY to backend/.env"
            )
        try:
            resp = requests.get(
                f"{self.base_url}/models",
                params={"pageSize": 1000},
                headers=self._headers(),
                timeout=CONNECT_TIMEOUT,
            )
        except requests.ConnectionError as exc:
            raise LLMConnectionError(f"gemini: cannot reach {self.base_url}.") from exc
        except requests.RequestException as exc:
            raise LLMError(f"gemini: failed to list models: {exc}") from exc

        if resp.status_code in (400, 401, 403):
            raise LLMError(
                f"gemini: API key invalid or restricted (HTTP {resp.status_code}). "
                f"Get a free key at https://aistudio.google.com/apikey and check "
                f"GEMINI_API_KEY."
            )
        if resp.status_code != 200:
            raise LLMError(
                f"gemini: GET /models returned HTTP {resp.status_code}: "
                f"{resp.text[:300]}"
            )
        ids = []
        for m in resp.json().get("models", []):
            name = m.get("name", "")
            if name.startswith("models/"):
                name = name[len("models/"):]
            if name:
                ids.append(name)
        return ids
# ------------------------------------------------------------------ #
    def resolve_model(self, override: Optional[str] = None) -> str:
        if override and override != "auto":
            self._last_resolved = override
            return override
        if self.model != "auto":
            self._last_resolved = self.model
            return self.model

        cached = self._model_cache[1]
        if cached and (time.monotonic() - self._model_cache[0]) < AUTO_MODEL_CACHE_TTL:
            self._last_resolved = cached
            return cached

        ids = self.list_models()
        for pref in self.preferred_models:
            if pref in ids:
                model = pref
                break
        else:
            model = ids[0]
        self._model_cache = (time.monotonic(), model)
        self._last_resolved = model
        log.info("Auto-selected Gemini model: %s", model)
        return model

    # ------------------------------------------------------------------ #
    def chat(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.2,
        model: Optional[str] = None,
    ) -> str:
        resolved = self.resolve_model(model)
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": temperature},
        }
        url = f"{self.base_url}/models/{resolved}{self.CHAT_ENDPOINT}"
        log.info("Calling Gemini: %s model=%s", url, resolved)
        started = time.monotonic()
        try:
            resp = requests.post(
                url,
                json=payload,
                headers=self._headers(),
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            )
        except requests.ConnectionError as exc:
            raise LLMConnectionError(
                f"gemini: cannot reach {self.base_url}."
            ) from exc
        except requests.Timeout as exc:
            raise LLMTimeoutError(
                f"gemini: did not answer within {READ_TIMEOUT}s."
            ) from exc
        except requests.RequestException as exc:
            raise LLMError(f"gemini: request failed: {exc}") from exc

        elapsed = time.monotonic() - started
        log.info("gemini responded in %.1fs (status=%s)", elapsed, resp.status_code)

        if resp.status_code in (400, 401, 403):
            raise LLMError(
                f"gemini: request rejected (HTTP {resp.status_code}): "
                f"{resp.text[:300]}"
            )
        try:
            resp.raise_for_status()
        except requests.HTTPError as exc:
            raise LLMError(
                f"gemini: HTTP {resp.status_code}: {resp.text[:300]}"
            ) from exc

        try:
            content = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMError(
                f"gemini: unexpected response shape: {resp.text[:300]}"
            ) from exc
        if not content:
            raise LLMError("gemini: empty content in response.")
        return str(content)

    def _headers(self) -> dict:
        return {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}
class LLMGateway:
    """Routes chat calls to providers based on config / per-request choice."""

    PROVIDER_NAMES = ("ollama", "omniroute", "openrouter", "openai", "gemini")

    def __init__(self) -> None:
        self.ollama = OllamaService(base_url=OLLAMA_URL, model=OLLAMA_MODEL)
        self.remote: dict[str, OpenAICompatProvider | GeminiProvider] = {
            "omniroute": OpenAICompatProvider(
                name="omniroute",
                api_key=OMNIROUTE_API_KEY,
                base_url=OMNIROUTE_BASE_URL,
                model=OMNIROUTE_MODEL,
                preferred_models=OMNIROUTE_PREFERRED_MODELS,
            ),
            "openrouter": OpenAICompatProvider(
                name="openrouter",
                api_key=OPENROUTER_API_KEY,
                base_url=OPENROUTER_BASE_URL,
                model=OPENROUTER_MODEL,
                preferred_models=OPENROUTER_PREFERRED_MODELS,
            ),
            "openai": OpenAICompatProvider(
                name="openai",
                api_key=OPENAI_API_KEY,
                base_url=OPENAI_BASE_URL,
                model=OPENAI_MODEL,
                preferred_models=OPENAI_PREFERRED_MODELS,
            ),
            "gemini": GeminiProvider(
                name="gemini",
                api_key=GEMINI_API_KEY,
                base_url=GEMINI_BASE_URL,
                model=GEMINI_MODEL,
                preferred_models=GEMINI_PREFERRED_MODELS,
            ),
        }
        self.last_result: Optional[tuple[str, str]] = None

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _provider(self, name: str) -> Optional[OpenAICompatProvider | GeminiProvider | OllamaService]:
        if name == "ollama":
            return self.ollama
        return self.remote.get(name)

    def _is_usable(self, name: str) -> bool:
        if name == "ollama":
            return True
        p = self.remote.get(name)
        return bool(p and p.is_configured())

    def _configured_order(self) -> list[str]:
        """Provider attempt order for ``auto`` mode."""
        order = [n for n in self.PROVIDER_NAMES if self._is_usable(n)]
        if "ollama" in order:
            order.remove("ollama")
            if self.ollama.is_available(timeout=2.0):
                order.insert(0, "ollama")
            else:
                order.append("ollama")  # last resort
        return order

    # ------------------------------------------------------------------ #
    # Key-availability model list (for the frontend dropdown)
    # ------------------------------------------------------------------ #
    def list_models(self, provider: Optional[str] = None) -> dict[str, list[str]]:
        """Return ``{provider: [model ids]}`` for the given (or all configured) providers.

        Each provider's list reflects what its API key can actually access.
        """
        if provider:
            names = [provider]
        else:
            names = [n for n in self.PROVIDER_NAMES if self._is_usable(n)]

        result: dict[str, list[str]] = {}
        errors: list[str] = []
        for name in names:
            p = self._provider(name)
            if p is None or not self._is_usable(name):
                errors.append(f"{name}: not configured")
                continue
            try:
                if name == "ollama":
                    result[name] = self.ollama.list_models()
                else:
                    result[name] = p.list_models()  # type: ignore[attr-defined]
            except (LLMError, OllamaError) as exc:
                errors.append(f"{name}: {exc}")
            except AttributeError:
                errors.append(f"{name}: list_models unsupported")

        if not result:
            raise LLMError("No models available. " + "; ".join(errors))
        if errors and not provider:
            for e in errors:
                log.warning("list_models: %s", e)
        return result

    def provider_statuses(self, model_limit: int = 40) -> list[dict]:
        """Return safe provider/model availability data for the frontend."""
        statuses: list[dict] = []
        for name in self.PROVIDER_NAMES:
            provider = self._provider(name)
            configured = name == "ollama" or bool(
                provider and getattr(provider, "is_configured", lambda: False)()
            )
            status = {
                "name": name,
                "configured": configured,
                "available": False,
                "models": [],
                "reason": "no_api_key" if not configured else "unreachable",
            }
            if not configured or provider is None:
                statuses.append(status)
                continue
            try:
                models = self.list_models(name).get(name, [])
                status["models"] = models[:model_limit]
                status["available"] = bool(models)
                status["reason"] = "ok" if models else "unreachable"
            except LLMError as exc:
                message = str(exc).lower()
                if any(term in message for term in ("invalid", "authentication", "401", "403")):
                    status["reason"] = "invalid_key"
            except (OllamaError, requests.RequestException):
                status["reason"] = "unreachable"
            statuses.append(status)
        return statuses
# ------------------------------------------------------------------ #
    # Chat
    # ------------------------------------------------------------------ #
    def chat(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.2,
        model: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> str:
        """Send a chat request with provider routing + fallback.

        Returns the raw assistant text. Raises :class:`LLMError` (or subclass)
        if **all** attempted providers fail.
        """
        pinned = provider or (LLM_PROVIDER if LLM_PROVIDER in self.PROVIDER_NAMES else None)

        if pinned:
            p = self._provider(pinned)
            if p is None or not self._is_usable(pinned):
                raise LLMConnectionError(
                    f"Provider '{pinned}' is not configured. "
                    "Check backend/.env for the matching *_API_KEY."
                )
            return self._chat_one(pinned, p, system, user, temperature, model)

        # auto mode: remote first, Ollama last resort.
        errors: list[str] = []
        for name in self._configured_order():
            p = self._provider(name)
            if p is None:
                continue
            try:
                return self._chat_one(name, p, system, user, temperature, model)
            except LLMError as exc:
                log.warning("%s failed, trying next provider: %s", name, exc)
                errors.append(f"{name}: {exc}")
            except Exception as exc:  # noqa: BLE001
                log.exception("Unexpected error from %s", name)
                errors.append(f"{name}: {exc}")

        if errors:
            raise LLMError("All LLM providers failed: " + "; ".join(errors))
        raise LLMError(
            "No LLM provider configured. Add a remote API key (OmniRoute / "
            "OpenRouter / OpenAI / Gemini) in backend/.env or start Ollama."
        )

    # ------------------------------------------------------------------ #
    def _chat_one(
        self,
        name: str,
        provider: OpenAICompatProvider | GeminiProvider | OllamaService,
        system: str,
        user: str,
        temperature: float,
        model: Optional[str],
    ) -> str:
        try:
            if model:
                text = provider.chat(system, user, temperature=temperature, model=model)
            else:
                text = provider.chat(system, user, temperature=temperature)
        except OllamaTimeoutError as exc:
            raise LLMTimeoutError(str(exc)) from exc
        except OllamaConnectionError as exc:
            raise LLMConnectionError(str(exc)) from exc
        except OllamaError as exc:
            raise LLMError(str(exc)) from exc
        label = getattr(provider, "_last_resolved", None) or getattr(provider, "model", name)
        self.last_result = (name, str(label))
        return text