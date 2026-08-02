# AGENTS.md

Canonical agent governance lives in `.agent-org/` (vendor-neutral source of
truth; this file and any vendor-specific files are projections of it).

- Constitution: `.agent-org/constitution.md` - non-negotiable rules
- Agent roles: `.agent-org/agents/*.md` (role, model_class, tools)
- Policies: `.agent-org/policies/` (security, approvals, token, memory, rollback)
- Workflows: `.agent-org/workflows/*.yaml`
- Regenerate everything: `python scripts/bootstrap_org.py`

Rules that bind any agent working in this repository:

1. Never modify `main` directly; use a worktree/branch.
2. Never claim a test ran when it did not; success requires executed evidence.
3. Record material decisions in `docs/architecture/decisions/` (ADR).
4. Update the relevant feature brain after accepted changes.
5. Run `python -m pytest -q` before declaring work complete.
