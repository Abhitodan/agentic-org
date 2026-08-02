---
name: epic-decomposition
description: Check an epic decomposes into stories with full two-way traceability — no orphan stories, no epic outcome left undelivered. Traceability is declared, never inferred.
category: product
personas:
  - product-manager-agent
  - product-owner-agent
  - architect-agent
triggers:
  - epic-decomposition
  - node_draft_charter
  - backlog-refinement
network: none
entrypoint: scripts/decompose.py:run
tools: []
---

# Epic Decomposition

> The failure is quiet: an epic is broken into stories, every story ships,
> and one outcome nobody claimed never gets built. Two-way traceability
> makes that gap loud at planning time instead of at launch.

## Guardrails

1. **Two-way traceability.** Every story declares a `parent`; every epic
   outcome must be claimed by at least one story's `covers` list. Orphans in
   either direction are errors.
2. **Never inferred from wording.** Similar phrasing is not coverage; only
   a declared `covers` entry counts.
3. **Width is a signal.** More than 20 stories under one epic usually means
   a program that should become several epics.
4. **Partial estimation is reported.** An epic where half the stories are
   estimated has an unknown size, and the result says so rather than
   summing what happens to be present.

## When to use

- After an epic or feature charter is drafted, before sprint planning
- When stories are added to an existing epic mid-flight
- Before a release scope decision, to confirm the epic is fully covered

## When NOT to use

- To split one oversized story — that is `story-splitting`
- To validate individual story quality — run `story-authoring` per story

## Inputs

| Arg | Type | Required | Validation |
| --- | ---- | -------- | ---------- |
| `epic` | dict/list/markdown | yes | first entry is the epic; its AC list is the outcome ledger |
| `stories` | list | yes | each declares `parent` and `covers` |
| `max_stories` | int | no | default 20; above it the epic warns as too wide |

## Finding codes

| Code | Severity | Meaning |
| ---- | -------- | ------- |
| `no_epic` | error | nothing to decompose |
| `no_stories` | error | epic has no children |
| `orphan_story` | error | story declares no parent epic |
| `wrong_parent` | error | story points at a different epic |
| `covers_unknown_outcome` | error | claims an outcome the epic does not have |
| `uncovered_outcomes` | error | epic outcomes no story delivers |
| `epic_too_wide` | warn | more children than `max_stories` |
| `epic_without_outcomes` | warn | epic has no acceptance criteria to trace against |
| `no_traceability` | warn | story declares no `covers` list |
| `partial_estimates` | warn | some children unestimated; epic size unknown |

## Output contract

```json
{
  "ok": false,
  "findings": [{"severity": "error", "code": "uncovered_outcomes",
                "subject": "EPIC-2", "detail": "…"}],
  "error_count": 1, "warn_count": 1, "info_count": 0,
  "epic_id": "EPIC-2",
  "story_count": 6,
  "epic_outcomes": ["AC-1", "AC-2", "AC-3"],
  "covered_outcomes": ["AC-1", "AC-2"],
  "uncovered_outcomes": ["AC-3"],
  "orphan_stories": [],
  "estimated_points": 34.0,
  "evidence": "deterministic_epic_traceability"
}
```

## Failure modes

| Condition | Behavior |
| --------- | -------- |
| Epic without acceptance criteria | warn; coverage checks skipped, not faked |
| No children | `no_stories` error |
| Mixed estimated/unestimated children | `estimated_points` reported with a warning |

## Anti-patterns

- WRONG: treating the story list as the epic's definition, so whatever was
  written becomes the scope.
  CORRECT: the epic's outcomes are the contract; stories are how it is met.
- WRONG: one catch-all story titled "everything else".
  CORRECT: name the remaining outcomes and give each a story, or remove them
  from the epic deliberately.

## Quality checklist

- [ ] `uncovered_outcomes` and `orphan_stories` are both empty
- [ ] Story count is within the width limit, or the epic is being split
- [ ] Every child is estimated before the epic is scheduled
- [ ] Removed outcomes were removed by decision, not by omission
