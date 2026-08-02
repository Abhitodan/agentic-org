"""Test-gated worktree implementation node."""

from __future__ import annotations

import json
from pathlib import Path

from agentic_org.context import build_context
from agentic_org.core.budget import Budget


def _seed_repo(repo: Path, *, broken: bool = True) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    import subprocess

    for cmd in (
        ["git", "init"],
        ["git", "config", "user.email", "test@agentic.org"],
        ["git", "config", "user.name", "Test"],
    ):
        subprocess.run(cmd, cwd=repo, check=True, capture_output=True)
    (repo / "app.py").write_text(
        "def add(a, b):\n    return a - b\n" if broken else "def add(a, b):\n    return a + b\n",
        encoding="utf-8",
    )
    (repo / "test_app.py").write_text(
        "from app import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True,
                   capture_output=True)


def _setup_planned(tmp_path: Path, repo: Path, actions: list[dict] | None):
    root = tmp_path / "org"
    root.mkdir()
    ctx = build_context(str(root))
    project = ctx.store.create_project("demo", str(repo))
    feature = ctx.store.create_feature(project["id"], "fix-add", "Fix add()")
    workflow = ctx.store.create_workflow(feature["id"], "existing-feature", Budget())
    feature_dir = root / "projects" / "demo" / "features" / "fix-add"
    artifacts = feature_dir / "artifacts"
    artifacts.mkdir(parents=True)
    (feature_dir / "implementation-plan.md").write_text("# plan\nfix add\n",
                                                        encoding="utf-8")
    (feature_dir / "charter.md").write_text("# charter\n", encoding="utf-8")
    if actions is not None:
        (artifacts / "implementation_actions.json").write_text(
            json.dumps(actions), encoding="utf-8"
        )
    # Jump state machine to PLANNED as if plan already completed.
    from agentic_org.core.state_machine import WorkflowState
    ctx.store.set_workflow_state(workflow["id"], WorkflowState.PLANNED.value)
    return ctx, workflow


def test_implement_succeeds_only_when_tests_pass(tmp_path: Path):
    repo = tmp_path / "repo"
    _seed_repo(repo, broken=True)
    actions = [{
        "op": "write",
        "path": "app.py",
        "content": "def add(a, b):\n    return a + b\n",
    }]
    ctx, workflow = _setup_planned(tmp_path, repo, actions)
    state = {
        "workflow_id": workflow["id"],
        "project_name": "demo",
        "feature_name": "fix-add",
        "repo_path": str(repo),
        "objective": "Fix add()",
        "blocked_reason": None,
        "notes": [],
    }
    out = ctx.runner.node_implement(state)
    final = ctx.store.get_workflow(workflow["id"])
    assert out.get("blocked_reason") is None
    assert final["state"] == "VALIDATING"
    events = {e["event_type"] for e in ctx.events.list(workflow_id=workflow["id"])}
    assert "implementation.succeeded" in events
    # Protected checkout unchanged; fix lives in worktree only.
    assert "a - b" in (repo / "app.py").read_text(encoding="utf-8")


def test_implement_blocks_when_tests_fail(tmp_path: Path):
    repo = tmp_path / "repo"
    _seed_repo(repo, broken=True)
    actions = [{
        "op": "write",
        "path": "app.py",
        "content": "def add(a, b):\n    return 0\n",
    }]
    ctx, workflow = _setup_planned(tmp_path, repo, actions)
    state = {
        "workflow_id": workflow["id"],
        "project_name": "demo",
        "feature_name": "fix-add",
        "repo_path": str(repo),
        "objective": "Fix add()",
        "blocked_reason": None,
        "notes": [],
    }
    out = ctx.runner.node_implement(state)
    final = ctx.store.get_workflow(workflow["id"])
    assert final["state"] == "BLOCKED"
    assert "tests failed" in (out.get("blocked_reason") or "")
    events = {e["event_type"] for e in ctx.events.list(workflow_id=workflow["id"])}
    assert "implementation.failed" in events
