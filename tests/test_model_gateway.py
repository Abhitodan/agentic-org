import os

import httpx

from agentic_org.gateway.model_gateway import (
    GEMINI_BASE_URL,
    GROQ_BASE_URL,
    ModelGateway,
    resolve_credentials,
)


def test_gemini_credentials_from_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    provider, key, base = resolve_credentials({"provider": "gemini"})
    assert provider == "gemini"
    assert key == "test-gemini-key"
    assert base == GEMINI_BASE_URL.rstrip("/")


def test_gemini_auto_detect_when_only_gemini_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "only-gemini")
    provider, key, base = resolve_credentials({"provider": "openai"})
    assert provider == "gemini"
    assert key == "only-gemini"
    assert "generativelanguage.googleapis.com" in base


def test_gateway_available_with_gemini_key(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    cfg = tmp_path / "models.yaml"
    cfg.write_text("provider: gemini\nclasses:\n  fast:\n    model: gemini-2.0-flash\n",
                   encoding="utf-8")
    gw = ModelGateway(cfg)
    assert gw.available()
    assert gw.provider == "gemini"


def test_groq_gsk_key_forces_groq_host(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_key_only")
    provider, key, base = resolve_credentials({
        "provider": "gemini",
        "base_url": GEMINI_BASE_URL,
    })
    assert provider == "groq"
    assert key.startswith("gsk_")
    assert base == GROQ_BASE_URL.rstrip("/")


def test_gateway_swaps_gemini_models_when_groq(monkeypatch, tmp_path):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_key_only")
    cfg = tmp_path / "models.yaml"
    cfg.write_text(
        "provider: gemini\nbase_url: https://generativelanguage.googleapis.com/v1beta/openai/\n"
        "classes:\n  standard:\n    model: gemini-2.5-flash\n",
        encoding="utf-8",
    )
    gw = ModelGateway(cfg)
    assert gw.provider == "groq"
    assert "llama" in gw.resolve("standard")["model"]


def test_complete_retries_on_429(monkeypatch, tmp_path):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_key_only")
    monkeypatch.setenv("AGENTIC_ORG_MODEL_RETRIES", "3")
    sleeps: list[float] = []
    monkeypatch.setattr(
        "agentic_org.gateway.model_gateway.time.sleep",
        lambda s: sleeps.append(s),
    )
    cfg = tmp_path / "models.yaml"
    cfg.write_text(
        "provider: groq\nclasses:\n  fast:\n    model: llama-3.1-8b-instant\n"
        "    input_per_1m_usd: 0.05\n    output_per_1m_usd: 0.08\n",
        encoding="utf-8",
    )
    calls = {"n": 0}

    def fake_post(*_a, **_k):
        calls["n"] += 1
        if calls["n"] < 3:
            req = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
            return httpx.Response(429, request=req, headers={"retry-after": "1"},
                                  text="rate limit")
        req = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
        return httpx.Response(
            200,
            request=req,
            json={
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    monkeypatch.setattr("agentic_org.gateway.model_gateway.httpx.post", fake_post)
    gw = ModelGateway(cfg)
    out = gw.complete("fast", "sys", "user")
    assert out.text == "ok"
    assert calls["n"] == 3
    assert sleeps  # backoff happened
