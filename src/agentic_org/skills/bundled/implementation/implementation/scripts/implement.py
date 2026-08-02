"""Apply bounded file actions in a worktree, then gate on tests.

Contract:
- Path containment and non-empty actions are enforced by `apply_actions`
  (rejects absolute paths, `..` traversal, and empty action lists).
- `ok: true` requires the test command to exit 0 — no other success path.
- `skip_tests` returns apply-only results and says so in the payload.
- Hard errors (bad argument types) raise; gate outcomes return ok/reason.
"""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

_EVIDENCE = "deterministic_apply_and_tests"
_TAIL_CHARS = 2000


def _normalize_command(command: list[str] | str | None) -> list[str] | None:
    """Return an argv list, or None to use the project default."""
    if command is None:
        return None
    if isinstance(command, str):
        argv = shlex.split(command, posix=False)
    else:
        argv = [str(part) for part in command]
    return argv or None  # empty command means "use the default", never []


def _failure(reason: str) -> dict[str, Any]:
    return {
        "ok": False,
        "reason": reason,
        "actions_applied": 0,
        "test": None,
        "evidence": _EVIDENCE,
    }


def run(
    worktree: str | Path,
    actions: list[dict[str, Any]] | None = None,
    test_command: list[str] | str | None = None,
    org_root: str | Path | None = None,
    skip_tests: bool = False,
) -> dict[str, Any]:
    if actions is not None:
        if not isinstance(actions, (list, tuple)):
            raise TypeError("actions must be a list of {op, path, content} dicts")
        for i, action in enumerate(actions):
            if not isinstance(action, dict):
                raise TypeError(f"actions[{i}] must be a dict, got {type(action).__name__}")

    from agentic_org.coding.implementer import apply_actions, run_tests

    wt = Path(worktree)
    if not wt.is_dir():
        return _failure(f"worktree missing: {wt}")

    try:
        applied = apply_actions(wt, list(actions or []))
    except ValueError as exc:  # containment violation / invalid / empty actions
        return _failure(str(exc))

    if skip_tests:
        return {
            "ok": True,
            "actions_applied": applied,
            "reason": "apply-only (tests skipped by caller)",
            "test": None,
            "evidence": _EVIDENCE,
        }

    test = run_tests(
        wt,
        _normalize_command(test_command),
        org_root=Path(org_root) if org_root else None,
    )
    return {
        "ok": bool(test.ok),
        "actions_applied": applied,
        "reason": (
            "" if test.ok
            else "tests failed after implementation; success not claimed"
        ),
        "test": {
            "ok": test.ok,
            "exit_code": test.exit_code,
            "command": test.command,
            "stdout_tail": test.stdout[-_TAIL_CHARS:],
            "stderr_tail": test.stderr[-_TAIL_CHARS:],
            "duration_ms": test.duration_ms,
        },
        "evidence": _EVIDENCE,
    }
