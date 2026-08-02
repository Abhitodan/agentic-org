# Retrieval Policy

Agents escalate context only as needed:

| Tier | Source | When |
| ---- | ------ | ---- |
| 0 | Role card + constitution | Always |
| 1 | Feature brain + managed docs | Default |
| 2 | Repo map | Before code edits |
| 3 | PageIndex tree navigation | Structured doc Q&A |
| 4 | Vector section search | Semantic overlap across docs |
| 5 | Broader git history | Explicitly justified |

## PageIndex (local)

Markdown documents are indexed into hierarchical JSON trees under
`features/<feature>/artifacts/pageindex/*.tree.json`. Retrieval prefers
section titles/summaries (structural) and may use LLM tree-reasoning when
`--llm` is passed to `agentctl docs-search`.

This is a **local PageIndex-inspired** implementation (tree + reason), not the
VectifyAI cloud API.

## Vector embeddings

Section nodes from PageIndex trees are embedded with a deterministic local
sparse TF hash (`sparse-tf`) into `.agent-org/state/vectors.db`. Hybrid search
interleaves vector and PageIndex hits.

## Commands

```text
agentctl docs-maintain <project> <feature>
agentctl docs-index --project <p> --feature <f>
agentctl docs-search "query" --mode hybrid
```
