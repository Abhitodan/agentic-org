"""Verify a story split: slices are shippable, sized, and cover the parent.

Contract:
- Coverage is checked by explicit AC traceability (`covers: [AC-1, ...]`),
  never by text similarity — an unclaimed parent criterion is a gap.
- A split that leaves any slice above the split threshold has not split.
"""

from __future__ import annotations

from typing import Any

_EVIDENCE = "deterministic_split_coverage"

MIN_SLICES = 2


def _claimed_criteria(slice_story: Any) -> list[str]:
    raw = slice_story.raw.get("covers") or slice_story.raw.get("covers_ac") or []
    if isinstance(raw, str):
        raw = [raw]
    return [str(item).strip().upper() for item in raw if str(item).strip()]


def run(
    parent: Any = None,
    slices: Any = None,
) -> dict[str, Any]:
    from agentic_org.agile import (
        SPLIT_THRESHOLD,
        FindingList,
        build_result,
        parse_stories,
    )

    parent_stories = parse_stories(parent)
    slice_stories = parse_stories(slices)
    findings = FindingList()

    if not parent_stories:
        findings.error("no_parent", "parent story required to check a split")
        return build_result(findings, _EVIDENCE, slice_count=len(slice_stories))
    parent_story = parent_stories[0]
    parent_id = parent_story.id or "<parent>"

    if len(slice_stories) < MIN_SLICES:
        findings.error(
            "not_split",
            f"{len(slice_stories)} slice(s); a split needs at least {MIN_SLICES}",
            parent_id,
        )

    parent_ac = {c.id.upper() for c in parent_story.acceptance_criteria}
    if not parent_ac:
        findings.warn(
            "parent_without_criteria",
            "parent has no acceptance criteria; coverage cannot be verified",
            parent_id,
            "acceptance_criteria",
        )

    covered: set[str] = set()
    total_points = 0.0
    for slice_story in slice_stories:
        subject = slice_story.id or slice_story.title or "<slice>"

        if not slice_story.acceptance_criteria:
            findings.error(
                "slice_without_criteria",
                "each slice needs its own acceptance criteria to be shippable",
                subject,
                "acceptance_criteria",
            )
        if slice_story.estimate is not None:
            total_points += slice_story.estimate
            if slice_story.estimate > SPLIT_THRESHOLD:
                findings.error(
                    "slice_still_too_large",
                    f"estimate {slice_story.estimate} exceeds {SPLIT_THRESHOLD}; "
                    "split further",
                    subject,
                    "estimate",
                )

        claims = _claimed_criteria(slice_story)
        unknown = [c for c in claims if parent_ac and c not in parent_ac]
        if unknown:
            findings.error(
                "covers_unknown_criteria",
                f"claims parent criteria that do not exist: {', '.join(unknown)}",
                subject,
                "covers",
            )
        covered.update(c for c in claims if c in parent_ac)

        if parent_ac and not claims:
            findings.warn(
                "no_traceability",
                "slice does not declare which parent criteria it covers",
                subject,
                "covers",
            )

        declared_parent = slice_story.parent.upper()
        if declared_parent and parent_story.id and declared_parent != parent_story.id.upper():
            findings.error(
                "wrong_parent",
                f"slice declares parent {slice_story.parent!r}, expected {parent_story.id!r}",
                subject,
                "parent",
            )

    uncovered = sorted(parent_ac - covered)
    if uncovered:
        findings.error(
            "uncovered_criteria",
            f"parent criteria not covered by any slice: {', '.join(uncovered)}",
            parent_id,
            "acceptance_criteria",
        )

    if parent_story.estimate and total_points and total_points > parent_story.estimate * 2:
        findings.warn(
            "split_inflation",
            f"slices total {total_points} against a parent estimate of "
            f"{parent_story.estimate}; re-check scope",
            parent_id,
            "estimate",
        )

    return build_result(
        findings,
        _EVIDENCE,
        parent_id=parent_story.id,
        slice_count=len(slice_stories),
        parent_criteria=sorted(parent_ac),
        covered_criteria=sorted(covered),
        uncovered_criteria=uncovered,
        slice_points_total=total_points or None,
    )
