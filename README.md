# agentic-org

<p align="center">
  <img src="docs/assets/showcase/03-mode-a-control-plane.png" alt="agentic-org: Humans approve. Agents execute. Everything leaves a trail." width="100%" />
</p>

<p align="center">
  <strong>Humans approve. Agents execute. Everything leaves a trail.</strong><br/>
  The local-first control plane for AI coding agents — budgets, human gates, reversible git, hash-chained audit.
</p>

<p align="center">
  <a href="https://github.com/Abhitodan/agentic-org/stargazers"><img src="https://img.shields.io/github/stars/Abhitodan/agentic-org?style=for-the-badge&logo=github&color=007AFF" alt="GitHub stars" /></a>
  <a href="https://github.com/Abhitodan/agentic-org/network/members"><img src="https://img.shields.io/github/forks/Abhitodan/agentic-org?style=for-the-badge&color=6e7781" alt="GitHub forks" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-1a7f37?style=for-the-badge" alt="MIT License" /></a>
  <a href="#try-it-in-2-minutes"><img src="https://img.shields.io/badge/try%20it-2%20minutes-0969da?style=for-the-badge" alt="Try it" /></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11%2B-3776ab?style=flat-square" alt="Python 3.11+" />
  <img src="https://img.shields.io/badge/skills-31%20executable-007AFF?style=flat-square" alt="31 skills" />
  <img src="https://img.shields.io/badge/personas-18%20roles-6e7781?style=flat-square" alt="18 personas" />
  <img src="https://img.shields.io/badge/fail%20closed-no%20fake%20LLM%20wins-cf222e?style=flat-square" alt="Fail closed" />
  <img src="https://img.shields.io/badge/local%20first-no%20cloud%20required-1a7f37?style=flat-square" alt="Local first" />
</p>

---

### Stop hoping your coding agent behaved. Prove it.

Most “agentic” tools are chat with tools. **agentic-org is the missing control plane**: a Scrum-shaped software org of AI personas that only advances when evidence, budgets, and humans say so.

| Pain today | What agentic-org enforces |
| ---------- | ------------------------- |
| Prompt → hope → maybe code | Intake → map → brain → **human gate** → plan → implement → review |
| Invisible spend | Hard-stop budgets (USD / tokens / tools) |
| “Done” with no proof | Hash-chained events + `agentctl verify` |
| Irreversible agent edits | Git checkpoints + one-command restore |
| Agents skip judgment calls | Plan / release **cannot** bypass humans |
| Prompt-only “skills” | **21 executable skills** — script + eval or it does not ship |

**Star this repo** if you want AI agents that are auditable by default — not just clever in a demo.

---

## See it live (30 seconds)

Real Command Center from the included bulk-member-import demo — workflow paused at a human gate, budget still enforceable, no invented LLM success.

<p align="center">
  <img src="docs/assets/screenshots/demo-command-center.gif" alt="Command Center demo: human gate, repo map, guardrails" width="100%" />
</p>

<details>
<summary><strong>Static screenshots</strong></summary>

![Human gate](docs/assets/screenshots/01-human-gate-overview.png)

![Repo map](docs/assets/screenshots/02-repo-map.png)

![Gates and guardrails](docs/assets/screenshots/03-gates-guardrails.png)

</details>

---

## Why teams switch

<p align="center">
  <img src="docs/assets/showcase/01-before-after.png" alt="Before ad-hoc agent chat vs after agentic-org" width="100%" />
</p>

<p align="center">
  <img src="docs/assets/showcase/02-how-it-helps.png" alt="What, how, and why agentic-org helps" width="100%" />
</p>

**Built for**

- **Engineering leads** who need cost, gates, and checkpoints before agent code hits `main`
- **ICs using Cursor / Claude / Codex** who want a trail instead of chat scrollback
- **Platform / AI eng** evaluating agent frameworks who need fail-closed behavior offline
- **Agile teams** who want Scrum ceremonies as software, not slide decks

---

## Try it in 2 minutes

No API key required for the honest Mode A path. Clone, run, open the UI, approve the gate.

<details open>
<summary><strong>Windows (PowerShell)</strong></summary>

```powershell
git clone https://github.com/Abhitodan/agentic-org.git
cd agentic-org
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe scripts\create_sample_repo.py

agentctl init
agentctl create-project enrollment-platform --repo .\examples\enrollment-sample
agentctl create-feature enrollment-platform bulk-member-import --objective "Add bulk member import"
agentctl run enrollment-platform bulk-member-import --budget-usd 8

agentctl status
agentctl verify
agentctl serve   # http://127.0.0.1:8787
```

</details>

<details>
<summary><strong>macOS / Linux</strong></summary>

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

agentctl status
agentctl verify
agentctl serve   # http://127.0.0.1:8787
```

</details>

Open the Command Center → open the workflow in **AWAITING_DECISION** → review charter / repo map → approve:

```bash
agentctl approve <workflow_id>
```

Optional (better charter/plan text only — not required to try the product):

```powershell
copy .env.example .env   # set GEMINI_API_KEY
```

Full walkthrough: [`docs/demo/bulk-member-import-walkthrough.md`](docs/demo/bulk-member-import-walkthrough.md)

---

## Four guarantees (non-negotiable)

| Guarantee | Meaning |
| --------- | ------- |
| **Evidence over claims** | No model → `BLOCKED` / wait honestly — never a fake “done” |
| **Everything reversible** | Git checkpoints before edits; restore without rewriting history |
| **Everything budgeted** | Overspend is a hard stop, not a warning toast |
| **Everything auditable** | Append-only, hash-chained events (`agentctl verify`) |

---

## Skills, personas, orchestration

Not a prompt dump. Every skill is executable software. Personas bind skills and list gates. Orchestration coordinates without skipping humans.

<p align="center">
  <img src="docs/assets/showcase/07-skill-catalog.png" alt="Skill catalog — 21 executable skills across nine categories" width="100%" />
</p>

<p align="center">
  <img src="docs/assets/showcase/08-agent-personas.png" alt="18 agent personas with bound skills and gates" width="100%" />
</p>

<p align="center">
  <img src="docs/assets/showcase/09-orchestration.png" alt="Orchestration around the Mode A runner" width="100%" />
</p>

| Layer | Ships today |
| ----- | ----------- |
| **Skills** | 31 executable skills — discovery (incl. code graph), product, planning, implementation, verification, review, delivery, ceremonies, orchestration |
| **Personas** | 18 role cards — domain context, bound skills, ceremony participation, handoffs |
| **Orchestration** | Mode A runner + human gates + budgets + hash-chained events |

Catalog: [`docs/SKILL_CATALOG.md`](docs/SKILL_CATALOG.md) · Install: [`docs/SKILLS.md`](docs/SKILLS.md)

<details>
<summary><strong>Architecture & Mode A diagrams</strong></summary>

<p align="center">
  <img src="docs/assets/showcase/04-system-architecture.png" alt="System architecture" width="100%" />
</p>

<p align="center">
  <img src="docs/assets/showcase/05-mode-a-flow.png" alt="Mode A flow with human gates" width="100%" />
</p>

<p align="center">
  <img src="docs/assets/showcase/06-evidence-path.png" alt="Evidence path to agentctl verify" width="100%" />
</p>

```text
agentctl / command-center UI
        │
        ▼
   FastAPI + context ──► SQLite (events, workflows, budgets)
        │
        ▼
   LangGraph Mode A ──► skills · personas · model gateway
        │
        ▼
   Target git repo (checkpoints / worktrees)
```

More: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

</details>

---

## Quick map of the repo

| Path | What it is |
| ---- | ---------- |
| `agentctl` | CLI — init, run, approve, verify, serve |
| `.agent-org/skills/` | Categorized executable skills |
| `.agent-org/agents/` | Persona cards (mission, skills, gates) |
| `docs/SKILL_CATALOG.md` | Full skill index |
| `examples/` | Sample target repos for demos |
| `docs/demo/` | End-to-end walkthroughs |

---

## Roadmap (high signal)

- [x] Mode A control plane (gates, budgets, audit, checkpoints)
- [x] Live Command Center
- [x] 31 executable skills + 18 personas (incl. delivery + orchestration)
- [x] Code graph / impact + review-pack (`code-intelligence`)
- [x] `agentctl skill-install` for Cursor / Claude / Codex / project

Full plan: [`docs/ROADMAP_SKILLS_AGENTS_PLATFORM.md`](docs/ROADMAP_SKILLS_AGENTS_PLATFORM.md)

---

## Star, fork, contribute

If this solves a pain you already have with coding agents:

1. **[Star the repo](https://github.com/Abhitodan/agentic-org)** so more engineers find a fail-closed alternative to chat wrappers  
2. **Fork** and run the 2-minute demo — open an issue if anything fails on your machine  
3. **Contribute** — skills, persona packs, and docs are the highest-leverage PRs ([CONTRIBUTING.md](CONTRIBUTING.md))

Good first contributions: a skill eval, a persona clarification, a clearer walkthrough screenshot, or a bug report with `agentctl verify` output.

---

## Limitations (honest)

See [docs/LIMITATIONS.md](docs/LIMITATIONS.md). Short version: live model quality is yours to evaluate; no SSO; Command Center is loopback-first; model costs in `models.yaml` are estimates.

---

## License & security

- [LICENSE](LICENSE) — **MIT**
- [SECURITY.md](SECURITY.md) — secrets only via environment variables
- [CONTRIBUTING.md](CONTRIBUTING.md) — `pytest` green before PRs that touch guarantees

<p align="center">
  <sub>Built for people who ship with agents — and still sleep at night.</sub><br/>
  <a href="https://github.com/Abhitodan/agentic-org">★ Star agentic-org on GitHub</a>
</p>
