"""Release dirty checks ignore bytecode noise."""

from __future__ import annotations

import subprocess
from pathlib import Path

from agentic_org.workspace.git_ws import GitWorkspace


def test_is_dirty_tracked_ignores_pycache(tmp_path: Path):
    repo = tmp_path / "r"
    repo.mkdir()
    for cmd in (
        ["git", "init"],
        ["git", "config", "user.email", "t@a.org"],
        ["git", "config", "user.name", "T"],
    ):
        subprocess.run(cmd, cwd=repo, check=True, capture_output=True)
    (repo / "app.py").write_text("x = 1\n", encoding="utf-8")
    cache = repo / "pkg" / "__pycache__"
    cache.mkdir(parents=True)
    (cache / "mod.cpython-313.pyc").write_bytes(b"abc")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True)
    (cache / "mod.cpython-313.pyc").write_bytes(b"changed")
    ws = GitWorkspace(repo)
    assert ws.is_dirty_tracked() is False
    (repo / "app.py").write_text("x = 2\n", encoding="utf-8")
    assert ws.is_dirty_tracked() is True
