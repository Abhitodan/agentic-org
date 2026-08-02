# Memory and Canonical Data Ownership

Canonical owners (conflicts always resolve to the owner):

| Store | Owns |
| ----- | ---- |
| Event store (SQLite `events`) | Immutable execution history |
| Git | Source code, brains, versioned project artifacts |
| Relational tables | Operational workflow state (projects, features, workflows, approvals, runs, checkpoints) |
| Graph projection (`graph.db`) | Relationships and impact analysis, **rebuilt** from events + tables + brains |
| Vector index (`vectors.db`) | Sparse section embeddings rebuilt from feature docs / PageIndex nodes |
| PageIndex trees | Hierarchical JSON under `artifacts/pageindex/` for vectorless navigation |
| Markdown brains + managed docs | Human-readable project knowledge (`documents.json` manifest) |

## Graph runtime

`agentic_org.memory.GraphMemory` persists nodes/edges in
`.agent-org/state/graph.db`. Rebuild with `agentctl memory-rebuild` or
`GraphMemory.rebuild(...)`.

Core relationships projected today:

- `FEATURE CONTAINED_IN PROJECT`
- `WORKFLOW FOR_FEATURE FEATURE`
- `FEATURE DOCUMENTED_BY BRAIN`
- `EVENT IN_WORKFLOW WORKFLOW` / `EVENT ABOUT_FEATURE FEATURE`
- `FEATURE TOUCHES WORKTREE` (from successful implementation events)

Vector search is implemented as local sparse embeddings over PageIndex
sections (`agentic_org.retrieval.vectors`). Dense Gemini/OpenAI embeddings are
optional future providers — the storage schema already has a `provider` column.
