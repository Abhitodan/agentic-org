#!/usr/bin/env python3
"""Minimal stdio MCP server for tests (echo + ping tools)."""

from __future__ import annotations

import json
import sys


TOOLS = [
    {
        "name": "ping",
        "description": "Return pong",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "echo",
        "description": "Echo a message",
        "inputSchema": {
            "type": "object",
            "properties": {"message": {"type": "string"}},
            "required": ["message"],
        },
    },
]


def respond(msg_id, result):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": result}) + "\n")
    sys.stdout.flush()


def fail(msg_id, code, message):
    sys.stdout.write(json.dumps({
        "jsonrpc": "2.0", "id": msg_id,
        "error": {"code": code, "message": message},
    }) + "\n")
    sys.stdout.flush()


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        method = req.get("method")
        msg_id = req.get("id")
        params = req.get("params") or {}
        if method == "notifications/initialized":
            continue
        if msg_id is None:
            continue
        if method == "initialize":
            respond(msg_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "mock-mcp", "version": "0.1.0"},
            })
        elif method == "tools/list":
            respond(msg_id, {"tools": TOOLS})
        elif method == "tools/call":
            name = params.get("name")
            args = params.get("arguments") or {}
            if name == "ping":
                respond(msg_id, {
                    "content": [{"type": "text", "text": "pong"}],
                    "isError": False,
                })
            elif name == "echo":
                respond(msg_id, {
                    "content": [{"type": "text", "text": str(args.get("message", ""))}],
                    "isError": False,
                })
            else:
                fail(msg_id, -32601, f"unknown tool: {name}")
        else:
            fail(msg_id, -32601, f"unknown method: {method}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
