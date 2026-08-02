import pytest

from agentic_org.core.state_machine import (
    ApprovalRequired,
    InvalidTransition,
    WorkflowState,
    validate_transition,
)


def test_happy_path_steps_allowed():
    validate_transition(WorkflowState.DRAFT, WorkflowState.INTAKE)
    validate_transition(WorkflowState.INTAKE, WorkflowState.DISCOVERY)
    validate_transition(WorkflowState.IMPLEMENTING, WorkflowState.INTEGRATING)


def test_skipping_states_rejected():
    with pytest.raises(InvalidTransition):
        validate_transition(WorkflowState.DRAFT, WorkflowState.IMPLEMENTING)


def test_human_gate_enforced():
    with pytest.raises(ApprovalRequired):
        validate_transition(WorkflowState.AWAITING_DECISION, WorkflowState.APPROVED)
    validate_transition(WorkflowState.AWAITING_DECISION, WorkflowState.APPROVED,
                        approval_granted=True)


def test_terminal_states_frozen():
    with pytest.raises(InvalidTransition):
        validate_transition(WorkflowState.COMPLETED, WorkflowState.IMPLEMENTING)


def test_blocked_is_recoverable():
    validate_transition(WorkflowState.BLOCKED, WorkflowState.RESEARCHING)


def test_validation_failure_loops_back():
    validate_transition(WorkflowState.VALIDATING, WorkflowState.IMPLEMENTING)
