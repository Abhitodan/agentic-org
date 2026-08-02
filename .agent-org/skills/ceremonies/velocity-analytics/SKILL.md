---
name: velocity-analytics
description: Velocity statistics and an empirical forecast range from completed sprints. The forecast is an observed range, never a model — under three sprints there is no forecast at all.
category: ceremonies
personas:
  - planning-agent
  - retrospective-agent
  - cost-governor-agent
triggers:
  - velocity-analytics
  - sprint-planning
  - retrospective
network: none
entrypoint: scripts/velocity.py:run
tools: []
---

# Velocity Analytics

> Velocity is a planning input, not a performance score. Used as a target it
> stops measuring anything, because point inflation is the easiest number in
> software to manufacture.

## Guardrails

1. **No forecast without three sprints.** Fewer sprints return an explicit
   "insufficient history" rather than a confident-looking average.
2. **The forecast is an observed range** — the min and max of the last three
   sprints — not a regression or a projection.
3. **Volatility is reported.** When the coefficient of variation exceeds
   0.35, the mean is not a usable planning number and the skill says so.
4. **Never a productivity measure.** The output carries no per-person data
   and must not be used to compare teams.

## When to use

- Before sprint planning, to set a realistic capacity expectation
- At the retrospective, to look at trend and volatility together
- During release forecasting, to express a range instead of a date

## When NOT to use

- To compare two teams; points are not a shared unit
- To set a velocity target; the number stops being informative immediately

## Inputs

| Arg | Type | Required | Validation |
| --- | ---- | -------- | ---------- |
| `sprints` | list | yes | numbers, or `{sprint, completed_points}` dicts |
| `planned_points` | list | no | committed points per sprint, for delivery ratio |

## Statistics returned

| Field | Meaning |
| ----- | ------- |
| `mean` / `median` / `stdev` | descriptive statistics over all sprints |
| `min` / `max` | observed extremes |
| `trend` | rising / falling / stable / insufficient_history (10% band) |
| `forecast_low` / `forecast_high` | min and max of the last three sprints |
| `forecast_basis` | plain-language statement of what the forecast rests on |
| `volatility` | stdev / mean, the coefficient of variation |
| `delivery_ratio` | delivered points over committed points |

## Finding codes

| Code | Severity | Meaning |
| ---- | -------- | ------- |
| `no_history` | error | no completed sprints supplied |
| `insufficient_history` | warn | fewer than three sprints; no forecast |
| `high_volatility` | warn | coefficient of variation above 0.35 |
| `falling_velocity` | warn | recent sprints deliver less than earlier ones |
| `chronic_overcommitment` | warn | under 80% of committed points delivered |
| `unreadable_sprint` | warn | non-numeric entry excluded from statistics |

## Output contract

```json
{
  "ok": true,
  "findings": [{"severity": "warn", "code": "high_volatility", "detail": "…"}],
  "error_count": 0, "warn_count": 1, "info_count": 0,
  "velocity": {"sprints": 6, "mean": 21.5, "median": 21.0, "stdev": 8.2,
               "min": 9.0, "max": 34.0, "trend": "stable",
               "forecast_low": 18.0, "forecast_high": 26.0,
               "forecast_basis": "observed range of last 3 sprints"},
  "sprint_labels": ["sprint-1", "…"],
  "volatility": 0.381,
  "delivery_ratio": 0.86,
  "evidence": "deterministic_velocity_statistics"
}
```

## Failure modes

| Condition | Behavior |
| --------- | -------- |
| Empty history | `ok: false` with `no_history`; all statistics null |
| One or two sprints | statistics returned, forecast null with the reason |
| Mixed dicts and numbers | both accepted; malformed entries warned and skipped |

## Anti-patterns

- WRONG: quoting a single mean as "the team's velocity" when volatility is
  high.
  CORRECT: quote the forecast range and say what drives the spread.
- WRONG: celebrating rising velocity without checking story sizing.
  CORRECT: rising points with flat delivered value usually means inflation.

## Quality checklist

- [ ] At least three sprints before any forecast is quoted
- [ ] Volatility reported alongside the mean, never the mean alone
- [ ] Forecast expressed as a range in every downstream document
- [ ] No per-person breakdown derived from this output
