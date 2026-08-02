"""Best-effort process and network sandbox for agent commands.

Hard guarantees on this host:
- Command must match an allowlist prefix.
- Working directory must stay inside configured roots.
- Environment is scrubbed of secrets and proxy variables when network=deny.

Linux optional: when `network=deny` and `unshare` is available, spawn with
`unshare -n` / `unshare --net` to drop network namespace. Windows has no
equivalent here — denial is policy + env scrubbing only (documented).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class SandboxError(Exception):
    pass


# Modules allowed after `python -m` when the interpreter is allowlisted.
_SAFE_PYTHON_MODULES = frozenset({"pytest"})


def dangerous_command_reason(command: list[str]) -> str | None:
    """Return a reason string if argv is on the hard denylist, else None."""
    if not command:
        return "empty command"
    exe = Path(command[0]).name.lower()
    args_l = [a.lower() for a in command[1:]]
    if exe in {"python", "python3", "python.exe", "py", "py.exe"}:
        if "-c" in args_l:
            return "python -c is denied"
        if "-m" in args_l:
            try:
                idx = args_l.index("-m")
                mod = args_l[idx + 1] if idx + 1 < len(args_l) else ""
            except (ValueError, IndexError):
                mod = ""
            if mod not in _SAFE_PYTHON_MODULES:
                return f"python -m {mod or '<missing>'} is denied"
    if exe in {"git", "git.exe"}:
        if "push" in args_l:
            return "git push is denied"
        if "reset" in args_l and "--hard" in args_l:
            return "git reset --hard is denied"
        if "clean" in args_l:
            return "git clean is denied"
    if exe in {"bash", "sh", "zsh", "cmd", "cmd.exe", "powershell",
               "powershell.exe", "pwsh", "pwsh.exe"}:
        if any(flag in args_l for flag in ("-c", "/c", "-command", "-encodedcommand")):
            return f"{exe} interactive/command flag is denied"
    return None


@dataclass
class SandboxPolicy:
    allowed_roots: list[Path]
    allowed_commands: list[list[str]] = field(default_factory=lambda: [
        [sys.executable, "-m", "pytest"],
        ["git"],
        [sys.executable],
    ])
    network: str = "deny"  # deny | allow
    timeout_seconds: int = 120
    extra_env: dict[str, str] = field(default_factory=dict)
    deny_dangerous: bool = True

    def allows_command(self, command: list[str]) -> bool:
        if not command:
            return False
        if self.deny_dangerous and dangerous_command_reason(command):
            return False
        for prefix in self.allowed_commands:
            if len(command) >= len(prefix) and command[: len(prefix)] == prefix:
                return True
            # Allow bare executable name match for git/python (still denylist-gated)
            if prefix and command[0] == prefix[0]:
                if len(prefix) == 1:
                    return True
                if command[: len(prefix)] == prefix:
                    return True
        return False

    def allows_cwd(self, cwd: Path) -> bool:
        resolved = cwd.resolve()
        for root in self.allowed_roots:
            try:
                resolved.relative_to(root.resolve())
                return True
            except ValueError:
                continue
        return False


@dataclass
class SandboxResult:
    ok: bool
    exit_code: int
    command: list[str]
    stdout: str
    stderr: str
    duration_ms: int
    network_mode: str
    used_unshare: bool = False


_SECRET_ENV_PREFIXES = (
    "GEMINI_", "GOOGLE_", "OPENAI_", "AWS_", "AZURE_", "AGENTIC_ORG_MODEL",
    "AGENTIC_ORG_API",
)
_PROXY_KEYS = (
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy",
    "all_proxy", "NO_PROXY", "no_proxy",
)


def scrub_env(network: str, extra: dict[str, str] | None = None) -> dict[str, str]:
    env = {
        k: v for k, v in os.environ.items()
        if not any(k.startswith(p) or k == p.rstrip("_") for p in _SECRET_ENV_PREFIXES)
        and "API_KEY" not in k and "TOKEN" not in k and "SECRET" not in k
    }
    # Keep PATH / SYSTEMROOT / essential runtime vars
    keep = {"PATH", "SYSTEMROOT", "WINDIR", "HOME", "USERPROFILE", "TEMP", "TMP",
            "LANG", "LC_ALL", "PYTHONPATH", "VIRTUAL_ENV", "PATHEXT", "COMSPEC"}
    env = {k: v for k, v in env.items() if k in keep or k.startswith("PYTHON")}
    if network == "deny":
        for key in _PROXY_KEYS:
            env.pop(key, None)
        env["AGENTIC_ORG_SANDBOX_NETWORK"] = "deny"
    if extra:
        env.update(extra)
    return env


def _wrap_unshare(command: list[str]) -> tuple[list[str], bool]:
    unshare = shutil.which("unshare")
    if not unshare:
        return command, False
    # Prefer --net; fall back to -n
    return [unshare, "--net", "--"] + command, True


def run_sandboxed(
    command: list[str],
    cwd: Path,
    policy: SandboxPolicy,
) -> SandboxResult:
    if policy.deny_dangerous:
        reason = dangerous_command_reason(command)
        if reason:
            raise SandboxError(f"command denied by sandbox policy: {reason}: {command}")
    if not policy.allows_command(command):
        raise SandboxError(f"command not allowlisted: {command}")
    if not policy.allows_cwd(cwd):
        raise SandboxError(f"cwd outside allowed roots: {cwd}")

    wrapped = list(command)
    used_unshare = False
    if policy.network == "deny" and os.name != "nt":
        wrapped, used_unshare = _wrap_unshare(command)

    env = scrub_env(policy.network, policy.extra_env)
    started = time.monotonic()
    try:
        proc = subprocess.run(
            wrapped,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=policy.timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise SandboxError(
            f"command timed out after {policy.timeout_seconds}s: {command}"
        ) from exc

    return SandboxResult(
        ok=proc.returncode == 0,
        exit_code=proc.returncode,
        command=wrapped,
        stdout=(proc.stdout or "")[-8000:],
        stderr=(proc.stderr or "")[-8000:],
        duration_ms=int((time.monotonic() - started) * 1000),
        network_mode=policy.network,
        used_unshare=used_unshare,
    )


def default_policy_for_repo(repo: Path, org_root: Path | None = None) -> SandboxPolicy:
    roots = [repo.resolve()]
    if org_root is not None:
        roots.append(org_root.resolve())
    return SandboxPolicy(allowed_roots=roots, network="deny")
