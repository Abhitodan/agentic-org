"""Sprint review gate: was the committed increment actually demonstrated?

Contract:
- A story counts as delivered only when its acceptance criteria are marked
  demonstrated AND test evidence is attached. Marking it done is a claim;
  evidence is proof.
- Undemonstrated work is reported as carryover, never quietly folded into
  the velocity number.
"""

from __future__ import annotations

from typing import Any

_EVIDENCE = "deterministic_increment_demo"


def _has_green_evidence(payload: Any) -> bool:
    return isinstance(payload, dict) and payload.get("ok") is True


def run(
    committed: Any = None,
    demonstrated_ids: Any = None,
    test_evidence: Any = None,
    sprint_goal: str = "",
) -> dict[str, Any]:
    from agentic_org.agile import FindingList, build_result, parse_stories

    parsed = parse_stories(committed)
    findings = FindingList()
    if not parsed:
        findings.error("no_commitment", "no committed stories supplied to review")
        return build_result(findings, _EVIDENCE, delivered=[], carryover=[])

    demonstrated = {str(i).strip().upper() for i in (demonstrated_ids or [])}
    evidence_map = dict(test_evidence or {})

    delivered: list[str] = []
    carryover: list[str] = []
    delivered_points = 0.0
    committed_points = 0.0

    for story in parsed:
        subject = story.id or story.title or "<story>"
        key = (story.id or "").upper()
        if story.estimate is not None:
            committed_points += story.estimate

        was_demoed = key in demonstrated
        evidence = evidence_map.get(story.id) or evidence_map.get(key)
        has_evidence = _has_green_evidence(evidence)

        if was_demoed and has_evidence:
            delivered.append(subject)
            if story.estimate is not None:
                delivered_points += story.estimate
            continue

        carryover.append(subject)
        if was_demoed and evidence is None:
            findings.error(
                "demo_without_evidence",
                "demonstrated but no test-evidence payload attached; "
                "a demo is not proof the increment works",
                subject,
                "test_evidence",
            )
        elif was_demoed and not has_evidence:
            findings.error(
                "demo_with_failing_tests",
                f"demonstrated while test evidence reports ok="
                f"{evidence.get('ok') if isinstance(evidence, dict) else evidence}",
                subject,
                "test_evidence",
            )
        else:
            findings.warn(
                "not_demonstrated",
                "committed but not demonstrated; carried to the next sprint",
                subject,
                "status",
            )

    if not str(sprint_goal or "").strip():
        findings.warn("no_sprint_goal", "no sprint goal recorded to review against")

    goal_met = bool(delivered) and not carryover
    if carryover:
        findings.info(
            "carryover_recorded",
            f"{len(carryover)} of {len(parsed)} committed stories carried over",
        )

    return build_result(
        findings,
        _EVIDENCE,
        sprint_goal=str(sprint_goal or "").strip(),
        committed_count=len(parsed),
        delivered=delivered,
        carryover=carryover,
        committed_points=committed_points,
        delivered_points=delivered_points,
        goal_met=goal_met,
    )
