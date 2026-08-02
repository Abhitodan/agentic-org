"""Registered offline evals for every shipped skill.

One entry per skill: the fixture arguments to invoke it with, the evidence
string it must return, and a predicate over the result. A skill without an
entry here is not considered shipped — `agentctl skill-eval` refuses it and
`tests/test_skill_eval_registry.py` fails the build.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

ArgBuilder = Callable[[Path, Path], dict[str, Any]]
ResultCheck = Callable[[dict[str, Any]], bool]


@dataclass(frozen=True)
class SkillEval:
    category: str
    expect_evidence: str
    build_args: ArgBuilder
    check: ResultCheck = lambda result: result.get("ok") is True


def _passes(result: dict[str, Any]) -> bool:
    return result.get("ok") is True


def _fails(result: dict[str, Any]) -> bool:
    """For evals whose fixture is deliberately defective."""
    return result.get("ok") is False


# A story that satisfies every product-category gate, reused across evals.
_READY_STORY = {
    "id": "US-1",
    "title": "Import member CSV",
    "as_a": "operations lead",
    "i_want": "to import a member CSV",
    "so_that": "enrolment stops being manual",
    "acceptance_criteria": [
        "AC-1: Given a 500-row CSV, when import runs, then invalid rows are "
        "reported with line numbers",
    ],
    "estimate": 5,
}


SKILL_EVALS: dict[str, SkillEval] = {
    # ---- discovery -------------------------------------------------------
    "repository-analysis": SkillEval(
        category="discovery",
        expect_evidence="deterministic_ast_and_filesystem",
        build_args=lambda fixture, root: {"repo_path": str(fixture)},
        check=lambda r: _passes(r) and int(r.get("file_count") or 0) >= 1,
    ),
    "dependency-doctor": SkillEval(
        category="discovery",
        expect_evidence="deterministic_manifest_scan",
        build_args=lambda fixture, root: {"repo_path": str(fixture)},
        check=lambda r: "findings" in r,
    ),
    "commit-archaeologist": SkillEval(
        category="discovery",
        expect_evidence="deterministic_git_history",
        build_args=lambda fixture, root: {
            "repo_path": str(fixture), "paths": ["app.py"],
        },
        # The fixture may not be a git repo; a structured answer is the pass.
        check=lambda r: isinstance(r.get("history"), list),
    ),
    # ---- planning --------------------------------------------------------
    "feature-planning": SkillEval(
        category="planning",
        expect_evidence="deterministic_ac_and_grounding",
        build_args=lambda fixture, root: {
            "charter": "- AC-1: Smoke works\n",
            "plan": "Touch `app.py`.\n",
            "repo_path": str(fixture),
            "hard_fail": False,
        },
    ),
    # ---- implementation --------------------------------------------------
    "implementation": SkillEval(
        category="implementation",
        expect_evidence="deterministic_apply_and_tests",
        build_args=lambda fixture, root: {
            "worktree": str(fixture),
            "actions": [{"op": "write", "path": "eval_note.txt", "content": "ok\n"}],
            "org_root": str(root),
        },
    ),
    # ---- verification ----------------------------------------------------
    "test-evidence": SkillEval(
        category="verification",
        expect_evidence="deterministic_test_run",
        build_args=lambda fixture, root: {
            "cwd": str(fixture), "org_root": str(root),
        },
    ),
    # ---- review ----------------------------------------------------------
    "scope-creep-detector": SkillEval(
        category="review",
        expect_evidence="deterministic_path_scope",
        build_args=lambda fixture, root: {
            "objective": "fix app.py",
            "changed_paths": ["app.py"],
            "plan_text": "Edit `app.py`.\n",
        },
    ),
    "code-review": SkillEval(
        category="review",
        expect_evidence="deterministic_diff_ac_tests",
        build_args=lambda fixture, root: {
            "diff_text": "diff --git a/app.py b/app.py\n+++ b/app.py\n+print(1)\n",
            "charter": "- AC-1: Smoke works\n",
            "objective": "fix app.py",
            "changed_paths": ["app.py"],
            "plan_text": "Edit `app.py`.\n",
            "test_evidence": {"ok": True, "exit_code": 0},
        },
    ),
    # ---- product ---------------------------------------------------------
    "story-authoring": SkillEval(
        category="product",
        expect_evidence="deterministic_story_structure",
        build_args=lambda fixture, root: {"stories": [_READY_STORY]},
    ),
    "acceptance-criteria-forge": SkillEval(
        category="product",
        expect_evidence="deterministic_ac_testability",
        build_args=lambda fixture, root: {
            "criteria": _READY_STORY["acceptance_criteria"], "story_id": "US-1",
        },
        check=lambda r: _passes(r) and r.get("testable_count") == 1,
    ),
    "story-splitting": SkillEval(
        category="product",
        expect_evidence="deterministic_split_coverage",
        build_args=lambda fixture, root: {
            "parent": {"id": "US-10", "acceptance_criteria": [
                "AC-1: then the importer accepts a valid file",
                "AC-2: then the importer rejects a malformed file",
            ]},
            "slices": [
                {"id": "US-10a", "parent": "US-10", "covers": ["AC-1"],
                 "acceptance_criteria": ["AC-1: then a valid file is accepted"],
                 "estimate": 3},
                {"id": "US-10b", "parent": "US-10", "covers": ["AC-2"],
                 "acceptance_criteria": ["AC-2: then a malformed file is rejected"],
                 "estimate": 5},
            ],
        },
        check=lambda r: _passes(r) and r.get("uncovered_criteria") == [],
    ),
    "backlog-prioritization": SkillEval(
        category="product",
        expect_evidence="deterministic_backlog_ranking",
        build_args=lambda fixture, root: {
            "stories": [
                {"id": "A", "business_value": 8, "time_criticality": 5,
                 "risk_reduction": 2, "job_size": 3},
                {"id": "B", "business_value": 8, "time_criticality": 5,
                 "risk_reduction": 2, "job_size": 1},
            ],
        },
        check=lambda r: [row["id"] for row in r.get("ranking", [])] == ["B", "A"],
    ),
    "definition-of-ready-gate": SkillEval(
        category="product",
        expect_evidence="deterministic_ready_gate",
        build_args=lambda fixture, root: {"stories": [_READY_STORY]},
        check=lambda r: _passes(r) and r.get("ready") == ["US-1"],
    ),
    "epic-decomposition": SkillEval(
        category="product",
        expect_evidence="deterministic_epic_traceability",
        build_args=lambda fixture, root: {
            "epic": {"id": "EPIC-1", "acceptance_criteria": [
                "AC-1: then members can self-enrol",
            ]},
            "stories": [{"id": "US-1", "parent": "EPIC-1", "covers": ["AC-1"],
                         "estimate": 3}],
        },
        check=lambda r: _passes(r) and r.get("uncovered_outcomes") == [],
    ),
    # ---- ceremonies ------------------------------------------------------
    "sprint-planning": SkillEval(
        category="ceremonies",
        expect_evidence="deterministic_sprint_commitment",
        build_args=lambda fixture, root: {
            "sprint_goal": "Members can self-enrol without support tickets",
            "stories": [_READY_STORY],
            "member_days": 20,
            "sprint_length_days": 10,
            "historical_velocity": [10, 11, 12],
            "ready_ids": ["US-1"],
        },
        check=lambda r: _passes(r) and r.get("utilization") is not None,
    ),
    "standup-synthesis": SkillEval(
        category="ceremonies",
        expect_evidence="deterministic_standup_signals",
        build_args=lambda fixture, root: {
            "updates": [{
                "member": "backend-agent",
                "yesterday": "wired the importer",
                "today": "finish validation",
                "blockers": [{"text": "staging credentials",
                              "owner": "release-agent"}],
            }],
            "team": ["backend-agent"],
        },
        check=lambda r: _passes(r) and r.get("blocker_count") == 1,
    ),
    "backlog-refinement": SkillEval(
        category="ceremonies",
        expect_evidence="deterministic_refinement_funnel",
        build_args=lambda fixture, root: {
            "stories": [
                dict(_READY_STORY, id=f"US-{index}", estimate=8)
                for index in range(1, 6)
            ],
            "ready_ids": [f"US-{index}" for index in range(1, 6)],
            "historical_velocity": [20, 21, 22],
        },
        check=lambda r: _passes(r) and (r.get("runway_sprints") or 0) >= 1.5,
    ),
    "sprint-review": SkillEval(
        category="ceremonies",
        expect_evidence="deterministic_increment_demo",
        build_args=lambda fixture, root: {
            "committed": [_READY_STORY],
            "demonstrated_ids": ["US-1"],
            "test_evidence": {"US-1": {"ok": True, "exit_code": 0}},
            "sprint_goal": "Members can self-enrol without support tickets",
        },
        check=lambda r: _passes(r) and r.get("delivered") == ["US-1"],
    ),
    "retrospective": SkillEval(
        category="ceremonies",
        expect_evidence="deterministic_retro_actions",
        build_args=lambda fixture, root: {
            "actions": [{
                "text": "Add a CI check that fails when coverage drops below 70%",
                "owner": "backend-agent",
                "due": "sprint-14",
                "impediment": "IMP-3",
            }],
        },
        check=lambda r: _passes(r) and r.get("complete_actions") == 1,
    ),
    "velocity-analytics": SkillEval(
        category="ceremonies",
        expect_evidence="deterministic_velocity_statistics",
        build_args=lambda fixture, root: {"sprints": [20, 21, 22, 20, 21]},
        check=lambda r: _passes(r) and r["velocity"]["forecast_low"] == 20,
    ),
    "impediment-tracker": SkillEval(
        category="ceremonies",
        expect_evidence="deterministic_impediment_ageing",
        build_args=lambda fixture, root: {
            "impediments": [{"id": "IMP-1", "severity": "medium",
                             "age_days": 2, "owner": "planning-agent"}],
        },
        check=lambda r: _passes(r) and r.get("open_count") == 1,
    ),
    # ---- discovery: code intelligence ------------------------------------
    "code-intelligence": SkillEval(
        category="discovery",
        expect_evidence="deterministic_python_ast_graph",
        build_args=lambda fixture, root: {
            "mode": "index",
            "repo_path": str(fixture),
            "graph_dir": str(fixture / ".agent-org" / "state" / "code-graph"),
        },
        check=lambda r: _passes(r) and int(r.get("node_count") or 0) >= 1,
    ),
    # ---- delivery --------------------------------------------------------
    "release-readiness": SkillEval(
        category="delivery",
        expect_evidence="deterministic_release_evidence",
        build_args=lambda fixture, root: {
            "stories": [_READY_STORY],
            "demonstrated_ids": ["US-1"],
            "test_evidence": {"US-1": {"ok": True, "exit_code": 0}},
            "review_result": {"ok": True, "findings": []},
            "approval": {"approved": True, "gate": "release-approval"},
            "rollback_plan": {"ok": True, "revert_to": "v1.0.0", "verify": "curl /health"},
        },
        check=lambda r: _passes(r) and r.get("ready") is True,
    ),
    "deployment-verification": SkillEval(
        category="delivery",
        expect_evidence="deterministic_deployment_checks",
        build_args=lambda fixture, root: {
            "cwd": str(fixture),
            "org_root": str(root),
            # Same allowlisted shape as test-evidence (sandbox rejects bare -c).
            "commands": [[
                __import__("sys").executable, "-m", "pytest", "-q",
                str(fixture / "tests"),
            ]],
            "deployment_record": {"status": "success"},
        },
        check=lambda r: _passes(r) and r.get("all_green") is True,
    ),
    "rollback-plan": SkillEval(
        category="delivery",
        expect_evidence="deterministic_rollback_completeness",
        build_args=lambda fixture, root: {
            "plan": {
                "revert_to": "sha-abc",
                "verify": "pytest -q",
                "owner": "release-agent",
            },
            "migrations": [{"name": "m1", "reversible": True}],
        },
    ),
    "changelog-forge": SkillEval(
        category="delivery",
        expect_evidence="deterministic_changelog_traceability",
        build_args=lambda fixture, root: {
            "stories": [_READY_STORY],
            "commits": [{"sha": "aaa", "message": "US-1 import csv"}],
        },
        check=lambda r: _passes(r) and r.get("entry_count") == 1,
    ),
    # ---- orchestration ---------------------------------------------------
    "handoff-contract": SkillEval(
        category="orchestration",
        expect_evidence="deterministic_handoff_completeness",
        build_args=lambda fixture, root: {
            "from_persona": "backend-agent",
            "to_persona": "reviewer-agent",
            "artifacts": {
                "diff": "diff --git a/x b/x\n",
                "test_evidence": {"ok": True},
            },
        },
        check=lambda r: _passes(r) and r.get("allowed") is True,
    ),
    "wip-limit-guard": SkillEval(
        category="orchestration",
        expect_evidence="deterministic_wip_enforcement",
        build_args=lambda fixture, root: {
            "assignments": [{"persona": "backend-agent"}],
            "limits": {"per_persona": 2},
            "proposed": {"persona": "backend-agent"},
        },
        check=lambda r: _passes(r) and r.get("accepted") is True,
    ),
    "work-routing": SkillEval(
        category="orchestration",
        expect_evidence="deterministic_capability_routing",
        build_args=lambda fixture, root: {
            "stories": [dict(_READY_STORY, components=["backend"])],
            "personas": [
                {"id": "backend-agent", "capabilities": ["backend", "implementation"]},
            ],
            "assignments": [],
            "wip_limit": 2,
        },
        check=lambda r: _passes(r) and r.get("routed_count") == 1,
    ),
    "escalation-protocol": SkillEval(
        category="orchestration",
        expect_evidence="deterministic_escalation_triggers",
        build_args=lambda fixture, root: {
            "budget": {"spent_usd": 1.0, "maximum_usd": 10.0},
            "confidence": 0.9,
            "policy_flags": [],
            "impediments": [],
        },
        check=lambda r: _passes(r) and r.get("must_escalate") is False,
    ),
    "ceremony-state-machine": SkillEval(
        category="orchestration",
        expect_evidence="deterministic_ceremony_sequence",
        build_args=lambda fixture, root: {
            "ceremony_log": [
                {"name": "backlog-refinement", "artifacts": {"ready_ids": ["US-1"]}},
                {"name": "sprint-planning",
                 "artifacts": {"sprint_goal": "Ship import", "commitment": ["US-1"]}},
                {"name": "sprint-review", "artifacts": {"demonstrated_ids": ["US-1"]}},
                {"name": "retrospective",
                 "artifacts": {"actions": [{"text": "Automate deploy", "owner": "x",
                                            "due": "s2"}]}},
            ],
        },
        check=lambda r: _passes(r) and r.get("ceremony_count") == 4,
    ),
}
