# Git Workflow (common)

## Must always

- Work in isolated worktrees (`agent/<task-id>` branches); the protected
  branch is only changed by the gated merge node.
- Checkpoint before modification — every workflow start creates a
  `checkpoints/*` tag; risky operations checkpoint again.
- Conventional commit style: `feat(scope):`, `fix(scope):`, `test:`,
  `docs:`, `refactor:`. Message explains why, not just what.
- Keep RED/GREEN evidence discoverable: if checkpoints get squashed, copy
  the evidence summary into the merge commit or PR body.

## Must never

- Force-push or rewrite history on the protected branch.
- Commit with `--no-verify` or equivalent hook-skipping flags.
- Mix unrelated changes in one commit ("and also fixed…").
- Treat commits from other branches or older work as checkpoint evidence
  for the current task.

## History as evidence

Before risky edits to unfamiliar code, consult history first — the
`commit-archaeologist` skill returns structured `git log` provenance so the
reviewer can answer "why does this code exist" from extracted facts instead
of guessing.
