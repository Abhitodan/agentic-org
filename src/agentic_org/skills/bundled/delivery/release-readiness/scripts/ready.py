"""Aggregate release evidence: demos, tests, review, approval, rollback."""

from __future__ import annotations

from typing import Any

_EVIDENCE = "deterministic_release_evidence"


def run(
    stories: Any = None,
    demonstrated_ids: Any = None,
    test_evidence: Any = None,
    review_result: Any = None,
    approval: Any = None,
    rollback_plan: Any = None,
) -> dict[str, Any]:
    from agentic_org.agile import FindingList, build_result, parse_stories

    parsed = parse_stories(stories)
    findings = FindingList()
    if not parsed:
        findings.error("no_stories", "release includes no stories")
        return build_result(findings, _EVIDENCE, ready=False)

    demonstrated = {str(i).strip().upper() for i in (demonstrated_ids or [])}
    evidence_map = dict(test_evidence or {})
    missing_demo: list[str] = []
    missing_tests: list[str] = []
    for story in parsed:
        subject = story.id or "<story>"
        key = subject.upper()
        if key not in demonstrated:
            missing_demo.append(subject)
            findings.error(
                "not_demonstrated",
                "story not demonstrated before release",
                subject,
            )
        ev = evidence_map.get(story.id) or evidence_map.get(key)
        if not (isinstance(ev, dict) and ev.get("ok") is True):
            missing_tests.append(subject)
            findings.error(
                "missing_test_evidence",
                "green test-evidence payload required",
                subject,
                "test_evidence",
            )

    review = review_result if isinstance(review_result, dict) else {}
    if not review:
        findings.error("no_review", "release requires a code-review result")
    elif review.get("ok") is not True:
        findings.error(
            "review_not_clean",
            f"review ok={review.get('ok')}; unresolved errors block release",
        )
    else:
        errors = [
            f for f in (review.get("findings") or [])
            if f.get("severity") == "error"
        ]
        if errors:
            findings.error(
                "review_has_errors",
                f"{len(errors)} unresolved error finding(s) in review",
            )

    appr = approval if isinstance(approval, dict) else {}
    if not appr or appr.get("approved") is not True:
        findings.error(
            "no_release_approval",
            "release-approval human gate not recorded as approved",
        )

    rb = rollback_plan if isinstance(rollback_plan, dict) else {}
    if not rb:
        findings.error("no_rollback_plan", "rollback plan artifact missing")
    elif rb.get("ok") is False:
        findings.error(
            "rollback_incomplete",
            "rollback plan reports ok=false",
        )

    result = build_result(
        findings,
        _EVIDENCE,
        story_count=len(parsed),
        missing_demo=missing_demo,
        missing_tests=missing_tests,
    )
    result["ready"] = result["ok"]
    return result
