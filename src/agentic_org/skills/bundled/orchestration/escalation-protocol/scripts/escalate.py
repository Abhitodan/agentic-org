"""Compute mandatory escalations from budget, confidence, policy, impediments."""

from __future__ import annotations

from typing import Any

_EVIDENCE = "deterministic_escalation_triggers"


def run(
    budget: Any = None,
    confidence: float | None = None,
    policy_flags: Any = None,
    impediments: Any = None,
    confidence_floor: float = 0.55,
    budget_ratio_limit: float = 0.9,
) -> dict[str, Any]:
    from agentic_org.agile import FindingList, build_result

    findings = FindingList()
    escalations: list[dict[str, Any]] = []

    bud = budget if isinstance(budget, dict) else {}
    spent = float(bud.get("spent_usd") or bud.get("spent") or 0)
    maximum = float(bud.get("maximum_usd") or bud.get("maximum") or 0)
    if maximum > 0 and spent / maximum >= budget_ratio_limit:
        escalations.append({
            "code": "budget_threshold",
            "detail": f"spent {spent} of {maximum} (>= {budget_ratio_limit:.0%})",
        })
        findings.error(
            "budget_threshold",
            f"budget consumption {spent / maximum:.0%} requires human escalation",
        )

    if confidence is not None and float(confidence) < confidence_floor:
        escalations.append({
            "code": "low_confidence",
            "detail": f"confidence {confidence} below floor {confidence_floor}",
        })
        findings.error(
            "low_confidence",
            f"confidence {confidence} below {confidence_floor}",
        )

    for flag in policy_flags or []:
        name = str(flag.get("name") if isinstance(flag, dict) else flag)
        triggered = True if not isinstance(flag, dict) else bool(flag.get("triggered", True))
        if triggered:
            escalations.append({"code": "policy_trigger", "detail": name})
            findings.error("policy_trigger", f"policy flag triggered: {name}", name)

    for raw in impediments or []:
        if not isinstance(raw, dict):
            continue
        if raw.get("escalate") or (
            str(raw.get("severity") or "").lower() == "blocker"
            and float(raw.get("age_days") or 0) >= 1
        ):
            iid = str(raw.get("id") or "impediment")
            escalations.append({
                "code": "impediment_age",
                "detail": iid,
            })
            findings.error(
                "impediment_escalation",
                f"impediment {iid} requires escalation",
                iid,
            )

    result = build_result(
        findings,
        _EVIDENCE,
        escalations=escalations,
        escalation_count=len(escalations),
    )
    result["must_escalate"] = bool(escalations)
    return result
