# Retention Policy

- Events: retained indefinitely (append-only); export via `agentctl audit`.
- Checkpoint tags: retained; pruning requires the destructive-action gate.
- Reverted experiment branches/tags: retained for analysis.
- Secrets: never stored, nothing to retain.
