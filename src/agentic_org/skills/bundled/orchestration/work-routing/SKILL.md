---
name: work-routing
description: Route ready stories to personas by declared capability and current WIP; unroutable stories are named.
category: orchestration
personas:
  - planning-agent
triggers:
  - work-routing
network: none
entrypoint: scripts/route.py:run
tools: []
---

# work-routing

> Route ready stories to personas by declared capability and current WIP; unroutable stories are named.

## Guardrails

1. **Deterministic only.** No LLM judgment in the gate.
2. **Missing inputs are findings**, never silent passes.
3. **Shared finding envelope** with other agile skills.
4. **Fail closed** on errors.

## When to use

- Orchestrator coordination for `work-routing`

## Inputs / outputs

See the script entrypoint and `orchestration/SPEC.md`.
