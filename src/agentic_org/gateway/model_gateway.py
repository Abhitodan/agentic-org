"""Model gateway with routing classes and honest failure.

Talks to any OpenAI-compatible chat-completions endpoint. Routing classes
(fast / standard / strong) map to concrete models in .agent-org/models.yaml.

Gemini is first-class: set provider: gemini in models.yaml and provide
GEMINI_API_KEY (or GOOGLE_API_KEY). The gateway uses Google's documented
OpenAI-compatible endpoint:
https://generativelanguage.googleapis.com/v1beta/openai/

Hard rule: if no endpoint or key is configured, ModelUnavailable is raised.
The gateway never fabricates a completion.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import yaml

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
OPENAI_BASE_URL = "https://api.openai.com/v1"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

DEFAULT_MODELS = {
    "provider": "gemini",
    "base_url": GEMINI_BASE_URL,
    "classes": {
        "fast": {
            "model": "gemini-2.0-flash",
            "input_per_1m_usd": 0.10,
            "output_per_1m_usd": 0.40,
        },
        "standard": {
            "model": "gemini-2.5-flash",
            "input_per_1m_usd": 0.15,
            "output_per_1m_usd": 0.60,
        },
        "strong": {
            "model": "gemini-2.5-pro",
            "input_per_1m_usd": 1.25,
            "output_per_1m_usd": 10.00,
            "expensive": True,
        },
    },
}

# Groq OpenAI-compatible defaults (gsk_… keys). Not xAI Grok.
GROQ_DEFAULT_MODELS = {
    "provider": "groq",
    "base_url": GROQ_BASE_URL,
    "classes": {
        "fast": {
            "model": "llama-3.1-8b-instant",
            "input_per_1m_usd": 0.05,
            "output_per_1m_usd": 0.08,
        },
        "standard": {
            "model": "llama-3.3-70b-versatile",
            "input_per_1m_usd": 0.59,
            "output_per_1m_usd": 0.79,
        },
        "strong": {
            "model": "llama-3.3-70b-versatile",
            "input_per_1m_usd": 0.59,
            "output_per_1m_usd": 0.79,
            "expensive": True,
        },
    },
}


class ModelUnavailable(Exception):
    """No configured model endpoint. Callers must block, never fake output."""


@dataclass
class CompletionResult:
    text: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    duration_ms: int
    is_expensive: bool


def _first_env(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def resolve_credentials(config: dict[str, Any]) -> tuple[str, str, str]:
    """Return (provider, api_key, base_url)."""
    provider = str(config.get("provider", "gemini")).lower()
    explicit_base = _first_env("AGENTIC_ORG_MODEL_BASE_URL", "OPENAI_BASE_URL")
    config_base = str(config.get("base_url", "")).strip()

    gemini_key = _first_env(
        "GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENERATIVE_AI_API_KEY",
    )
    groq_key = _first_env("GROQ_API_KEY")
    openai_key = _first_env("OPENAI_API_KEY")
    generic_key = _first_env("AGENTIC_ORG_MODEL_API_KEY")

    if provider == "gemini":
        api_key = generic_key or gemini_key
        default_base = GEMINI_BASE_URL
    elif provider in {"groq", "grok"}:  # gsk_ keys are Groq; "grok" accepted as alias
        provider = "groq"
        api_key = generic_key or groq_key
        default_base = GROQ_BASE_URL
    else:
        api_key = generic_key or openai_key or groq_key
        default_base = OPENAI_BASE_URL

    # Prefer an available key when yaml provider has none.
    if not api_key and groq_key:
        provider = "groq"
        api_key = groq_key
        default_base = GROQ_BASE_URL
    elif not api_key and gemini_key and not openai_key:
        provider = "gemini"
        api_key = gemini_key
        default_base = GEMINI_BASE_URL

    base_url = explicit_base or config_base or default_base
    # Groq keys must hit Groq host even if yaml still says Gemini.
    if api_key.startswith("gsk_") and "groq.com" not in base_url:
        provider = "groq"
        default_base = GROQ_BASE_URL
        if not explicit_base:
            base_url = GROQ_BASE_URL

    return provider, api_key, base_url.rstrip("/")


class ModelGateway:
    def __init__(self, config_path: Path | None = None):
        self.config = DEFAULT_MODELS
        if config_path and config_path.exists():
            loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            if loaded and "classes" in loaded:
                self.config = loaded
        self.provider, self.api_key, self.base_url = resolve_credentials(self.config)
        # If credentials resolved to Groq but yaml still lists Gemini model ids,
        # swap in Groq defaults so chat/completions does not 404 on model names.
        if self.provider == "groq":
            model = str(
                (self.config.get("classes") or {}).get("standard", {}).get("model")
                or ""
            )
            if model.startswith("gemini") or "gemini" in model:
                self.config = {
                    **GROQ_DEFAULT_MODELS,
                    "provider": "groq",
                    "base_url": self.base_url,
                }

    def available(self) -> bool:
        return bool(self.api_key)

    def resolve(self, model_class: str) -> dict[str, Any]:
        classes = self.config["classes"]
        if model_class not in classes:
            raise KeyError(f"unknown model class: {model_class}")
        return classes[model_class]

    def complete(
        self,
        model_class: str,
        system: str,
        user: str,
        max_output_tokens: int = 2000,
        temperature: float = 0.2,
    ) -> CompletionResult:
        if not self.available():
            raise ModelUnavailable(
                "No model API key configured. For Gemini set GEMINI_API_KEY; "
                "for Groq set GROQ_API_KEY (gsk_…); for OpenAI set OPENAI_API_KEY "
                "or AGENTIC_ORG_MODEL_API_KEY. Optionally set "
                "AGENTIC_ORG_MODEL_BASE_URL. The gateway does not fabricate results."
            )
        spec = self.resolve(model_class)
        started = time.monotonic()
        max_attempts = max(1, int(os.environ.get("AGENTIC_ORG_MODEL_RETRIES", "6")))
        data: dict[str, Any] | None = None
        last_status_error: httpx.HTTPStatusError | None = None
        for attempt in range(max_attempts):
            try:
                response = httpx.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": spec["model"],
                        "messages": [
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        "max_tokens": max_output_tokens,
                        "temperature": temperature,
                    },
                    timeout=120,
                )
                if response.status_code == 429 and attempt + 1 < max_attempts:
                    time.sleep(_retry_wait_seconds(response, attempt))
                    continue
                response.raise_for_status()
                data = response.json()
                break
            except httpx.HTTPStatusError as exc:
                last_status_error = exc
                if (
                    exc.response is not None
                    and exc.response.status_code == 429
                    and attempt + 1 < max_attempts
                ):
                    time.sleep(_retry_wait_seconds(exc.response, attempt))
                    continue
                raise ModelUnavailable(
                    f"model HTTP {exc.response.status_code} from {self.base_url}: "
                    f"{exc.response.text[:300]}"
                ) from exc
            except httpx.HTTPError as exc:
                raise ModelUnavailable(
                    f"model transport error talking to {self.base_url}: {exc}"
                ) from exc
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                raise ModelUnavailable(
                    f"model returned unusable completion payload: {exc}"
                ) from exc
        if data is None:
            if last_status_error is not None:
                raise ModelUnavailable(
                    f"model HTTP {last_status_error.response.status_code} from "
                    f"{self.base_url}: {last_status_error.response.text[:300]}"
                ) from last_status_error
            raise ModelUnavailable("model request failed after retries")
        duration_ms = int((time.monotonic() - started) * 1000)
        usage = data.get("usage", {}) or {}
        tokens_in = int(usage.get("prompt_tokens", 0))
        tokens_out = int(usage.get("completion_tokens", 0))
        cost = (
            tokens_in / 1_000_000 * float(spec.get("input_per_1m_usd", 0))
            + tokens_out / 1_000_000 * float(spec.get("output_per_1m_usd", 0))
        )
        text = data["choices"][0]["message"]["content"]
        if text is None:
            raise ModelUnavailable("model returned empty message content")
        return CompletionResult(
            text=text,
            model=spec["model"],
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=round(cost, 6),
            duration_ms=duration_ms,
            is_expensive=bool(spec.get("expensive", False)),
        )


def _retry_wait_seconds(response: httpx.Response, attempt: int) -> float:
    """Honor Retry-After when present; else exponential backoff (capped)."""
    header = (response.headers.get("retry-after") or "").strip()
    if header.isdigit():
        return min(60.0, float(header))
    # Groq free-tier RPM: start at 2s, double, cap 45s.
    return min(45.0, 2.0 * (2 ** attempt))
