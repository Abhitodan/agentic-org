"""Release tagging after readiness checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..coding.implementer import default_test_command
from ..sandbox.policy import default_policy_for_repo, run_sandboxed
from ..workspace.git_ws import GitError, GitWorkspace


@dataclass
class ReleaseResult:
    ok: bool
    version: str
    tag: str | None = None
    commit: str | None = None
    reason: str = ""
    checks: dict[str, bool] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


def create_release(
    repo_path: Path,
    version: str,
    *,
    org_root: Path | None = None,
    release_notes: str = "",
    require_clean: bool = True,
    run_tests: bool = True,
) -> ReleaseResult:
    """Create an annotated release tag after checklist gates."""
    ws = GitWorkspace(repo_path)
    checks: dict[str, bool] = {}
    notes: list[str] = []

    if not ws.is_repo():
        return ReleaseResult(ok=False, version=version, reason="not a git repository")

    try:
        # Tracked changes only — pytest cache / __pycache__ must not block release.
        dirty = ws.is_dirty_tracked()
    except GitError as exc:
        return ReleaseResult(ok=False, version=version, reason=str(exc))
    checks["clean_worktree"] = not dirty
    if require_clean and dirty:
        return ReleaseResult(
            ok=False, version=version, checks=checks,
            reason="working tree not clean",
        )

    if run_tests:
        sand = default_policy_for_repo(repo_path, org_root)
        try:
            test = run_sandboxed(default_test_command(), repo_path, sand)
        except Exception as exc:
            checks["tests"] = False
            return ReleaseResult(
                ok=False, version=version, checks=checks,
                reason=f"release tests error: {exc}",
            )
        checks["tests"] = test.ok
        notes.append(f"tests_exit={test.exit_code}")
        if not test.ok:
            return ReleaseResult(
                ok=False, version=version, checks=checks,
                reason="release tests failed",
                notes=notes,
            )
    else:
        checks["tests"] = True

    tag = f"release/{version}"
    body = release_notes or f"Release {version}"
    try:
        commit = ws.create_annotated_tag(tag, body)
    except GitError as exc:
        return ReleaseResult(
            ok=False, version=version, checks=checks,
            reason=f"tag failed: {exc}", notes=notes,
        )
    checks["tagged"] = True
    return ReleaseResult(
        ok=True,
        version=version,
        tag=tag,
        commit=commit,
        reason="release tag created",
        checks=checks,
        notes=notes,
    )
