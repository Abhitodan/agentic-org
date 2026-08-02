---
name: ceremony-state-machine
description: Validate ceremony order and required artifacts; illegal transitions are errors.
category: orchestration
personas:
  - planning-agent
  - retrospective-agent
triggers:
  - ceremony-state-machine
network: none
entrypoint: scripts/ceremony.py:run
tools: []
---

# ceremony-state-machine

> Validate ceremony order and required artifacts; illegal transitions are errors.

## Guardrails

1. **Deterministic only.** No LLM judgment in the gate.
2. **Missing inputs are findings**, never silent passes.
3. **Shared finding envelope** with other agile skills.
4. **Fail closed** on errors.

## When to use

- Orchestrator coordination for `ceremony-state-machine`

## Inputs / outputs

See the script entrypoint and `orchestration/SPEC.md`.
