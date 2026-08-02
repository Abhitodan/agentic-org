# implementation — remaining skills

`implementation` is shipped. The four below are specified and not yet built.

## Planned skills

### `tdd-cycle`

Enforce the red/green sequence with evidence: the test ran and failed before
the change, and ran and passed after it. A test that never failed proves
nothing about what it tests.

- Inputs: test id, pre-change run, post-change run
- Gate: a missing red phase is an error, not a formality
- Evidence: `deterministic_red_green_proof`

### `refactor-safety`

Confirm a change claimed as a refactor did not alter behavior: the test set
is unchanged, all tests pass before and after, and no acceptance criterion
was touched.

- Inputs: diff, test set before and after, criteria
- Gate: a modified test inside a claimed refactor is an error
- Evidence: `deterministic_behavior_preservation`

### `database-migration`

Check a migration is reversible or explicitly declares why it is not, runs
inside a transaction where the engine supports it, and has a verified
down-path. Data loss requires a human gate.

- Inputs: migration files, engine capabilities
- Gate: destructive operations without an approval record are blocked
- Evidence: `deterministic_migration_reversibility`

### `api-contract`

Detect breaking changes against the published contract: removed endpoints,
narrowed types, new required fields, changed status codes. Breaking changes
require a version bump and a deprecation record.

- Inputs: previous and current schema
- Gate: an unversioned breaking change is an error
- Evidence: `deterministic_contract_diff`

## Build order

`tdd-cycle` first — it uses the run/hash machinery `test-evidence` already
provides and directly strengthens the review gate.
