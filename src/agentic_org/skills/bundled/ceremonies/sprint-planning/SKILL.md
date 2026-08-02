---
name: sprint-planning
description: Sprint commitment gate — goal present, every story ready and estimated, committed points within capacity derived from the team's own velocity history.
category: ceremonies
personas:
  - planning-agent
  - product-owner-agent
  - cost-governor-agent
triggers:
  - sprint-planning
  - node_plan
network: none
entrypoint: scripts/plan_sprint.py:run
tools: []
---

# Sprint Planning

> Overcommitment is not optimism, it is a decision made without arithmetic.
> This skill supplies the arithmetic so the team's discussion is about what
> to build, not about whether it fits.

## Guardrails

1. **Capacity comes from history.** Points per day is derived from the
   team's own past velocity and sprint length. Without both, capacity is
   reported as unknown and the commitment goes unchecked — never guessed.
2. **Unready work cannot be committed.** Readiness was already decided by
   `definition-of-ready-gate`; committing outside that set is an error.
3. **Unestimated work cannot be committed.** There is nothing to fit.
4. **Undercommitment is surfaced too.** Consistently filling 50% of capacity
   is a planning problem in the other direction.

## When to use

- Sprint planning, once the candidate set has passed the readiness gate
- Re-planning mid-sprint after a scope change
- Before the orchestrator commits a sprint to execution

## When NOT to use

- To choose *which* stories to pull — that is `backlog-prioritization`
- To assess whether the backlog can fill future sprints — that is
  `backlog-refinement`

## Inputs

| Arg | Type | Required | Validation |
| --- | ---- | -------- | ---------- |
| `sprint_goal` | str | yes | empty → error; under 15 chars → warning |
| `stories` | list/dict/markdown | yes | the proposed commitment |
| `member_days` | float | yes | total person-days available; negative raises |
| `focus_factor` | float | no | default 0.7; must be within (0, 1] |
| `historical_velocity` | list | no | completed points per past sprint |
| `sprint_length_days` | float | no | required with history to derive capacity |
| `ready_ids` | list | no | ids cleared by the readiness gate |

## How capacity is computed

```text
available_days  = member_days * focus_factor
points_per_day  = mean(historical_velocity) / sprint_length_days
capacity_points = available_days * points_per_day
utilization     = committed_points / capacity_points
```

Over 100% is an error. Under 60% is a warning.

## Finding codes

| Code | Severity | Meaning |
| ---- | -------- | ------- |
| `no_sprint_goal` | error | sprint has no stated outcome |
| `no_stories` | error | nothing proposed |
| `unestimated_in_sprint` | error | story cannot be fitted to capacity |
| `unready_in_sprint` | error | story is outside the ready set |
| `overcommitted` | error | committed points exceed capacity |
| `no_capacity` | error | computed capacity is zero or negative |
| `capacity_unknown` | warn | no history/length; commitment unchecked |
| `undercommitted` | warn | below 60% of capacity |
| `thin_sprint_goal` | warn | goal is a label, not an outcome |
| `above_best_sprint` | warn | commitment beats the team's best recorded sprint |

## Output contract

```json
{
  "ok": false,
  "findings": [{"severity": "error", "code": "overcommitted", "detail": "…"}],
  "error_count": 1, "warn_count": 0, "info_count": 0,
  "sprint_goal": "Members can self-enrol without support",
  "story_count": 7,
  "committed_points": 42.0,
  "capacity": {"member_days": 40.0, "focus_factor": 0.7,
               "available_days": 28.0, "points_per_day": 1.2,
               "capacity_points": 33.6},
  "utilization": 1.25,
  "velocity": {"sprints": 5, "mean": 12.0, "trend": "stable", "…": "…"},
  "unestimated": [], "not_ready": [],
  "evidence": "deterministic_sprint_commitment"
}
```

## Failure modes

| Condition | Behavior |
| --------- | -------- |
| No velocity history | capacity `null` + `capacity_unknown` warning |
| `focus_factor` outside (0, 1] | raises ValueError → `skill.failed` |
| Negative `member_days` | raises ValueError → `skill.failed` |

## Anti-patterns

- WRONG: raising `focus_factor` to 1.0 so the commitment fits.
  CORRECT: focus factor reflects observed reality; change the commitment.
- WRONG: pulling an unready story because "it is nearly ready".
  CORRECT: it goes back to refinement; pull a ready one instead.

## Quality checklist

- [ ] Sprint goal states an outcome a stakeholder would recognize
- [ ] `not_ready` and `unestimated` are both empty
- [ ] Utilization reviewed by the team, not just the planner
- [ ] Capacity inputs reflect actual availability including leave
