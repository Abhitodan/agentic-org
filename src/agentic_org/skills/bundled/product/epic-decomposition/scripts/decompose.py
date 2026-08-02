"""Check an epic decomposes cleanly into stories with full traceability.

Contract:
- Every epic outcome must be claimed by at least one story, and every story
  must belong to a declared epic. Orphans in either direction are errors.
- Traceability is explicit (`parent` / `covers`), never inferred from wording.
"""

from __future__ import annotations

from typing import Any

_EVIDENCE = "deterministic_epic_traceability"

# A decomposition this wide is usually a program, not an epic.
MAX_STORIES_PER_EPIC = 20


def _covers(story: Any) -> list[str]:
    raw = story.raw.get("covers") or story.raw.get("covers_ac") or []
    if isinstance(raw, str):
        raw = [raw]
    return [str(item).strip().upper() for item in raw if str(item).strip()]


def run(
    epic: Any = None,
    stories: Any = None,
    max_stories: int = MAX_STORIES_PER_EPIC,
) -> dict[str, Any]:
    from agentic_org.agile import FindingList, build_result, parse_stories

    epics = parse_stories(epic)
    children = parse_stories(stories)
    findings = FindingList()

    if not epics:
        findings.error("no_epic", "an epic is required to check decomposition")
        return build_result(findings, _EVIDENCE, story_count=len(children))
    parent = epics[0]
    epic_id = parent.id or "<epic>"

    if not children:
        findings.error("no_stories", "epic has no child stories", epic_id)
        return build_result(findings, _EVIDENCE, epic_id=parent.id, story_count=0)

    if len(children) > max_stories:
        findings.warn(
            "epic_too_wide",
            f"{len(children)} stories exceeds {max_stories}; "
            "consider splitting the epic into features",
            epic_id,
        )

    epic_outcomes = {c.id.upper() for c in parent.acceptance_criteria}
    if not epic_outcomes:
        findings.warn(
            "epic_without_outcomes",
            "epic declares no acceptance criteria; coverage is unverifiable",
            epic_id,
            "acceptance_criteria",
        )

    claimed: set[str] = set()
    orphans: list[str] = []
    total_points = 0.0
    estimated = 0
    for story in children:
        subject = story.id or story.title or "<story>"

        declared_parent = story.parent.strip().upper()
        if not declared_parent:
            orphans.append(subject)
            findings.error(
                "orphan_story",
                "story declares no parent epic",
                subject,
                "parent",
            )
        elif parent.id and declared_parent != parent.id.upper():
            findings.error(
                "wrong_parent",
                f"declares parent {story.parent!r}, expected {parent.id!r}",
                subject,
                "parent",
            )

        covers = _covers(story)
        unknown = [c for c in covers if epic_outcomes and c not in epic_outcomes]
        if unknown:
            findings.error(
                "covers_unknown_outcome",
                f"claims epic outcomes that do not exist: {', '.join(unknown)}",
                subject,
                "covers",
            )
        claimed.update(c for c in covers if c in epic_outcomes)
        if epic_outcomes and not covers:
            findings.warn(
                "no_traceability",
                "story does not declare which epic outcomes it delivers",
                subject,
                "covers",
            )

        if story.estimate is not None:
            total_points += story.estimate
            estimated += 1

    uncovered = sorted(epic_outcomes - claimed)
    if uncovered:
        findings.error(
            "uncovered_outcomes",
            f"epic outcomes no story delivers: {', '.join(uncovered)}",
            epic_id,
            "acceptance_criteria",
        )

    if estimated and estimated < len(children):
        findings.warn(
            "partial_estimates",
            f"{estimated}/{len(children)} stories estimated; epic size is unknown",
            epic_id,
            "estimate",
        )

    return build_result(
        findings,
        _EVIDENCE,
        epic_id=parent.id,
        story_count=len(children),
        epic_outcomes=sorted(epic_outcomes),
        covered_outcomes=sorted(claimed),
        uncovered_outcomes=uncovered,
        orphan_stories=orphans,
        estimated_points=total_points if estimated else None,
    )
