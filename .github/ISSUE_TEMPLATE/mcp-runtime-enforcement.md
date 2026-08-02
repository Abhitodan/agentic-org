---
name: MCP runtime enforcement
about: Enforce deny-by-default MCP permissions in code
labels: security, enhancement
---

## Problem

`.agent-org/mcp/registry.yaml` and `permissions.yaml` exist, but no runtime client/enforcer was found under `src/agentic_org/`. Policy is advisory only.

## Acceptance criteria

- [ ] MCP calls go through a single gateway that checks permissions
- [ ] Deny-by-default: unknown server/tool rejected with auditable event
- [ ] Unit tests for allow and deny
- [ ] `evals` negative control `claim.mcp_runtime_enforcement` updated when symbols exist
- [ ] SECURITY.md updated

## References

- `docs/SCIENTIFIC_AUDIT.md` (dissent matrix)
- `.agent-org/mcp/`
