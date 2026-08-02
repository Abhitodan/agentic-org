---
name: code-intelligence
description: Persistent Python AST code graph with provenance-aware impact and review-pack queries. EXTRACTED edges are certain; INFERRED edges never claim certainty.
category: discovery
personas:
  - repository-agent
  - reviewer-agent
  - architect-agent
triggers:
  - code-intelligence
  - graph-impact
  - review-pack
network: none
entrypoint: scripts/intel.py:run
tools: []
---

# Code Intelligence

> Grep finds strings. A graph finds dependents. This skill indexes a local
> Python AST graph and answers impact / review-pack questions without an LLM.

## Guardrails

1. **Provenance is mandatory.** Every edge is `EXTRACTED` or `INFERRED`.
   Review packs surface inferred count; agents must not treat inferred as fact.
2. **Missing graph is not success.** Query modes return `ok: false` with a
   reason when `graph.json` is absent — never an empty silent pass.
3. **No network, no LLM.** Indexing is filesystem + AST only.
4. **Python first.** Other languages are future work; they are not invented.

## When to use

- After mapping a repo, before review, to shrink the file set
- When `code-review` needs an impact neighborhood for a diff
- When an architect asks "what breaks if this module changes?"

## When NOT to use

- To invent architecture that is not on disk
- As a substitute for test evidence

## Inputs

| Arg | Mode | Notes |
| --- | ---- | ----- |
| `mode` | all | `index` / `impact` / `review-pack` / `query` |
| `repo_path` | index | required |
| `graph_dir` | all | default `<repo>/.agent-org/state/code-graph` |
| `paths` / `changed_paths` | impact, review-pack | seed files |
| `include_inferred` | impact | default true |
| `max_files` | review-pack | default 20 |

## Output contract

Index returns `node_count`, `edge_count`, artifacts. Impact returns
`impacted[]` with `certain` flags. Review-pack returns ranked `files[]`.

## Evidence strings

| Mode | Evidence |
| ---- | -------- |
| index | `deterministic_python_ast_graph` |
| impact | `deterministic_graph_impact` |
| review-pack | `deterministic_graph_review_pack` |
| query | `deterministic_graph_query` |
