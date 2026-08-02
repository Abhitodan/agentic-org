# Testing (common)

## Must always

- Evidence over claims: success means a test command exited 0 — never
  "the code looks correct". This is the organization's core honesty rule.
- RED before GREEN for bug fixes: write or identify a test that fails for
  the intended reason before touching production code. A test that was never
  run does not count as RED.
- Tests verify user-visible behavior, not implementation internals.
- Each test is independent: no ordering dependencies, no shared mutable
  fixtures across tests.
- Arrange–Act–Assert structure with descriptive names that state the
  guarantee ("test_empty_actions_are_rejected", not "test_case_2").
- Cover edge cases deliberately: empty, null/None, boundary values,
  duplicate input, permission denied, missing files.

## Must never

- Claim a test passed without running it (fabricated PASS is the worst
  defect this organization recognizes).
- Write tests that cannot fail (assert True, over-mocked mirrors of the
  implementation).
- Skip or disable failing tests to get green — fix or delete with a recorded
  reason.
- Let a merge proceed when the declared test command fails.

## Evidence format

When reporting test results, always include: the exact command, the exit
code, and the relevant output tail. The `test-evidence` skill produces
hash-backed payloads for audit events — prefer it over prose.

## Deep reference

Workflows and patterns live in the skills: `implementation` (apply + test
gate), `test-evidence` (hash-backed runs), `code-review` (evidence-required
review).
