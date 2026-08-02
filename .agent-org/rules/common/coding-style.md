# Coding Style (common)

## Must always

- Readability first: code is read far more than written. Clear names beat
  comments; comments explain *why*, never *what*.
- KISS / YAGNI: simplest working solution; no speculative generality; add
  complexity only when a real requirement demands it.
- DRY with judgment: extract shared logic when it repeats *and* means the
  same thing. Do not merge coincidentally similar code.
- Prefer immutable updates over mutating shared state (see stack overlay for
  language idioms).
- Small focused files: 200–400 lines typical, 800 max. Split by
  responsibility, not by technical layer.
- Functions do one thing. Deep nesting (>4 levels) is a smell — use early
  returns and extract helpers.
- Naming: verb–noun for functions (`build_repo_map`, `validate_plan`),
  descriptive nouns for values. Single letters only for trivial indices.

## Must never

- Silently swallow errors. Empty `except`/`catch` blocks are defects.
- Leave dead code: commented-out blocks, unused imports, unreachable
  branches. Delete them; git preserves history.
- Add narration comments ("increment counter", "return result").
- Ship debug prints / `console.log`-style output in production paths.
- Invent new patterns when the repository already has an established one for
  the same problem. Follow the existing pattern or write an ADR to change it.

## Code smells to flag in review

| Smell | Threshold | Remedy |
| ----- | --------- | ------ |
| Long function | > 50 lines of logic | extract helpers |
| Long file | > 800 lines | split by responsibility |
| Deep nesting | > 4 levels | early returns |
| Boolean flag params | any | split functions |
| Shotgun surgery | one change touches many files repeatedly | consolidate module |
| Speculative hooks | "for future use" | delete (YAGNI) |
