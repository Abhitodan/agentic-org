---
name: wip-limit-guard
description: Reject assignments that breach per-persona or team WIP limits; finishing work is the remedy.
category: orchestration
personas:
  - planning-agent
  - cost-governor-agent
triggers:
  - wip-limit-guard
network: none
entrypoint: scripts/wip.py:run
tools: []
---

# wip-limit-guard

> Reject assignments that breach per-persona or team WIP limits; finishing work is the remedy.

## Guardrails

1. **Deterministic only.** No LLM judgment in the gate.
2. **Missing inputs are findings**, never silent passes.
3. **Shared finding envelope** with other agile skills.
4. **Fail closed** on errors.

## When to use

- Orchestrator coordination for `wip-limit-guard`

## Inputs / outputs

See the script entrypoint and `orchestration/SPEC.md`.
