# Limitations and known risks

Honest constraints as of the 2026-08-01 scientific audit.

## Functional

| Limitation | Impact | Evidence |
| ---------- | ------ | -------- |
| Live LLM job needs `GEMINI_API_KEY` secret | CI skips live path without secret | `.github/workflows/ci.yml` |
| Windows network sandbox is policy/env only | No kernel net namespace on Windows | Linux may use `unshare --net` |
| Vector embeddings are local sparse-TF | Not dense Gemini/OpenAI embeddings yet | `retrieval/vectors.py` provider column ready |
| PageIndex is local tree+reason, not Vectify cloud | No PageIndex.ai API dependency | Compatible philosophy; different code |
| MCP HTTP/SSE transports not implemented | Stdio only | `mcp/stdio_client.py` |
| No SSO / multi-tenant | Local-trust MVP | Planned |
| Experiment ledger not automated | No Karpathy loop execution | Schema/template only |

## Security

| Risk | Severity | Mitigation today |
| ---- | -------- | ---------------- |
| Mutating API unauthenticated when token unset | High if bound non-loopback | Default `127.0.0.1`; `serve` **exits** on non-loopback without `AGENTIC_ORG_API_TOKEN` |
| GET/SSE open even with token | Medium | Documented; dashboard constraint |
| Vendored React still needs update process | Low | Local `apps/command-center/vendor/` (no unpkg) |
| `git reset --hard` on revert | Medium | Operator-triggered; history via tags |
| Secret redaction patterns incomplete | Medium | Event payloads redacted (`core/redact.py`); not all secret shapes |

## Reliability / scale

| Limitation | Notes |
| ---------- | ----- |
| SQLite single-node | Fine for local MVP; not HA |
| In-memory `_JOBS` registry | Lost on process restart; unbounded growth risk |
| Mapper scalability | Untested above tiny sample repos |
| CI present but limited | `.github/workflows/ci.yml` runs pytest/evals; live LLM optional/skipped without secret |

## Evaluation gaps

- No LLM task-quality benchmark
- No latency/cost SLOs under real traffic
- No browser E2E UI tests
- No multi-seed stochastic evaluation (deterministic core only)

## Documentation / packaging

- Parent folder `AITeams/` is not the git root; package lives in `agentic-org/`
- Skill/prompt directories under `.agent-org` are largely empty placeholders
