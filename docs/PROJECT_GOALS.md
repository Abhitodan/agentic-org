# Project Goals

**Date:** 2026-08-01  
**Inferred from code + docs (not marketing).**

---

## Inferred current goal (as the repo behaves)

Operate a **local, auditable, budgeted Mode A workflow** that takes a feature on an existing git product from intake through human-gated plan and test-gated implement/merge/release — failing closed when the model key is missing — with a command-center UI for operators.

Secondary (partially built): product topology config, doc retrieval, graph projection, MCP library.

---

## Proposed clearer goals

### Technical goal

```text
Goal: Ship a trustworthy planner-executor control plane for one-repo (and later multi-component) feature delivery with enforced gates, budgets, and audit events.
Why it matters: Matches implemented architecture; avoids fake multi-agent claims.
Success metric: 100% of Mode A nodes either deterministic-tested or LLM-plumbed with BLOCKED on model failure; 0 doc/code contradictions in CI.
Validation method: pytest + contradiction scanner + model-error integration test.
Dependencies: Stable WorkflowRunner; honest README matrix.
Risks: Scope creep into unsupervised multi-agent.
```

### Measurable research goal

```text
Goal: Quantify whether LLM charter/plan/implement steps improve feature delivery vs a deterministic template baseline under human gates.
Why it matters: Justifies keeping LLM nodes scientifically.
Success metric: On ≥5 held-out tasks, report pass@1, grounding precision, cost_usd, human edit distance vs baseline templates; publish evals/reports.
Validation method: Rubric + automated path grounding; multi-seed optional.
Dependencies: Task corpus; ban empty-implement gaming.
Risks: Underpowered n; model drift.
```

### Practical user goal

```text
Goal: An engineer can configure a product, run Mode A on a feature, approve plan/release in the UI, and restore via checkpoint — without silent spend or fake success.
Why it matters: Stated problem in README.
Success metric: Timed usability: <15 min first successful blocked-or-completed run on sample repo; 0 unauthorized mutating API on non-loopback without token.
Validation method: Scripted walkthrough + serve auth test.
Dependencies: Product switcher; docs truth.
Risks: Sample-repo-only success.
```

### Production-readiness goal (local production, not SaaS)

```text
Goal: Harden the local single-tenant control plane for daily engineering use on trusted machines.
Why it matters: “Enterprise” is out of scope; reliable local use is not.
Success metric: Security tests for path escape + sandbox deny list + mandatory token off-loopback; job persistence across restart; CI green on every PR.
Validation method: CI security job; restart soak.
Dependencies: Immediate fixes in IMPROVEMENT_PLAN.
Risks: Over-building multi-tenant.
```

### Six-month development direction

```text
Goal: Evolve from one-repo Mode A MVP → product-topology-aware delivery (P1 work packages) with Autonomy A suggestions, without unsupervised cross-repo merges.
Why it matters: Matches approved product topology design; preserves human gates.
Success metric: ≥1 real multi-component feature demo with per-component tests; graph suggestions shown but never auto-approve; quality suite n≥10 tasks tracked monthly.
Validation method: E2E multi-comp test; monthly eval report vs baseline.
Dependencies: P0 topology (done); P1 execute; doc trust.
Risks: Building graph theater before quality evals.
```

---

## Non-goals (explicit)

- Multi-tenant SaaS / SSO in the next six months
- Fully autonomous merge/release without humans
- Claiming Vectify/PageIndex cloud or dense embeddings as shipped
- Replacing git/pytest with agent judgment

---

## Recommended single north-star (next 90 days)

**“Trustworthy local Mode A for existing-product features: claims match code; LLM steps measured; multi-repo remains config until P1 execute ships.”**

Primary KPI: **doc/code contradiction count = 0** and **implement quality suite pass@1 reported** (even if low).
