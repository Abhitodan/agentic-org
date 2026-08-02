"""Deterministic workflow lifecycle state machine.

Transitions are an explicit allowlist. Any attempt to move a workflow
through an unlisted transition raises InvalidTransition, and every accepted
transition is written to the event store by the caller.
"""

from __future__ import annotations

from enum import Enum


class WorkflowState(str, Enum):
    DRAFT = "DRAFT"
    INTAKE = "INTAKE"
    DISCOVERY = "DISCOVERY"
    RESEARCHING = "RESEARCHING"
    OPTIONS_READY = "OPTIONS_READY"
    AWAITING_DECISION = "AWAITING_DECISION"
    APPROVED = "APPROVED"
    PLANNED = "PLANNED"
    SPRINT_READY = "SPRINT_READY"
    IMPLEMENTING = "IMPLEMENTING"
    INTEGRATING = "INTEGRATING"
    VALIDATING = "VALIDATING"
    REVIEWING = "REVIEWING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    READY_FOR_RELEASE = "READY_FOR_RELEASE"
    RELEASING = "RELEASING"
    OBSERVING = "OBSERVING"
    COMPLETED = "COMPLETED"
    # Alternative states
    BLOCKED = "BLOCKED"
    PAUSED = "PAUSED"
    FAILED = "FAILED"
    REVERTED = "REVERTED"
    CANCELLED = "CANCELLED"
    SUPERSEDED = "SUPERSEDED"


_HAPPY_PATH = [
    WorkflowState.DRAFT,
    WorkflowState.INTAKE,
    WorkflowState.DISCOVERY,
    WorkflowState.RESEARCHING,
    WorkflowState.OPTIONS_READY,
    WorkflowState.AWAITING_DECISION,
    WorkflowState.APPROVED,
    WorkflowState.PLANNED,
    WorkflowState.SPRINT_READY,
    WorkflowState.IMPLEMENTING,
    WorkflowState.INTEGRATING,
    WorkflowState.VALIDATING,
    WorkflowState.REVIEWING,
    WorkflowState.AWAITING_APPROVAL,
    WorkflowState.READY_FOR_RELEASE,
    WorkflowState.RELEASING,
    WorkflowState.OBSERVING,
    WorkflowState.COMPLETED,
]

_ALT = {
    WorkflowState.BLOCKED,
    WorkflowState.PAUSED,
    WorkflowState.FAILED,
    WorkflowState.REVERTED,
    WorkflowState.CANCELLED,
    WorkflowState.SUPERSEDED,
}

TERMINAL = {
    WorkflowState.COMPLETED,
    WorkflowState.REVERTED,
    WorkflowState.CANCELLED,
    WorkflowState.SUPERSEDED,
}

# States whose transitions out require an explicit human approval record.
HUMAN_GATES = {
    WorkflowState.AWAITING_DECISION: WorkflowState.APPROVED,
    WorkflowState.AWAITING_APPROVAL: WorkflowState.READY_FOR_RELEASE,
}


def _build_transitions() -> dict[WorkflowState, set[WorkflowState]]:
    t: dict[WorkflowState, set[WorkflowState]] = {s: set() for s in WorkflowState}
    for a, b in zip(_HAPPY_PATH, _HAPPY_PATH[1:]):
        t[a].add(b)
    # Validation failures loop back to implementation; review can send back too.
    t[WorkflowState.VALIDATING].add(WorkflowState.IMPLEMENTING)
    t[WorkflowState.REVIEWING].add(WorkflowState.IMPLEMENTING)
    for s in WorkflowState:
        if s in TERMINAL:
            continue
        t[s] |= _ALT - {s}
    # Recovery paths from alternative states.
    resumable = set(_HAPPY_PATH) - {WorkflowState.COMPLETED}
    t[WorkflowState.BLOCKED] |= resumable
    t[WorkflowState.PAUSED] |= resumable
    t[WorkflowState.FAILED] |= {
        WorkflowState.IMPLEMENTING,
        WorkflowState.REVERTED,
        WorkflowState.CANCELLED,
    }
    return t


TRANSITIONS = _build_transitions()


class InvalidTransition(Exception):
    pass


class ApprovalRequired(Exception):
    pass


def validate_transition(
    current: WorkflowState,
    target: WorkflowState,
    approval_granted: bool = False,
) -> None:
    if target not in TRANSITIONS.get(current, set()):
        raise InvalidTransition(f"{current.value} -> {target.value} is not allowed")
    if HUMAN_GATES.get(current) == target and not approval_granted:
        raise ApprovalRequired(
            f"{current.value} -> {target.value} requires an approved human gate"
        )
