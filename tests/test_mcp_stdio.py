import sys
from pathlib import Path

import yaml

from agentic_org.context import build_context
from agentic_org.mcp.stdio_client import StdioMcpClient


def test_stdio_mcp_client_ping():
    server = Path(__file__).resolve().parents[1] / "scripts" / "mock_mcp_server.py"
    with StdioMcpClient([sys.executable, str(server)]) as client:
        tools = {t.name for t in client.list_tools()}
        assert "ping" in tools and "echo" in tools
        result = client.call_tool("echo", {"message": "hello"})
        text = result["content"][0]["text"]
        assert text == "hello"


def test_gateway_stdio_transport_after_grant(tmp_path: Path):
    root = tmp_path / "org"
    root.mkdir()
    server = Path(__file__).resolve().parents[1] / "scripts" / "mock_mcp_server.py"
    mcp = root / ".agent-org" / "mcp"
    mcp.mkdir(parents=True)
    (mcp / "registry.yaml").write_text(
        yaml.safe_dump({
            "servers": [{
                "name": "mock",
                "command": sys.executable,
                "args": [str(server)],
                "network": "deny",
            }],
        }),
        encoding="utf-8",
    )
    (mcp / "permissions.yaml").write_text(
        yaml.safe_dump({
            "grants": [{
                "id": "g1", "server": "mock", "tools": ["*"], "effect": "allow",
            }],
        }),
        encoding="utf-8",
    )
    ctx = build_context(str(root))
    out = ctx.mcp.call("mock", "ping", {}, role="backend-agent")
    assert out.allowed
    assert out.output["transport"] == "stdio"
    assert out.output["result"]["content"][0]["text"] == "pong"
