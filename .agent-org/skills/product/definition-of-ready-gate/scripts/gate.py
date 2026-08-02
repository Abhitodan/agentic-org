"""Definition of Ready gate: may this story enter a sprint?

Contract:
- The gate is a checklist evaluated per story; every failed check names the
  missing artifact so the Product Owner knows exactly what to supply.
- Unresolved dependencies and open questions block. "We'll figure it out in
  the sprint" is the failure mode this gate exists to prevent.
"""

from __future__ import annotations

from typing import Any

_EVIDENCE = "deterministic_ready_gate"

# Checks every story must pass, in the order they are reported.
DOR_CHECKS = (
    "has_id",
    "has_narrative",
    "has_acceptance_criteria",
    "criteria_measurable",
    "has_estimate",
    "estimate_within_threshold",
    "dependencies_resolved",
    "no_open_questions",
)


def run(
    stories: Any = None,
    completed_ids: Any = None,
    require_estimate: bool = True,
    require_components: bool = False,
) -> dict[str, Any]:
    from agentic_org.agile import (
        SPLIT_THRESHOLD,
        FindingList,
        build_result,
        parse_stories,
    )

    parsed = parse_stories(stories)
    findings = FindingList()
    if not parsed:
        findings.error("no_stories", "no stories submitted to the readiness gate")
        return build_result(findings, _EVIDENCE, ready=[], not_ready=[], checked=0)

    done = {str(item).strip().upper() for item in (completed_ids or [])}
    known = {s.id.upper() for s in parsed if s.id}
    ready: list[str] = []
    not_ready: list[str] = []
    report: list[dict[str, Any]] = []

    for story in parsed:
        subject = story.id or story.title or "<story>"
        failed: list[str] = []

        if not story.id:
            failed.append("has_id")
            findings.error("missing_id", "story has no id", subject, "id")

        if not story.has_narrative():
            failed.append("has_narrative")
            findings.error(
                "incomplete_narrative",
                "narrative must state as_a / i_want / so_that",
                subject,
                "narrative",
            )

        if not story.acceptance_criteria:
            failed.append("has_acceptance_criteria")
            findings.error(
                "no_acceptance_criteria",
                "no acceptance criteria; nothing to verify at review",
                subject,
                "acceptance_criteria",
            )
        else:
            unmeasurable = [
                c.id for c in story.acceptance_criteria if not c.is_measurable()
            ]
            if unmeasurable:
                failed.append("criteria_measurable")
                findings.error(
                    "unmeasurable_criteria",
                    f"criteria without an observable outcome: {', '.join(unmeasurable)}",
                    subject,
                    "acceptance_criteria",
                )

        if story.estimate is None:
            if require_estimate:
                failed.append("has_estimate")
                findings.error(
                    "missing_estimate",
                    "story is unestimated; capacity cannot be planned",
                    subject,
                    "estimate",
                )
        elif story.estimate > SPLIT_THRESHOLD:
            failed.append("estimate_within_threshold")
            findings.error(
                "too_large",
                f"estimate {story.estimate} exceeds {SPLIT_THRESHOLD}; split first",
                subject,
                "estimate",
            )

        unresolved = [
            dep for dep in story.dependencies
            if dep.strip().upper() not in done
        ]
        if unresolved:
            failed.append("dependencies_resolved")
            blocking_inside = [d for d in unresolved if d.strip().upper() in known]
            detail = f"unresolved dependencies: {', '.join(unresolved)}"
            if blocking_inside:
                detail += f" (also in this batch: {', '.join(blocking_inside)})"
            findings.error("blocked_by_dependency", detail, subject, "dependencies")

        if story.open_questions:
            failed.append("no_open_questions")
            findings.error(
                "open_questions",
                f"{len(story.open_questions)} unanswered question(s) remain",
                subject,
                "open_questions",
            )

        if require_components and not story.components:
            findings.warn(
                "no_components",
                "no components or paths identified; grounding is unverified",
                subject,
                "components",
            )

        if failed:
            not_ready.append(story.id or subject)
        else:
            ready.append(story.id or subject)
        report.append({
            "id": story.id,
            "ready": not failed,
            "failed_checks": failed,
        })

    return build_result(
        findings,
        _EVIDENCE,
        checked=len(parsed),
        ready=ready,
        not_ready=not_ready,
        ready_count=len(ready),
        checks=list(DOR_CHECKS),
        report=report,
    )
