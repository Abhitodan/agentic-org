"""Structured git history for paths: sha, author, date, subject.

Contract:
- Repository detection uses `git rev-parse --is-inside-work-tree` (correct
  for worktrees and submodules), never fragile `.git` existence checks.
- Output is extracted facts only; interpretation belongs to the caller,
  who must cite shas for any provenance claim.
- Hard errors (bad argument types) raise; git outcomes return ok/reason.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

_EVIDENCE = "deterministic_git_history"
_MAX_COMMITS_CAP = 100
_FIELD_SEP = "\x09"  # tab; subjects containing tabs are split-limited below


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True, text=True, encoding="utf-8",
        errors="replace", check=False,
    )


def _result(ok: bool, history: list[dict[str, str]], *,
            reason: str = "", path_count: int = 0) -> dict[str, Any]:
    return {
        "ok": ok,
        "history": history,
        "path_count": path_count,
        "reason": reason,
        "evidence": _EVIDENCE,
    }


def run(
    repo_path: str | Path,
    paths: list[str] | None = None,
    max_commits: int = 20,
) -> dict[str, Any]:
    if paths is not None and not isinstance(paths, (list, tuple)):
        raise TypeError("paths must be a list of relative paths")

    root = Path(repo_path)
    if not root.is_dir():
        return _result(False, [], reason=f"repo_path missing: {root}")

    try:
        probe = _git(root, "rev-parse", "--is-inside-work-tree")
    except OSError as exc:  # git binary unavailable
        return _result(False, [], reason=f"git unavailable: {exc}")
    if probe.returncode != 0 or probe.stdout.strip() != "true":
        return _result(False, [], reason="not a git repository")

    limit = max(1, min(int(max_commits), _MAX_COMMITS_CAP))
    args = [
        "log", f"-n{limit}", "--date=short",
        f"--pretty=format:%H{_FIELD_SEP}%an{_FIELD_SEP}%ad{_FIELD_SEP}%s",
    ]
    clean_paths = [str(p).strip() for p in (paths or []) if str(p).strip()]
    if clean_paths:
        args.append("--")
        args.extend(clean_paths)

    proc = _git(root, *args)
    if proc.returncode != 0:
        return _result(
            False, [],
            reason=(proc.stderr or proc.stdout or "git log failed")[:500],
            path_count=len(clean_paths),
        )

    history: list[dict[str, str]] = []
    for line in (proc.stdout or "").splitlines():
        parts = line.split(_FIELD_SEP, 3)
        if len(parts) == 4:
            history.append({
                "sha": parts[0],
                "author": parts[1],
                "date": parts[2],
                "subject": parts[3],
            })
    return _result(True, history, path_count=len(clean_paths))
