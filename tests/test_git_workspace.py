from pathlib import Path

from agentic_org.workspace.git_ws import GitWorkspace


def test_checkpoint_and_revert(git_repo: Path):
    ws = GitWorkspace(git_repo)
    assert ws.is_repo()
    baseline = ws.checkpoint("baseline", "before experiment")

    target = git_repo / "main.py"
    target.write_text("print('modified by experiment')\n", encoding="utf-8")
    modified = ws.checkpoint("experiment", "after change")

    assert baseline in ws.list_checkpoints()
    assert modified in ws.list_checkpoints()
    diff = ws.diff_checkpoints(baseline, modified)
    assert "main.py" in diff

    ws.restore_checkpoint(baseline)
    assert "hello" in target.read_text(encoding="utf-8")
    # Reverted work is preserved, not destroyed: the experiment tag survives.
    assert modified in ws.list_checkpoints()


def test_worktree_isolation(git_repo: Path, tmp_path: Path):
    ws = GitWorkspace(git_repo)
    ws.checkpoint("init", "seed")
    worktree = ws.create_worktree("task-123", tmp_path / "worktrees")
    assert (worktree / "main.py").exists()
    # Changes in the worktree do not touch the protected branch checkout.
    (worktree / "main.py").write_text("isolated change\n", encoding="utf-8")
    assert "isolated change" not in (git_repo / "main.py").read_text(encoding="utf-8")
    ws.remove_worktree(worktree)
