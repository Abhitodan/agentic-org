"""Reject new assignments that breach per-persona or team WIP limits."""

from __future__ import annotations

from typing import Any

_EVIDENCE = "deterministic_wip_enforcement"


def run(
    assignments: Any = None,
    limits: Any = None,
    proposed: Any = None,
) -> dict[str, Any]:
    from agentic_org.agile import FindingList, build_result

    findings = FindingList()
    current = list(assignments or [])
    lim = limits if isinstance(limits, dict) else {}
    per_persona = int(lim.get("per_persona") or lim.get("persona") or 2)
    team_limit = int(lim.get("team") or 0)  # 0 = unlimited

    counts: dict[str, int] = {}
    for item in current:
        if isinstance(item, dict):
            who = str(item.get("persona") or item.get("assignee") or "").strip()
        else:
            who = ""
        if who:
            counts[who] = counts.get(who, 0) + 1

    prop = proposed if isinstance(proposed, dict) else {}
    persona = str(prop.get("persona") or prop.get("assignee") or "").strip()
    if not persona:
        findings.error("no_assignee", "proposed assignment names no persona")
        result = build_result(findings, _EVIDENCE, accepted=False, counts=counts)
        return result

    new_count = counts.get(persona, 0) + 1
    if new_count > per_persona:
        findings.error(
            "persona_wip_exceeded",
            f"{persona} would have {new_count} items; limit is {per_persona}",
            persona,
        )
    team_total = sum(counts.values()) + 1
    if team_limit and team_total > team_limit:
        findings.error(
            "team_wip_exceeded",
            f"team would have {team_total} items; limit is {team_limit}",
        )

    # Current breaches (informational for remediation)
    for who, count in counts.items():
        if count > per_persona:
            findings.warn(
                "persona_already_over",
                f"{who} already at {count} (limit {per_persona})",
                who,
            )

    result = build_result(
        findings,
        _EVIDENCE,
        counts=counts,
        proposed_persona=persona,
        per_persona_limit=per_persona,
        team_limit=team_limit or None,
    )
    result["accepted"] = result["ok"]
    return result
