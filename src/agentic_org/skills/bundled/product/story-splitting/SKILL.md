---
name: story-splitting
description: Verify a split produced independently shippable slices that cover every parent criterion. Explicit traceability only — coverage is never inferred from wording.
category: product
personas:
  - product-owner-agent
  - planning-agent
  - architect-agent
triggers:
  - story-splitting
  - backlog-refinement
network: none
entrypoint: scripts/split.py:run
tools: []
---

# Story Splitting

> Splitting fails in two directions: slices that still cannot ship, and
> slices that quietly drop part of the original promise. This skill checks
> both with the parent's acceptance criteria as the ledger.

## Guardrails

1. **Coverage is explicit.** Each slice declares `covers: [AC-1, AC-2]`.
   Unclaimed parent criteria are an error — coverage is never guessed from
   similar wording.
2. **Every slice ships alone.** A slice without its own acceptance criteria
   is not a slice; it is a task.
3. **A split that leaves a slice above the threshold has not split.**
4. **Inflation is visible.** Slices totalling far more than the parent
   estimate signals scope grew during splitting; that is surfaced, not hidden.

## When to use

- After `story-authoring` reports `too_large_to_commit`
- During refinement when a story spans more than one sprint
- Before planning, so capacity is computed on shippable units

## When NOT to use

- To decide *how* to split (by workflow step, data variation, or interface —
  that is a team conversation)
- To decompose an epic into stories — that is `epic-decomposition`

## Inputs

| Arg | Type | Required | Validation |
| --- | ---- | -------- | ---------- |
| `parent` | dict/list/markdown | yes | first story is treated as the parent |
| `slices` | list | yes | each slice may declare `parent` and `covers` |

## Finding codes

| Code | Severity | Meaning |
| ---- | -------- | ------- |
| `no_parent` | error | nothing to split |
| `not_split` | error | fewer than two slices |
| `slice_without_criteria` | error | slice cannot ship independently |
| `slice_still_too_large` | error | slice estimate above the split threshold |
| `uncovered_criteria` | error | parent criteria no slice delivers |
| `covers_unknown_criteria` | error | slice claims a criterion the parent lacks |
| `wrong_parent` | error | slice declares a different parent id |
| `no_traceability` | warn | slice declares no `covers` list |
| `parent_without_criteria` | warn | coverage cannot be verified |
| `split_inflation` | warn | slice points far exceed the parent estimate |

## Output contract

```json
{
  "ok": false,
  "findings": [{"severity": "error", "code": "uncovered_criteria",
                "subject": "US-10", "detail": "…"}],
  "error_count": 1, "warn_count": 0, "info_count": 0,
  "parent_id": "US-10",
  "slice_count": 3,
  "parent_criteria": ["AC-1", "AC-2", "AC-3"],
  "covered_criteria": ["AC-1", "AC-2"],
  "uncovered_criteria": ["AC-3"],
  "slice_points_total": 13.0,
  "evidence": "deterministic_split_coverage"
}
```

## Failure modes

| Condition | Behavior |
| --------- | -------- |
| Parent has no criteria | warn; coverage checks are skipped, not faked |
| Slice omits `covers` | warn per slice, plus `uncovered_criteria` if gaps remain |
| Single slice supplied | `not_split` error |

## Anti-patterns

- WRONG: splitting by technical layer ("backend story", "frontend story") —
  neither ships value alone.
  CORRECT: split by workflow step, data variation, or rule complexity, so
  each slice is demonstrable.
- WRONG: dropping the awkward criterion during a split.
  CORRECT: `uncovered_criteria` makes the drop visible; either a slice takes
  it or the Product Owner removes it deliberately.

## Quality checklist

- [ ] `uncovered_criteria` is empty
- [ ] Every slice has its own acceptance criteria and an estimate
- [ ] No slice exceeds the split threshold
- [ ] Each slice could be demonstrated at a sprint review on its own
