"""Validate user-story structure: narrative, acceptance criteria, sizing.

Contract:
- Checks structure, never content quality judgment — it cannot know whether a
  story is valuable, only whether it is well formed enough to be worked.
- Errors block refinement; warnings inform the Product Owner.
"""

from __future__ import annotations

from typing import Any

_EVIDENCE = "deterministic_story_structure"

MIN_TITLE_CHARS = 8
MIN_AC_COUNT = 1
MAX_AC_COUNT = 12


def run(
    stories: Any = None,
    require_estimate: bool = False,
    max_acceptance_criteria: int = MAX_AC_COUNT,
) -> dict[str, Any]:
    from agentic_org.agile import (
        SPLIT_THRESHOLD,
        FindingList,
        build_result,
        is_valid_estimate,
        parse_stories,
    )

    parsed = parse_stories(stories)
    findings = FindingList()
    if not parsed:
        findings.error("no_stories", "no stories supplied to validate")
        return build_result(findings, _EVIDENCE, story_count=0, stories=[])

    seen_ids: set[str] = set()
    for story in parsed:
        subject = story.id or story.title or "<unidentified>"

        if not story.id:
            findings.error("missing_id", "story has no id", subject, "id")
        elif story.id in seen_ids:
            findings.error(
                "duplicate_id", f"story id {story.id!r} used more than once", subject, "id"
            )
        seen_ids.add(story.id)

        if len(story.title) < MIN_TITLE_CHARS:
            findings.warn(
                "thin_title",
                f"title under {MIN_TITLE_CHARS} characters",
                subject,
                "title",
            )

        if not story.has_narrative():
            missing = [
                name for name, value in
                (("as_a", story.as_a), ("i_want", story.i_want), ("so_that", story.so_that))
                if not value
            ]
            findings.error(
                "incomplete_narrative",
                f"missing narrative part(s): {', '.join(missing)}",
                subject,
                "narrative",
            )

        leaked = story.solution_terms()
        if leaked:
            findings.warn(
                "solution_in_narrative",
                f"narrative names implementation detail: {', '.join(leaked)}",
                subject,
                "narrative",
            )

        criteria = story.acceptance_criteria
        if len(criteria) < MIN_AC_COUNT:
            findings.error(
                "no_acceptance_criteria",
                "story has no acceptance criteria",
                subject,
                "acceptance_criteria",
            )
        elif len(criteria) > max_acceptance_criteria:
            findings.warn(
                "too_many_criteria",
                f"{len(criteria)} criteria exceeds {max_acceptance_criteria}; "
                "story is probably an epic",
                subject,
                "acceptance_criteria",
            )

        if require_estimate and story.estimate is None:
            findings.error(
                "missing_estimate", "estimate required but absent", subject, "estimate"
            )
        elif story.estimate is not None:
            if not is_valid_estimate(story.estimate):
                findings.warn(
                    "off_scale_estimate",
                    f"estimate {story.estimate} is not on the Fibonacci scale",
                    subject,
                    "estimate",
                )
            if story.estimate > SPLIT_THRESHOLD:
                findings.error(
                    "too_large_to_commit",
                    f"estimate {story.estimate} exceeds split threshold "
                    f"{SPLIT_THRESHOLD}; split before committing",
                    subject,
                    "estimate",
                )

        if story.open_questions:
            findings.warn(
                "open_questions",
                f"{len(story.open_questions)} unresolved question(s)",
                subject,
                "open_questions",
            )

    return build_result(
        findings,
        _EVIDENCE,
        story_count=len(parsed),
        stories=[
            {
                "id": s.id,
                "has_narrative": s.has_narrative(),
                "criteria": len(s.acceptance_criteria),
                "estimate": s.estimate,
            }
            for s in parsed
        ],
    )
