"""Phase 1 hardening: sandbox denylist, MCP role, wall-clock, redact, grounding."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from agentic_org.coding.grounding import extract_cited_paths, missing_grounded_paths
from agentic_org.context import build_context
from agentic_org.core.budget import Budget, BudgetExceeded, BudgetTracker, Spent
from agentic_org.core.events import Event
from agentic_org.core.redact import redact_text
from agentic_org.mcp import McpDenied
from agentic_org.mcp.builtin import SERVER_NAME, TOOL_REPO_SUMMARY, repo_summary_executor
from agentic_org.sandbox import SandboxError, SandboxPolicy, run_sandboxed
from agentic_org.sandbox.policy import dangerous_command_reason


def test_dangerous_python_c_denied():
    assert dangerous_command_reason([sys.executable, "-c", "print(1)"])


def test_sandbox_denies_python_c_even_if_allowlisted(tmp_path: Path):
    policy = SandboxPolicy(
        allowed_roots=[tmp_path],
        allowed_commands=[[sys.executable]],
        deny_dangerous=True,
    )
    with pytest.raises(SandboxError, match="python -c"):
        run_sandboxed([sys.executable, "-c", "print(1)"], tmp_path, policy)


def test_sandbox_denies_git_push(tmp_path: Path):
    policy = SandboxPolicy(
        allowed_roots=[tmp_path],
        allowed_commands=[["git"]],
        deny_dangerous=True,
    )
    with pytest.raises(SandboxError, match="git push"):
        run_sandboxed(["git", "push", "origin", "main"], tmp_path, policy)


def test_sandbox_allows_pytest_module(tmp_path: Path):
    policy = SandboxPolicy(
        allowed_roots=[tmp_path],
        allowed_commands=[[sys.executable, "-m", "pytest"]],
        deny_dangerous=True,
    )
    # May fail tests but must be allowlisted (not denied as dangerous).
    assert policy.allows_command([sys.executable, "-m", "pytest", "-q"])


def test_mcp_role_none_denied_when_roles_required(tmp_path: Path):
    mcp = tmp_path / ".agent-org" / "mcp"
    mcp.mkdir(parents=True)
    (mcp / "registry.yaml").write_text(
        yaml.safe_dump({"servers": [{"name": "fs"}]}), encoding="utf-8"
    )
    (mcp / "permissions.yaml").write_text(
        yaml.safe_dump({"grants": [{
            "id": "g1", "server": "fs", "tools": ["read_file"],
            "roles": ["backend-agent"], "effect": "allow",
        }]}),
        encoding="utf-8",
    )
    gw = build_context(str(tmp_path)).mcp
    with pytest.raises(McpDenied):
        gw.authorize("fs", "read_file", role=None)


def test_builtin_mcp_repo_summary_on_map_path(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text("x = 1\n", encoding="utf-8")
    ctx = build_context(str(tmp_path))
    out = ctx.mcp.call(
        SERVER_NAME,
        TOOL_REPO_SUMMARY,
        {"repo_path": str(repo)},
        role="repository-agent",
        executor=repo_summary_executor,
    )
    assert out.allowed
    assert out.output["ok"] is True
    assert out.output["file_count"] >= 1


def test_wall_clock_budget_enforced():
    started = (datetime.now(timezone.utc) - timedelta(minutes=90)).isoformat()
    tracker = BudgetTracker(
        Budget(maximum_wall_clock_minutes=60, maximum_cost_usd=10),
        Spent(started_at=started),
    )
    with pytest.raises(BudgetExceeded) as exc:
        tracker.charge(tool_calls=1)
    assert exc.value.dimension == "maximum_wall_clock_minutes"


def test_event_payload_redacts_api_key_shapes(tmp_path: Path):
    ctx = build_context(str(tmp_path))
    ctx.events.append(Event(
        event_type="test.secret",
        payload={
            "msg": "token AIzaSyDummyKeyValue123456789012345 and sk-abcdefghijklmnopqrstuvwxyz0123",
            "nested": {"api_key": "supersecretvalue99"},
        },
    ))
    rows = ctx.events.list(event_type="test.secret", limit=1)
    blob = str(rows[0]["payload"])
    assert "AIza" not in blob or "***REDACTED***" in blob
    assert "sk-abcdefghijklmnopqrstuvwxyz0123" not in blob
    assert "***REDACTED***" in blob


def test_redact_text_bearer():
    assert "***REDACTED***" in redact_text("Authorization: Bearer abcdefghijklmnop")


def test_grounding_detects_missing_paths(tmp_path: Path):
    (tmp_path / "real.py").write_text("ok\n", encoding="utf-8")
    text = "Edit `real.py` and also touch `missing/module.py` please."
    assert "real.py" in extract_cited_paths(text)
    missing = missing_grounded_paths(text, tmp_path)
    assert "missing/module.py" in missing
    assert "real.py" not in missing


def test_jobs_persist_across_context(tmp_path: Path):
    ctx = build_context(str(tmp_path))
    ctx.store.upsert_job({
        "id": "job_test1", "kind": "run", "workflow_id": "wf_1",
        "label": "t", "status": "running", "started_at": "2026-01-01T00:00:00Z",
        "finished_at": None, "error": None, "result_state": None,
    })
    ctx2 = build_context(str(tmp_path))
    jobs = ctx2.store.list_jobs()
    assert any(j["id"] == "job_test1" for j in jobs)
    assert "wf_1" in ctx2.store.running_workflow_ids()
