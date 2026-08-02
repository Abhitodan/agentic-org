"""Validate ceremony order and required artifacts in a sprint cadence log."""

from __future__ import annotations

from typing import Any

_EVIDENCE = "deterministic_ceremony_sequence"

# Legal predecessor sets (empty means may open the sprint).
ORDER: dict[str, frozenset[str]] = {
    "backlog-refinement": frozenset(),
    "sprint-planning": frozenset({"backlog-refinement"}),
    "standup": frozenset({"sprint-planning"}),
    "sprint-review": frozenset({"sprint-planning"}),
    "retrospective": frozenset({"sprint-review"}),
}

REQUIRED_ARTIFACTS: dict[str, tuple[str, ...]] = {
    "backlog-refinement": ("ready_ids",),
    "sprint-planning": ("sprint_goal", "commitment"),
    "standup": ("updates",),
    "sprint-review": ("demonstrated_ids",),
    "retrospective": ("actions",),
}


def run(ceremony_log: Any = None) -> dict[str, Any]:
    from agentic_org.agile import FindingList, build_result

    findings = FindingList()
    events = list(ceremony_log or [])
    if not events:
        findings.error("empty_log", "no ceremony events supplied")
        return build_result(findings, _EVIDENCE, sequence=[])

    seen: set[str] = set()
    sequence: list[str] = []
    for index, raw in enumerate(events, 1):
        if not isinstance(raw, dict):
            findings.error(
                "malformed_event",
                "ceremony event must be a dict with name + artifacts",
                f"event-{index}",
            )
            continue
        name = str(raw.get("name") or raw.get("ceremony") or "").strip().lower()
        subject = name or f"event-{index}"
        if name not in ORDER:
            findings.error(
                "unknown_ceremony",
                f"{name!r} is not a known ceremony",
                subject,
            )
            continue
        preds = ORDER[name]
        if preds and not preds.issubset(seen):
            missing_pred = sorted(preds - seen)
            findings.error(
                "illegal_order",
                f"{name} before required predecessor(s): {', '.join(missing_pred)}",
                subject,
            )
        arts = raw.get("artifacts") if isinstance(raw.get("artifacts"), dict) else {}
        for key in REQUIRED_ARTIFACTS.get(name, ()):
            if key not in arts or arts.get(key) in (None, "", [], {}):
                findings.error(
                    "missing_ceremony_artifact",
                    f"{name} missing required artifact {key!r}",
                    subject,
                    key,
                )
        seen.add(name)
        sequence.append(name)

    return build_result(
        findings,
        _EVIDENCE,
        sequence=sequence,
        ceremony_count=len(sequence),
    )
