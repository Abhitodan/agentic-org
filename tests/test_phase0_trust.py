"""Phase 0 trust floor: path escape, empty actions, model HTTP→unavailable, serve auth."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

from agentic_org.coding.implementer import apply_actions
from agentic_org.gateway.model_gateway import ModelGateway, ModelUnavailable


def test_apply_actions_rejects_empty_list(tmp_path: Path):
    wt = tmp_path / "wt"
    wt.mkdir()
    with pytest.raises(ValueError, match="empty implementation"):
        apply_actions(wt, [])


def test_apply_actions_rejects_parent_escape(tmp_path: Path):
    wt = tmp_path / "wt"
    wt.mkdir()
    sibling = tmp_path / "sibling"
    sibling.mkdir()
    with pytest.raises(ValueError, match="escapes"):
        apply_actions(wt, [{
            "op": "write",
            "path": "../sibling/evil.txt",
            "content": "x",
        }])
    assert not (sibling / "evil.txt").exists()


def test_apply_actions_rejects_prefix_sibling(tmp_path: Path):
    """Classic startswith bug: worktree vs worktree-evil."""
    wt = tmp_path / "worktree"
    evil = tmp_path / "worktree-evil"
    wt.mkdir()
    evil.mkdir()
    # Relative path that resolves outside via crafted name is blocked by .. check;
    # also ensure absolute-style escape fails.
    with pytest.raises(ValueError, match="escapes"):
        apply_actions(wt, [{
            "op": "write",
            "path": str(evil / "pwned.txt"),
            "content": "x",
        }])
    assert not (evil / "pwned.txt").exists()


def test_apply_actions_writes_inside(tmp_path: Path):
    wt = tmp_path / "wt"
    wt.mkdir()
    n = apply_actions(wt, [{
        "op": "write", "path": "a.txt", "content": "ok",
    }])
    assert n == 1
    assert (wt / "a.txt").read_text(encoding="utf-8") == "ok"


def test_gateway_http_status_becomes_model_unavailable(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    cfg = tmp_path / "models.yaml"
    cfg.write_text(
        "provider: gemini\nclasses:\n  fast:\n    model: gemini-2.0-flash\n"
        "    input_per_1m_usd: 0.1\n    output_per_1m_usd: 0.4\n",
        encoding="utf-8",
    )
    gw = ModelGateway(cfg)

    def boom(*_a, **_k):
        req = httpx.Request("POST", "https://example.test/chat/completions")
        resp = httpx.Response(500, request=req, text="upstream down")
        raise httpx.HTTPStatusError("500", request=req, response=resp)

    monkeypatch.setattr(httpx, "post", boom)
    with pytest.raises(ModelUnavailable, match="HTTP 500"):
        gw.complete("fast", "sys", "user")


def test_serve_refuses_nonlocal_without_token(monkeypatch):
    import uvicorn
    from typer.testing import CliRunner

    from agentic_org.cli.main import app

    monkeypatch.delenv("AGENTIC_ORG_API_TOKEN", raising=False)
    mock_run = MagicMock()
    monkeypatch.setattr(uvicorn, "run", mock_run)
    runner = CliRunner()
    result = runner.invoke(app, ["serve", "--host", "0.0.0.0", "--port", "8799"])
    assert result.exit_code == 2
    assert mock_run.call_count == 0
    combined = (result.output or "") + (result.stderr or "")
    assert "refusing" in combined.lower() or "AGENTIC_ORG_API_TOKEN" in combined
