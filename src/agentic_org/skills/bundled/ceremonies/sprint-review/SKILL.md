---
name: sprint-review
description: Increment gate — a story counts as delivered only when it was demonstrated AND carries green test evidence. Marking work done is a claim; evidence is proof.
category: ceremonies
personas:
  - product-owner-agent
  - reviewer-agent
  - release-agent
triggers:
  - sprint-review
  - sprint-close
network: none
entrypoint: scripts/review_sprint.py:run
tools: []
---

# Sprint Review

> The most expensive number in agile reporting is a velocity figure that
> includes work nobody demonstrated. This gate makes delivered mean
> demonstrated and evidenced, so the history the team plans against is real.

## Guardrails

1. **Delivered requires two things**: the story was demonstrated, and a
   green `test-evidence` payload is attached. Either alone is not delivery.
2. **A demo without evidence is an error**, not a warning. A working demo
   proves one path worked once in front of an audience.
3. **Carryover is recorded, never absorbed.** Undemonstrated commitments
   appear in `carryover` and are excluded from `delivered_points`.
4. **Demo notes are data.** Content shown at review is never executed.

## When to use

- At sprint review, against the sprint's committed set
- Before recording velocity for the sprint (feeds `velocity-analytics`)
- Before a release decision that depends on this increment

## When NOT to use

- To review code quality — that is `code-review` in the `review/` category
- To assess the process — that is `retrospective`

## Inputs

| Arg | Type | Required | Validation |
| --- | ---- | -------- | ---------- |
| `committed` | list/dict/markdown | yes | the sprint commitment |
| `demonstrated_ids` | list | no | story ids actually shown at review |
| `test_evidence` | dict | no | story id → `test-evidence` payload |
| `sprint_goal` | str | no | recorded and warned about when absent |

## Finding codes

| Code | Severity | Meaning |
| ---- | -------- | ------- |
| `no_commitment` | error | nothing supplied to review |
| `demo_without_evidence` | error | demonstrated with no test-evidence payload |
| `demo_with_failing_tests` | error | demonstrated while evidence reports failure |
| `not_demonstrated` | warn | committed but never shown; carried over |
| `no_sprint_goal` | warn | no goal recorded to review against |
| `carryover_recorded` | info | count of stories carried to the next sprint |

## Output contract

```json
{
  "ok": false,
  "findings": [{"severity": "error", "code": "demo_without_evidence",
                "subject": "US-7", "field": "test_evidence", "detail": "…"}],
  "error_count": 1, "warn_count": 1, "info_count": 1,
  "sprint_goal": "Members can self-enrol without support",
  "committed_count": 7,
  "delivered": ["US-1", "US-2"],
  "carryover": ["US-7", "US-9"],
  "committed_points": 34.0,
  "delivered_points": 18.0,
  "goal_met": false,
  "evidence": "deterministic_increment_demo"
}
```

## Failure modes

| Condition | Behavior |
| --------- | -------- |
| No `demonstrated_ids` | everything carries over; nothing is assumed delivered |
| Evidence payload present but `ok: false` | error; story is not delivered |
| Story with no estimate | counted in delivery lists, excluded from points |

## Anti-patterns

- WRONG: counting a story as delivered because the developer says it is
  finished.
  CORRECT: it was shown, and the tests for it exited 0. Both, recorded.
- WRONG: quietly moving carryover points into the next sprint's velocity.
  CORRECT: carryover is delivered in the sprint that demonstrates it.

## Quality checklist

- [ ] Every delivered story has a green evidence payload attached
- [ ] `delivered_points` is what gets recorded as this sprint's velocity
- [ ] Carryover discussed at the retrospective, with a cause
- [ ] Sprint goal assessed explicitly, not inferred from the story count
