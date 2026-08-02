---
name: acceptance-criteria-forge
description: Check acceptance criteria are testable — observable outcomes, no subjective wording, one guarantee per criterion. A criterion no test can express is a defect.
category: product
personas:
  - product-owner-agent
  - testing-agent
  - domain-analyst-agent
triggers:
  - acceptance-criteria-forge
  - node_draft_charter
  - backlog-refinement
network: none
entrypoint: scripts/forge.py:run
tools: []
---

# Acceptance Criteria Forge

> "It works properly" cannot fail, so it cannot pass. Every criterion this
> organization accepts names an observable outcome that a test can assert.

## Guardrails

1. **Testability is judged structurally.** A criterion qualifies when it
   contains an outcome marker (then, returns, rejects, must, within…), a
   number, or a Given/When/Then structure — never by guessing intent.
2. **Subjective wording is a finding, not a style note.** Words like
   "properly", "intuitive", "fast" describe a feeling; paired with no
   measurable outcome they are an error.
3. **One guarantee per criterion.** Compound criteria hide half-passes.
4. **Criteria are never rewritten for you.** The skill reports what is
   wrong; the Product Owner supplies the corrected wording.

## When to use

- While drafting a charter or story, before estimation
- Inside refinement, after `story-authoring` confirms structure
- When QA reports that a criterion could not be turned into a test

## When NOT to use

- To generate criteria — that is human/LLM authoring work
- To check whether criteria are *covered* by a diff — that is `code-review`

## Inputs

| Arg | Type | Required | Validation |
| --- | ---- | -------- | ---------- |
| `criteria` | list/str | yes | strings, `{id, text}` dicts, or a markdown block |
| `story_id` | str | no | prefixes finding subjects for traceability |
| `require_gherkin` | bool | no | when true, non-Given/When/Then criteria warn |

## Finding codes

| Code | Severity | Meaning |
| ---- | -------- | ------- |
| `no_criteria` | error | nothing supplied |
| `criterion_too_short` | error | under 15 characters; expresses no guarantee |
| `not_measurable` | error | no observable outcome, number, or Gherkin structure |
| `vague_wording` | error/warn | subjective terms; error when also unmeasurable |
| `duplicate_criterion_id` | error | ids must be unique within a story |
| `compound_criterion` | warn | asserts more than one guarantee |
| `not_gherkin` | warn | only when `require_gherkin` is set |

## What a good criterion looks like

```markdown
- AC-1: Given a CSV with 500 rows, when the import runs, then all valid rows
  are stored and each invalid row is reported with its line number.
```

Observable, singular, and directly expressible as a test.

## Output contract

```json
{
  "ok": false,
  "findings": [{"severity": "error", "code": "not_measurable",
                "subject": "US-3/AC-2", "field": "text", "detail": "…"}],
  "error_count": 1, "warn_count": 0, "info_count": 0,
  "criterion_count": 3,
  "testable_count": 2,
  "criteria": [{"id": "AC-1", "measurable": true, "vague_terms": []}],
  "evidence": "deterministic_ac_testability"
}
```

## Failure modes

| Condition | Behavior |
| --------- | -------- |
| Empty criteria list | `ok: false` with `no_criteria` |
| Criterion measurable but vague | warn, not error — the outcome is still testable |
| Criterion neither measurable nor specific | two errors; it must be rewritten |

## Anti-patterns

- WRONG: "AC-2: The dashboard is fast and user-friendly."
  CORRECT: "AC-2: The dashboard renders the first 50 rows within 2 seconds
  on a cold cache."
- WRONG: splitting a criterion into two ids that restate the same guarantee
  to raise the testable count.
  CORRECT: one criterion per distinct, independently failable guarantee.

## Quality checklist

- [ ] `testable_count` equals `criterion_count`
- [ ] No criterion mixes two guarantees
- [ ] Each criterion could be handed to QA and turned into one test
- [ ] Numbers and thresholds come from the business, not from the code
