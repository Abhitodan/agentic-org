"""Run tests and return hash-backed evidence. The only proof of "tests pass".

Contract:
- Commands run under the organization sandbox policy (allowlisted argv,
  never an arbitrary shell). String commands are shell-split locally.
- stdout/stderr are sha256-hashed so evidence is tamper-evident and compact;
  tails are included for humans.
- Hard errors (bad argument types) raise; run outcomes return ok/exit_code.
"""

from __future__ import annotations

import hashlib
import shlex
from pathlib import Path
from typing import Any

_EVIDENCE = "deterministic_test_run"
_TAIL_CHARS = 2000


def _sha256(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", errors="replace")).hexdigest()


def _normalize_command(command: list[str] | str | None) -> list[str] | None:
    if command is None:
        return None
    if isinstance(command, str):
        argv = shlex.split(command, posix=False)
    else:
        argv = [str(part) for part in command]
    return argv or None  # empty means "use the default", never []


def run(
    cwd: str | Path,
    command: list[str] | str | None = None,
    org_root: str | Path | None = None,
) -> dict[str, Any]:
    from agentic_org.coding.implementer import run_tests

    work = Path(cwd)
    if not work.is_dir():
        return {
            "ok": False,
            "reason": f"cwd missing: {work}",
            "exit_code": None,
            "evidence": _EVIDENCE,
        }

    result = run_tests(
        work,
        _normalize_command(command),
        org_root=Path(org_root) if org_root else None,
    )
    return {
        "ok": bool(result.ok),
        "exit_code": result.exit_code,
        "command": result.command,
        "stdout_hash": _sha256(result.stdout),
        "stderr_hash": _sha256(result.stderr),
        "stdout_tail": result.stdout[-_TAIL_CHARS:],
        "stderr_tail": result.stderr[-_TAIL_CHARS:],
        "duration_ms": result.duration_ms,
        "evidence": _EVIDENCE,
    }
