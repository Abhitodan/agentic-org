"""Minimal MCP JSON-RPC client over stdio (initialize / tools/list / tools/call)."""

from __future__ import annotations

import json
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..sandbox.policy import SandboxError, SandboxPolicy, scrub_env


class McpTransportError(Exception):
    pass


@dataclass
class McpTool:
    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)


class StdioMcpClient:
    """Spawn an MCP server process and speak newline-delimited JSON-RPC 2.0."""

    PROTOCOL_VERSION = "2024-11-05"

    def __init__(
        self,
        command: list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        policy: SandboxPolicy | None = None,
        timeout_seconds: float = 30.0,
    ):
        if not command:
            raise McpTransportError("empty MCP server command")
        if policy is not None:
            if not policy.allows_command(command[:1] if len(command) == 1 else command):
                # Allow first token + args if python script pattern
                if not policy.allows_command([command[0]]):
                    raise SandboxError(f"MCP server command not allowlisted: {command}")
            if cwd is not None and not policy.allows_cwd(cwd):
                raise SandboxError(f"MCP cwd outside allowed roots: {cwd}")
        self.command = command
        self.cwd = cwd
        self.timeout_seconds = timeout_seconds
        base_env = scrub_env(policy.network if policy else "deny", env)
        self._env = base_env
        self._proc: subprocess.Popen[str] | None = None
        self._next_id = 1
        self._lock = threading.Lock()

    def __enter__(self) -> "StdioMcpClient":
        self.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def start(self) -> None:
        if self._proc is not None:
            return
        self._proc = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(self.cwd) if self.cwd else None,
            env=self._env,
            bufsize=1,
        )
        self.initialize()

    def close(self) -> None:
        if self._proc is None:
            return
        try:
            if self._proc.stdin:
                self._proc.stdin.close()
            self._proc.terminate()
            self._proc.wait(timeout=5)
        except Exception:
            try:
                self._proc.kill()
            except Exception:
                pass
        self._proc = None

    def _rpc(self, method: str, params: dict[str, Any] | None = None) -> Any:
        if self._proc is None or self._proc.stdin is None or self._proc.stdout is None:
            raise McpTransportError("MCP client not started")
        with self._lock:
            req_id = self._next_id
            self._next_id += 1
            payload = {
                "jsonrpc": "2.0",
                "id": req_id,
                "method": method,
                "params": params or {},
            }
            line = json.dumps(payload, separators=(",", ":"))
            self._proc.stdin.write(line + "\n")
            self._proc.stdin.flush()
            # Read until matching id (skip notifications / noise)
            deadline_reads = 50
            for _ in range(deadline_reads):
                raw = self._proc.stdout.readline()
                if not raw:
                    err = ""
                    if self._proc.stderr:
                        err = self._proc.stderr.read()
                    raise McpTransportError(
                        f"MCP server closed stdout during {method}: {err[-500:]}"
                    )
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if msg.get("id") != req_id:
                    continue
                if "error" in msg:
                    raise McpTransportError(f"MCP error on {method}: {msg['error']}")
                return msg.get("result")
            raise McpTransportError(f"no response for {method}")

    def _notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        if self._proc is None or self._proc.stdin is None:
            raise McpTransportError("MCP client not started")
        payload = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        self._proc.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
        self._proc.stdin.flush()

    def initialize(self) -> dict[str, Any]:
        result = self._rpc(
            "initialize",
            {
                "protocolVersion": self.PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "agentic-org", "version": "0.1.0"},
            },
        )
        self._notify("notifications/initialized", {})
        return result or {}

    def list_tools(self) -> list[McpTool]:
        result = self._rpc("tools/list", {}) or {}
        tools = []
        for item in result.get("tools") or []:
            tools.append(McpTool(
                name=item.get("name", ""),
                description=item.get("description", ""),
                input_schema=item.get("inputSchema") or {},
            ))
        return tools

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        return self._rpc(
            "tools/call",
            {"name": name, "arguments": arguments or {}},
        )
