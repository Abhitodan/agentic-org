"""Git workspace manager: checkpoints, worktrees, and reverts.

Checkpoints are real git commits (tagged refs) so every reversion is a
plain git operation and history is never lost. Agent tasks get isolated
worktrees on their own branches; the protected branch is never modified
directly.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from ..core.ids import new_id


class GitError(Exception):
    pass


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


class GitWorkspace:
    def __init__(self, repo_path: Path):
        self.repo = Path(repo_path).resolve()

    def is_repo(self) -> bool:
        try:
            _git(self.repo, "rev-parse", "--git-dir")
            return True
        except GitError:
            return False

    def current_commit(self) -> str | None:
        try:
            return _git(self.repo, "rev-parse", "HEAD")
        except GitError:
            return None  # no commits yet

    def checkpoint(self, kind: str, note: str = "") -> str:
        """Commit all current changes and tag the commit as a checkpoint ref."""
        checkpoint_id = new_id("ckpt")
        _git(self.repo, "add", "-A")
        status = _git(self.repo, "status", "--porcelain")
        if status:
            _git(self.repo, "commit", "-m", f"checkpoint({kind}): {note or checkpoint_id}")
        commit = self.current_commit()
        if commit is None:
            raise GitError("cannot checkpoint an empty repository with no changes")
        _git(self.repo, "tag", "-f", f"checkpoints/{checkpoint_id}", commit)
        return checkpoint_id

    def restore_checkpoint(self, checkpoint_id: str) -> str:
        """Hard-restore working tree to a checkpoint. History is preserved
        because checkpoints are tags, not rewrites."""
        ref = f"checkpoints/{checkpoint_id}"
        commit = _git(self.repo, "rev-parse", ref)
        _git(self.repo, "reset", "--hard", commit)
        return commit

    def diff_checkpoints(self, checkpoint_a: str, checkpoint_b: str) -> str:
        return _git(
            self.repo, "diff", "--stat",
            f"checkpoints/{checkpoint_a}", f"checkpoints/{checkpoint_b}",
        )

    def create_worktree(self, task_id: str, worktrees_dir: Path) -> Path:
        """Create an isolated worktree + branch for an agent task."""
        worktrees_dir.mkdir(parents=True, exist_ok=True)
        branch = f"agent/{task_id}"
        path = worktrees_dir / task_id
        _git(self.repo, "worktree", "add", "-b", branch, str(path))
        return path

    def remove_worktree(self, path: Path) -> None:
        _git(self.repo, "worktree", "remove", "--force", str(path))

    def list_checkpoints(self) -> list[str]:
        out = _git(self.repo, "tag", "--list", "checkpoints/*")
        return [t.removeprefix("checkpoints/") for t in out.splitlines() if t]

    def status_porcelain(self) -> str:
        return _git(self.repo, "status", "--porcelain")

    def is_dirty_tracked(self) -> bool:
        """True when meaningful tracked files differ from HEAD.

        Ignores untracked files and bytecode paths (`__pycache__`, `*.pyc`)
        so local test runs cannot block merge/release.
        """
        try:
            unstaged = _git(self.repo, "diff", "--name-only")
            staged = _git(self.repo, "diff", "--cached", "--name-only")
        except GitError:
            return True
        names = [
            n.strip().replace("\\", "/")
            for n in (unstaged + "\n" + staged).splitlines()
            if n.strip()
        ]
        meaningful = [
            n for n in names
            if "__pycache__/" not in f"/{n}/"
            and not n.endswith(".pyc")
            and not n.endswith(".pyo")
        ]
        return bool(meaningful)

    def current_branch(self) -> str:
        return _git(self.repo, "rev-parse", "--abbrev-ref", "HEAD")

    def commit_worktree(self, worktree: Path, message: str) -> str:
        """Commit pending changes inside a worktree; return HEAD."""
        wt = Path(worktree).resolve()
        _git(wt, "add", "-A")
        status = _git(wt, "status", "--porcelain")
        if status:
            _git(wt, "commit", "-m", message)
        return _git(wt, "rev-parse", "HEAD")

    def merge_branch(self, branch: str, message: str = "") -> str:
        """Merge branch into the protected checkout (no fast-forward)."""
        msg = message or f"merge {branch}"
        try:
            _git(self.repo, "merge", "--no-ff", branch, "-m", msg)
        except GitError as exc:
            # Already up to date is success for empty agent diffs.
            if "Already up to date" in str(exc) or "already up to date" in str(exc):
                return self.current_commit() or ""
            raise
        return self.current_commit() or ""

    def create_annotated_tag(self, tag: str, message: str) -> str:
        commit = self.current_commit()
        if commit is None:
            raise GitError("cannot tag empty repository")
        _git(self.repo, "tag", "-a", tag, "-m", message, commit)
        return commit
