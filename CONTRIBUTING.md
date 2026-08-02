# Contributing

Thank you — agentic-org grows fastest through **executable skills**, clearer demos, and honest bug reports.

## Good first contributions

- Add or harden a skill eval (`agentctl skill-eval <name>`)
- Clarify a persona card under `.agent-org/agents/` (gates, handoffs, ceremony role)
- Improve the 2-minute walkthrough or capture a cleaner Command Center screenshot
- File a bug with exact commands + `agentctl verify` output

## Workflow

1. Set up: `python -m venv .venv && ./.venv/Scripts/python.exe -m pip install -e ".[dev]"` (Unix: `source .venv/bin/activate` then `pip install -e ".[dev]"`).
2. Work on a branch; keep `main` clean.
3. Every change ships with tests; run `python -m pytest -q` (all green).
4. Material design choices get an ADR in `docs/architecture/decisions/`.
5. Upgraded skills/agents with real entrypoints or `skills:` frontmatter are authored work — bootstrap must not overwrite them.
6. No fabricated results: tests and docs state only what actually executed. Prefer updating `docs/LIMITATIONS.md` over marketing language.
7. New skills need `SKILL.md` + script + a registered eval — see `docs/SKILLS.md`.
