# ADR-001: Event-sourced SQLite core with hash-chained audit log

Status: Accepted (2026-07-31)

## Context
The framework requires complete execution logging, event-sourced history,
audit trails, and tamper evidence - local-first, no Postgres/Docker (user
constraint).

## Decision
A single SQLite database holds (a) an append-only `events` table where each
event's SHA-256 hash covers its canonical JSON plus the previous event's
hash, and (b) rebuildable operational tables. No update/delete API exists
for events. `agentctl verify` recomputes the chain offline.

## Options considered
- Temporal/EventStoreDB: durable but operationally heavy for local MVP.
- Plain logging: not tamper-evident, not queryable as history.

## Consequences
- Tampering anywhere in history is detectable (validated by test).
- Graph/vector projections can be rebuilt from events + git later.
- Migration path to Postgres is a driver swap; schema is portable SQL.
