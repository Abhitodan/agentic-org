import sys
from pathlib import Path

import pytest

from agentic_org.sandbox import SandboxError, SandboxPolicy, run_sandboxed


def test_sandbox_denies_disallowed_command(tmp_path: Path):
    policy = SandboxPolicy(allowed_roots=[tmp_path], allowed_commands=[["git"]])
    with pytest.raises(SandboxError):
        run_sandboxed([sys.executable, "-c", "print(1)"], tmp_path, policy)


def test_sandbox_denies_cwd_escape(tmp_path: Path):
    inside = tmp_path / "jail"
    inside.mkdir()
    policy = SandboxPolicy(
        allowed_roots=[inside],
        allowed_commands=[[sys.executable, "-c"]],
        network="deny",
        deny_dangerous=False,  # isolate cwd check from argv denylist
    )
    with pytest.raises(SandboxError):
        run_sandboxed([sys.executable, "-c", "print(1)"], tmp_path, policy)


def test_sandbox_runs_allowlisted(tmp_path: Path):
    policy = SandboxPolicy(
        allowed_roots=[tmp_path],
        allowed_commands=[[sys.executable, "-c"]],
        network="deny",
        deny_dangerous=False,  # intentional -c for sandbox smoke
    )
    result = run_sandboxed(
        [sys.executable, "-c", "print('ok')"], tmp_path, policy,
    )
    assert result.ok
    assert "ok" in result.stdout
