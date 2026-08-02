"""Unit tests for Acceptance-Trace Lock (ATL / C³)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from agentic_org.atl.criteria import parse_acceptance_criteria
from agentic_org.atl.lock import evaluate_atl, unlocked_suite_green_allows_completed
from agentic_org.atl.seal import mint_seal, seal_digest
from agentic_org.atl.trace import save_linkage


def _git_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for cmd in (
        ["git", "init"],
        ["git", "config", "user.email", "atl@a.org"],
        ["git", "config", "user.name", "ATL"],
    ):
        subprocess.run(cmd, cwd=path, check=True, capture_output=True)


def _commit_all(repo: Path, msg: str = "wip") -> None:
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", msg, "--allow-empty"],
        cwd=repo, check=True, capture_output=True,
    )


def test_parse_acceptance_criteria_formats():
    text = """
## Acceptance Criteria
- AC-1: rejects invalid rows
- **AC-2**: retries failed batches
* [AC-3] writes an audit receipt
- AC-1: duplicate ignored
"""
    crits = parse_acceptance_criteria(text)
    assert [c.id for c in crits] == ["AC-1", "AC-2", "AC-3"]
    assert "invalid" in crits[0].text


def test_atl_allows_when_trace_is_complete(tmp_path: Path):
    repo = tmp_path / "repo"
    arts = tmp_path / "artifacts"
    _git_repo(repo)
    (repo / "app.py").write_text("def ok():\n    return True\n", encoding="utf-8")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_ok.py").write_text(
        '"""ATL_COVERS: AC-1"""\nfrom app import ok\n\ndef test_ac1():\n    assert ok()\n',
        encoding="utf-8",
    )
    _commit_all(repo, "seed")
    save_linkage(arts / "acceptance_linkage.json", {"AC-1": ["tests/test_ok.py::test_ac1"]})
    charter = "## Acceptance Criteria\n- AC-1: feature works\n"
    decision = evaluate_atl(
        repo=repo,
        charter_text=charter,
        feature_artifacts=arts,
        workflow_id="wf_test",
        writes_count=1,
        gate_digests={"plan-approval": "apr_plan", "release-approval": "apr_rel"},
        mint_if_missing=True,
        org_root=tmp_path,
    )
    assert decision.allowed, decision.reason
    assert (arts / "acceptance_trace.json").exists()


def test_f1_empty_implement_blocked(tmp_path: Path):
    repo = tmp_path / "repo"
    arts = tmp_path / "artifacts"
    _git_repo(repo)
    (repo / "tests").mkdir()
    (repo / "tests" / "test_x.py").write_text(
        "def test_x():\n    assert True  # AC-1\n", encoding="utf-8",
    )
    _commit_all(repo)
    save_linkage(arts / "acceptance_linkage.json", {"AC-1": ["tests/test_x.py::test_x"]})
    decision = evaluate_atl(
        repo=repo,
        charter_text="- AC-1: x\n",
        feature_artifacts=arts,
        workflow_id="wf",
        writes_count=0,
        gate_digests={"plan-approval": "a", "release-approval": "b"},
        mint_if_missing=True,
        org_root=tmp_path,
    )
    assert not decision.allowed
    assert decision.forge_class == "F1"


def test_f2_hollow_tests_blocked(tmp_path: Path):
    repo = tmp_path / "repo"
    arts = tmp_path / "artifacts"
    _git_repo(repo)
    (repo / "tests").mkdir()
    # Passes but never mentions AC-1 / ATL_COVERS
    (repo / "tests" / "test_hollow.py").write_text(
        "def test_hello():\n    assert True\n", encoding="utf-8",
    )
    _commit_all(repo)
    save_linkage(
        arts / "acceptance_linkage.json",
        {"AC-1": ["tests/test_hollow.py::test_hello"]},
    )
    decision = evaluate_atl(
        repo=repo,
        charter_text="- AC-1: real requirement\n",
        feature_artifacts=arts,
        workflow_id="wf",
        writes_count=2,
        gate_digests={"plan-approval": "a", "release-approval": "b"},
        mint_if_missing=True,
        org_root=tmp_path,
    )
    assert not decision.allowed
    assert decision.forge_class == "F2"
    # Unlocked Mode A would still allow COMPLETED on suite green
    assert unlocked_suite_green_allows_completed(suite_exit_code=0, writes_count=2)


def test_f3_orphan_criteria_blocked(tmp_path: Path):
    repo = tmp_path / "repo"
    arts = tmp_path / "artifacts"
    _git_repo(repo)
    (repo / "tests").mkdir()
    (repo / "tests" / "test_a.py").write_text(
        "def test_a():\n    assert True  # AC-1\n", encoding="utf-8",
    )
    _commit_all(repo)
    save_linkage(arts / "acceptance_linkage.json", {"AC-1": ["tests/test_a.py::test_a"]})
    decision = evaluate_atl(
        repo=repo,
        charter_text="- AC-1: covered\n- AC-2: orphan\n",
        feature_artifacts=arts,
        workflow_id="wf",
        writes_count=1,
        gate_digests={"plan-approval": "a", "release-approval": "b"},
        mint_if_missing=True,
        org_root=tmp_path,
    )
    assert not decision.allowed
    assert decision.forge_class == "F3"


def test_f4_stale_seal_blocked(tmp_path: Path):
    repo = tmp_path / "repo"
    arts = tmp_path / "artifacts"
    _git_repo(repo)
    (repo / "tests").mkdir()
    (repo / "tests" / "test_a.py").write_text(
        "def test_a():\n    assert True  # AC-1\n", encoding="utf-8",
    )
    _commit_all(repo, "v1")
    save_linkage(arts / "acceptance_linkage.json", {"AC-1": ["tests/test_a.py::test_a"]})
    seal = mint_seal(
        repo,
        paths_to_hash=["tests/test_a.py"],
        org_root=tmp_path,
        command=[sys.executable, "-m", "pytest", "-v", "-q"],
    )
    # Mutate code after seal
    (repo / "extra.py").write_text("X=1\n", encoding="utf-8")
    _commit_all(repo, "v2")
    decision = evaluate_atl(
        repo=repo,
        charter_text="- AC-1: x\n",
        feature_artifacts=arts,
        workflow_id="wf",
        writes_count=1,
        gate_digests={"plan-approval": "a", "release-approval": "b"},
        seal=seal,
        mint_if_missing=False,
        org_root=tmp_path,
    )
    assert not decision.allowed
    assert decision.forge_class == "F4"


def test_f5_missing_gate_digest_blocked(tmp_path: Path):
    repo = tmp_path / "repo"
    arts = tmp_path / "artifacts"
    _git_repo(repo)
    (repo / "tests").mkdir()
    (repo / "tests" / "test_a.py").write_text(
        "def test_a():\n    assert True  # AC-1\n", encoding="utf-8",
    )
    _commit_all(repo)
    save_linkage(arts / "acceptance_linkage.json", {"AC-1": ["tests/test_a.py::test_a"]})
    decision = evaluate_atl(
        repo=repo,
        charter_text="- AC-1: x\n",
        feature_artifacts=arts,
        workflow_id="wf",
        writes_count=1,
        gate_digests={"plan-approval": "apr_plan"},  # missing release
        mint_if_missing=True,
        org_root=tmp_path,
    )
    assert not decision.allowed
    assert decision.forge_class == "F5"


def test_seal_digest_tamper_detected(tmp_path: Path):
    repo = tmp_path / "repo"
    _git_repo(repo)
    (repo / "t.py").write_text("def test_t():\n    assert True\n", encoding="utf-8")
    _commit_all(repo)
    seal = mint_seal(
        repo,
        exit_code=0,
        passed_nodeids=["t.py::test_t"],
        paths_to_hash=[],
    )
    assert seal.digest == seal_digest(seal)
    seal.exit_code = 1
    assert seal.digest != seal_digest(seal)
