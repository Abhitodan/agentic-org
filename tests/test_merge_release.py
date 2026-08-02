from pathlib import Path

from agentic_org.release.merge import merge_agent_branch
from agentic_org.release.release import create_release
from agentic_org.workspace.git_ws import GitWorkspace


def _repo_with_worktree(tmp_path: Path):
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    for cmd in (
        ["git", "init"],
        ["git", "config", "user.email", "t@a.org"],
        ["git", "config", "user.name", "T"],
    ):
        subprocess.run(cmd, cwd=repo, check=True, capture_output=True)
    (repo / "app.py").write_text("def add(a,b):\n    return a+b\n", encoding="utf-8")
    (repo / "test_app.py").write_text(
        "from app import add\n\ndef test_add():\n    assert add(1,2)==3\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True,
                   capture_output=True)
    ws = GitWorkspace(repo)
    wt = ws.create_worktree("task-merge", tmp_path / "wts")
    (wt / "app.py").write_text(
        "def add(a,b):\n    return a+b\n\ndef mul(a,b):\n    return a*b\n",
        encoding="utf-8",
    )
    return repo, wt, "agent/task-merge"


def test_merge_agent_branch_and_release(tmp_path: Path):
    repo, wt, branch = _repo_with_worktree(tmp_path)
    merged = merge_agent_branch(repo, wt, branch, org_root=tmp_path)
    assert merged.ok, merged.reason
    assert "mul" in (repo / "app.py").read_text(encoding="utf-8")
    released = create_release(repo, "0.1.0", org_root=tmp_path,
                              release_notes="test release")
    assert released.ok, released.reason
    assert released.tag == "release/0.1.0"
    tags = GitWorkspace(repo).list_checkpoints()  # not tags helper for release
    import subprocess
    out = subprocess.run(
        ["git", "-C", str(repo), "tag", "--list", "release/*"],
        capture_output=True, text=True, check=True,
    ).stdout
    assert "release/0.1.0" in out
