"""Post-deploy checks must run and pass; output hashed like test-evidence."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

_EVIDENCE = "deterministic_deployment_checks"
_TAIL = 2000


def _sha(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", errors="replace")).hexdigest()


def run(
    commands: Any = None,
    cwd: str | Path | None = None,
    org_root: str | Path | None = None,
    deployment_record: Any = None,
) -> dict[str, Any]:
    from agentic_org.agile import FindingList, build_result
    from agentic_org.coding.implementer import run_tests

    findings = FindingList()
    record = deployment_record if isinstance(deployment_record, dict) else {}
    if not record:
        findings.warn(
            "no_deployment_record",
            "no deployment record supplied; verifying commands only",
        )

    cmd_list = list(commands or [])
    if not cmd_list:
        findings.error(
            "no_verification_commands",
            "deployment claimed without verification commands",
        )
        return build_result(findings, _EVIDENCE, checks=[])

    work = Path(cwd) if cwd else Path.cwd()
    if not work.is_dir():
        findings.error("cwd_missing", f"cwd missing: {work}")
        return build_result(findings, _EVIDENCE, checks=[])

    checks: list[dict[str, Any]] = []
    for index, raw in enumerate(cmd_list, 1):
        if isinstance(raw, str):
            import shlex
            argv = shlex.split(raw, posix=False)
        else:
            argv = [str(p) for p in raw]
        subject = f"check-{index}"
        result = run_tests(work, argv, org_root=Path(org_root) if org_root else None)
        entry = {
            "command": result.command,
            "ok": bool(result.ok),
            "exit_code": result.exit_code,
            "stdout_hash": _sha(result.stdout),
            "stderr_hash": _sha(result.stderr),
            "stdout_tail": result.stdout[-_TAIL:],
        }
        checks.append(entry)
        if not result.ok:
            findings.error(
                "verification_failed",
                f"exit={result.exit_code} command={result.command}",
                subject,
            )

    if record.get("status") == "success" and any(not c["ok"] for c in checks):
        findings.error(
            "success_without_green_checks",
            "deployment_record status=success but verification failed",
        )

    return build_result(
        findings,
        _EVIDENCE,
        checks=checks,
        check_count=len(checks),
        all_green=all(c["ok"] for c in checks),
    )
