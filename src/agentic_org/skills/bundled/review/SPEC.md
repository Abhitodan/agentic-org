# review — remaining skills

`code-review` and `scope-creep-detector` are shipped. The two below are
specified and not yet built.

## Planned skills

### `security-review`

Deterministic checks over a diff: secrets committed, injection-prone string
construction, authentication or authorization removed from a handler,
dependency changes pulling in known-vulnerable versions. Findings report
`file:line` locations and never echo the secret itself.

- Inputs: diff, dependency changes, existing policy in `.agent-org/policies/security.md`
- Gate: a committed secret is an error that blocks the merge unconditionally
- Evidence: `deterministic_security_patterns`
- Constraint: reports locations and categories only; never reproduces
  credential material into events, brains, or logs

### `architecture-conformance`

Check a diff against recorded architecture decisions: layering violations,
forbidden imports across module boundaries, and changes that contradict an
accepted ADR without superseding it.

- Inputs: diff, import graph, ADRs under `.agent-org/templates/adr.md` conventions
- Gate: contradicting an accepted ADR without a superseding record is an error
- Evidence: `deterministic_adr_conformance`

## Build order

`security-review` first. It is the highest-consequence gate still missing,
and its checks are pattern-based rather than requiring the code graph that
`architecture-conformance` wants.
