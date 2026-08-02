"""Daily standup synthesis: who is blocked, what is silent, what is stalled.

Contract:
- The skill reports coordination facts (missing updates, unowned blockers,
  stories in progress too long). It never evaluates individual productivity.
- A blocker with no owner is an error: the point of the ceremony is that
  someone leaves with it.
"""

from __future__ import annotations

from typing import Any

_EVIDENCE = "deterministic_standup_signals"

# Days a story may sit in progress before it is worth a conversation.
STALLED_DAYS = 3

# Concurrent in-progress stories per person before focus is lost.
WIP_PER_PERSON = 2


def run(
    updates: Any = None,
    team: Any = None,
    stalled_days: int = STALLED_DAYS,
    wip_per_person: int = WIP_PER_PERSON,
) -> dict[str, Any]:
    from agentic_org.agile import FindingList, build_result

    findings = FindingList()
    entries = list(updates or [])
    roster = [str(m).strip() for m in (team or []) if str(m).strip()]

    if not entries:
        findings.error("no_updates", "no standup updates supplied")
        return build_result(
            findings, _EVIDENCE, reported=[], missing=roster, blockers=[],
        )

    reported: list[str] = []
    blockers: list[dict[str, str]] = []
    stalled: list[dict[str, Any]] = []
    wip_by_person: dict[str, int] = {}

    for index, raw in enumerate(entries, 1):
        if not isinstance(raw, dict):
            findings.error(
                "malformed_update",
                "each update must be a dict with member, yesterday, today, blockers",
                f"update-{index}",
            )
            continue
        member = str(raw.get("member") or raw.get("who") or "").strip()
        subject = member or f"update-{index}"
        if not member:
            findings.error("no_member", "update does not name a team member", subject)
        else:
            reported.append(member)

        today = str(raw.get("today") or "").strip()
        if not today:
            findings.warn(
                "no_plan_today",
                "update states no plan for today",
                subject,
                "today",
            )

        for blocker in raw.get("blockers") or []:
            if isinstance(blocker, dict):
                text = str(blocker.get("text") or blocker.get("detail") or "").strip()
                owner = str(blocker.get("owner") or "").strip()
            else:
                text, owner = str(blocker).strip(), ""
            if not text:
                continue
            blockers.append({"member": member, "text": text, "owner": owner})
            if not owner:
                findings.error(
                    "unowned_blocker",
                    f"blocker has no owner to resolve it: {text}",
                    subject,
                    "blockers",
                )

        in_progress = raw.get("in_progress") or []
        wip_by_person[member or subject] = len(in_progress)
        for story in in_progress:
            if not isinstance(story, dict):
                continue
            story_id = str(story.get("id") or "<story>")
            try:
                days = float(story.get("days_in_progress", 0) or 0)
            except (TypeError, ValueError):
                continue
            if days > stalled_days:
                stalled.append({"id": story_id, "member": member, "days": days})
                findings.warn(
                    "stalled_story",
                    f"{story_id} in progress {days:g} day(s), past {stalled_days}",
                    subject,
                    "in_progress",
                )

    for person, count in wip_by_person.items():
        if count > wip_per_person:
            findings.warn(
                "wip_exceeded",
                f"{count} stories in progress exceeds the limit of {wip_per_person}",
                person,
                "in_progress",
            )

    missing = [m for m in roster if m not in reported]
    for member in missing:
        findings.warn(
            "no_update", "team member did not report at standup", member,
        )

    return build_result(
        findings,
        _EVIDENCE,
        reported=reported,
        missing=missing,
        blockers=blockers,
        blocker_count=len(blockers),
        stalled=stalled,
        wip=wip_by_person,
    )
