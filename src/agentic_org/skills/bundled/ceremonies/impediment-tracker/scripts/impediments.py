"""Impediment ledger: ownership, ageing, and escalation thresholds.

Contract:
- Escalation is a function of age and severity, evaluated the same way every
  day. It does not depend on who remembers to raise the issue.
- An impediment with no owner is the most common reason one never clears,
  so it is an error rather than a note.
"""

from __future__ import annotations

from typing import Any

_EVIDENCE = "deterministic_impediment_ageing"

SEVERITIES = ("blocker", "high", "medium", "low")

# Days an impediment may age at each severity before it must be escalated.
ESCALATION_DAYS = {"blocker": 1, "high": 3, "medium": 5, "low": 10}

# Age beyond which any impediment is stale regardless of severity.
STALE_DAYS = 15


def run(
    impediments: Any = None,
    escalation_days: Any = None,
) -> dict[str, Any]:
    from agentic_org.agile import FindingList, build_result

    findings = FindingList()
    thresholds = dict(ESCALATION_DAYS)
    for severity, days in (escalation_days or {}).items():
        key = str(severity).strip().lower()
        if key not in ESCALATION_DAYS:
            raise ValueError(
                f"unknown severity {severity!r}; expected one of {', '.join(SEVERITIES)}"
            )
        thresholds[key] = int(days)

    items = list(impediments or [])
    if not items:
        return build_result(
            findings, _EVIDENCE, impediment_count=0, escalate=[], open_count=0,
            thresholds=thresholds,
        )

    escalate: list[dict[str, Any]] = []
    open_count = 0
    report: list[dict[str, Any]] = []
    for index, raw in enumerate(items, 1):
        if not isinstance(raw, dict):
            findings.error(
                "malformed_impediment",
                "each impediment must be a dict with id, severity, age_days, owner",
                f"impediment-{index}",
            )
            continue
        subject = str(raw.get("id") or f"impediment-{index}")
        status = str(raw.get("status") or "open").strip().lower()
        severity = str(raw.get("severity") or "").strip().lower()
        owner = str(raw.get("owner") or "").strip()

        if severity not in SEVERITIES:
            findings.error(
                "invalid_severity",
                f"{severity or '<empty>'!r} is not one of {', '.join(SEVERITIES)}",
                subject,
                "severity",
            )
            severity = ""

        try:
            age = float(raw.get("age_days", 0) or 0)
        except (TypeError, ValueError):
            findings.error(
                "invalid_age", "age_days must be numeric", subject, "age_days"
            )
            age = 0.0

        if status != "open":
            report.append({"id": subject, "status": status, "escalate": False})
            continue
        open_count += 1

        if not owner:
            findings.error(
                "no_owner",
                "open impediment has no owner; it will not clear itself",
                subject,
                "owner",
            )

        limit = thresholds.get(severity)
        needs_escalation = bool(severity) and age > limit
        if needs_escalation:
            escalate.append({"id": subject, "severity": severity, "age_days": age})
            findings.error(
                "escalation_due",
                f"{severity} impediment open {age:g} day(s), past the "
                f"{limit}-day threshold",
                subject,
                "age_days",
            )
        if age > STALE_DAYS:
            findings.warn(
                "stale_impediment",
                f"open {age:g} day(s); re-assess whether this is still real",
                subject,
                "age_days",
            )
        report.append({
            "id": subject,
            "status": status,
            "severity": severity,
            "age_days": age,
            "owner": owner,
            "escalate": needs_escalation,
        })

    if open_count and not any(r.get("severity") == "blocker" for r in report):
        findings.info(
            "no_blockers",
            f"{open_count} open impediment(s), none at blocker severity",
        )

    return build_result(
        findings,
        _EVIDENCE,
        impediment_count=len(items),
        open_count=open_count,
        escalate=escalate,
        thresholds=thresholds,
        report=report,
    )
