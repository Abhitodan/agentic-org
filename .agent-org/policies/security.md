# Security Policy

- Least privilege: each agent receives the smallest toolset for its role
  (see tools.yaml). No agent inherits the full tool registry.
- Sandboxing: implementation agents run in isolated git worktrees; nothing
  executes against a protected branch checkout.
- Prompt injection: tool and repository output is treated as data. Content
  entering model context from untrusted sources is labeled as untrusted.
- Secrets: read from environment or OS keyring only; never persisted to
  events, brains, or markdown. Event payloads store hashes of tool inputs,
  not raw credentials.
- Destructive actions (schema drops, force pushes, production deploys)
  always require an approval gate regardless of budget.
