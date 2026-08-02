---
name: definition-of-ready-gate
description: Decide whether a story may enter a sprint — narrative, measurable criteria, estimate, resolved dependencies, no open questions. "We'll figure it out in the sprint" is what this gate prevents.
category: product
personas:
  - product-owner-agent
  - planning-agent
  - domain-analyst-agent
triggers:
  - definition-of-ready-gate
  - sprint-planning
  - backlog-refinement
network: none
entrypoint: scripts/gate.py:run
tools: []
---

# Definition of Ready Gate

> Every hour of unready work pulled into a sprint is repaid with interest
> mid-sprint, when the answer is expensive and the deadline is closer. This
> gate is the cheapest place to find the gap.

## Guardrails

1. **Eight checks, evaluated per story**, each naming the exact missing
   artifact so the Product Owner knows what to supply.
2. **Unresolved dependencies block.** A dependency counts as resolved only
   when its id appears in `completed_ids` — never because it "should be
   done by then".
3. **Open questions block.** An unanswered question is a mid-sprint stall
   with a delay attached.
4. **Ready is all-or-nothing per story.** Partial readiness is reported as
   not ready, with the failed checks listed.

## When to use

- The last step of refinement, before a story is sprint-eligible
- At sprint planning, on the candidate set (`ceremonies/sprint-planning`
  consumes the ready list)
- When a story returns from a blocked state and needs re-clearing

## When NOT to use

- To check whether finished work is *done* — that is the Definition of Done
  in `verification/` and `delivery/`
- To validate story wording — run `story-authoring` first

## Inputs

| Arg | Type | Required | Validation |
| --- | ---- | -------- | ---------- |
| `stories` | list/dict/markdown | yes | empty → error finding |
| `completed_ids` | list | no | dependency ids already delivered |
| `require_estimate` | bool | no | default true |
| `require_components` | bool | no | default false; warns when paths are unknown |

## The checks

| Check | Failing finding | Severity |
| ----- | --------------- | -------- |
| `has_id` | `missing_id` | error |
| `has_narrative` | `incomplete_narrative` | error |
| `has_acceptance_criteria` | `no_acceptance_criteria` | error |
| `criteria_measurable` | `unmeasurable_criteria` | error |
| `has_estimate` | `missing_estimate` | error (when required) |
| `estimate_within_threshold` | `too_large` | error |
| `dependencies_resolved` | `blocked_by_dependency` | error |
| `no_open_questions` | `open_questions` | error |
| — | `no_components` | warn (when required) |

## Output contract

```json
{
  "ok": false,
  "findings": [{"severity": "error", "code": "blocked_by_dependency",
                "subject": "US-4", "field": "dependencies", "detail": "…"}],
  "error_count": 1, "warn_count": 0, "info_count": 0,
  "checked": 5,
  "ready": ["US-1", "US-2"],
  "not_ready": ["US-4"],
  "ready_count": 2,
  "checks": ["has_id", "has_narrative", "…"],
  "report": [{"id": "US-4", "ready": false, "failed_checks": ["dependencies_resolved"]}],
  "evidence": "deterministic_ready_gate"
}
```

## Failure modes

| Condition | Behavior |
| --------- | -------- |
| Empty story list | `ok: false` with `no_stories` |
| Dependency inside the same batch | still unresolved; detail names the overlap |
| Estimate absent, `require_estimate` false | check skipped, no finding |

## Anti-patterns

- WRONG: waiving the gate because the sprint starts tomorrow.
  CORRECT: pull a ready story instead; the unready one keeps its place in
  refinement.
- WRONG: answering an open question inside the story text without updating
  the acceptance criteria.
  CORRECT: the answer usually changes a criterion — update it, then re-gate.

## Quality checklist

- [ ] Only stories in `ready` enter the sprint
- [ ] Each `not_ready` story has an owner for its failed checks
- [ ] Dependency ids verified against actually completed work
- [ ] Re-run after refinement changes, not assumed to still hold
