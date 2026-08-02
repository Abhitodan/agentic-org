# Contributing

1. Set up: `python -m venv .venv && ./.venv/Scripts/python.exe -m pip install -e ".[dev]"` (Unix: `source .venv/bin/activate` then `pip install -e ".[dev]"`).
2. Work on a branch; keep `main` clean.
3. Every change ships with tests; run `python -m pytest -q` (all green).
4. Material design choices get an ADR in `docs/architecture/decisions/`.
5. Governance files under `.agent-org/` are generated — edit `scripts/bootstrap_org.py` and regenerate; do not hand-edit outputs.
6. No fabricated results: tests and docs state only what actually executed. Prefer updating `docs/LIMITATIONS.md` over marketing language.
