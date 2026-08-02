"""Sprint planning gate: goal, readiness, and capacity versus commitment.

Contract:
- Capacity is derived from the team's own history; with no history the skill
  reports capacity as unknown rather than inventing a number.
- Committing unready stories is an error, not a warning: readiness was
  already decided by the Definition of Ready gate.
"""

from __future__ import annotations

from typing import Any

_EVIDENCE = "deterministic_sprint_commitment"

# Committing above this share of computed capacity leaves no slack for the
# defects and interruptions every sprint actually contains.
OVERCOMMIT_RATIO = 1.0
UNDERCOMMIT_RATIO = 0.6

MIN_GOAL_CHARS = 15


def run(
    sprint_goal: str = "",
    stories: Any = None,
    member_days: float = 0.0,
    focus_factor: float | None = None,
    historical_velocity: Any = None,
    sprint_length_days: float | None = None,
    ready_ids: Any = None,
) -> dict[str, Any]:
    from agentic_org.agile import (
        DEFAULT_FOCUS_FACTOR,
        FindingList,
        build_result,
        compute_capacity,
        parse_stories,
        velocity_stats,
    )

    parsed = parse_stories(stories)
    findings = FindingList()

    goal = str(sprint_goal or "").strip()
    if not goal:
        findings.error("no_sprint_goal", "sprint has no goal; commitment is unfocused")
    elif len(goal) < MIN_GOAL_CHARS:
        findings.warn(
            "thin_sprint_goal",
            f"goal under {MIN_GOAL_CHARS} characters; state the outcome, not a label",
        )

    if not parsed:
        findings.error("no_stories", "no stories proposed for the sprint")

    ready = {str(i).strip().upper() for i in (ready_ids or [])}
    committed_points = 0.0
    unestimated: list[str] = []
    not_ready: list[str] = []
    for story in parsed:
        subject = story.id or story.title or "<story>"
        if story.estimate is None:
            unestimated.append(subject)
            findings.error(
                "unestimated_in_sprint",
                "story has no estimate; it cannot be committed",
                subject,
                "estimate",
            )
        else:
            committed_points += story.estimate
        if ready and story.id and story.id.upper() not in ready:
            not_ready.append(subject)
            findings.error(
                "unready_in_sprint",
                "story is not in the ready set; run the readiness gate first",
                subject,
                "status",
            )

    history = [float(v) for v in (historical_velocity or []) if v is not None]
    stats = velocity_stats(history)
    capacity = compute_capacity(
        member_days=float(member_days or 0.0),
        focus_factor=(
            DEFAULT_FOCUS_FACTOR if focus_factor is None else float(focus_factor)
        ),
        historical_velocity=history,
        sprint_length_days=sprint_length_days,
    )

    capacity_points = capacity.capacity_points
    utilization: float | None = None
    if capacity_points is None:
        findings.warn(
            "capacity_unknown",
            "no velocity history and sprint length supplied; "
            "point capacity cannot be computed and commitment is unchecked",
        )
    elif capacity_points <= 0:
        findings.error(
            "no_capacity",
            f"computed capacity is {capacity_points}; the team cannot commit",
        )
    else:
        utilization = round(committed_points / capacity_points, 3)
        if utilization > OVERCOMMIT_RATIO:
            findings.error(
                "overcommitted",
                f"committed {committed_points} points against a capacity of "
                f"{round(capacity_points, 1)} ({utilization:.0%})",
            )
        elif utilization < UNDERCOMMIT_RATIO:
            findings.warn(
                "undercommitted",
                f"committed only {utilization:.0%} of capacity; "
                "confirm this is deliberate",
            )

    if history and committed_points and stats["max"] and committed_points > stats["max"]:
        findings.warn(
            "above_best_sprint",
            f"commitment of {committed_points} exceeds the team's best recorded "
            f"sprint ({stats['max']})",
        )

    return build_result(
        findings,
        _EVIDENCE,
        sprint_goal=goal,
        story_count=len(parsed),
        committed_points=committed_points,
        capacity=capacity.to_dict(),
        utilization=utilization,
        velocity=stats,
        unestimated=unestimated,
        not_ready=not_ready,
    )
