# Testing — Python

> Extends [common/testing.md](../common/testing.md) with pytest specifics.

Applies to: `**/*.py`

## Must always

- pytest with plain `assert`; fixtures via `tmp_path` for filesystem work —
  never write into the repository during tests.
- Markers for anything that leaves the process: `live_llm` for real model
  calls (skipped by default), network access mocked or absent.
- One behavior per test; parametrize instead of copy-pasting cases.
- Failure output must identify the case: use ids in `pytest.param` for
  parametrized tests.

## Command canon

```bash
python -m pytest -q --tb=line        # default gate
python -m pytest -q -m "not live_llm" # offline suite
```

The sandbox policy allowlists the pytest invocation; do not invent bespoke
runner wrappers per module.
