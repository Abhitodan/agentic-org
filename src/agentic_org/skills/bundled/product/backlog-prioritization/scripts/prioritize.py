"""Rank a backlog by WSJF or validate a MoSCoW allocation. Pure arithmetic.

Contract:
- WSJF ranking is computed, not opined: cost of delay over job size, with a
  documented deterministic tie-break so the same backlog always ranks the same.
- Missing inputs produce findings, never imputed defaults — a story with no
  job size is unranked, not guessed at.
"""

from __future__ import annotations

from typing import Any

_EVIDENCE = "deterministic_backlog_ranking"

MOSCOW_LEVELS = ("must", "should", "could", "wont")

# Beyond this share of Must-have items, the release has no flex left.
_MUST_SHARE_LIMIT = 0.6

_WSJF_FIELDS = ("business_value", "time_criticality", "risk_reduction", "job_size")


def _score_fields(raw: dict[str, Any]) -> dict[str, float] | None:
    values: dict[str, float] = {}
    for field_name in _WSJF_FIELDS:
        value = raw.get(field_name)
        if value is None:
            return None
        try:
            values[field_name] = float(value)
        except (TypeError, ValueError):
            return None
    return values


def _rank_wsjf(stories: list[Any], findings: Any) -> list[dict[str, Any]]:
    from agentic_org.agile import wsjf

    scored: list[dict[str, Any]] = []
    for story in stories:
        subject = story.id or story.title or "<story>"
        values = _score_fields(story.raw)
        if values is None:
            findings.warn(
                "unrankable",
                f"needs numeric {', '.join(_WSJF_FIELDS)} to compute WSJF",
                subject,
                "wsjf",
            )
            continue
        if values["job_size"] <= 0:
            findings.error(
                "invalid_job_size",
                f"job_size must be positive, got {values['job_size']}",
                subject,
                "job_size",
            )
            continue
        scored.append({
            "id": story.id,
            "wsjf": wsjf(
                values["business_value"],
                values["time_criticality"],
                values["risk_reduction"],
                values["job_size"],
            ),
            "job_size": values["job_size"],
        })
    # Highest WSJF first; ties broken by smaller job size, then id — stable.
    scored.sort(key=lambda row: (-row["wsjf"], row["job_size"], row["id"]))
    for position, row in enumerate(scored, 1):
        row["rank"] = position
    return scored


def _check_moscow(stories: list[Any], findings: Any) -> dict[str, int]:
    tally = {level: 0 for level in MOSCOW_LEVELS}
    classified = 0
    for story in stories:
        subject = story.id or story.title or "<story>"
        raw_level = str(story.raw.get("moscow") or "").strip().lower().replace("'", "")
        raw_level = raw_level.replace("must have", "must").replace("won t", "wont")
        if not raw_level:
            findings.warn("unclassified", "no MoSCoW classification", subject, "moscow")
            continue
        level = next((lvl for lvl in MOSCOW_LEVELS if raw_level.startswith(lvl)), None)
        if level is None:
            findings.error(
                "invalid_moscow",
                f"{raw_level!r} is not one of {', '.join(MOSCOW_LEVELS)}",
                subject,
                "moscow",
            )
            continue
        tally[level] += 1
        classified += 1

    if classified and tally["must"] / classified > _MUST_SHARE_LIMIT:
        findings.warn(
            "must_have_inflation",
            f"{tally['must']}/{classified} items are Must — "
            "a plan with no optional scope has no room to absorb surprise",
        )
    return tally


def run(
    stories: Any = None,
    method: str = "wsjf",
) -> dict[str, Any]:
    from agentic_org.agile import FindingList, build_result, parse_stories

    normalized = str(method or "wsjf").strip().lower()
    if normalized not in {"wsjf", "moscow"}:
        raise ValueError(f"method must be 'wsjf' or 'moscow', got {method!r}")

    parsed = parse_stories(stories)
    findings = FindingList()
    if not parsed:
        findings.error("no_stories", "no backlog items supplied")
        return build_result(findings, _EVIDENCE, method=normalized, ranking=[])

    if normalized == "wsjf":
        ranking = _rank_wsjf(parsed, findings)
        if not ranking:
            findings.error(
                "nothing_ranked",
                "no item carried the numeric inputs WSJF requires",
            )
        return build_result(
            findings,
            _EVIDENCE,
            method="wsjf",
            ranking=ranking,
            ranked_count=len(ranking),
            item_count=len(parsed),
        )

    tally = _check_moscow(parsed, findings)
    return build_result(
        findings,
        _EVIDENCE,
        method="moscow",
        tally=tally,
        item_count=len(parsed),
        ranking=[],
    )
