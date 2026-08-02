"""Deny-by-default MCP gateway with real stdio transport.

Authorization always runs first. When a server declares `command` (+ optional
`args`) in the registry and no custom executor is supplied, the gateway
spawns a JSON-RPC stdio MCP client (`initialize` / `tools/list` / `tools/call`).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ..core.events import Event, EventStore
from ..sandbox.policy import SandboxPolicy
from .stdio_client import McpTransportError, StdioMcpClient


class McpDenied(Exception):
    """Raised when a call is not explicitly granted."""

    def __init__(self, server: str, tool: str, reason: str):
        self.server = server
        self.tool = tool
        self.reason = reason
        super().__init__(f"MCP denied {server}/{tool}: {reason}")


@dataclass
class McpCallResult:
    server: str
    tool: str
    allowed: bool
    reason: str
    output: Any = None


class McpGateway:
    def __init__(
        self,
        registry_path: Path,
        permissions_path: Path,
        events: EventStore | None = None,
        *,
        org_root: Path | None = None,
    ):
        self.registry_path = registry_path
        self.permissions_path = permissions_path
        self.events = events
        self.org_root = org_root
        self.registry = self._load_yaml(registry_path)
        self.permissions = self._load_yaml(permissions_path)

    @staticmethod
    def _load_yaml(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {"servers": [], "grants": []}
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            return {"servers": [], "grants": []}
        return data

    def reload(self) -> None:
        self.registry = self._load_yaml(self.registry_path)
        self.permissions = self._load_yaml(self.permissions_path)

    def list_servers(self) -> list[dict[str, Any]]:
        servers = self.registry.get("servers") or []
        return list(servers) if isinstance(servers, list) else []

    def get_server(self, server: str) -> dict[str, Any] | None:
        for item in self.list_servers():
            if item.get("name") == server:
                return item
        return None

    def server_registered(self, server: str) -> bool:
        return self.get_server(server) is not None

    def is_allowed(
        self,
        server: str,
        tool: str,
        *,
        role: str | None = None,
        workflow_state: str | None = None,
    ) -> tuple[bool, str]:
        """Return (allowed, reason). Deny by default."""
        if not self.server_registered(server):
            return False, "server not registered"
        grants = self.permissions.get("grants") or []
        if not isinstance(grants, list) or not grants:
            return False, "deny-by-default: no grants configured"
        for grant in grants:
            if not isinstance(grant, dict):
                continue
            if grant.get("server") != server:
                continue
            tools = grant.get("tools") or []
            if tools != ["*"] and tool not in tools:
                continue
            roles = grant.get("roles")
            if roles:
                # Role-scoped grants require an explicit role (no role=None bypass).
                if role is None:
                    continue
                if role not in roles:
                    continue
            states = grant.get("workflow_states")
            if states:
                if workflow_state is None:
                    continue
                if workflow_state not in states:
                    continue
            if grant.get("effect", "allow") != "allow":
                continue
            return True, f"granted by {grant.get('id', 'grant')}"
        return False, "deny-by-default: no matching grant"

    def authorize(
        self,
        server: str,
        tool: str,
        *,
        role: str | None = None,
        workflow_state: str | None = None,
        workflow_id: str | None = None,
        raise_on_deny: bool = True,
    ) -> McpCallResult:
        allowed, reason = self.is_allowed(
            server, tool, role=role, workflow_state=workflow_state
        )
        result = McpCallResult(
            server=server, tool=tool, allowed=allowed, reason=reason
        )
        if self.events is not None:
            self.events.append(Event(
                event_type="mcp.authorized" if allowed else "mcp.denied",
                workflow_id=workflow_id,
                agent_role=role,
                status="ok" if allowed else "denied",
                payload={
                    "server": server,
                    "tool": tool,
                    "allowed": allowed,
                    "reason": reason,
                    "workflow_state": workflow_state,
                },
            ))
        if not allowed and raise_on_deny:
            raise McpDenied(server, tool, reason)
        return result

    def _stdio_command(self, server_cfg: dict[str, Any]) -> list[str]:
        command = server_cfg.get("command")
        if not command:
            return []
        if isinstance(command, list):
            return [str(x) for x in command]
        args = server_cfg.get("args") or []
        return [str(command), *[str(a) for a in args]]

    def call(
        self,
        server: str,
        tool: str,
        arguments: dict[str, Any] | None = None,
        *,
        role: str | None = None,
        workflow_state: str | None = None,
        workflow_id: str | None = None,
        executor: Any | None = None,
    ) -> McpCallResult:
        """Authorize, then invoke executor or real stdio MCP server."""
        auth = self.authorize(
            server, tool, role=role, workflow_state=workflow_state,
            workflow_id=workflow_id, raise_on_deny=True,
        )
        if executor is not None:
            auth.output = executor(server, tool, arguments or {})
        else:
            server_cfg = self.get_server(server) or {}
            cmd = self._stdio_command(server_cfg)
            if not cmd:
                auth.output = {"authorized": True, "arguments": arguments or {},
                               "transport": "none"}
            else:
                cwd = Path(server_cfg["cwd"]).resolve() if server_cfg.get("cwd") else None
                roots = []
                if self.org_root:
                    roots.append(self.org_root)
                if cwd:
                    roots.append(cwd)
                policy = SandboxPolicy(
                    allowed_roots=roots or [Path.cwd()],
                    allowed_commands=[[cmd[0]]],
                    network=str(server_cfg.get("network", "deny")),
                )
                try:
                    with StdioMcpClient(cmd, cwd=cwd, policy=policy) as client:
                        auth.output = {
                            "transport": "stdio",
                            "result": client.call_tool(tool, arguments or {}),
                        }
                except (McpTransportError, OSError) as exc:
                    auth.output = {
                        "transport": "stdio",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                    if self.events is not None:
                        self.events.append(Event(
                            event_type="mcp.call_failed",
                            workflow_id=workflow_id,
                            agent_role=role,
                            status="failed",
                            payload={"server": server, "tool": tool,
                                     "error": str(exc)},
                        ))
                    return auth

        if self.events is not None:
            self.events.append(Event(
                event_type="mcp.called",
                workflow_id=workflow_id,
                agent_role=role,
                payload={"server": server, "tool": tool,
                         "arguments_keys": sorted((arguments or {}).keys()),
                         "transport": (auth.output or {}).get("transport")
                         if isinstance(auth.output, dict) else "executor"},
            ))
        return auth
