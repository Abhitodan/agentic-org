# Code Review (common)

## Confidence-based filtering

Report a finding only when you are confident (>80%) it is a real problem.
Noise erodes trust faster than missed findings.

### Pre-report gate — all four or drop

1. **Exact location** — file and line. "Somewhere in the auth layer" is not
   a finding.
2. **Concrete failure mode** — name the input, state, and bad outcome. If
   you cannot name the trigger, you are pattern-matching, not reviewing.
3. **Context read** — check callers, imports, and tests; many issues are
   handled one frame up.
4. **Defensible severity** — a missing docstring is never HIGH; severity
   inflation is a defect of the review itself.

HIGH/CRITICAL findings additionally require: the exact snippet, the specific
failure scenario, and why existing guards do not catch it.

## Zero findings is a valid review

Do not manufacture findings to justify the invocation. If the diff is small,
tested, and follows repository patterns, the correct verdict is APPROVE with
zero rows.

## Skip these common false positives

- "Consider adding error handling" where the caller or framework handles it
- "Missing validation" on internal functions whose callers validate
- "Magic number" for well-known constants (HTTP codes, 1024, index 0/-1)
- "Function too long" for exhaustive dispatch tables or test tables
- Hardcoded values in test fixtures — tests *should* have hardcoded expectations

## Severity ladder

| Severity | Meaning | Gate |
| -------- | ------- | ---- |
| CRITICAL | security flaw, data loss, fabricated evidence | blocks merge |
| HIGH | real bug or missing test evidence | blocks merge |
| MEDIUM | quality issue with concrete impact | fix soon |
| LOW | style / consistency | note only |

## Evidence requirement

No review verdict without a test-evidence payload. "Tests pass" as prose is
not evidence — require the command + exit code (see `test-evidence` skill).
