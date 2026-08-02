"""Load and validate workflow definitions from `.agent-org/workflows/`."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class WorkflowNotImplemented(Exception):
    """Raised when a workflow YAML exists but is not marked implemented."""


class WorkflowDefinitionError(Exception):
    """Raised when a workflow YAML is missing or inconsistent with the runner."""


@dataclass
class WorkflowDef:
    name: str
    description: str
    nodes: list[str]
    states: list[str] = field(default_factory=list)
    human_gates: list[dict[str, Any]] = field(default_factory=list)
    implemented: bool = False
    path: Path | None = None

    def require_nodes(self, registered: set[str]) -> None:
        missing = [n for n in self.nodes if n not in registered]
        extra_doc = sorted(registered - set(self.nodes))
        if missing:
            raise WorkflowDefinitionError(
                f"workflow '{self.name}' lists unknown nodes: {missing}"
            )
        # Runner may register only the nodes this workflow uses; extras in the
        # runner graph that are not listed are a drift signal.
        if extra_doc:
            raise WorkflowDefinitionError(
                f"runner nodes not listed in workflow '{self.name}': {extra_doc}"
            )


DEFAULT_EXISTING_FEATURE: dict[str, Any] = {
    "description": "Mode A: feature in an existing repository (MVP vertical slice)",
    "states": [
        "DRAFT", "INTAKE", "DISCOVERY", "RESEARCHING", "OPTIONS_READY",
        "AWAITING_DECISION", "APPROVED", "PLANNED", "SPRINT_READY",
        "IMPLEMENTING", "INTEGRATING", "VALIDATING", "REVIEWING",
        "AWAITING_APPROVAL", "READY_FOR_RELEASE", "RELEASING", "OBSERVING",
        "COMPLETED",
    ],
    "nodes": [
        "intake", "map_repository", "create_brain", "draft_charter",
        "request_decision", "plan", "implement", "merge",
        "request_release", "release",
    ],
    "human_gates": [
        {"gate": "plan-approval", "between": ["AWAITING_DECISION", "APPROVED"]},
        {"gate": "release-approval",
         "between": ["AWAITING_APPROVAL", "READY_FOR_RELEASE"]},
    ],
    "implemented": True,
    "notes": (
        "Runner loads this YAML and refuses other kinds until implemented: true."
    ),
}


def ensure_workflow_defs(root: Path) -> Path:
    """Ensure Mode A YAML exists (does not clobber intentional local edits)."""
    wf_dir = root / ".agent-org" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    path = wf_dir / "existing-feature.yaml"
    if not path.exists():
        path.write_text(
            yaml.safe_dump(DEFAULT_EXISTING_FEATURE, sort_keys=False),
            encoding="utf-8",
        )
    # Stub unimplemented kinds so docs and loader agree they do not run.
    for kind in (
        "new-product", "defect-resolution", "performance-optimization",
        "security-remediation", "sprint-planning", "release",
    ):
        stub = wf_dir / f"{kind}.yaml"
        if not stub.exists():
            stub.write_text(
                yaml.safe_dump(
                    {
                        "description": f"{kind} (not implemented)",
                        "implemented": False,
                        "nodes": [],
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
    return path


def load_workflow_def(root: Path, kind: str = "existing-feature") -> WorkflowDef:
    ensure_workflow_defs(root)
    path = root / ".agent-org" / "workflows" / f"{kind}.yaml"
    if not path.exists():
        raise WorkflowDefinitionError(f"workflow definition not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise WorkflowDefinitionError(f"invalid workflow YAML: {path}")
    implemented = bool(data.get("implemented", False))
    nodes = list(data.get("nodes") or [])
    if implemented and not nodes:
        raise WorkflowDefinitionError(
            f"implemented workflow '{kind}' must declare nodes"
        )
    return WorkflowDef(
        name=kind,
        description=str(data.get("description") or ""),
        nodes=nodes,
        states=list(data.get("states") or []),
        human_gates=list(data.get("human_gates") or []),
        implemented=implemented,
        path=path,
    )


def require_implemented(root: Path, kind: str) -> WorkflowDef:
    definition = load_workflow_def(root, kind)
    if not definition.implemented:
        raise WorkflowNotImplemented(
            f"workflow '{kind}' is documented but not implemented "
            f"(set implemented: true only when the runner executes it)"
        )
    return definition
