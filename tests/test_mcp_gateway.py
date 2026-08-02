"""MCP deny-by-default gateway."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from agentic_org.context import build_context
from agentic_org.mcp import McpDenied, McpGateway


def _write_mcp(root: Path, servers, grants) -> McpGateway:
    mcp = root / ".agent-org" / "mcp"
    mcp.mkdir(parents=True, exist_ok=True)
    (mcp / "registry.yaml").write_text(
        yaml.safe_dump({"servers": servers}), encoding="utf-8"
    )
    (mcp / "permissions.yaml").write_text(
        yaml.safe_dump({"grants": grants}), encoding="utf-8"
    )
    ctx = build_context(str(root))
    return ctx.mcp


def test_deny_by_default_when_no_grants(tmp_path: Path):
    gw = _write_mcp(
        tmp_path,
        servers=[{"name": "fs", "command": "npx", "args": ["demo"]}],
        grants=[],
    )
    with pytest.raises(McpDenied) as exc:
        gw.call("fs", "read_file", {"path": "x"}, role="backend-agent")
    assert "deny-by-default" in str(exc.value)
    events = [e for e in gw.events.list() if e["event_type"] == "mcp.denied"]
    assert events


def test_deny_unregistered_server(tmp_path: Path):
    gw = _write_mcp(tmp_path, servers=[], grants=[
        {"id": "g1", "server": "fs", "tools": ["*"], "effect": "allow"},
    ])
    with pytest.raises(McpDenied) as exc:
        gw.authorize("fs", "read_file")
    assert "not registered" in str(exc.value)


def test_allow_matching_grant_and_executor(tmp_path: Path):
    gw = _write_mcp(
        tmp_path,
        servers=[{"name": "fs"}],
        grants=[{
            "id": "g-fs",
            "server": "fs",
            "tools": ["read_file"],
            "roles": ["backend-agent"],
            "effect": "allow",
        }],
    )

    def executor(server, tool, arguments):
        return {"echo": arguments}

    result = gw.call(
        "fs", "read_file", {"path": "a.txt"},
        role="backend-agent", executor=executor,
    )
    assert result.allowed is True
    assert result.output == {"echo": {"path": "a.txt"}}
    assert any(e["event_type"] == "mcp.called" for e in gw.events.list())
