"""Retrospective validator: are the actions real commitments or good intentions?

Contract:
- An action item needs an owner, a due sprint, and a measurable outcome.
  Anything less is a wish that will reappear next retrospective.
- Carryover is counted, not excused: an action repeated across sprints is
  surfaced as a systemic finding.
"""

from __future__ import annotations

import re
from typing import Any

_EVIDENCE = "deterministic_retro_actions"

MIN_ACTION_CHARS = 12
MAX_ACTIONS = 5  # More than this and none of them get done.

_MEASURABLE = re.compile(
    r"\d|\b(?:reduce|increase|eliminate|automate|add|remove|document|"
    r"enable|enforce|split|delete|migrate|cap|limit)\b",
    re.IGNORECASE,
)

_VAGUE_ACTION = re.compile(
    r"^\s*(?:be|try|continue|keep|remember|focus|think|consider|discuss|"
    r"communicate|collaborate)\b",
    re.IGNORECASE,
)


def run(
    actions: Any = None,
    previous_actions: Any = None,
    themes: Any = None,
    max_actions: int = MAX_ACTIONS,
) -> dict[str, Any]:
    from agentic_org.agile import FindingList, build_result

    findings = FindingList()
    items = list(actions or [])
    if not items:
        findings.error(
            "no_actions",
            "retrospective produced no action items; either record the "
            "decision to change nothing, or capture what will change",
        )

    if len(items) > max_actions:
        findings.warn(
            "too_many_actions",
            f"{len(items)} actions exceeds {max_actions}; "
            "an overloaded action list is a list nobody completes",
        )

    previous = {
        str(a.get("text") if isinstance(a, dict) else a).strip().lower()
        for a in (previous_actions or [])
    }

    accepted: list[dict[str, Any]] = []
    carryover: list[str] = []
    for index, raw in enumerate(items, 1):
        if isinstance(raw, dict):
            text = str(raw.get("text") or raw.get("action") or "").strip()
            owner = str(raw.get("owner") or "").strip()
            due = str(raw.get("due") or raw.get("due_sprint") or "").strip()
            impediment = str(raw.get("impediment") or raw.get("linked") or "").strip()
        else:
            text, owner, due, impediment = str(raw).strip(), "", "", ""
        subject = f"action-{index}"

        if len(text) < MIN_ACTION_CHARS:
            findings.error(
                "action_too_vague",
                f"under {MIN_ACTION_CHARS} characters; state what changes",
                subject,
                "text",
            )
        if not owner:
            findings.error(
                "no_owner",
                "action has no owner; unowned actions do not happen",
                subject,
                "owner",
            )
        if not due:
            findings.error(
                "no_due_sprint",
                "action has no due sprint; it cannot be followed up",
                subject,
                "due",
            )
        if text and not _MEASURABLE.search(text):
            findings.error(
                "not_measurable",
                "no observable change described; name what will be different",
                subject,
                "text",
            )
        if text and _VAGUE_ACTION.match(text):
            findings.warn(
                "aspirational_action",
                "starts as an intention ('be better', 'try to…') rather than a change",
                subject,
                "text",
            )
        if text and text.lower() in previous:
            carryover.append(text)
            findings.warn(
                "carried_over",
                "identical action was already agreed in a previous retrospective; "
                "the blocker is systemic",
                subject,
                "text",
            )
        if not impediment:
            findings.info(
                "no_linked_impediment",
                "action is not linked to a recorded impediment",
                subject,
                "impediment",
            )
        accepted.append({
            "text": text,
            "owner": owner,
            "due": due,
            "impediment": impediment,
            "complete": bool(text and owner and due),
        })

    theme_list = [str(t).strip() for t in (themes or []) if str(t).strip()]
    if theme_list and not items:
        findings.warn(
            "themes_without_actions",
            f"{len(theme_list)} theme(s) discussed but nothing was committed",
        )

    return build_result(
        findings,
        _EVIDENCE,
        action_count=len(items),
        complete_actions=sum(1 for a in accepted if a["complete"]),
        actions=accepted,
        carryover=carryover,
        themes=theme_list,
    )
