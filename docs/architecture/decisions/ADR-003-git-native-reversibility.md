# ADR-003: Git-native checkpoints and worktree isolation

Status: Accepted (2026-07-31)

## Context
Every agent action must be reversible; agents must not touch protected
branches; Windows local-first rules out container sandboxes for the MVP.

## Decision
Checkpoints are git commits tagged `checkpoints/<id>`. Revert is
`reset --hard` to a tag - history and reverted work stay reachable.
Agent tasks get isolated worktrees on `agent/<task>` branches.

## Consequences
- Rollback demonstrated live: bad change checkpointed, tree restored,
  experiment tag preserved for analysis.
- No process/network sandboxing yet; that is Phase 6 (container/cloud
  sandbox), and the workspace manager is the seam where it plugs in.
