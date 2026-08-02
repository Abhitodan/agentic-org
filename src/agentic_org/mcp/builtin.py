"""Built-in local-org MCP server (read-only) for Mode A wiring."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

SERVER_NAME = "local-org"
TOOL_REPO_SUMMARY = "repo_summary"


def ensure_builtin_mcp(mcp_dir: Path) -> None:
    """Ensure local-org server + read-only grant exist (idempotent merge)."""
    mcp_dir.mkdir(parents=True, exist_ok=True)
    reg_path = mcp_dir / "registry.yaml"
    perm_path = mcp_dir / "permissions.yaml"
    registry = _load(reg_path)
    permissions = _load(perm_path)
    servers = registry.setdefault("servers", [])
    if not isinstance(servers, list):
        servers = []
        registry["servers"] = servers
    if not any(isinstance(s, dict) and s.get("name") == SERVER_NAME for s in servers):
        servers.append({
            "name": SERVER_NAME,
            "description": "Built-in read-only org/repo summary (in-process)",
            "transport": "inprocess",
        })
        reg_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")

    grants = permissions.setdefault("grants", [])
    if not isinstance(grants, list):
        grants = []
        permissions["grants"] = grants
    grant_id = "grant-local-org-repo-summary"
    if not any(isinstance(g, dict) and g.get("id") == grant_id for g in grants):
        grants.append({
            "id": grant_id,
            "server": SERVER_NAME,
            "tools": [TOOL_REPO_SUMMARY],
            "roles": ["repository-agent"],
            "effect": "allow",
        })
        perm_path.write_text(
            yaml.safe_dump(permissions, sort_keys=False), encoding="utf-8"
        )


def repo_summary_executor(
    server: str, tool: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    """In-process read-only tool body."""
    if server != SERVER_NAME or tool != TOOL_REPO_SUMMARY:
        return {"error": "unknown builtin tool"}
    repo = Path(str(arguments.get("repo_path", ".")))
    if not repo.exists():
        return {"ok": False, "error": "repo_path missing", "repo_path": str(repo)}
    files = [
        str(p.relative_to(repo)).replace("\\", "/")
        for p in sorted(repo.rglob("*"))
        if p.is_file() and ".git" not in p.parts
    ][:200]
    return {
        "ok": True,
        "repo_path": str(repo.resolve()),
        "file_count": len(files),
        "sample_files": files[:40],
        "readonly": True,
    }


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}
