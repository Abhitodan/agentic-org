# Rollback Policy

- A git checkpoint (commit + checkpoints/<id> tag) is created at workflow
  start and before any code modification, dependency change, migration,
  merge, or deployment.
- Reverting restores the working tree to a checkpoint without destroying
  history; reverted work remains reachable via its tags for analysis.
- Every experiment records its baseline checkpoint so KEEP/REVERT is a
  deterministic git operation.
- Irreversible actions (data deletion, external side effects) must be
  declared in advance and pass the destructive-action gate.
