"""Phase 4: chaos — interrupt Mid-run and resume from checkpoint."""

from __future__ import annotations

import subprocess
from pathlib import Path

from agentic_org.context import build_context
from agentic_org.core.budget import Budget
from agentic_org.core.state_machine import WorkflowState
from agentic_org.orchestrator.runner import PLAN_GATE


def _repo(path: Path) -> None:
    path.mkdir()
    (path / "app.py").write_text("def hi():\n    return 1\n", encoding="utf-8")
    (path / "test_app.py").write_text(
        "from app import hi\n\ndef test_hi():\n    assert hi() == 1\n",
        encoding="utf-8",
    )
    for cmd in (
        ["git", "init"],
        ["git", "config", "user.email", "c@a.org"],
        ["git", "config", "user.name", "C"],
        ["git", "add", "-A"],
        ["git", "commit", "-m", "i"],
    ):
        subprocess.run(cmd, cwd=path, check=True, capture_output=True)


def test_resume_after_awaiting_decision(tmp_path: Path, monkeypatch):
    """Simulate operator crash after charter: state persisted; resume continues."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AGENTIC_ORG_MODEL_API_KEY", raising=False)

    repo = tmp_path / "repo"
    _repo(repo)
    org = tmp_path / "org"
    org.mkdir()
    ctx = build_context(str(org))
    project = ctx.store.create_project("chaos", str(repo))
    feature = ctx.store.create_feature(project["id"], "f", "chaos objective")
    workflow = ctx.store.create_workflow(feature["id"], "existing-feature", Budget())
    # Without key, run blocks at charter — that is still a resume-safe state.
    ctx.runner.start("chaos", "f", feature["objective"], str(repo), workflow["id"])
    mid = ctx.store.get_workflow(workflow["id"])
    assert mid["state"] in {
        WorkflowState.BLOCKED.value,
        WorkflowState.AWAITING_DECISION.value,
        WorkflowState.OPTIONS_READY.value,
    }
    # "Kill process": drop context; new context reads same SQLite.
    ctx.store.conn.close()
    ctx2 = build_context(str(org))
    again = ctx2.store.get_workflow(workflow["id"])
    assert again["state"] == mid["state"]
    # If blocked for model, resume stays blocked (honest). If awaiting, approve path.
    if again["state"] == WorkflowState.AWAITING_DECISION.value:
        ctx2.store.decide_approval(workflow["id"], PLAN_GATE, True, "chaos", "ok")
        ctx2.runner.resume(workflow["id"])
        final = ctx2.store.get_workflow(workflow["id"])
        assert final["state"] in {
            WorkflowState.PLANNED.value,
            WorkflowState.BLOCKED.value,
            WorkflowState.AWAITING_APPROVAL.value,
        }
