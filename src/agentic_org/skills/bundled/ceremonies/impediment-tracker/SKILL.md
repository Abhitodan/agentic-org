---
name: impediment-tracker
description: Impediment ledger with mechanical escalation — ownership, ageing, and severity thresholds evaluated identically every day, independent of who remembers to raise it.
category: ceremonies
personas:
  - planning-agent
  - retrospective-agent
  - cost-governor-agent
triggers:
  - impediment-tracker
  - daily-standup
  - retrospective
network: none
entrypoint: scripts/impediments.py:run
tools: []
---

# Impediment Tracker

> Impediments do not fail to clear because nobody cares. They fail because
> escalation depends on somebody choosing to escalate. This skill makes
> escalation a function of severity and age instead.

## Guardrails

1. **Escalation is mechanical**: severity plus age against a fixed
   threshold. It does not depend on persistence or seniority.
2. **An open impediment without an owner is an error.** Unowned impediments
   do not clear themselves.
3. **Closed items are counted, never re-escalated.** Only `status: open`
   entries age.
4. **Thresholds are explicit and overridable**, but an unknown severity name
   raises rather than silently defaulting.

## When to use

- Daily, after `standup-synthesis` identifies blockers worth recording
- At the retrospective, to show what aged and why
- Whenever the orchestrator needs the current escalation set

## When NOT to use

- To capture blockers in the moment — that is `standup-synthesis`
- To track story progress; impediments are obstacles, not work items

## Inputs

| Arg | Type | Required | Validation |
| --- | ---- | -------- | ---------- |
| `impediments` | list | yes | dicts of `{id, severity, age_days, owner, status}` |
| `escalation_days` | dict | no | per-severity overrides; unknown key raises |

## Default escalation thresholds

| Severity | Escalate after |
| -------- | -------------- |
| blocker | 1 day |
| high | 3 days |
| medium | 5 days |
| low | 10 days |

Any impediment open beyond 15 days is additionally flagged as stale.

## Finding codes

| Code | Severity | Meaning |
| ---- | -------- | ------- |
| `escalation_due` | error | past its severity threshold |
| `no_owner` | error | open impediment with nobody accountable |
| `invalid_severity` | error | outside blocker/high/medium/low |
| `invalid_age` | error | `age_days` is not numeric |
| `malformed_impediment` | error | entry is not a dict |
| `stale_impediment` | warn | open beyond 15 days |
| `no_blockers` | info | open items exist, none at blocker severity |

## Output contract

```json
{
  "ok": false,
  "findings": [{"severity": "error", "code": "escalation_due",
                "subject": "IMP-3", "field": "age_days", "detail": "…"}],
  "error_count": 1, "warn_count": 0, "info_count": 1,
  "impediment_count": 5,
  "open_count": 3,
  "escalate": [{"id": "IMP-3", "severity": "high", "age_days": 6.0}],
  "thresholds": {"blocker": 1, "high": 3, "medium": 5, "low": 10},
  "report": [{"id": "IMP-3", "status": "open", "severity": "high",
              "age_days": 6.0, "owner": "planning-agent", "escalate": true}],
  "evidence": "deterministic_impediment_ageing"
}
```

## Failure modes

| Condition | Behavior |
| --------- | -------- |
| Empty list | `ok: true`, zero counts — an empty ledger is a valid state |
| Unknown severity in overrides | raises ValueError → `skill.failed` |
| Non-dict entry | error finding; other entries still processed |

## Anti-patterns

- WRONG: raising the threshold because an impediment keeps escalating.
  CORRECT: escalation is the signal working; the fix is upstream.
- WRONG: closing an impediment because the sprint ended.
  CORRECT: it either cleared or it carries; closing by calendar hides the
  pattern the retrospective needs.

## Quality checklist

- [ ] Every open impediment has an owner who can actually remove it
- [ ] The `escalate` list is acted on the day it appears
- [ ] Stale items re-assessed rather than left ageing
- [ ] Recurring impediments linked to retrospective actions
