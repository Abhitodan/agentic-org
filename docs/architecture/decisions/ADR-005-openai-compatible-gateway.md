# ADR-005: OpenAI-compatible model gateway with routing classes and honest failure

Status: Accepted (2026-07-31)

## Context
Model independence, cost tracking, and routing (fast/standard/strong) are
non-negotiable. Fabricated model output is forbidden.

## Decision
One HTTP adapter targets any OpenAI-compatible `/chat/completions`
endpoint (OpenAI, Azure, OpenRouter, Ollama, vLLM). Routing classes map to
concrete models and per-1M-token prices in `.agent-org/models.yaml`. If no
key is configured the gateway raises `ModelUnavailable`; the orchestrator
converts that to a `BLOCKED` state with an audited reason.

## Consequences
- Local/private models are a base-URL change, no code change.
- Cost per call is computed from real usage fields and charged against the
  workflow budget before results are accepted.
- Provider-specific prompt caching is not abstracted yet (Phase 3 token
  optimization work).
