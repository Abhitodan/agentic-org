# verification — remaining skills

`test-evidence` is shipped. The four below are specified and not yet built.

## Planned skills

### `test-strategy`

Check that a story's declared tests cover its acceptance criteria one for
one. A criterion with no corresponding test is a gap; a test suite with no
traceability to criteria is untargeted.

- Inputs: acceptance criteria, test declarations
- Gate: any criterion without a mapped test is an error
- Evidence: `deterministic_ac_test_mapping`

### `edge-case-canon`

Apply a fixed catalogue of edge classes (empty, boundary, duplicate, unicode,
concurrent, permission-denied, oversized) to the inputs a story names, and
report which classes are unaddressed. The catalogue is fixed so coverage is
comparable across stories.

- Inputs: story inputs and their types, existing tests
- Gate: unaddressed classes reported; the team decides which are in scope
- Evidence: `deterministic_edge_class_coverage`

### `regression-guard`

Verify a fixed defect has a test that fails without the fix. Confirms the
test genuinely reproduces the defect rather than merely passing afterwards.

- Inputs: defect record, test id, pre-fix and post-fix test runs
- Gate: a test that passes before the fix is not a regression test
- Evidence: `deterministic_regression_proof`

### `performance-budget`

Compare measured latency, memory, and query counts against declared budgets.
Budgets come from acceptance criteria; measurements come from real runs.

- Inputs: declared budgets, measurement output
- Gate: a breached budget is an error; a missing measurement is not a pass
- Evidence: `deterministic_budget_comparison`

## Build order

`test-strategy` first — it closes the loop between `product/` criteria and
the test evidence the review gate already demands.
