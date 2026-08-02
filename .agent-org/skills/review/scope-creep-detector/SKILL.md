---
name: scope-creep-detector
description: Compare changed paths against the stated objective and plan allowlist. Verdict keep, justify, or split — before scope drift reaches the protected branch.
category: review
personas:
  - reviewer-agent
  - planning-agent
triggers:
  - scope-creep-detector
  - node_review
  - code-review
network: none
entrypoint: scripts/detect.py:run
tools: []
---

# Scope Creep Detector

> The most expensive diff is the one that quietly does three unrelated
> things. This skill forces the "keep / justify / split" conversation
> before merge, with paths as evidence.

## Guardrails

1. **Segment-aware matching only.** Allowlist matches whole path segments —
   `src` covers `src/x.py`, but `s` never covers `src`. No substring games.
2. **The heuristic declares itself.** Each in-scope path reports whether it
   matched by `allowlist` or `token_overlap`, and the result names the
   heuristic — reviewers can weigh it accordingly.
3. **The objective is fixed at intake.** Widening the objective text after
   the fact so everything "fits" is itself scope creep; scope grows only
   via a new recorded decision.
4. **`justify` is a question, not a pass.** The reviewer must acknowledge
   each out-of-scope path or request a split.

## When to use

- Inside `code-review` (automatic, Mode A review node)
- Before opening a PR from a long agent session
- When a diff "grew" during implementation and someone asks why

## When NOT to use

- On repositories with no stated objective — fix the charter first
- As a substitute for human judgment on `justify` verdicts

## Inputs

| Arg | Type | Required | Validation |
| --- | ---- | -------- | ---------- |
| `objective` | str | yes | TypeError if not a string |
| `changed_paths` | list | yes | TypeError if not a list |
| `allow_prefixes` | list | no | explicit allowlist prefixes |
| `plan_text` | str | no | cited paths join the allowlist |

## Workflow

1. **Build the allowlist** — explicit prefixes + every path cited in the
   plan, normalized and deduplicated.
2. **Classify each changed path** — segment-covered by the allowlist, or
   sharing meaningful tokens (stopwords removed, extensions stripped) with
   the objective/plan.
3. **Verdict thresholds**:
   - all in scope → **keep** (`ok: true`)
   - out-of-scope ≤ ⅓ of paths → **justify** (`ok: true`, acknowledge each)
   - more → **split** (`ok: false`, blocks review)

## Output contract

```json
{
  "ok": false,
  "verdict": "split",
  "in_scope": ["auth/login.py"],
  "out_of_scope": ["payments/stripe_webhook.py", "legacy/unused.py"],
  "matched_by": {"auth/login.py": "allowlist"},
  "allow_prefixes": ["auth/"],
  "heuristic": "segment_allowlist+token_overlap",
  "evidence": "deterministic_path_scope"
}
```

## Verdict playbook

| Verdict | Meaning | Action |
| ------- | ------- | ------ |
| keep | diff matches objective | proceed |
| justify | small spillover | one line per out-of-scope path, or split |
| split | diff is doing multiple jobs | separate action lists / features |

## Failure modes

| Condition | Behavior |
| --------- | -------- |
| Empty `changed_paths` | verdict `keep` — nothing to drift |
| Non-string objective | raises TypeError → `skill.failed` |
| Path matched only by tokens | reported in `matched_by` for reviewer scrutiny |

## Anti-patterns

- WRONG: widening the objective text after the fact so everything "fits".
  CORRECT: the objective is fixed at intake; scope grows via a new decision.
- WRONG: batching drive-by refactors with a bug fix "to save time".
  CORRECT: separate worktree, separate review — cheap here, expensive mixed.

## Quality checklist

- [ ] Allowlist reflects the approved plan, not post-hoc additions
- [ ] Every `justify` path has a written acknowledgement
- [ ] `token_overlap` matches sanity-checked by the reviewer
- [ ] `split` verdicts result in actual splits, not overrides
