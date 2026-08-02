---
name: Validate live LLM Mode A path
about: Exercise charter → approve → plan with a real model key
labels: research, evaluation
---

## Problem

`draft_charter` / `plan` nodes are coded but the happy path past the human gate is unverified without a live API key (`docs/operations/validation-report.md`).

## Hypothesis

With a valid `GEMINI_API_KEY`, Mode A reaches `PLANNED` after approve+resume, writing non-empty `charter.md` and `implementation-plan.md`, with cost_usd > 0 and a valid event chain.

## Acceptance criteria

- [ ] Scripted or documented run against `examples/enrollment-sample`
- [ ] Redacted transcript/fixture committed under `evals/fixtures/` (no secrets)
- [ ] Automated assertion: final state `PLANNED` OR explicit skip when key absent
- [ ] Cost and token totals recorded in eval JSON
- [ ] No fabricated content when key missing (existing honesty test still passes)

## Confounders

- Provider outages, model renames, price drift in `models.yaml`

## References

- `src/agentic_org/orchestrator/runner.py`
- `docs/EVALUATION_METHOD.md` (H4/H5)
