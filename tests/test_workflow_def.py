"""Workflow YAML must drive what the runner will execute."""

from pathlib import Path

import pytest
import yaml

from agentic_org.orchestrator.workflow_def import (
    WorkflowNotImplemented,
    ensure_workflow_defs,
    load_workflow_def,
    require_implemented,
)
from agentic_org.orchestrator.runner import MODE_A_NODES, WorkflowRunner
from agentic_org.core import db
from agentic_org.core.events import EventStore
from agentic_org.core.store import Store
from agentic_org.gateway.model_gateway import ModelGateway


def test_ensure_and_require_mode_a(tmp_path: Path):
    ensure_workflow_defs(tmp_path)
    definition = require_implemented(tmp_path, "existing-feature")
    assert definition.implemented is True
    assert definition.nodes == MODE_A_NODES


def test_unimplemented_workflow_refused(tmp_path: Path):
    ensure_workflow_defs(tmp_path)
    with pytest.raises(WorkflowNotImplemented):
        require_implemented(tmp_path, "release")


def test_runner_rejects_yaml_node_drift(tmp_path: Path):
    ensure_workflow_defs(tmp_path)
    path = tmp_path / ".agent-org" / "workflows" / "existing-feature.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["nodes"] = ["intake", "plan"]  # drifted
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    conn = db.connect(tmp_path / ".agent-org" / "state" / "t.db")
    with pytest.raises(Exception):
        WorkflowRunner(
            tmp_path, Store(conn), EventStore(conn), ModelGateway(None)
        )


def test_load_marks_stubs_not_implemented(tmp_path: Path):
    ensure_workflow_defs(tmp_path)
    release = load_workflow_def(tmp_path, "release")
    assert release.implemented is False
