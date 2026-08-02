---
name: Add CI workflow
about: Run pytest and evals on every PR
labels: enhancement, dx
---

## Problem

There is no in-repo CI. Regressions in guarantees (events, budget, honesty, API auth) can merge unnoticed.

## Acceptance criteria

- [ ] GitHub Actions (or equivalent) runs on pull_request and push to default branch
- [ ] Steps: setup Python ≥3.11, `pip install -e ".[dev]"`, `pytest -q`, `python evals/run_evals.py`
- [ ] Fail the job on eval exit code ≠ 0
- [ ] Document the workflow in CONTRIBUTING.md

## Evidence to attach

- Link to green CI run
- Note any skipped cases and why

## References

- `docs/ROADMAP.md` (priority 1)
- `evals/README.md`
