---
name: handoff-contract
description: Verify required artifacts exist before a persona handoff; missing keys block the handoff.
category: orchestration
personas:
  - planning-agent
  - reviewer-agent
  - release-agent
triggers:
  - handoff-contract
network: none
entrypoint: scripts/handoff.py:run
tools: []
---

# handoff-contract

> Verify required artifacts exist before a persona handoff; missing keys block the handoff.

## Guardrails

1. **Deterministic only.** No LLM judgment in the gate.
2. **Missing inputs are findings**, never silent passes.
3. **Shared finding envelope** with other agile skills.
4. **Fail closed** on errors.

## When to use

- Orchestrator coordination for `handoff-contract`

## Inputs / outputs

See the script entrypoint and `orchestration/SPEC.md`.
