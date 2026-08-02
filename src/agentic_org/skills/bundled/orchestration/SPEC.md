# orchestration — specified, not yet built

Coordination skills for the orchestrator: who does what next, what must be
true at a handoff, and when to stop and escalate.

These directories contain no scripts on purpose. A stub skill that returns
`ok: true` is worse than a missing one, because the gate looks enforced.

## Planned skills

### `work-routing`

Assign a ready story to a persona deterministically from declared
capabilities, current WIP, and the story's components. Never routes to a
persona already at its WIP limit; never invents a capability a persona has
not declared.

- Inputs: ready stories, persona registry with capabilities and WIP, current assignments
- Gate: every ready story is either routed or reported as unroutable with a named reason
- Evidence: `deterministic_capability_routing`

### `handoff-contract`

Verify the artifacts a handoff requires are present before the receiving
persona starts. Planning to implementation requires an approved plan with
acceptance criteria; implementation to review requires a diff plus test
evidence; review to release requires an approved review with zero
unresolved errors.

- Inputs: from-persona, to-persona, artifact bundle
- Gate: missing required artifact blocks the handoff and names what is absent
- Evidence: `deterministic_handoff_completeness`

### `wip-limit-guard`

Enforce work-in-progress limits per persona and for the team. Starting new
work while at the limit is an error; the remedy is finishing, never raising
the limit silently.

- Inputs: current assignments, limits, proposed new assignment
- Gate: proposed assignment rejected when it breaches a limit
- Evidence: `deterministic_wip_enforcement`

### `escalation-protocol`

Decide whether a condition escalates to a human, using budget consumption,
confidence thresholds, policy triggers, and impediment age. Escalation is
computed, never left to whoever notices.

- Inputs: budget state, confidence, policy flags, impediment ledger
- Gate: any triggered threshold produces a mandatory escalation record
- Evidence: `deterministic_escalation_triggers`

### `ceremony-state-machine`

Validate the sprint cadence itself: ceremonies happened in a legal order,
each produced its required artifact, and no gate was skipped. Sprint review
cannot precede the sprint; planning cannot run without a refined backlog.

- Inputs: ceremony log with timestamps and produced artifacts
- Gate: illegal transitions and missing ceremony artifacts are errors
- Evidence: `deterministic_ceremony_sequence`

## Build order

`handoff-contract` and `wip-limit-guard` first — they gate work already
flowing through Mode A. `ceremony-state-machine` last, once the ceremony
skills have produced enough real artifacts to validate a sequence against.
