---
name: repository-analysis
description: Deterministic repository mapping with zero LLM calls — language inventory, import graph, tests, entry points. Evidence first, inference never.
category: discovery
personas:
  - repository-agent
  - domain-analyst-agent
triggers:
  - map-repository
  - node_map_repository
network: none
entrypoint: scripts/analyze.py:run
tools: []
---

# Repository Analysis

> Before any planning, know what is actually on disk. Every downstream claim
> (charter, plan, review) is checked against this map — so the map itself
> must contain zero invention.

## Guardrails

1. **Extraction only.** Everything in the result comes from the filesystem
   or the AST. There is no inference step: a file either exists or it is
   not in the map.
2. **Missing repo is a hard failure.** Mapping nothing must never look like
   mapping something — a nonexistent path raises and surfaces as
   `skill.failed`.
3. **No network, no LLM.** The skill declares `network: none` and the
   runner enforces it.
4. **Honest zeros.** `tests: 0` and `entry_points: 0` are legitimate,
   useful answers. Never pad the map.

## When to use

- Mode A discovery (`node_map_repository`) — mandatory before charter/plan
- Taking over an unfamiliar or legacy repository
- Before refactoring: identify what is core, what is test, what is dead
- CLI: `agentctl map-repository` / `agentctl skill-run repository-analysis`

## When NOT to use

- Semantic questions ("what does this product mean?") — docs retrieval or a
  human
- Version/CVE lookups — needs network; out of scope by design
- As a substitute for reading the code you are about to edit

## Inputs

| Arg | Type | Required | Validation |
| --- | ---- | -------- | ---------- |
| `repo_path` | path | yes | must be an existing directory (else raises) |
| `out_dir` | path | no | created if absent; writes `repo-map.json` + `repo-map.md` |

## Workflow

1. **Classify** — walk the tree; tag each file by language and role
   (source / test / config / doc), skipping VCS internals.
2. **Extract structure** — parse Python imports via AST (never regex
   guessing); edges are EXTRACTED facts.
3. **Locate tests and entry points** — pytest patterns, `__main__` blocks,
   console entry declarations.
4. **Summarize** — counts per language, markdown summary for the feature
   brain; optionally persist artifacts.

## Output contract

```json
{
  "ok": true,
  "summary": "…",
  "file_count": 123,
  "languages": {"python": 100},
  "tests": 14,
  "entry_points": 3,
  "artifacts": ["…/repo-map.json", "…/repo-map.md"],
  "repo_map": {"files": ["…"]},
  "evidence": "deterministic_ast_and_filesystem"
}
```

## Failure modes

| Condition | Behavior |
| --------- | -------- |
| `repo_path` not a directory | raises `FileNotFoundError` → `skill.failed` |
| Unreadable/unparsable file | skipped, never guessed |
| Entrypoint script missing | rejected fail-closed by the skill runner |

## Anti-patterns

- WRONG: inferring a framework from a README claim.
  CORRECT: report the import that proves it, or omit it.
- WRONG: "probably has tests somewhere".
  CORRECT: report the test files found, or `tests: 0`.

## Quality checklist (all yes before trusting the map)

- [ ] Every path in `repo_map.files` exists on disk (spot-check allowed)
- [ ] `evidence` equals `deterministic_ast_and_filesystem`
- [ ] Zero LLM/tool-network events emitted during the run
- [ ] Artifacts written when `out_dir` was provided

## References

- `references/evidence-rules.md` — what counts as evidence in this org
- `.agent-org/rules/common/review.md` — how the map is consumed in review
