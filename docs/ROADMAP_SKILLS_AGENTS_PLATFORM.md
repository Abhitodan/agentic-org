# Platform roadmap: skills, agents, and instructions

Date: 2026-08-02  
Status: Phase 0 complete; Phase 2 complete (SWE skill pack + Mode A review node);
Phase 2.5 complete (categorized catalog, `product/` and `ceremonies/` packs, persona cards)  
Audience: Make agentic-org a development platform anyone can run, with skills/agents that match or beat market bar.

**Catalog:** `docs/SKILL_CATALOG.md` is the live index of shipped and specified skills.

## Executive verdict

agentic-org already has the **control-plane spine** most skill packs lack:

- Mode A FSM + human gates  
- Budget hard-stops  
- Hash-chained audit events  
- Git checkpoints / revert  
- MCP deny-by-default gateway  
- Process sandbox (partial)  
- Command Center observability  

What it lacks vs the market is **depth of skills and agents**:

| Area | Today in agentic-org | Market bar |
| ---- | -------------------- | ---------- |
| Skills | 4 stubs (`SKILL.md` + empty `scripts/` / `references/`) | Executable scripts + on-demand references + evals ([awesome-llm-apps agent_skills](https://github.com/Shubhamsaboo/awesome-llm-apps/tree/main/agent_skills)) |
| Agents | 18 thin role cards | Role + tools + verification gates + model-tier routing |
| Code intel | Deterministic repo map + sparse vectors + PageIndex | Persistent AST/code graph + impact queries ([code-review-graph](https://github.com/tirth8205/code-review-graph), [graphify](https://github.com/Graphify-Labs/graphify)) |
| Governance | Policies + gates + redact + sandbox allowlist | Policy engine as real control surface, privilege rings, compliance verify ([agent-governance-toolkit](https://github.com/microsoft/agent-governance-toolkit)) |
| Orchestration | Hardcoded Mode A runner | Advisor / worker tiers, subagents, durable runs ([deer-flow](https://github.com/bytedance/deer-flow), [Prefect](https://github.com/PrefectHQ/prefect)) |
| Skill catalog | Tiny | Large curated catalog with install paths ([claude-skills](https://github.com/alirezarezvani/claude-skills)) — adopt structure, not bloat |
| External research | None | Opt-in reach / synthesis skills ([Agent-Reach](https://github.com/Panniantong/Agent-Reach), [last30days-skill](https://github.com/mvanhorn/last30days-skill)) |
| Automation language | YAML workflows (mostly aspirational) | Clear, auditable playbook semantics ([Ansible](https://github.com/ansible/ansible) inspiration only) |

**Non-negotiable product rule:** do not become a prompt dump. Every skill must earn its place with scripts and checkable evidence — same bar as [awesome-llm-apps agent_skills](https://github.com/Shubhamsaboo/awesome-llm-apps/tree/main/agent_skills).

---

## Source map (what to steal / what to ignore)

### A. Skill packaging & quality bar
**Sources:** [awesome-llm-apps/agent_skills](https://github.com/Shubhamsaboo/awesome-llm-apps/tree/main/agent_skills), [claude-skills](https://github.com/alirezarezvani/claude-skills), [hermes-agent](https://github.com/NousResearch/hermes-agent)

| Extract | Why |
| ------- | --- |
| `SKILL.md` + `scripts/` + `references/` + evals | Skills become software, not essays |
| Advisor–orchestrator–worker + verification gates | Cheaper models for parallel work; strong model only at commitment boundaries |
| Scope-creep detector pattern | Diff vs stated objective before merge |
| Commit archaeologist pattern | Intent from git history for risky edits |
| Dependency-doctor pattern | Deterministic manifest autopsy |
| Multi-agent install layout (`.agents/skills/`, Cursor/Claude paths) | Platform usable by anyone’s coding agent |
| Ignore | Marketing skill spam, untested prompt packs, network-by-default skills |

### B. Code intelligence
**Sources:** [code-review-graph](https://github.com/tirth8205/code-review-graph), [graphify](https://github.com/Graphify-Labs/graphify)

| Extract | Why |
| ------- | --- |
| Persistent local code graph | Review/implement agents read only what matters |
| AST-first deterministic edges + EXTRACTED vs INFERRED tags | Aligns with fail-closed / evidence culture |
| MCP tools: impact, blast radius, review pack | Wire into Mode A map / implement / review nodes |
| Ignore | Replacing our event/audit store with a vector DB; cloud-only graphs |

### C. Governance & runtime trust
**Source:** [agent-governance-toolkit](https://github.com/microsoft/agent-governance-toolkit)

| Extract | Why |
| ------- | --- |
| Policy engine as control surface (not “please follow rules”) | Matches our constitution/policies ambition |
| Privilege rings for sandbox | Deepens `sandbox/` beyond argv allowlist |
| Compliance verify CLI (`agt verify` analogue → `agentctl governance-check`) | Ship trust evidence |
| MCP gateway + identity ideas | We already have deny-by-default; tighten grants/trust tiers |
| Ignore | Copying their full product surface; security theater docs without code |

### D. Long-horizon harness & memory
**Sources:** [deer-flow](https://github.com/bytedance/deer-flow), [hermes-agent](https://github.com/NousResearch/hermes-agent)

| Extract | Why |
| ------- | --- |
| Sandbox + skills + subagents + memory as harness layers | Clear mental model for “anyone can develop” |
| Message gateway / channel adapters (later) | Optional surface, not core Mode A |
| Growing personal/project memory with retention | Extends `.agent-org/memory` |
| Ignore | Becoming a general chat SuperAgent; diluting Mode A |

### E. Durable orchestration & automation clarity
**Sources:** [Prefect](https://github.com/PrefectHQ/prefect), [Ansible](https://github.com/ansible/ansible)

| Extract | Why |
| ------- | --- |
| Explicit retries, caching, observability of steps | Mode A nodes should be durable/resumable with clear state |
| Human-readable automation semantics | Workflow YAML should mean what it says (we already test alignment) |
| Server UI for runs | We have Command Center — keep deepening it |
| Ignore | Replacing LangGraph with Prefect; becoming infra-CM |

### F. External research skills (opt-in)
**Sources:** [Agent-Reach](https://github.com/Panniantong/Agent-Reach), [last30days-skill](https://github.com/mvanhorn/last30days-skill)

| Extract | Why |
| ------- | --- |
| Structured research → grounded brief skill | Domain analyst / planning enrichment |
| Declared network use + sandbox | Never silent egress |
| Ignore | Bundling scrapers as default; any skill that hides network |

---

## Current inventory (baseline)

### Skills
| Skill | Status |
| ----- | ------ |
| `repository-analysis` | Executable — Mode A map |
| `feature-planning` | Executable — Mode A plan grounding |
| `implementation` | Executable — Mode A implement (mono) |
| `code-review` | Executable — Mode A `review` before merge |
| `scope-creep-detector` | Executable — used by review + CLI |
| `commit-archaeologist` | Executable — CLI / review context |
| `dependency-doctor` | Executable — CLI / planning |
| `test-evidence` | Executable — implement/review evidence |

### Agents (role cards)
18 agents under `.agent-org/agents/`. Skills-bound: `repository-agent`, `planning-agent`, `backend-agent`, `frontend-agent`, `reviewer-agent`.

### Platform modules already valuable
`orchestrator/runner.py`, `core/{budget,events,state_machine}`, `sandbox/`, `mcp/`, `memory/graph.py`, `repo_intel/`, `retrieval/`, `coding/`, Command Center.

---

## Skill standard (applies to every phase)

Every skill shipped under `.agent-org/skills/<name>/` MUST have:

1. **`SKILL.md`** — frontmatter (`name`, `description`, `triggers`, `tools`, `network: none|declared`), when to use / not use, inputs/outputs, failure modes  
2. **`scripts/`** — at least one deterministic entrypoint the runner/CLI can call  
3. **`references/`** — deep material loaded on demand (not stuffed into the prompt)  
4. **`evals/` or `tests/skills/`** — executable check on real or fixture inputs  
5. **Events** — skill invocations emit audit events (`skill.started`, `skill.finished`, `skill.failed`)  
6. **Budget** — charges iterations/tool calls through existing budget object  
7. **No secrets** — env only; skill never writes keys into brains/events  

Agent cards MUST reference skills by name and list **verification gates** before commitment actions.

---

## Phased delivery

### Phase 0 — Skill & agent platform foundation
**Goal:** Make skills first-class software inside agentic-org.  
**Context:** Packaging, discovery, runner hooks, docs.

| Work item | Detail |
| --------- | ------ |
| P0.1 Skill schema | JSON schema for skill frontmatter; `agentctl skill-list` / `skill-show` |
| P0.2 Skill loader | Load from `.agent-org/skills` (+ optional project `.agents/skills`) |
| P0.3 Runner hook | Mode A nodes resolve skill by name; fail closed if script missing |
| P0.4 Event + budget wiring | All skill runs audited and budgeted |
| P0.5 Agent card upgrade | Template: mission, skills[], gates[], model_class, stop conditions |
| P0.6 Dual install docs | How humans use `agentctl` + how Cursor/Claude load the same skills |
| P0.7 Skill eval harness | `pytest tests/skills` + `agentctl skill-eval <name>` |

**Exit criteria:** One upgraded skill (e.g. `repository-analysis`) has real script + eval; runner invokes it; events prove it. ✅

**Done in tree:** `src/agentic_org/skills/{schema,loader,runner}.py`, bundled skill under `skills/bundled/`, CLI `skill-list|show|run|eval`, bootstrap preserves upgraded skills, e2e uses package fallback when org skills absent.

**Sources:** awesome-llm-apps bar, claude-skills install layout, hermes growth model (memory of skill use later).

---

### Phase 1 — Code intelligence context (graph)
**Goal:** Agents stop grepping blindly; map/review/implement use a persistent local graph.  
**Context:** Repo intel + retrieval + MCP.

| Work item | Detail |
| --------- | ------ |
| P1.1 AST graph builder | tree-sitter (or adopt/adapt patterns from graphify / code-review-graph) into `.agent-org/state/code-graph` |
| P1.2 Edge provenance | Tag EXTRACTED vs INFERRED; never claim certainty on inferred |
| P1.3 MCP tools | `graph.query`, `graph.impact`, `graph.review_pack` behind McpGateway grants |
| P1.4 Mode A map node | Prefer graph rebuild/query over ad-hoc walk where available |
| P1.5 Skill: `code-intelligence` | Scripts wrap index/query; references document query language |
| P1.6 Benchmark | Context-token reduction on review fixture (inspired by code-review-graph evals) |

**Exit criteria:** Review skill can request impact subgraph for a diff; offline fixture shows fewer files read with equal finding coverage.

**Sources:** [graphify](https://github.com/Graphify-Labs/graphify), [code-review-graph](https://github.com/tirth8205/code-review-graph).

---

### Phase 2 — Core SWE skills (executable pack)
**Goal:** Depth for the default development loop anyone runs.  
**Context:** Skills only (agents updated to bind them).

| Skill | Scripts / behavior | Source inspiration |
| ----- | ------------------ | ------------------ |
| `repository-analysis` | Repo map + graph index + languages/tests report | graphify, our mapper |
| `feature-planning` | Charter/plan grounding checklist; AC extraction | our brain + awesome planning patterns |
| `implementation` | Apply actions with path containment + test gate | our implementer |
| `code-review` | Diff vs AC + impact graph + test evidence required | code-review-graph + scope-creep |
| `scope-creep-detector` | Diff vs objective; keep/split/justify | awesome-llm scope-creep-detector |
| `commit-archaeologist` | Why this code exists from git history | awesome-llm commit-archaeologist |
| `dependency-doctor` | Manifest autopsy (stdlib shadow, unpinned, conflicts) | awesome-llm dependency-doctor |
| `test-evidence` | Run declared tests; attach junit/log hashes to events | our guarantees |

**Exit criteria:** Mode A path uses these skills end-to-end on enrollment-sample; each has an eval. ✅ (scripts + `skill-eval` + Mode A `review` node; hybrid LLM still generates plan/actions)

**Sources:** [awesome-llm-apps agent_skills](https://github.com/Shubhamsaboo/awesome-llm-apps/tree/main/agent_skills).

**Spec / plan:** `docs/superpowers/specs/2026-08-02-phase2-swe-skills-design.md`, `docs/superpowers/plans/2026-08-02-phase2-swe-skills.md`.

---

### Phase 2.5 — Categorized catalog + agile operating skills
**Goal:** Cover the whole Scrum delivery loop, not just the coding middle of it.  
**Context:** Skill taxonomy, agile packs, persona binding.

| Work item | Detail |
| --------- | ------ |
| P2.5.1 Categories | Loader discovers `skills/<category>/<skill>/`; flat layout still works; duplicate names in one root raise |
| P2.5.2 Schema | `category`, `personas`, `domain` on the manifest; `skill-list --grouped/--category/--persona` |
| P2.5.3 Shared primitives | `src/agentic_org/agile/` — story parsing, finding envelope, estimation math, parsed once not six times |
| P2.5.4 `product/` pack | story-authoring, acceptance-criteria-forge, story-splitting, backlog-prioritization, definition-of-ready-gate, epic-decomposition |
| P2.5.5 `ceremonies/` pack | sprint-planning, standup-synthesis, backlog-refinement, sprint-review, retrospective, velocity-analytics, impediment-tracker |
| P2.5.6 Eval registry | `cli/skill_evals.py`; a skill without an eval fails the build |
| P2.5.7 Persona cards | 18 agent cards carry domain context, bound skills, gates, ceremony role, handoffs |
| P2.5.8 Remaining categories | `SPEC.md` per category stating the gate each planned skill enforces — no stub scripts |

**Design choice:** ceremony skills satisfy the executable-only rule by shipping
deterministic *validators*. The skill checks that a retrospective action has an
owner, a due sprint, and a measurable change; the facilitation judgment stays
with the persona. No exception was carved into the runner.

**Exit criteria:** 21 skills across 8 categories, each with a registered eval;
`skill-list --grouped` renders the catalog; full suite green. ✅

---

### Phase 3 — Agent operating model (roles that actually operate)
**Goal:** Agents are more than markdown; they are budgeted operators with verification.  
**Context:** Agents + model gateway + gates.

| Work item | Detail |
| --------- | ------ |
| P3.1 Model tiers | Map `model_class` → cheap worker / strong advisor (advisor-orchestrator-worker) |
| P3.2 Verification gates | Between steps: schema check, test run, policy check — not “model said OK” |
| P3.3 Subagent spawn policy | Explicit grants; parent owns budget; children cannot escalate tools |
| P3.4 Rewrite top agents | intake, repository, planning, implement, reviewer, release, cost-governor |
| P3.5 Dual-control review | Reviewer never approves own implement output without independent evidence |
| P3.6 Agent theater fidelity | Each agent action names skill + script + event id in UI |

**Exit criteria:** A Mode A run shows worker vs advisor usage; cost drops vs all-strong baseline on fixture; Command Center labels skills.

**Sources:** awesome-llm advisor-orchestrator-worker, deer-flow subagents, our cost-governor.

---

### Phase 4 — Governance hardening
**Goal:** Policy/sandbox/identity match production-agent reality.  
**Context:** Policies, sandbox, MCP, compliance.

| Work item | Detail |
| --------- | ------ |
| P4.1 Policy engine seam | Evaluate tool/skill calls against YAML policies before execution |
| P4.2 Privilege rings | e.g. read-only → workspace write → network → destructive (Windows-honest) |
| P4.3 `agentctl governance-check` | Lint policies + map controls to published risks (OWASP agentic categories) without shipping attack recipes |
| P4.4 Trust tiers for MCP | Tool grants require role + trust score / explicit allow |
| P4.5 Skill network declarations | Skills with `network: declared` need human gate first time |
| P4.6 Red-team regression | Extend existing adversarial evals for injection → tool abuse paths |

**Exit criteria:** Policy deny is an event + BLOCKED path; governance-check runs in CI; no silent network from skills.

**Sources:** [agent-governance-toolkit](https://github.com/microsoft/agent-governance-toolkit) (patterns, not a wholesale vendor lock-in).

---

### Phase 5 — Durable Mode A / workflow semantics
**Goal:** Long runs survive crashes; YAML means execution.  
**Context:** Orchestrator + workflows + Command Center.

| Work item | Detail |
| --------- | ------ |
| P5.1 Node durability | Checkpoint after each Mode A node (Prefect-style resume semantics on our SQLite) |
| P5.2 Retries with budget | Bounded retries; each attempt is an event |
| P5.3 Workflow YAML enforcement | Expand beyond Mode A hardcode toward declared graphs (keep tests) |
| P5.4 Playbook clarity | Human-readable step docs (Ansible-like clarity, not Ansible clone) |
| P5.5 CC improvements | Skill timeline, governance denials, graph impact panel |

**Exit criteria:** Kill runner mid-implement; resume continues without reinventing completed nodes.

**Sources:** [Prefect](https://github.com/PrefectHQ/prefect), [Ansible](https://github.com/ansible/ansible), [deer-flow](https://github.com/bytedance/deer-flow).

---

### Phase 6 — Research & market-sensing skills (opt-in pack)
**Goal:** Optional skills for discovery — never default-on.  
**Context:** Domain analyst / product skills.

| Skill | Behavior | Gate |
| ----- | -------- | ---- |
| `web-research-brief` | Multi-source synthesis with citations (last30days pattern) | network + human approve |
| `repo-radar` | Structured GitHub/docs read via declared CLI (Agent-Reach pattern) | network + allowlist domains |
| `prior-art-scan` | Local + optional web; writes FEATURE_BRAIN section with sources | evidence required |

**Exit criteria:** Disabled by default; enabling requires policy grant; all fetches audited.

**Sources:** [last30days-skill](https://github.com/mvanhorn/last30days-skill), [Agent-Reach](https://github.com/Panniantong/Agent-Reach).

---

### Phase 7 — Catalog, install UX, and “anyone can develop”
**Goal:** Outsider can adopt skills like a package ecosystem without drowning.  
**Context:** Docs + packaging + export.

| Work item | Detail |
| --------- | ------ |
| P7.1 Skill catalog page | Curated list with maturity (alpha/beta/stable) |
| P7.2 `npx skills`-compatible layout notes | Document copy paths for Cursor/Claude/Codex |
| P7.3 Project vs org skills | Merge order: org defaults ← project overrides |
| P7.4 github-release export | Ship skill packs + evals; keep research out |
| P7.5 Starter kits | “Solo IC”, “Team lead”, “OSS maintainer” skill sets |
| P7.6 Anti-bloat rule | Cap: no skill without script+eval; archive weak skills |

**Sources:** [claude-skills](https://github.com/alirezarezvani/claude-skills) (structure), awesome-llm-apps (bar).

---

### Phase 8 — Self-improving loop (careful)
**Goal:** Improve skills from measured failures — not unbounded self-modification.  
**Context:** Evals + memory.

| Work item | Detail |
| --------- | ------ |
| P8.1 Skill scorecards | Pass rate, cost, false claim rate from events |
| P8.2 Proposed patches | System proposes SKILL.md/script diffs; human gate required |
| P8.3 Golden fixtures | Lock regressions; no silent prompt drift |
| P8.4 Ignore autopilot | No unsupervised rewrite of production skills |

**Sources:** awesome-llm self-improving-agent-skills (pattern only), hermes “grows with you” (memory), our audit chain.

---

## Cross-cutting workstreams (run every phase)

1. **Instructions quality** — AGENTS.md + constitution + per-skill “do / don’t”; short system prompts, deep references on demand  
2. **Tests** — unit for scripts; workflow e2e for bindings; adversarial for governance  
3. **Observability** — Command Center panels for skills/graph/governance  
4. **Security** — no secrets in skills; network declared; destructive actions gated  
5. **Docs** — update CAPABILITY_MATRIX + LIMITATIONS honestly after each phase  
6. **Export** — `export_github_release.py` includes new skills/evals, excludes research  

---

## Suggested sequence (critical path)

```text
Phase 0 (foundation)
    → Phase 1 (code graph) + Phase 2 (SWE skills) in parallel after P0.3
    → Phase 3 (agent operating model) binds skills
    → Phase 4 (governance) hardens execution
    → Phase 5 (durable Mode A) for long runs
    → Phase 6 (opt-in research) when core loop is solid
    → Phase 7 (catalog/UX) for adoption
    → Phase 8 (measured self-improve) last
```

---

## Explicit non-goals

- Shipping hundreds of shallow prompt skills  
- Replacing Mode A with a chat SuperAgent  
- Silent web scraping by default  
- Vendor lock-in to any one external toolkit  
- Publishing internal research / paper / security exploit material  

---

## Decision needed

Phases 0 and 2 (full SWE pack) are in tree. Reply with next focus:

- **Phase 1** — code intelligence graph (recommended)  
- **Phase 3** — agent operating model (tiers + verification theater)  
- **Export / GitHub sync** of skills into `github-release/`
