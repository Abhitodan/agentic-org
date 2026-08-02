---
name: commit-archaeologist
description: Why does this code exist? Structured git history for given paths — authors, dates, subjects — so risky edits start from provenance, not guesses.
category: discovery
personas:
  - repository-agent
  - reviewer-agent
triggers:
  - commit-archaeologist
  - code-review
network: none
entrypoint: scripts/archaeology.py:run
tools: []
---

# Commit Archaeologist

> Code that looks wrong is often load-bearing. Before "fixing" unfamiliar
> code, read its history: the commit that introduced it usually explains
> the constraint you cannot see.

## Guardrails

1. **Facts only.** The skill returns extracted `git log` records — no
   interpretation, no summarizing-away. Conclusions belong to the caller.
2. **Cite shas.** Any provenance claim built on this output must cite the
   commit that supports it.
3. **Correct repository detection.** Uses `git rev-parse
   --is-inside-work-tree` — works for worktrees and submodules; never
   guesses from `.git` existence.
4. **Bounded output.** Commit count capped at 100; this is the summary
   layer, not a dump.

## When to use

- Before risky edits to unfamiliar or legacy modules
- During review, when a diff deletes or rewrites long-standing behavior
- When a reviewer asks "why is it done this way?" — answer from history,
  not intuition

## When NOT to use

- On non-git directories (returns `ok: false`, no guessing)
- As a full blame/bisect replacement — drop to raw `git blame`/`git bisect`
  for line-level or regression hunts

## Inputs

| Arg | Type | Required | Validation |
| --- | ---- | -------- | ---------- |
| `repo_path` | path | yes | must exist; must be inside a work tree |
| `paths` | list | no | TypeError if not a list; blanks dropped |
| `max_commits` | int | no | default 20, capped at 100 |

## Workflow

1. Verify the directory is a git work tree (`rev-parse`).
2. Run `git log` with a stable tab-separated format (sha, author, date,
   subject), optionally scoped to paths.
3. Parse into structured records; return facts.

## Output contract

```json
{
  "ok": true,
  "history": [
    {"sha": "…", "author": "…", "date": "2026-07-30",
     "subject": "fix: guard empty import"}
  ],
  "path_count": 1,
  "reason": "",
  "evidence": "deterministic_git_history"
}
```

## Reading the record — what to look for

- **Fix clusters**: several `fix:` commits on one file = fragile area;
  raise implementation risk.
- **Recent rewrites**: a fresh refactor plus your change = coordinate, do
  not silently overwrite intent.
- **Old untouched code + failing assumptions**: the constraint probably
  lives elsewhere (config, caller); widen the investigation.

## Failure modes

| Condition | Behavior |
| --------- | -------- |
| Not a git repository | `ok: false`, reason recorded |
| git binary unavailable | `ok: false`, reason recorded |
| Paths with no history | `ok: true`, empty history — honest empty |

## Anti-patterns

- WRONG: "this looks dead, deleting" without history.
  CORRECT: check when it last changed and why it was added; then decide.
- WRONG: quoting history conclusions without shas.
  CORRECT: every provenance claim cites the commit that supports it.

## Quality checklist

- [ ] Provenance claims in downstream artifacts cite shas from `history`
- [ ] Path scoping used when investigating specific files
- [ ] `ok: false` reasons surfaced to the caller, not swallowed
