"""Merge an agent worktree branch into the protected checkout.

Steps:
1. Commit any pending worktree changes.
2. Re-run tests in the worktree (sandboxed).
3. Checkpoint the protected branch.
4. Merge the agent branch.
5. Re-run tests on the protected checkout; on failure, restore checkpoint.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..coding.implementer import default_test_command
from ..sandbox.policy import SandboxPolicy, default_policy_for_repo, run_sandboxed
from ..workspace.git_ws import GitError, GitWorkspace


@dataclass
class MergeResult:
    ok: bool
    branch: str
    merge_commit: str | None = None
    checkpoint_id: str | None = None
    reason: str = ""
    notes: list[str] = field(default_factory=list)


def merge_agent_branch(
    repo_path: Path,
    worktree: Path,
    branch: str,
    *,
    org_root: Path | None = None,
    test_command: list[str] | None = None,
    policy: SandboxPolicy | None = None,
    message: str = "",
) -> MergeResult:
    ws = GitWorkspace(repo_path)
    notes: list[str] = []
    cmd = test_command or default_test_command()
    sand = policy or default_policy_for_repo(repo_path, org_root)

    try:
        pre = run_sandboxed(cmd, worktree, sand)
    except Exception as exc:  # SandboxError or OSError
        return MergeResult(
            ok=False, branch=branch, reason=f"pre-merge worktree tests error: {exc}",
            notes=notes,
        )
    notes.append(f"worktree_tests_ok={pre.ok} exit={pre.exit_code}")
    if not pre.ok:
        return MergeResult(
            ok=False, branch=branch,
            reason="worktree tests failed; merge refused",
            notes=notes + [pre.stdout[-500:], pre.stderr[-500:]],
        )

    # Drop pytest caches so they are not committed into the agent branch.
    from ..coding.implementer import _cleanup_noise

    _cleanup_noise(worktree)

    try:
        commit = ws.commit_worktree(worktree, message or f"agent changes on {branch}")
        notes.append(f"worktree_commit={commit}")
    except GitError as exc:
        return MergeResult(ok=False, branch=branch, reason=f"worktree commit failed: {exc}")

    try:
        checkpoint_id = ws.checkpoint("pre-merge", f"before merging {branch}")
    except GitError as exc:
        return MergeResult(
            ok=False, branch=branch, reason=f"pre-merge checkpoint failed: {exc}",
            notes=notes,
        )
    notes.append(f"checkpoint={checkpoint_id}")

    try:
        merge_commit = ws.merge_branch(branch, message or f"merge {branch}")
    except GitError as exc:
        return MergeResult(
            ok=False, branch=branch, checkpoint_id=checkpoint_id,
            reason=f"git merge failed: {exc}", notes=notes,
        )

    try:
        post = run_sandboxed(cmd, repo_path, sand)
    except Exception as exc:
        ws.restore_checkpoint(checkpoint_id)
        return MergeResult(
            ok=False, branch=branch, checkpoint_id=checkpoint_id,
            reason=f"post-merge tests error; restored checkpoint: {exc}",
            notes=notes,
        )
    notes.append(f"main_tests_ok={post.ok} exit={post.exit_code}")
    if not post.ok:
        ws.restore_checkpoint(checkpoint_id)
        return MergeResult(
            ok=False, branch=branch, checkpoint_id=checkpoint_id,
            reason="post-merge tests failed; protected branch restored",
            notes=notes + [post.stdout[-500:], post.stderr[-500:]],
        )

    return MergeResult(
        ok=True,
        branch=branch,
        merge_commit=merge_commit,
        checkpoint_id=checkpoint_id,
        reason="merged; protected branch tests passed",
        notes=notes,
    )
