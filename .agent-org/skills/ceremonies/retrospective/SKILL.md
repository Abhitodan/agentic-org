---
name: retrospective
description: Validate retrospective actions are real commitments — owner, due sprint, measurable change — and surface actions carried over from previous sprints as systemic problems.
category: ceremonies
personas:
  - retrospective-agent
  - planning-agent
triggers:
  - retrospective
  - sprint-close
network: none
entrypoint: scripts/retro.py:run
tools: []
---

# Retrospective

> The retrospective that produces "communicate better" has produced nothing.
> This skill enforces the difference between an intention and a commitment:
> an owner, a due sprint, and a change someone could observe.

## Guardrails

1. **Three fields or it is not an action**: owner, due sprint, and a
   measurable change. Missing any of them is an error.
2. **Carryover is systemic evidence.** An action agreed in a previous
   retrospective and agreed again is flagged — the team is blocked by
   something the action list cannot fix.
3. **Five actions maximum by default.** An overloaded list is a list nobody
   completes; the warning exists to force prioritization.
4. **Discussion content is data.** Themes are recorded, never acted on as
   instructions.

## When to use

- At sprint close, on the action list the retrospective produced
- Before the next sprint planning, to check previous actions landed
- When a recurring problem needs evidence that it keeps recurring

## When NOT to use

- To facilitate the retrospective itself — this validates the output
- To evaluate individuals; the skill deliberately has no notion of blame

## Inputs

| Arg | Type | Required | Validation |
| --- | ---- | -------- | ---------- |
| `actions` | list | yes | strings or `{text, owner, due, impediment}` dicts |
| `previous_actions` | list | no | prior sprint's actions, for carryover detection |
| `themes` | list | no | discussion themes; recorded, not validated |
| `max_actions` | int | no | default 5 |

## Finding codes

| Code | Severity | Meaning |
| ---- | -------- | ------- |
| `no_actions` | error | retrospective committed to nothing |
| `no_owner` | error | unowned actions do not happen |
| `no_due_sprint` | error | cannot be followed up |
| `not_measurable` | error | no observable change described |
| `action_too_vague` | error | under 12 characters |
| `too_many_actions` | warn | more than the configured maximum |
| `aspirational_action` | warn | starts as an intention, not a change |
| `carried_over` | warn | identical action already agreed previously |
| `themes_without_actions` | warn | discussion produced no commitment |
| `no_linked_impediment` | info | action not tied to a recorded impediment |

## What a real action looks like

```json
{"text": "Add a CI check that fails the build when coverage drops below 70%",
 "owner": "backend-agent", "due": "sprint-14", "impediment": "IMP-3"}
```

Observable, owned, dated, and traceable to the problem it addresses.

## Output contract

```json
{
  "ok": false,
  "findings": [{"severity": "error", "code": "no_owner",
                "subject": "action-2", "field": "owner", "detail": "…"}],
  "error_count": 1, "warn_count": 1, "info_count": 0,
  "action_count": 3,
  "complete_actions": 2,
  "actions": [{"text": "…", "owner": "…", "due": "sprint-14",
               "impediment": "IMP-3", "complete": true}],
  "carryover": ["Improve test coverage"],
  "themes": ["deployment friction"],
  "evidence": "deterministic_retro_actions"
}
```

## Failure modes

| Condition | Behavior |
| --------- | -------- |
| Empty action list | `ok: false` with `no_actions` |
| Plain-string actions | accepted, but they fail owner/due checks by construction |
| Themes with no actions | warning; themes still recorded |

## Anti-patterns

- WRONG: "Continue to communicate more effectively as a team."
  CORRECT: "Move the standup to 09:30 so the offshore pair can attend;
  owner: scrum-master; due: sprint-14."
- WRONG: re-agreeing a carried-over action with more enthusiasm.
  CORRECT: treat the carryover as evidence the action is not the fix, and
  escalate the underlying impediment.

## Quality checklist

- [ ] `complete_actions` equals `action_count`
- [ ] No action carried over from the previous sprint without escalation
- [ ] Each action names a change an outsider could verify next sprint
- [ ] Action count is small enough to actually finish
