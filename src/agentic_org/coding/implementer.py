"""Worktree-based implementation gated on real test execution.

Success is never declared because code was generated. The only success
signal is a test command exiting 0 inside the isolated worktree.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..gateway.model_gateway import ModelGateway, ModelUnavailable
from ..sandbox.policy import SandboxError, SandboxPolicy, default_policy_for_repo, run_sandboxed
from ..workspace.git_ws import GitError, GitWorkspace


@dataclass
class TestRunResult:
    ok: bool
    exit_code: int
    command: list[str]
    stdout: str
    stderr: str
    duration_ms: int


@dataclass
class ImplementationResult:
    ok: bool
    worktree: Path | None
    task_id: str
    actions_applied: int = 0
    test: TestRunResult | None = None
    reason: str = ""
    notes: list[str] = field(default_factory=list)


def run_tests(
    cwd: Path,
    command: list[str] | None = None,
    *,
    policy: SandboxPolicy | None = None,
    org_root: Path | None = None,
) -> TestRunResult:
    cmd = command or [sys.executable, "-m", "pytest", "-q", "--tb=line"]
    sand = policy or default_policy_for_repo(cwd, org_root)
    # Ensure pytest invocation is allowlisted even when using -m pytest form.
    if not sand.allows_command(cmd):
        sand.allowed_commands.append(cmd[:3] if len(cmd) >= 3 else cmd)
    try:
        result = run_sandboxed(cmd, cwd, sand)
    except SandboxError as exc:
        return TestRunResult(
            ok=False, exit_code=126, command=cmd,
            stdout="", stderr=str(exc), duration_ms=0,
        )
    return TestRunResult(
        ok=result.ok,
        exit_code=result.exit_code,
        command=result.command,
        stdout=result.stdout,
        stderr=result.stderr,
        duration_ms=result.duration_ms,
    )


_IGNORE_ON_COMMIT = {".pytest_cache", "__pycache__", ".mypy_cache", ".ruff_cache"}


def _cleanup_noise(worktree: Path) -> None:
    import shutil

    for name in _IGNORE_ON_COMMIT:
        path = worktree / name
        if path.exists():
            shutil.rmtree(path, ignore_errors=True)


def _contained_in_worktree(worktree: Path, target: Path) -> bool:
    """True if target is worktree or a descendant (not a path-prefix sibling)."""
    root = worktree.resolve()
    path = target.resolve()
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def apply_actions(worktree: Path, actions: list[dict[str, Any]]) -> int:
    """Apply JSON file actions. Supported ops: write, append."""
    if not actions:
        raise ValueError(
            "empty implementation actions are not success; provide at least one write/append"
        )
    count = 0
    for action in actions:
        op = action.get("op")
        rel = action.get("path")
        if not op or not rel:
            raise ValueError(f"invalid action: {action!r}")
        # Reject absolute / parent traversal before resolve games.
        rel_path = Path(rel)
        if rel_path.is_absolute() or ".." in rel_path.parts:
            raise ValueError(f"action path escapes worktree: {rel}")
        target = (worktree / rel_path).resolve()
        if not _contained_in_worktree(worktree, target):
            raise ValueError(f"action path escapes worktree: {rel}")
        target.parent.mkdir(parents=True, exist_ok=True)
        content = action.get("content", "")
        if op == "write":
            target.write_text(str(content), encoding="utf-8")
        elif op == "append":
            prev = target.read_text(encoding="utf-8") if target.exists() else ""
            target.write_text(prev + str(content), encoding="utf-8")
        else:
            raise ValueError(f"unsupported action op: {op}")
        count += 1
    return count


def _extract_json_array(text: str) -> list[dict[str, Any]]:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    else:
        start, end = text.find("["), text.rfind("]")
        if start >= 0 and end > start:
            text = text[start : end + 1]
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("expected JSON array of actions")
    return data


class Implementer:
    """Creates a worktree, applies actions, runs tests, reports evidence."""

    def __init__(
        self,
        repo_path: Path,
        worktrees_dir: Path,
        *,
        org_root: Path | None = None,
        sandbox_policy: SandboxPolicy | None = None,
    ):
        self.repo = Path(repo_path)
        self.worktrees_dir = Path(worktrees_dir)
        self.org_root = org_root
        self.sandbox_policy = sandbox_policy
        self.ws = GitWorkspace(self.repo)

    def load_actions_file(self, path: Path) -> list[dict[str, Any]]:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError(f"actions file must be a JSON array: {path}")
        return data

    def propose_actions_via_llm(
        self,
        gateway: ModelGateway,
        objective: str,
        plan_text: str,
        file_listing: str,
    ) -> list[dict[str, Any]]:
        result = gateway.complete(
            "standard",
            system=(
                "You are a coding agent. Return ONLY a JSON array of file actions "
                "to implement the plan in a small repository. Each item: "
                '{"op":"write"|"append","path":"relative/path","content":"..."}. '
                "Do not wrap in prose. Do not invent unrelated files. Prefer "
                "minimal changes that make tests pass."
            ),
            user=(
                f"Objective:\n{objective}\n\nPlan:\n{plan_text[:6000]}\n\n"
                f"Repository files:\n{file_listing[:4000]}"
            ),
            max_output_tokens=3000,
        )
        return _extract_json_array(result.text)

    def run(
        self,
        task_id: str,
        actions: list[dict[str, Any]] | None = None,
        *,
        gateway: ModelGateway | None = None,
        objective: str = "",
        plan_text: str = "",
        test_command: list[str] | None = None,
    ) -> ImplementationResult:
        if not self.ws.is_repo():
            return ImplementationResult(
                ok=False, worktree=None, task_id=task_id,
                reason="target path is not a git repository",
            )
        try:
            worktree = self.ws.create_worktree(task_id, self.worktrees_dir)
        except GitError as exc:
            return ImplementationResult(
                ok=False, worktree=None, task_id=task_id,
                reason=f"worktree creation failed: {exc}",
            )

        notes: list[str] = [f"worktree={worktree}"]
        try:
            if actions is None:
                if gateway is None or not gateway.available():
                    return ImplementationResult(
                        ok=False, worktree=worktree, task_id=task_id,
                        reason="no implementation_actions.json and model unavailable",
                        notes=notes,
                    )
                listing = "\n".join(
                    str(p.relative_to(worktree))
                    for p in sorted(worktree.rglob("*"))
                    if p.is_file() and ".git" not in p.parts
                )[:4000]
                try:
                    actions = self.propose_actions_via_llm(
                        gateway, objective, plan_text, listing
                    )
                except (ModelUnavailable, ValueError, json.JSONDecodeError) as exc:
                    return ImplementationResult(
                        ok=False, worktree=worktree, task_id=task_id,
                        reason=f"could not obtain implementation actions: {exc}",
                        notes=notes,
                    )
                notes.append(f"actions_from=llm count={len(actions)}")
            else:
                notes.append(f"actions_from=file count={len(actions)}")

            applied = apply_actions(worktree, actions)
            test = run_tests(
                worktree, test_command,
                policy=self.sandbox_policy, org_root=self.org_root,
            )
            notes.append(
                f"tests_ok={test.ok} exit={test.exit_code} ms={test.duration_ms}"
            )
            if not test.ok:
                return ImplementationResult(
                    ok=False,
                    worktree=worktree,
                    task_id=task_id,
                    actions_applied=applied,
                    test=test,
                    reason="tests failed after implementation; success not claimed",
                    notes=notes,
                )
            return ImplementationResult(
                ok=True,
                worktree=worktree,
                task_id=task_id,
                actions_applied=applied,
                test=test,
                reason="tests passed in worktree",
                notes=notes,
            )
        except Exception as exc:  # evidence over claims
            return ImplementationResult(
                ok=False, worktree=worktree, task_id=task_id,
                reason=f"implementation error: {type(exc).__name__}: {exc}",
                notes=notes,
            )


def default_test_command() -> list[str]:
    override = os.environ.get("AGENTIC_ORG_TEST_COMMAND", "").strip()
    if override:
        return override.split()
    return [sys.executable, "-m", "pytest", "-q", "--tb=line"]
