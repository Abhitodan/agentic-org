# Roadmap

Prioritization uses **Impact × Evidence × Feasibility ÷ Risk** from the scientific audit. Dates are intentionally omitted; order is priority.

## Immediate fixes (done or next)

| Item | Status | Why |
| ---- | ------ | --- |
| Truthful README (no graph-memory/enterprise overclaim) | Done (audit) | Credibility |
| `evals/` harness + baselines | Done (audit) | Measurable regressions |
| Optional mutating API token | Done (audit) | Security on shared binds |
| GitHub issue templates for top gaps | Done (audit) | OSS readiness |
| CI workflow running pytest + evals | Done | `.github/workflows/ci.yml` |
| Live Gemini Mode A fixture | Done (optional live job) | `evals/fixtures/mode_a_live_redacted/` |
| Worktree implement node gated on tests | Done | `coding/implementer.py` + runner node |
| MCP deny-by-default + stdio transport | Done | `mcp/gateway.py` + `stdio_client.py` |
| Workflow YAML aligned with runner | Done | `workflow_def.py` loads Mode A |
| Graph memory projection | Done | `memory/graph.py` |
| Vector embeddings + PageIndex docs | Done | `retrieval/` + `docs/workspace.py` |
| Auto-merge + release tagging | Done | `release/` + Mode A nodes |
| Process/network sandbox | Done (Linux net ns best-effort) | `sandbox/policy.py` |

## High-value experiments

1. **Keyed Mode A happy path** — run charter→approve→plan with Gemini; store redacted transcript + assert `PLANNED`.
2. **Implementation node spike** — worktree + failing test → patch → retest on enrollment sample.
3. **Mapper benchmark** — synthetic 1k/10k file trees; record wall time/memory.

## Architectural improvements

1. Load Mode A definition from `.agent-org/workflows/*.yaml` or delete the implication that YAML is executable.
2. Bound/persist command-center job registry.
3. Vendoring or pinning command-center JS dependencies.
4. MCP client with deny-by-default enforcement matching `permissions.yaml`.

## Documentation improvements

1. Keep `docs/product/current-state-assessment.md` synced after each phase.
2. Add browser screenshots only from a real `agentctl serve` session.
3. Publish eval reports in PRs.

## Long-term research

1. Experiment ledger + automated Karpathy loops (Phase 3 product backlog).
2. Multi-agent sprint simulation (Phase 4).
3. Graph/vector projections + portfolio brain (Phase 5).
4. SSO, multi-tenancy, sandboxing, policy engine (Phase 6).

## Priority table

| Rank | Item | Impact | Evidence need | Feasibility | Risk |
| ---- | ---- | ------ | ------------- | ----------- | ---- |
| 1 | CI | High | Low | High | Low |
| 2 | Live LLM Mode A validation | High | High | Medium | Medium (cost/secrets) |
| 3 | Implementation node | High | High | Medium | Medium |
| 4 | MCP runtime enforcement | Medium | Medium | Medium | Low |
| 5 | YAML-driven workflows | Medium | Medium | Medium | Medium (rewrite) |
| 6 | Graph memory | High (aspirational) | High | Low | High |
