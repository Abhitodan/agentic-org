"""Refinement health: is there enough ready work, and is the backlog ageing?

Contract:
- Runway is measured in sprints of ready work against the team's own average
  velocity. With no velocity history, runway is reported as unknown.
- The skill measures the funnel; it does not refine anything itself.
"""

from __future__ import annotations

from typing import Any

_EVIDENCE = "deterministic_refinement_funnel"

# Sprints of ready work the team should keep ahead of itself.
TARGET_RUNWAY_SPRINTS = 1.5
MIN_RUNWAY_SPRINTS = 1.0

# Days a backlog item may sit untouched before it is probably stale.
STALE_ITEM_DAYS = 90


def run(
    stories: Any = None,
    ready_ids: Any = None,
    historical_velocity: Any = None,
) -> dict[str, Any]:
    from agentic_org.agile import (
        FindingList,
        build_result,
        parse_stories,
        velocity_stats,
    )

    parsed = parse_stories(stories)
    findings = FindingList()
    if not parsed:
        findings.error("no_backlog", "no backlog items supplied")
        return build_result(findings, _EVIDENCE, item_count=0, runway_sprints=None)

    ready = {str(i).strip().upper() for i in (ready_ids or [])}
    ready_points = 0.0
    ready_count = 0
    unestimated = 0
    unready_count = 0
    stale: list[str] = []

    for story in parsed:
        subject = story.id or story.title or "<story>"
        is_ready = bool(story.id) and story.id.upper() in ready
        if not ready:
            # No explicit ready list: treat an estimate plus criteria as ready.
            is_ready = story.estimate is not None and bool(story.acceptance_criteria)
        if is_ready:
            ready_count += 1
            if story.estimate is None:
                unestimated += 1
                findings.warn(
                    "ready_without_estimate",
                    "counted as ready but carries no estimate; runway is understated",
                    subject,
                    "estimate",
                )
            else:
                ready_points += story.estimate
        else:
            unready_count += 1

        try:
            age = float(story.raw.get("age_days", 0) or 0)
        except (TypeError, ValueError):
            age = 0.0
        if age > STALE_ITEM_DAYS:
            stale.append(subject)

    if stale:
        findings.warn(
            "stale_backlog_items",
            f"{len(stale)} item(s) untouched for over {STALE_ITEM_DAYS} days; "
            "confirm they are still wanted or close them",
        )

    stats = velocity_stats([float(v) for v in (historical_velocity or []) if v is not None])
    mean_velocity = stats["mean"]
    runway: float | None = None
    if not mean_velocity:
        findings.warn(
            "runway_unknown",
            "no velocity history supplied; ready runway cannot be expressed in sprints",
        )
    else:
        runway = round(ready_points / mean_velocity, 2)
        if runway < MIN_RUNWAY_SPRINTS:
            findings.error(
                "insufficient_runway",
                f"{runway} sprint(s) of ready work, below the minimum "
                f"{MIN_RUNWAY_SPRINTS}; the next sprint cannot be filled",
            )
        elif runway < TARGET_RUNWAY_SPRINTS:
            findings.warn(
                "thin_runway",
                f"{runway} sprint(s) of ready work, below the target "
                f"{TARGET_RUNWAY_SPRINTS}",
            )

    if ready_count == 0:
        findings.error("nothing_ready", "no backlog item is ready for a sprint")

    return build_result(
        findings,
        _EVIDENCE,
        item_count=len(parsed),
        ready_count=ready_count,
        unready_count=unready_count,
        ready_points=ready_points,
        ready_without_estimate=unestimated,
        mean_velocity=mean_velocity,
        runway_sprints=runway,
        stale_items=stale,
    )
