---
name: release-readiness
description: Aggregate release evidence — demonstrated stories, green tests, clean review, approval gate, rollback plan.
category: delivery
personas:
  - release-agent
  - product-owner-agent
triggers:
  - release-readiness
network: none
entrypoint: scripts/ready.py:run
tools: []
---

# Release Readiness

> Aggregate release evidence — demonstrated stories, green tests, clean review, approval gate, rollback plan.

## Guardrails

1. **Evidence over claims.** Missing artifacts are errors, never assumed present.
2. **Fail closed.** Incomplete inputs produce findings, not a quiet pass.
3. **No network, no LLM.** Deterministic validation only.
4. **Shared envelope.** Returns ok / findings / evidence like other agile skills.

## When to use

- At release / deploy time for the $(System.Collections.Hashtable.n) gate

## When NOT to use

- To invent release notes or rollback steps the team did not supply

## Inputs

See `scripts/` entrypoint parameters and the category `SPEC.md`.

## Output contract

Standard finding envelope with skill-specific fields. Evidence string is declared in the script.
