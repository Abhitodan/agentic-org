---
name: test-evidence
description: Run declared tests and return hash-backed evidence — exact command, exit code, output hashes. The only acceptable proof of "tests pass".
category: verification
personas:
  - testing-agent
  - backend-agent
  - frontend-agent
triggers:
  - node_implement
  - node_review
  - test-evidence
network: none
entrypoint: scripts/evidence.py:run
tools: []
---

# Test Evidence

> "Tests pass" as prose is a claim. Command + exit code + output hash is
> evidence. Reviews and releases in this organization accept only the latter.

## Guardrails

1. **Sandboxed execution.** Commands run under the org sandbox policy —
   allowlisted argv, never an arbitrary shell. String commands are
   shell-split locally, not passed to a shell.
2. **Tamper-evident output.** stdout/stderr are sha256-hashed; the hashes
   travel with the audit event, so a payload cannot be quietly edited.
3. **Honest zeros.** Running zero tests successfully is recorded as exactly
   that — this skill is not a substitute for writing tests.
4. **A fabricated PASS is the most serious defect this organization
   recognizes.** Never present results for a command that was not run.

## When to use

- After applying implementation actions (feeds the review node)
- Before claiming review or release readiness
- Whenever anyone asserts test status — replace the assertion with a payload

## When NOT to use

- To run arbitrary commands — the sandbox allowlists test invocations;
  this is not a shell escape
- As the test *strategy* — what to test is the testing-agent's job

## Inputs

| Arg | Type | Required | Validation |
| --- | ---- | -------- | ---------- |
| `cwd` | path | yes | must exist; else `ok: false` |
| `command` | list/str | no | empty → project default (`python -m pytest -q --tb=line`) |
| `org_root` | path | no | sandbox policy root |

## Workflow

1. Resolve the command and run it under the sandbox policy.
2. Hash stdout and stderr (sha256) — evidence is compact and tamper-evident;
   full logs need not live in events.
3. Return exit code, tails for humans, hashes for the audit chain.

## Output contract

```json
{
  "ok": true,
  "exit_code": 0,
  "command": ["python", "-m", "pytest", "-q"],
  "stdout_hash": "sha256…",
  "stderr_hash": "sha256…",
  "stdout_tail": "… 21 passed …",
  "duration_ms": 4200,
  "evidence": "deterministic_test_run"
}
```

## Evidence report convention

When summarizing for humans (brains, PR bodies), present guarantees as a
table — what is guaranteed, the command, the result, the evidence:

```markdown
| # | Guarantee | Command | Result | Evidence |
|---|-----------|---------|--------|----------|
| 1 | Empty actions are rejected | pytest tests/test_skills.py -q | PASS | exit 0, sha256 abc… |
```

Quote actual commands and outcomes. Never invent a PASS.

## Failure modes

| Condition | Behavior |
| --------- | -------- |
| `cwd` missing | `ok: false` with reason; no fake run |
| Sandbox denies command | exit_code 126 with the denial in stderr |
| Tests fail | `ok: false`, full evidence still returned |

## Anti-patterns

- WRONG: "the suite passed earlier today" as review evidence.
  CORRECT: fresh payload from the current worktree state.
- WRONG: trimming a failing tail so the payload "looks green".
  CORRECT: hashes make this detectable; report it as tampering.

## Quality checklist

- [ ] Command shown verbatim in the payload
- [ ] Exit code present and consistent with `ok`
- [ ] Hashes recorded in the audit event
- [ ] Payload generated after the last file change, not before
