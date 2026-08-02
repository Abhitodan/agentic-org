---
name: Implement coding node behind worktrees
about: Extend Mode A past plan into reversible implementation
labels: enhancement, architecture
---

## Problem

The runner stops at planning. User value for an “organization that ships software” requires an implementation step with tests as evidence.

## Proposal

- Add an `implement` node that creates an isolated git worktree
- Require failing→passing tests (or explicit waiver + human gate) before success
- Checkpoint before edits; never claim success on generation alone

## Acceptance criteria

- [ ] Worktree isolation test (existing pattern in `tests/test_git_workspace.py`)
- [ ] Success event only after test command exit 0
- [ ] Budget charges for tool calls
- [ ] Eval case covering fail-closed when tests fail
- [ ] Docs updated: README verified table + LIMITATIONS

## References

- `docs/ROADMAP.md`
- `docs/product/implementation-backlog.md`
