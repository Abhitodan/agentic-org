# ADR-004: Vendor-neutral .agent-org/ as canonical governance source

Status: Accepted (2026-07-31)

## Context
Claude Code, Copilot, and Cursor each have their own agent/skill/memory
file conventions. Making any one canonical creates lock-in and drift.

## Decision
`.agent-org/` (constitution, policies, agents, skills, workflows, schemas,
templates) is canonical and generated from a single script
(`scripts/bootstrap_org.py`) so definitions cannot drift from one another.
Vendor files (CLAUDE.md, .github/agents, .cursor/rules) must be generated
projections.

## Consequences
- One edit point; idempotent regeneration; projections are Phase 4 work.
- Agent front matter (role, model_class, tools) is machine-readable for the
  runtime registry.
