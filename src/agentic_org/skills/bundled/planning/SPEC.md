# planning — remaining skills

`feature-planning` is shipped. The three below are specified and not yet
built; their directories are intentionally empty of scripts.

## Planned skills

### `sprint-capacity-planner`

Per-person capacity from working days, leave, ceremony overhead, and
support rotation — the input `ceremonies/sprint-planning` currently takes as
a single `member_days` figure. Computes availability rather than accepting
an assertion.

- Inputs: roster, calendar, leave, ceremony hours, support rotation
- Gate: a person allocated beyond their available days is an error
- Evidence: `deterministic_capacity_breakdown`

### `dependency-mapper`

Build the dependency graph across stories and detect cycles, cross-team
blocks, and critical-path length. A cycle is an error; the sprint cannot be
ordered.

- Inputs: stories with dependency declarations
- Gate: cycles and unresolvable external dependencies block planning
- Evidence: `deterministic_dependency_graph`

### `risk-register`

Validate that risks carry a likelihood, an impact, an owner, and a mitigation
with a trigger condition. A risk with no trigger is a worry, not a plan.

- Inputs: risk entries
- Gate: risks missing owner, mitigation, or trigger are errors
- Evidence: `deterministic_risk_completeness`

## Build order

`dependency-mapper` first — sprint ordering depends on it and cycle
detection is well-defined graph work.
