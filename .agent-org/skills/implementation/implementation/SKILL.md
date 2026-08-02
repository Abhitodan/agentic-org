---
name: implementation
description: Apply bounded file actions in an isolated worktree with path containment and a hard test gate. Success is a test command exiting 0 — nothing else.
category: implementation
personas:
  - backend-agent
  - frontend-agent
  - database-agent
triggers:
  - node_implement
  - implementation
network: none
entrypoint: scripts/implement.py:run
tools: []
---

# Implementation

> Code generation is cheap; verified change is the product. This skill turns
> a list of file actions into a test-gated, evidence-backed change — or a
> clean, auditable failure.

## Guardrails

1. **Path containment.** Every action path must resolve inside the
   worktree. Absolute paths and `..` traversal are rejected outright — the
   action list fails, it is never "fixed" silently.
2. **Non-empty actions.** An empty action list is a validation error, not a
   success. Empty work claiming success is the exact failure mode this
   organization exists to prevent.
3. **Test gate.** The declared test command runs in the worktree under the
   sandbox policy. `ok: true` requires exit 0. There is no "probably passes".
4. **Worktrees only.** Never runs against the protected checkout; the gated
   merge node is the only writer to the protected branch.
5. **Explicit skips.** `skip_tests: true` returns an apply-only payload
   that says so — it can never masquerade as a green test run.

## When to use

- Mode A `node_implement`, after actions exist
- CLI/agent application of reviewed action lists into a worktree
- Any programmatic edit that must be contained and test-gated

## When NOT to use

- To *propose* actions (the runner's LLM step or a human does that)
- Directly against the protected branch — worktrees only
- When no test command exists and `skip_tests` would hide that fact:
  record the gap instead

## Inputs

| Arg | Type | Required | Validation |
| --- | ---- | -------- | ---------- |
| `worktree` | path | yes | must exist; else `ok: false` |
| `actions` | list | yes | each item must be a dict `{op: write\|append, path, content}` |
| `test_command` | list/str | no | shell-split locally; empty → project default |
| `org_root` | path | no | sandbox policy root |
| `skip_tests` | bool | no | apply-only mode; recorded in `reason` |

## Workflow

1. Validate the worktree and action shapes (TypeError on malformed input).
2. Apply actions with containment checks (`apply_actions`) — a single bad
   path fails the whole list.
3. Run the test command sandboxed (allowlisted argv, no arbitrary shell).
4. Return the evidence payload; the runner attaches it to
   `implementation.succeeded/failed` events and hands it to review.

## Output contract

```json
{
  "ok": true,
  "actions_applied": 3,
  "reason": "",
  "test": {"ok": true, "exit_code": 0,
           "command": ["python", "-m", "pytest", "-q"],
           "stdout_tail": "…", "duration_ms": 1234},
  "evidence": "deterministic_apply_and_tests"
}
```

On failure, `reason` names the cause: containment violation, invalid or
empty actions, or "tests failed after implementation; success not claimed".

## Failure modes

| Condition | Behavior |
| --------- | -------- |
| Worktree missing | `ok: false`, nothing applied |
| Path escapes worktree | `ok: false`, whole action list rejected |
| Tests fail | `ok: false` with full test payload — evidence preserved |
| Malformed action item | raises TypeError → `skill.failed` |

## Anti-patterns

- WRONG: weakening a failing test or lint config so the gate passes.
  CORRECT: fix the code; gates are fixed by fixing causes.
- WRONG: `skip_tests: true` to hide a missing test suite.
  CORRECT: record the gap honestly and let review decide.
- WRONG: "while I'm here" edits outside assigned scope.
  CORRECT: one bounded change per action list; extra work goes back to
  planning.

## Quality checklist

- [ ] Every applied path is inside the worktree
- [ ] `test.exit_code` is present (or `skip_tests` reason is recorded)
- [ ] Failure payloads preserved verbatim — no summarized-away stderr
- [ ] No test/lint/type config was modified to achieve green

## References

- `.agent-org/rules/common/testing.md` — RED/GREEN discipline
- `test-evidence` skill — standalone hash-backed test runs
