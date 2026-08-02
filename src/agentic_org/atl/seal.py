"""Named test oracle seals bound to a git HEAD (freshness)."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..core.ids import new_id, utc_now
from ..sandbox.policy import default_policy_for_repo, run_sandboxed

_PASSED = re.compile(r"([^\s:]+::[^\s]+)\s+PASSED")
_NODE_LINE = re.compile(r"^([^\s:]+::[^\s]+)\s*$", re.MULTILINE)


@dataclass
class OracleSeal:
    seal_id: str
    repo_head: str
    tree_hash: str
    command: list[str]
    exit_code: int
    passed_nodeids: list[str] = field(default_factory=list)
    file_hashes: dict[str, str] = field(default_factory=dict)
    minted_at: str = ""
    digest: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OracleSeal:
        return cls(
            seal_id=str(data.get("seal_id") or ""),
            repo_head=str(data.get("repo_head") or ""),
            tree_hash=str(data.get("tree_hash") or ""),
            command=list(data.get("command") or []),
            exit_code=int(data.get("exit_code") if data.get("exit_code") is not None else -1),
            passed_nodeids=list(data.get("passed_nodeids") or []),
            file_hashes=dict(data.get("file_hashes") or {}),
            minted_at=str(data.get("minted_at") or ""),
            digest=str(data.get("digest") or ""),
        )


def _git(repo: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, check=True,
    )
    return out.stdout.strip()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _canonical_digest(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def seal_digest(seal: OracleSeal) -> str:
    body = {
        "seal_id": seal.seal_id,
        "repo_head": seal.repo_head,
        "tree_hash": seal.tree_hash,
        "command": seal.command,
        "exit_code": seal.exit_code,
        "passed_nodeids": sorted(seal.passed_nodeids),
        "file_hashes": seal.file_hashes,
        "minted_at": seal.minted_at,
    }
    return _canonical_digest(body)


def hash_paths(repo: Path, rel_paths: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for rel in sorted(set(rel_paths)):
        path = repo / rel
        if path.is_file():
            out[rel.replace("\\", "/")] = _sha256_file(path)
    return out


def mint_seal(
    repo: Path,
    *,
    command: list[str] | None = None,
    paths_to_hash: list[str] | None = None,
    org_root: Path | None = None,
    passed_nodeids: list[str] | None = None,
    exit_code: int | None = None,
) -> OracleSeal:
    """Mint a seal from a live pytest run (or inject results for unit forges)."""
    cmd = command or [sys.executable, "-m", "pytest", "-v", "--tb=line", "-q"]
    head = _git(repo, "rev-parse", "HEAD")
    tree = _git(repo, "rev-parse", "HEAD^{tree}")

    if exit_code is None or passed_nodeids is None:
        sand = default_policy_for_repo(repo, org_root)
        run_cmd = list(cmd) if cmd else [sys.executable, "-m", "pytest", "-q", "--tb=line"]
        # Prefer python -m pytest form for sandbox allowlists
        if run_cmd and run_cmd[0].endswith("pytest"):
            run_cmd = [sys.executable, "-m", "pytest", *run_cmd[1:]]
        try:
            result = run_sandboxed(run_cmd, repo, sand)
        except Exception:
            seal = OracleSeal(
                seal_id=new_id("seal"),
                repo_head=head,
                tree_hash=tree,
                command=run_cmd,
                exit_code=126,
                passed_nodeids=[],
                file_hashes=hash_paths(repo, paths_to_hash or []),
                minted_at=utc_now(),
            )
            seal.digest = seal_digest(seal)
            return seal
        exit_code = result.exit_code
        text = (result.stdout or "") + "\n" + (result.stderr or "")
        found = _PASSED.findall(text)
        if not found and exit_code == 0:
            # When quiet mode hides nodeids, collect all selected tests as passed.
            collect_cmd = [sys.executable, "-m", "pytest", "--collect-only", "-q"]
            try:
                collected = run_sandboxed(collect_cmd, repo, sand)
                ctext = (collected.stdout or "") + "\n" + (collected.stderr or "")
                found = [m.replace("\\", "/") for m in _NODE_LINE.findall(ctext)]
            except Exception:
                found = []
        passed_nodeids = [n.replace("\\", "/") for n in found]
        cmd = run_cmd

    seal = OracleSeal(
        seal_id=new_id("seal"),
        repo_head=head,
        tree_hash=tree,
        command=list(cmd),
        exit_code=int(exit_code),
        passed_nodeids=list(passed_nodeids or []),
        file_hashes=hash_paths(repo, paths_to_hash or []),
        minted_at=utc_now(),
    )
    seal.digest = seal_digest(seal)
    return seal


def verify_seal_against_repo(seal: OracleSeal, repo: Path) -> tuple[bool, str]:
    """Freshness: seal HEAD/tree must match current repo; digest must verify."""
    if not seal.digest or seal.digest != seal_digest(seal):
        return False, "seal digest mismatch (tampered or incomplete)"
    try:
        head = _git(repo, "rev-parse", "HEAD")
        tree = _git(repo, "rev-parse", "HEAD^{tree}")
    except subprocess.CalledProcessError as exc:
        return False, f"git rev-parse failed: {exc}"
    if seal.repo_head != head:
        return False, f"stale seal: seal.repo_head={seal.repo_head[:12]} current={head[:12]}"
    if seal.tree_hash != tree:
        return False, "stale seal: tree hash mismatch"
    if seal.exit_code != 0:
        return False, f"seal exit_code={seal.exit_code} (not passing)"
    # Re-check hashed files if present
    for rel, expected in seal.file_hashes.items():
        path = repo / rel
        if not path.is_file():
            return False, f"sealed file missing: {rel}"
        if _sha256_file(path) != expected:
            return False, f"sealed file changed since mint: {rel}"
    return True, "ok"
