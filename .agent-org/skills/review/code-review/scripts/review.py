"""Deterministic review gate: test evidence, acceptance criteria, scope.

Contract:
- Test evidence is mandatory; its absence is an ERROR finding, never a pass.
- Scope check degrades LOUDLY: if the scope detector cannot run, that is a
  WARN finding (`scope_check_unavailable`) — never a silent "keep".
- Findings are deduplicated and ordered errors-first.
- Hard errors (bad argument types) raise; review outcomes return ok/findings.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_EVIDENCE = "deterministic_diff_ac_tests"

# Finding codes (stable API)
ERR_MISSING_EVIDENCE = "missing_test_evidence"
ERR_TESTS_NOT_GREEN = "tests_not_green"
ERR_SCOPE_CREEP = "scope_creep"
WARN_NO_AC = "no_ac"
WARN_SCOPE_JUSTIFY = "scope_justify"
WARN_SCOPE_UNAVAILABLE = "scope_check_unavailable"
WARN_AC_UNREFERENCED = "ac_unreferenced"

_MIN_AC_FRAGMENT = 12  # chars of AC text required for a substring match to count


def _paths_from_diff(diff_text: str) -> list[str]:
    """Extract changed paths from a unified diff (new-side priority)."""
    paths: list[str] = []
    seen: set[str] = set()

    def _add(rel: str) -> None:
        rel = rel.replace("\\", "/").strip()
        if rel and rel != "/dev/null" and rel not in seen:
            seen.add(rel)
            paths.append(rel)

    for line in (diff_text or "").splitlines():
        if line.startswith("+++ b/") or line.startswith("--- a/"):
            _add(line[6:])
        elif line.startswith("diff --git "):
            match = re.search(r" b/(.+)$", line)
            if match:
                _add(match.group(1))
    return paths


def _locate_sibling_script(skill: str, script: str) -> Path | None:
    """Find another skill's script without assuming a category layout.

    Walks up from this file looking for the skills root, then matches both
    flat (`<root>/<skill>`) and categorized (`<root>/<cat>/<skill>`) layouts,
    so relocating a skill between categories cannot silently break review.
    """
    here = Path(__file__).resolve()
    for ancestor in here.parents:
        for candidate in (
            ancestor / skill / "scripts" / script,
            *(ancestor.glob(f"*/{skill}/scripts/{script}")),
        ):
            if candidate.is_file():
                return candidate
        if ancestor.name == "skills":
            break
    return None


def _run_scope_check(
    objective: str, paths: list[str], plan_text: str,
) -> tuple[dict[str, Any], dict[str, str] | None]:
    """Invoke the sibling scope-creep-detector script.

    Returns (scope_result, warn_finding). On any load failure the scope is
    reported as unavailable — an explicit warning, never a silent keep.
    """
    detect_path = _locate_sibling_script("scope-creep-detector", "detect.py")
    try:
        if detect_path is None:
            raise FileNotFoundError("scope-creep-detector/scripts/detect.py not found")
        from importlib.util import module_from_spec, spec_from_file_location

        spec = spec_from_file_location("agentic_org_scope_detect", detect_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load {detect_path}")
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        scope = module.run(
            objective=objective, changed_paths=paths, plan_text=plan_text,
        )
        return scope, None
    except Exception as exc:  # degrade loudly, not silently
        warn = {
            "severity": "warn",
            "code": WARN_SCOPE_UNAVAILABLE,
            "detail": f"scope detector unavailable: {type(exc).__name__}: {exc}",
        }
        return {"ok": None, "verdict": "unknown", "out_of_scope": [],
                "in_scope": paths, "evidence": "unavailable"}, warn


def run(
    diff_text: str = "",
    charter: str = "",
    test_evidence: dict[str, Any] | None = None,
    objective: str = "",
    changed_paths: list[str] | None = None,
    plan_text: str = "",
) -> dict[str, Any]:
    if test_evidence is not None and not isinstance(test_evidence, dict):
        raise TypeError("test_evidence must be a dict (from the test-evidence skill)")
    if changed_paths is not None and not isinstance(changed_paths, (list, tuple)):
        raise TypeError("changed_paths must be a list of relative paths")

    from agentic_org.atl.criteria import parse_acceptance_criteria

    paths = [str(p) for p in changed_paths] if changed_paths else _paths_from_diff(diff_text)
    findings: list[dict[str, str]] = []

    # Gate 1 — test evidence (mandatory)
    evidence_payload = test_evidence or {}
    if not evidence_payload:
        findings.append({
            "severity": "error",
            "code": ERR_MISSING_EVIDENCE,
            "detail": "review requires a test-evidence payload (command + exit code)",
        })
    elif evidence_payload.get("ok") is not True:
        findings.append({
            "severity": "error",
            "code": ERR_TESTS_NOT_GREEN,
            "detail": (
                f"test evidence ok={evidence_payload.get('ok')} "
                f"exit={evidence_payload.get('exit_code')}"
            ),
        })

    # Gate 2 — scope
    scope, scope_warn = _run_scope_check(objective or "", paths, plan_text or "")
    if scope_warn:
        findings.append(scope_warn)
    elif scope.get("verdict") == "split":
        findings.append({
            "severity": "error",
            "code": ERR_SCOPE_CREEP,
            "detail": f"out_of_scope={scope.get('out_of_scope')}",
        })
    elif scope.get("verdict") == "justify" and scope.get("out_of_scope"):
        findings.append({
            "severity": "warn",
            "code": WARN_SCOPE_JUSTIFY,
            "detail": f"acknowledge each: out_of_scope={scope.get('out_of_scope')}",
        })

    # Gate 3 — acceptance criteria presence and reference
    criteria = parse_acceptance_criteria(charter or "")
    if not criteria:
        findings.append({
            "severity": "warn",
            "code": WARN_NO_AC,
            "detail": "charter has no AC-# criteria",
        })
    searchable = f"{diff_text or ''}\n{plan_text or ''}".lower()
    ac_referenced = [
        c.id for c in criteria
        if c.id.lower() in searchable
        or (len(c.text) >= _MIN_AC_FRAGMENT and c.text.lower()[:40] in searchable)
    ]
    if criteria and not ac_referenced and diff_text:
        findings.append({
            "severity": "warn",
            "code": WARN_AC_UNREFERENCED,
            "detail": "neither diff nor plan references any AC id",
        })

    # Deduplicate, order errors first (stable within severity).
    unique: dict[tuple[str, str], dict[str, str]] = {}
    for f in findings:
        unique.setdefault((f["severity"], f["code"]), f)
    ordered = sorted(unique.values(), key=lambda f: 0 if f["severity"] == "error" else 1)

    errors = [f for f in ordered if f["severity"] == "error"]
    return {
        "ok": not errors,
        "findings": ordered,
        "scope": scope,
        "ac_ids": [c.id for c in criteria],
        "ac_referenced": ac_referenced,
        "changed_paths": paths,
        "evidence": _EVIDENCE,
    }
