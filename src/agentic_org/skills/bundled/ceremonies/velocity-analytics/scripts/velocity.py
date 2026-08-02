"""Velocity statistics and an empirical forecast range from completed sprints.

Contract:
- The forecast is the observed min/max of recent sprints, not a model. Fewer
  than three completed sprints yields no forecast at all.
- Volatility and trend are reported as facts; what to do about them is a
  retrospective conversation, not an output of this skill.
"""

from __future__ import annotations

from typing import Any

_EVIDENCE = "deterministic_velocity_statistics"

# Coefficient of variation above which the average stops being predictive.
VOLATILITY_LIMIT = 0.35


def _completed_points(sprints: Any) -> tuple[list[float], list[str], list[str]]:
    """Return (velocities, labels, malformed entries) from mixed input."""
    values: list[float] = []
    labels: list[str] = []
    malformed: list[str] = []
    for index, entry in enumerate(sprints or [], 1):
        if isinstance(entry, dict):
            raw = entry.get("completed_points", entry.get("velocity"))
            label = str(entry.get("sprint") or entry.get("id") or f"sprint-{index}")
        else:
            raw, label = entry, f"sprint-{index}"
        try:
            values.append(float(raw))
            labels.append(label)
        except (TypeError, ValueError):
            malformed.append(label)
    return values, labels, malformed


def run(
    sprints: Any = None,
    planned_points: Any = None,
) -> dict[str, Any]:
    from agentic_org.agile import (
        MIN_SPRINTS_FOR_FORECAST,
        FindingList,
        build_result,
        velocity_stats,
    )

    values, labels, malformed = _completed_points(sprints)
    findings = FindingList()

    for label in malformed:
        findings.warn(
            "unreadable_sprint",
            "completed_points is not numeric; sprint excluded from statistics",
            label,
            "completed_points",
        )

    if not values:
        findings.error("no_history", "no completed sprints supplied")
        return build_result(findings, _EVIDENCE, velocity=velocity_stats([]))

    stats = velocity_stats(values)
    if len(values) < MIN_SPRINTS_FOR_FORECAST:
        findings.warn(
            "insufficient_history",
            f"{len(values)} sprint(s) recorded; a forecast needs "
            f"{MIN_SPRINTS_FOR_FORECAST}",
        )

    mean = stats["mean"] or 0.0
    stdev = stats["stdev"] or 0.0
    volatility = round(stdev / mean, 3) if mean else None
    if volatility is not None and volatility > VOLATILITY_LIMIT:
        findings.warn(
            "high_volatility",
            f"coefficient of variation {volatility} exceeds {VOLATILITY_LIMIT}; "
            "the average is not a reliable planning number",
        )
    if stats["trend"] == "falling":
        findings.warn(
            "falling_velocity",
            "recent sprints deliver less than earlier ones; "
            "take this to the retrospective with causes, not blame",
        )

    delivery_ratio: float | None = None
    planned = [float(p) for p in (planned_points or []) if p is not None]
    if planned:
        paired = min(len(planned), len(values))
        planned_total = sum(planned[-paired:])
        delivered_total = sum(values[-paired:])
        if planned_total > 0:
            delivery_ratio = round(delivered_total / planned_total, 3)
            if delivery_ratio < 0.8:
                findings.warn(
                    "chronic_overcommitment",
                    f"delivered {delivery_ratio:.0%} of committed points across "
                    f"the last {paired} sprints",
                )

    return build_result(
        findings,
        _EVIDENCE,
        velocity=stats,
        sprint_labels=labels,
        volatility=volatility,
        delivery_ratio=delivery_ratio,
    )
