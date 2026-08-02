"""Verify required artifacts exist before a persona handoff proceeds."""

from __future__ import annotations

from typing import Any

_EVIDENCE = "deterministic_handoff_completeness"

# from -> to -> required artifact keys in the bundle
CONTRACTS: dict[tuple[str, str], tuple[str, ...]] = {
    ("planning-agent", "backend-agent"): ("approved_plan", "acceptance_criteria"),
    ("planning-agent", "frontend-agent"): ("approved_plan", "acceptance_criteria"),
    ("planning-agent", "implementation"): ("approved_plan", "acceptance_criteria"),
    ("backend-agent", "reviewer-agent"): ("diff", "test_evidence"),
    ("frontend-agent", "reviewer-agent"): ("diff", "test_evidence"),
    ("implementation", "reviewer-agent"): ("diff", "test_evidence"),
    ("reviewer-agent", "release-agent"): ("approved_review",),
}


def run(
    from_persona: str = "",
    to_persona: str = "",
    artifacts: Any = None,
) -> dict[str, Any]:
    from agentic_org.agile import FindingList, build_result

    findings = FindingList()
    src = str(from_persona or "").strip()
    dst = str(to_persona or "").strip()
    if not src or not dst:
        findings.error("missing_personas", "from_persona and to_persona are required")
        return build_result(findings, _EVIDENCE, allowed=False)

    bundle = artifacts if isinstance(artifacts, dict) else {}
    required = CONTRACTS.get((src, dst))
    if required is None:
        # Allow generic role aliases
        for (a, b), req in CONTRACTS.items():
            if a.split("-")[0] in src and b.split("-")[0] in dst:
                required = req
                break
    if required is None:
        findings.warn(
            "unknown_handoff",
            f"no named contract for {src} -> {dst}; checking common keys only",
        )
        required = ()

    missing: list[str] = []
    for key in required:
        value = bundle.get(key)
        if value is None or value == "" or value == {} or value == []:
            missing.append(key)
            findings.error(
                "missing_artifact",
                f"handoff {src} -> {dst} requires {key!r}",
                field_name=key,
            )
        elif key == "test_evidence" and isinstance(value, dict) and value.get("ok") is not True:
            findings.error(
                "test_evidence_not_green",
                "test_evidence must report ok=true",
                field_name=key,
            )
        elif key == "approved_plan" and isinstance(value, dict) and value.get("approved") is not True:
            findings.error(
                "plan_not_approved",
                "approved_plan.approved must be true",
                field_name=key,
            )
        elif key == "approved_review" and isinstance(value, dict):
            if value.get("ok") is not True:
                findings.error(
                    "review_not_approved",
                    "approved_review.ok must be true",
                    field_name=key,
                )
            errors = [f for f in (value.get("findings") or []) if f.get("severity") == "error"]
            if errors:
                findings.error(
                    "review_has_errors",
                    f"{len(errors)} unresolved error(s) block handoff to release",
                    field_name=key,
                )
        elif key == "acceptance_criteria" and not value:
            findings.error(
                "no_acceptance_criteria",
                "acceptance_criteria must be non-empty",
                field_name=key,
            )

    result = build_result(
        findings,
        _EVIDENCE,
        from_persona=src,
        to_persona=dst,
        required=list(required),
        missing=missing,
    )
    result["allowed"] = result["ok"]
    return result
