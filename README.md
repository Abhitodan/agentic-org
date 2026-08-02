# agentic-org

<p align="center">
  <img src="docs/assets/hero-control-plane.svg" alt="agentic-org Mode A control plane: Humans approve. Agents execute. Everything leaves a trail." width="100%" />
</p>

<p align="center">
  <strong>Humans approve. Agents execute. Everything leaves a trail.</strong><br/>
  Local-first control plane for budgeted, auditable, reversible AI feature work.
</p>

<p align="center">
  <a href="#quick-start"><img src="https://img.shields.io/badge/quick%20start-2%20min-1a7f37?style=flat-square" alt="Quick start" /></a>
  <a href="#four-guarantees"><img src="https://img.shields.io/badge/fail%20closed-no%20fake%20LLM%20wins-0969da?style=flat-square" alt="Fail closed" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-TBD-6e7781?style=flat-square" alt="License TBD" /></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-3776ab?style=flat-square" alt="Python 3.11+" />
</p>

---

Not a chat wrapper. A **workflow control plane** so humans and agents can ship features from intake through planning (Mode A) with four enforceable guarantees — and **never fabricate LLM success** when a model is unavailable.

## Four guarantees

| Guarantee | What it means |
| --------- | ------------- |
| **Evidence over claims** | If the model cannot run, the workflow goes `BLOCKED` with an auditable reason — never a fake completion |
| **Everything reversible** | Git checkpoints (commit + tag) before modifications; restore without rewriting history |
| **Everything budgeted** | Workflows carry a budget; overspend is a hard stop |
| **Everything auditable** | Append-only, hash-chained events (`agentctl verify`) |

## Why this exists

Ad-hoc agent coding sessions lose the trail, spend silently, and cannot be rolled back safely.

**Built for** engineers and tech leads who want local AI-assisted feature work with observability, budget caps, and human approval gates.

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

# Demonstration target repository
.\.venv\Scripts\python.exe scripts\create_sample_repo.py

# Mode A vertical slice (blocks honestly without a model key)
agentctl init
agentctl create-project enrollment-platform --repo .\examples\enrollment-sample
agentctl create-feature enrollment-platform bulk-member-import --objective "Add bulk member import"
agentctl run enrollment-platform bulk-member-import --budget-usd 8

agentctl status
agentctl verify
agentctl serve            # http://127.0.0.1:8787
```

On macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python scripts/create_sample_repo.py
agentctl init
agentctl create-project enrollment-platform --repo ./examples/enrollment-sample
agentctl create-feature enrollment-platform bulk-member-import --objective "Add bulk member import"
agentctl run enrollment-platform bulk-member-import --budget-usd 8
agentctl serve
```

Enable LLM charter/plan steps with `.env` (from `.env.example`):

```powershell
copy .env.example .env
# put your Gemini API key in GEMINI_API_KEY (https://aistudio.google.com/apikey)
```

Optional: set `AGENTIC_ORG_API_TOKEN` so mutating `/api/*` calls require
`Authorization: Bearer <token>` (or `X-Agentic-Org-Token`). For the web UI,
store the same value in `localStorage.agentic_org_api_token`.

## Minimal working example

```powershell
agentctl map-repository .\examples\enrollment-sample
agentctl run enrollment-platform bulk-member-import --budget-usd 8
agentctl audit --type workflow.transition
```

Without a model key the run reaches `BLOCKED` after writing a real repo map
and feature brain — see `tests/test_workflow_e2e.py`.

## Architecture overview

```text
agentctl / command-center UI
        │
        ▼
   FastAPI + context wiring ──► SQLite (events, workflows, budgets)
        │
        ▼
   LangGraph Mode A runner ──► repo intel, feature brain, model gateway
        │
        ▼
   Target git repository (checkpoints / worktrees)
```

Governance trees live under `.agent-org/` (constitution, policies, agent
role docs, schemas).

Details:

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/DOCUMENTATION.md](docs/DOCUMENTATION.md)
- [docs/PROJECT_SHOWCASE.md](docs/PROJECT_SHOWCASE.md)
- [docs/RUNBOOK.md](docs/RUNBOOK.md)
- [docs/CAPABILITY_MATRIX.md](docs/CAPABILITY_MATRIX.md)

## Limitations

See [docs/LIMITATIONS.md](docs/LIMITATIONS.md). High level:

- Live model charter/plan/implement **quality** is unverified without your own API key and evaluation.
- Command center has **no SSO**; default bind is loopback.
- Cost figures in `.agent-org/models.yaml` are estimates until reconciled with provider billing.

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Run `pytest` before proposing changes
that touch the core guarantees.

## Security

See [SECURITY.md](SECURITY.md). Secrets belong in environment variables only
(never commit `.env`).

## License

See [LICENSE](LICENSE). License terms are not yet finalized.

## Layout

```text
.agent-org/     governance: constitution, policies, agents, skills, workflows
src/agentic_org core platform
apps/           command center dashboard
projects/       project and feature brains (git-versioned memory)
examples/       demonstration target repo (generated by script)
docs/           product and architecture docs
tests/          pytest suite
scripts/        bootstrap_org, create_sample_repo
```
