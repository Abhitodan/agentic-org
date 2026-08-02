# Coding Style — Python

> Extends [common/coding-style.md](../common/coding-style.md) with Python
> specifics. Where they conflict, this file wins.

Applies to: `**/*.py`

## Must always

- Type annotations on public functions; `from __future__ import annotations`
  in new modules.
- `pathlib.Path` over string paths; never concatenate paths with `+`.
- Dataclasses (`frozen=True` where practical) for structured values;
  TypedDict for dict-shaped state.
- f-strings for formatting; explicit `encoding="utf-8"` on every file
  read/write (Windows honesty).
- Narrow `except` clauses naming the expected exception types; re-raise or
  record — never `except: pass`.
- Module docstring stating the module's single responsibility.

## Idiom notes vs common rules

- In-place mutation of *locally owned* lists/dicts during construction is
  idiomatic Python and allowed; mutation of shared/passed-in structures is
  not.
- Comprehensions preferred over `map`/`filter` chains when they stay on one
  or two lines.

## Must never

- Mutable default arguments (`def f(x=[])`).
- Wildcard imports.
- `assert` for runtime validation in production paths (stripped under `-O`);
  raise explicit exceptions.
