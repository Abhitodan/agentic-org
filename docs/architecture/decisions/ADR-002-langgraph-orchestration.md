# ADR-002: LangGraph for checkpointed orchestration, framework-owned semantics

Status: Accepted (2026-07-31)

## Context
Workflows need durable graph execution, human-interrupt gates, and resume.
The user selected the FastAPI + LangGraph stack.

## Decision
LangGraph `StateGraph` + `SqliteSaver` executes workflow pipelines with
`interrupt_before` at human gates (thread id = workflow id). However, all
load-bearing semantics stay framework-owned: the 24-state machine, event
emission, budget charging, and approval records live in `agentic_org.core`,
not in graph state.

## Consequences
- Human gate resume works today (`agentctl approve` + `agentctl resume`).
- Lock-in is bounded: replacing LangGraph means rewriting one file
  (`orchestrator/runner.py` graph wiring), nothing else.
- Hidden LangGraph channel state is never a source of truth (constitution
  rule 12): everything material is in events, SQLite, and git.
