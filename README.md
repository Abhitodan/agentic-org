# agentic-org

<p align="center">
  <img src="docs/assets/hero-control-plane.svg" alt="agentic-org Mode A control plane: Humans approve. Agents execute. Everything leaves a trail." width="100%" />
</p>

<p align="center">
  <strong>Humans approve. Agents execute. Everything leaves a trail.</strong><br/>
  Local-first control plane for budgeted, auditable, reversible AI feature work.
</p>

<p align="center">
  <a href="#try-it-in-2-minutes"><img src="https://img.shields.io/badge/try%20it-2%20minutes-1a7f37?style=flat-square" alt="Try it" /></a>
  <a href="#use-case-bulk-member-import"><img src="https://img.shields.io/badge/use%20case-bulk%20import-0969da?style=flat-square" alt="Use case" /></a>
  <a href="#four-guarantees"><img src="https://img.shields.io/badge/fail%20closed-no%20fake%20LLM%20wins-cf222e?style=flat-square" alt="Fail closed" /></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-3776ab?style=flat-square" alt="Python 3.11+" />
</p>

---

Not a chat wrapper. A **workflow control plane** so humans and agents can ship features from intake through planning (Mode A) with four enforceable guarantees — and **never fabricate LLM success** when a model is unavailable.

## The difference (why people switch)

<p align="center">
  <img src="docs/assets/showcase/before-vs-after.svg" alt="Before ad-hoc agent chat vs after agentic-org Mode A control plane" width="100%" />
</p>

<p align="center">
  <img src="docs/assets/showcase/how-it-helps.svg" alt="What it does, how it works, how it helps" width="100%" />
</p>

| Without agentic-org | With agentic-org |
| ------------------- | ---------------- |
| Prompt → hope → maybe code | Intake → map → brain → **human gate** → plan → implement |
| Spend is invisible | Guardrails hard-stop on USD / tokens / tools |
| “Done” with no proof | Hash-chained events + `agentctl verify` |
| Hard to undo agent edits | Git checkpoints + one-click revert |
| Agents keep going past judgment calls | Plan / release **cannot** bypass humans |

## Live Command Center (real UI)

Captured from the included **bulk-member-import** use case — workflow paused at a human gate with budget `$0 / $8` still enforceable.

<p align="center">
  <img src="docs/assets/screenshots/demo-command-center.gif" alt="Animated demo of the Command Center: human gate, repo map, guardrails" width="100%" />
</p>

<details>
<summary><strong>Static screenshots</strong></summary>

**1. Human gate — agents stop; you decide**

![Human gate overview](docs/assets/screenshots/01-human-gate-overview.png)

**2. Repo map — what the system actually found**

![Repo map](docs/assets/screenshots/02-repo-map.png)

**3. Guardrails + gate events**

![Gates and guardrails](docs/assets/screenshots/03-gates-guardrails.png)

</details>

## Use case: bulk member import

**Goal:** Add bulk member import to a tiny enrollment sample app — with a human approval before planning continues.

**What you will see**

1. **Intake / Repo Map / Brain** run without inventing progress.
2. Workflow lands on **AWAITING_DECISION** (plan-approval human gate).
3. Command Center shows Agent Theater, Documents (charter / repo map), Guardrails, Checkpoints.
4. You approve/reject — agents cannot skip the gate.

Full walkthrough: [`docs/demo/bulk-member-import-walkthrough.md`](docs/demo/bulk-member-import-walkthrough.md)

## Try it in 2 minutes

```powershell
git clone https://github.com/Abhitodan/agentic-org.git
cd agentic-org
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

# Demo target repo
.\.venv\Scripts\python.exe scripts\create_sample_repo.py

# Mode A vertical slice (honest without a model key)
agentctl init
agentctl create-project enrollment-platform --repo .\examples\enrollment-sample
agentctl create-feature enrollment-platform bulk-member-import --objective "Add bulk member import"
agentctl run enrollment-platform bulk-member-import --budget-usd 8

agentctl status
agentctl verify
agentctl serve            # http://127.0.0.1:8787
```

macOS / Linux:

```bash
git clone https://github.com/Abhitodan/agentic-org.git
cd agentic-org
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python scripts/create_sample_repo.py
agentctl init
agentctl create-project enrollment-platform --repo ./examples/enrollment-sample
agentctl create-feature enrollment-platform bulk-member-import --objective "Add bulk member import"
agentctl run enrollment-platform bulk-member-import --budget-usd 8
agentctl serve   # http://127.0.0.1:8787
```

Open the Command Center, click the workflow in **AWAITING_DECISION**, review the charter / repo map, then:

```powershell
agentctl approve <workflow_id>
```

Optional LLM charter/plan quality (not required to try the product):

```powershell
copy .env.example .env
# put your Gemini API key in GEMINI_API_KEY
```

## Four guarantees

| Guarantee | What it means |
| --------- | ------------- |
| **Evidence over claims** | If the model cannot run, the workflow goes `BLOCKED` / waits honestly — never a fake completion |
| **Everything reversible** | Git checkpoints before modifications; restore without rewriting history |
| **Everything budgeted** | Workflows carry a budget; overspend is a hard stop |
| **Everything auditable** | Append-only, hash-chained events (`agentctl verify`) |

## How it helps (concrete)

- **Leads / staff engineers:** See cost, gates, and checkpoints before agent code lands on main.
- **ICs using coding agents:** Keep a reversible trail instead of a chat scrollback.
- **Teams evaluating “agentic” tools:** Fail-closed behavior is testable offline — clone and run without buying a model key.

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

More: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · [docs/PROJECT_SHOWCASE.md](docs/PROJECT_SHOWCASE.md) · [docs/RUNBOOK.md](docs/RUNBOOK.md)

## Limitations

See [docs/LIMITATIONS.md](docs/LIMITATIONS.md). High level: live model quality is yours to evaluate; no SSO; loopback-first command center; costs in `models.yaml` are estimates.

## Contributing / Security / License

- [CONTRIBUTING.md](CONTRIBUTING.md) — run `pytest` before PRs that touch guarantees  
- [SECURITY.md](SECURITY.md) — secrets only via environment variables  
- [LICENSE](LICENSE) — terms not yet finalized (placeholder)
