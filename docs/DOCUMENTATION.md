# Documentation system

## Feature folder layout

```text
projects/<project>/
  README.md
  features/<feature>/
    README.md
    feature.yaml
    documents.json          # manifest
    FEATURE_BRAIN.md        # 22-section brain
    charter.md              # template stub → workflow/human fill
    implementation-plan.md
    decisions/
    sessions/
    summaries/
    docs/                   # extra markdown
    artifacts/
      repo-map.md
      pageindex/*.tree.json # PageIndex trees
```

## Lifecycle

| Action | Command / API |
| ------ | ------------- |
| Create project folder | `agentctl create-project` |
| Create feature + stubs + index | `agentctl create-feature` |
| Repair missing stubs/dirs | `agentctl docs-maintain` |
| List docs | `agentctl docs-list` / `GET /api/features/{id}/documents` |
| Write a doc | `agentctl docs-write ... --file` |
| Rebuild indexes | `agentctl docs-index` / `POST .../docs-index` |
| Search | `agentctl docs-search` / `GET /api/docs/search?q=` |

## PageIndex

Each markdown file is parsed into a heading tree (natural sections). Trees are
stored as JSON for **vectorless** navigation. Search can:

1. Score titles/summaries structurally (default)
2. Ask the model to pick `node_id`s from the outline (`--llm`)

Inspired by [PageIndex](https://docs.pageindex.ai/) (VectifyAI); implemented
locally without their cloud API.

## Vectors

PageIndex section nodes are embedded with a deterministic local sparse TF hash
into `.agent-org/state/vectors.db`. Hybrid search merges vector + PageIndex
hits. Dense cloud embeddings can be added later as another `provider`.
