# Capability matrix (Phase 0)

Machine-checked by `scripts/check_doc_code_matrix.py`. Update this table when
adding or removing Mode A capabilities. Docs must not claim “not built” for
rows marked **Present**.

| Capability | Symbol / path | Present | Evidence |
| ---------- | ------------- | ------- | -------- |
| Draft charter | `node_draft_charter` | Yes | `orchestrator/runner.py` |
| Plan | `node_plan` | Yes | `orchestrator/runner.py` |
| Implement (worktree + tests) | `node_implement` / `Implementer` | Yes | `coding/implementer.py` |
| Merge | `node_merge` | Yes | `orchestrator/runner.py` |
| Release approval gate | `node_release_approval` | Yes | `orchestrator/runner.py` |
| Release | `node_release` | Yes | `orchestrator/runner.py` |
| Fail-closed model gateway | `ModelUnavailable` | Yes | `gateway/model_gateway.py` |
| HTTP→unavailable | `HTTPStatusError` → `ModelUnavailable` | Yes | Phase 0 |
| Path-safe apply_actions | `relative_to` containment | Yes | `coding/implementer.py` |
| Empty actions ≠ success | raise / BLOCKED | Yes | Phase 0 tests |
| Serve auth off-loopback | exit 2 without token | Yes | `cli/main.py` |
| Product topology config | `products/topology.py` | Yes | mono/multi |
| Work packages plan JSON | `products/work_packages.py` | Yes | Phase 3 |
| Multi-component execute | `products/execute.py` | Yes | per-component test_command |
| Graph suggestion rail | `products/suggestions.py` | Yes | Autonomy A; never auto-approve |
| Cross-component checklist | `cross_component_checklist` | Yes | before release gate |
| Ops runbook | `docs/RUNBOOK.md` | Yes | backup/restore drill |
| MCP gateway library | `McpGateway` | Yes | Mode A map calls `local-org/repo_summary` via gateway |
| MCP role=None deny | role-scoped grants | Yes | Phase 1 |
| Sandbox dangerous argv denylist | `dangerous_command_reason` | Yes | Phase 1 |
| Wall-clock budget | `maximum_wall_clock_minutes` | Yes | enforced on charge |
| Jobs SQLite | `jobs` table | Yes | Phase 1 |
| Event secret redaction | `core/redact.py` | Yes | Phase 1 |
| Path grounding report | `coding/grounding.py` | Yes | charter/plan artifacts |
| Vendored React UMD | `apps/command-center/vendor` | Yes | no unpkg CDN |
| Skill loader / invoke | `skills.invoke_skill` | Yes | `skills/{schema,loader,runner}.py` |
| Skill CLI | `skill-list` / `skill-show` / `skill-run` / `skill-eval` | Yes | `cli/main.py` |
| Skill `repository-analysis` script | `.agent-org/skills/…` + `skills/bundled/…` | Yes | Mode A map node; empty org roots fall back to package bundle |
| Phase 2 SWE skills | feature-planning, implementation, code-review, scope-creep, commit-archaeologist, dependency-doctor, test-evidence | Yes | Mode A plan/implement/review; `agentctl skill-eval` |
| Mode A `review` node | `node_review` → `code-review` skill | Yes | Between implement and merge |
| Rules pack | `.agent-org/rules/{common,python}` | Yes | Layered standards (common + stack overlays); see `research/HARNESS_PATTERNS.md` |
| Dense cloud embeddings | — | No | sparse-TF only |
| SSO / multi-tenant | — | No | local-trust MVP |

## Eval lanes

| Lane | Entry | Meaning |
| ---- | ----- | ------- |
| Plumbing | `evals/run_plumbing.py` | Invariants + harness + doc matrix |
| Adversarial | `evals/run_adversarial.py` | Anti-manipulation / trust floor |
| Quality | `evals/run_quality.py` | Live LLM; skip ≠ pass |
