---
name: backlog-prioritization
description: Rank a backlog by WSJF or validate a MoSCoW allocation. Deterministic arithmetic with a stable tie-break — the same backlog always ranks the same way.
category: product
personas:
  - product-owner-agent
  - product-manager-agent
  - cost-governor-agent
triggers:
  - backlog-prioritization
  - backlog-refinement
  - sprint-planning
network: none
entrypoint: scripts/prioritize.py:run
tools: []
---

# Backlog Prioritization

> Priority arguments are cheaper when the arithmetic is not in dispute. This
> skill computes the ranking; the team argues about the inputs, which is the
> conversation worth having.

## Guardrails

1. **Inputs are never imputed.** A story missing `job_size` is reported as
   unrankable, not scored with an assumed default.
2. **The tie-break is fixed and documented**: higher WSJF first, then
   smaller job size, then id. Reruns cannot reshuffle equal-scoring items.
3. **The score is an input to judgment, not a verdict.** Ranking output is
   advisory to the Product Owner, who owns the ordering.
4. **Must-have inflation is surfaced.** A MoSCoW list that is mostly Must
   has no flex left, and the skill says so.

## When to use

- Refinement, once stories carry value/criticality/risk/size inputs
- Release scoping with MoSCoW, to check the allocation is honest
- Before sprint planning, to order the candidate set

## When NOT to use

- To *assign* the value or size numbers — that is the team's estimation work
- To decide sprint capacity — that is `sprint-planning`

## Inputs

| Arg | Type | Required | Validation |
| --- | ---- | -------- | ---------- |
| `stories` | list/dict/markdown | yes | empty → error finding |
| `method` | str | no | `wsjf` (default) or `moscow`; anything else raises |

WSJF requires numeric `business_value`, `time_criticality`,
`risk_reduction`, and a positive `job_size` on each story.
MoSCoW requires a `moscow` field of must / should / could / wont.

## How WSJF is computed

```text
cost_of_delay = business_value + time_criticality + risk_reduction
wsjf          = cost_of_delay / job_size
```

Higher is sooner. Job size in the denominator is why small high-value work
outranks large high-value work.

## Finding codes

| Code | Severity | Meaning |
| ---- | -------- | ------- |
| `no_stories` | error | empty backlog supplied |
| `invalid_job_size` | error | job size must be positive |
| `nothing_ranked` | error | no item carried the required numeric inputs |
| `invalid_moscow` | error | classification outside must/should/could/wont |
| `unrankable` | warn | item lacks WSJF inputs and was skipped |
| `unclassified` | warn | item has no MoSCoW level |
| `must_have_inflation` | warn | over 60% of classified items are Must |

## Output contract

```json
{
  "ok": true,
  "findings": [{"severity": "warn", "code": "unrankable", "subject": "US-9", "detail": "…"}],
  "error_count": 0, "warn_count": 1, "info_count": 0,
  "method": "wsjf",
  "ranking": [{"id": "US-3", "wsjf": 4.5, "job_size": 2.0, "rank": 1}],
  "ranked_count": 6,
  "item_count": 7,
  "evidence": "deterministic_backlog_ranking"
}
```

MoSCoW runs return `tally` instead of a populated `ranking`.

## Failure modes

| Condition | Behavior |
| --------- | -------- |
| Unknown method | raises ValueError → `skill.failed` |
| All items unrankable | `nothing_ranked` error; empty ranking |
| Non-numeric score fields | item skipped with `unrankable`, never coerced to 0 |

## Anti-patterns

- WRONG: tuning `business_value` upward until a favoured story ranks first.
  CORRECT: if the ranking feels wrong, the inputs are wrong — fix the
  estimate of value or size, and say why.
- WRONG: classifying everything as Must to protect scope.
  CORRECT: Must means the release fails without it; the warning exists
  because that is rarely true of 90% of a backlog.

## Quality checklist

- [ ] `ranked_count` equals `item_count`, or each gap is explained
- [ ] Score inputs come from the team, not from the skill
- [ ] Ties resolved by the documented rule, not by re-running
- [ ] Must-have share reviewed before committing a release scope
