# Security

- Policy source of truth: `.agent-org/policies/security.md`.
- Secrets are read from environment variables only and are never written
  to events, brains, logs, or markdown.
- The audit event chain is append-only and tamper-evident; report any
  `agentctl verify` failure immediately.
- Destructive actions (force push, schema drops, production deploys)
  require the destructive-action approval gate.
- Report vulnerabilities via a private issue to the repository owner.

## Command-center API

- Default bind is `127.0.0.1` (loopback). Binding to a non-loopback host
  without `AGENTIC_ORG_API_TOKEN` is refused (`agentctl serve` exits with
  code 2). When token is set on a non-loopback bind, mutating `/api/*`
  still require that token.
- When `AGENTIC_ORG_API_TOKEN` is set, `POST`/`PUT`/`PATCH`/`DELETE` under
  `/api/` require `Authorization: Bearer <token>` or header
  `X-Agentic-Org-Token`. `GET`/`HEAD`/`OPTIONS` (including SSE) stay open
  so the local dashboard can observe state without EventSource custom
  headers.
- This is a local-trust MVP control, not SSO or multi-tenant isolation.
- MCP calls must go through `agentic_org.mcp.McpGateway` (deny-by-default).
  Empty `grants` deny all tools; matching grants emit `mcp.authorized` /
  `mcp.called` events. Wire-protocol MCP clients are still future work.
