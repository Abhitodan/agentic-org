---
name: escalation-protocol
description: Compute mandatory human escalations from budget, confidence, policy flags, and impediment age.
category: orchestration
personas:
  - cost-governor-agent
  - planning-agent
triggers:
  - escalation-protocol
network: none
entrypoint: scripts/escalate.py:run
tools: []
---

# escalation-protocol

> Compute mandatory human escalations from budget, confidence, policy flags, and impediment age.

## Guardrails

1. **Deterministic only.** No LLM judgment in the gate.
2. **Missing inputs are findings**, never silent passes.
3. **Shared finding envelope** with other agile skills.
4. **Fail closed** on errors.

## When to use

- Orchestrator coordination for `escalation-protocol`

## Inputs / outputs

See the script entrypoint and `orchestration/SPEC.md`.
