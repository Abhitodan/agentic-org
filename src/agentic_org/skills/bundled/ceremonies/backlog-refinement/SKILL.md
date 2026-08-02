---
name: backlog-refinement
description: Measure the refinement funnel — sprints of ready runway against the team's own velocity, plus stale and under-specified items. Measures the funnel; refines nothing itself.
category: ceremonies
personas:
  - product-owner-agent
  - planning-agent
  - domain-analyst-agent
triggers:
  - backlog-refinement
  - sprint-planning
network: none
entrypoint: scripts/refine.py:run
tools: []
---

# Backlog Refinement

> A team that runs out of ready work discovers it on the morning of sprint
> planning. Runway is the leading indicator: how many sprints of ready work
> sit ahead of the team right now.

## Guardrails

1. **Runway is measured in the team's own sprints**, using mean velocity.
   Without velocity history, runway is reported as unknown rather than
   expressed in points that mean nothing.
2. **Ready means demonstrably ready.** With an explicit `ready_ids` list it
   is authoritative; without one, a story counts as ready only if it has both
   an estimate and acceptance criteria.
3. **Below one sprint of runway is an error**, not a warning — the next
   sprint cannot be filled.
4. **Ageing items are surfaced, never auto-closed.** Closing backlog items
   is a Product Owner decision.

## When to use

- At the refinement ceremony, to check the funnel is healthy
- Before sprint planning, to confirm the sprint can be filled
- Periodically, to find items that have aged out of relevance

## When NOT to use

- To decide readiness of a specific story — that is
  `definition-of-ready-gate`
- To order the backlog — that is `backlog-prioritization`

## Inputs

| Arg | Type | Required | Validation |
| --- | ---- | -------- | ---------- |
| `stories` | list/dict/markdown | yes | the whole candidate backlog |
| `ready_ids` | list | no | authoritative ready set from the readiness gate |
| `historical_velocity` | list | no | completed points per past sprint |

Stories may carry `age_days` for staleness detection.

## How runway is computed

```text
ready_points  = sum(estimate of every ready story)
runway_sprints = ready_points / mean(historical_velocity)
```

Target is 1.5 sprints; below 1.0 is an error.

## Finding codes

| Code | Severity | Meaning |
| ---- | -------- | ------- |
| `no_backlog` | error | nothing supplied |
| `nothing_ready` | error | no item is sprint-eligible |
| `insufficient_runway` | error | below one sprint of ready work |
| `thin_runway` | warn | below the 1.5-sprint target |
| `runway_unknown` | warn | no velocity history to divide by |
| `ready_without_estimate` | warn | counted ready but unsized; runway understated |
| `stale_backlog_items` | warn | items untouched for over 90 days |

## Output contract

```json
{
  "ok": false,
  "findings": [{"severity": "error", "code": "insufficient_runway", "detail": "…"}],
  "error_count": 1, "warn_count": 1, "info_count": 0,
  "item_count": 40,
  "ready_count": 6,
  "unready_count": 34,
  "ready_points": 18.0,
  "ready_without_estimate": 1,
  "mean_velocity": 21.5,
  "runway_sprints": 0.84,
  "stale_items": ["US-2"],
  "evidence": "deterministic_refinement_funnel"
}
```

## Failure modes

| Condition | Behavior |
| --------- | -------- |
| No velocity history | runway `null` + `runway_unknown` warning |
| No `ready_ids` supplied | readiness inferred from estimate + criteria |
| Missing `age_days` | treated as zero; no false staleness claim |

## Anti-patterns

- WRONG: refining forty stories to build a six-sprint runway.
  CORRECT: runway beyond about two sprints ages faster than it is used;
  refine just ahead of need.
- WRONG: marking stories ready to raise the runway number.
  CORRECT: the readiness gate is the authority; this skill only counts.

## Quality checklist

- [ ] Runway at or above the target before planning starts
- [ ] Every ready story is also estimated
- [ ] Stale items closed or deliberately kept, with a reason
- [ ] Unready count trending down, not accumulating
