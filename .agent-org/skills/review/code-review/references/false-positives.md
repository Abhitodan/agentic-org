# Review False Positives — Do Not Flag

Patterns LLM reviewers commonly mis-flag. Skip these unless you have
evidence specific to this codebase. Litmus test before flagging anything:
"Would a senior engineer on this team actually request this change?"

## Error handling

- "Consider adding error handling" on calls whose error path is handled by
  the caller or framework (middleware, error boundaries, top-level
  try/except, upstream `.catch`).
- "Missing input validation" on internal functions whose callers validate.
  Trace at least one caller before flagging.
- "Possible null/None dereference" when a preceding guard or type narrows
  it. Trace the flow instead of pattern-matching on `.get(`/`?.`.

## Constants and size

- "Magic number" for well-known constants: HTTP status codes, 1000 ms,
  1024, 60, 24, index 0/-1, single-use locals whose name says the meaning.
- "Function too long" for exhaustive dispatch tables, config objects, test
  tables, or generated code. Length is not complexity.
- "Missing docstring" on single-purpose internal helpers whose name and
  signature are self-describing.

## Tests and fixtures

- "Hardcoded value" in test fixtures, examples, docs snippets — tests
  *should* have hardcoded expectations.
- "Duplicated code" across parametrized test cases that assert different
  guarantees.

## Async / concurrency

- "Missing await" on intentionally detached fire-and-forget calls (logging,
  metrics, queue pushes). Look for a comment or explicit detachment first.
- "Race condition" claims without naming the two interleaving operations
  and the shared state.

## Security theater

- Non-cryptographic randomness (jitter, sampling, animation) flagged as
  insecure RNG.
- `.env.example` placeholders and obviously fake test credentials flagged
  as leaked secrets.
- Content hashes (sha256 hex) flagged as high-entropy secrets.

## Stack changes

- "Should use X instead" where X is a different language, framework, or
  major library. Match the project's stack; propose changes via ADR, not
  review findings.
