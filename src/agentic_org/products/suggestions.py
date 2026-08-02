"""Autonomy A suggestion rail — suggest only, never auto-approve."""

from __future__ import annotations

from typing import Any

from ..memory.graph import GraphMemory
from .topology import ProductTopology


def build_suggestions(
    topology: ProductTopology,
    *,
    memory: GraphMemory | None = None,
    feature_id: str | None = None,
    workflow_state: str | None = None,
) -> dict[str, Any]:
    """Graph + topology ordering suggestions. Humans still own gates."""
    policy = topology.policies or {}
    suggest_only = bool(policy.get("suggest_only", True))
    default_order = policy.get("component_order_default")
    if isinstance(default_order, list) and default_order:
        id_to_comp = {c.id: c for c in topology.components}
        ordered_ids = [i for i in default_order if i in id_to_comp]
        for c in sorted(topology.components, key=lambda x: (x.order_hint, x.id)):
            if c.id not in ordered_ids:
                ordered_ids.append(c.id)
    else:
        ordered_ids = [
            c.id for c in sorted(
                topology.components, key=lambda x: (x.order_hint, x.id)
            )
        ]

    components = []
    for cid in ordered_ids:
        c = topology.component(cid)
        if not c:
            continue
        components.append({
            "id": c.id,
            "name": c.name,
            "kind": c.kind,
            "path": c.path,
            "order_hint": c.order_hint,
            "test_command": c.test_command,
            "suggested_role": _role_for_kind(c.kind),
        })

    next_agent = _next_agent(workflow_state)
    graph_impact = None
    if memory is not None and feature_id:
        try:
            graph_impact = memory.impact(feature_id)
        except Exception as exc:  # never break the rail
            graph_impact = {"error": f"{type(exc).__name__}: {exc}"}

    return {
        "suggest_only": suggest_only,
        "never_auto_approve": True,
        "autonomy": "A",
        "product": topology.name,
        "shape": topology.shape,
        "suggested_component_order": ordered_ids,
        "components": components,
        "next_agent": next_agent,
        "human_gates": list(policy.get("human_gates") or [
            "plan-approval", "release-approval",
        ]),
        "graph_impact": graph_impact,
        "disclaimer": (
            "Suggestions only. Plan and release gates remain human-approved."
        ),
    }


def _role_for_kind(kind: str) -> str:
    return {
        "sql": "data-agent",
        "backend": "backend-agent",
        "frontend": "frontend-agent",
        "ssis": "integration-agent",
        "ssrs": "reporting-agent",
        "docs": "docs-agent",
        "main": "backend-agent",
    }.get(kind, "backend-agent")


def _next_agent(workflow_state: str | None) -> str:
    state = (workflow_state or "").upper()
    mapping = {
        "DRAFT": "intake-agent",
        "INTAKE": "repository-agent",
        "DISCOVERY": "repository-agent",
        "RESEARCHING": "product-manager-agent",
        "OPTIONS_READY": "human",
        "AWAITING_DECISION": "human",
        "APPROVED": "planning-agent",
        "PLANNED": "backend-agent",
        "SPRINT_READY": "backend-agent",
        "IMPLEMENTING": "backend-agent",
        "VALIDATING": "release-agent",
        "REVIEWING": "human",
        "AWAITING_APPROVAL": "human",
    }
    return mapping.get(state, "human")
