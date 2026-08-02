"""MCP permission gateway (deny-by-default)."""

from .gateway import McpDenied, McpGateway, McpCallResult

__all__ = ["McpDenied", "McpGateway", "McpCallResult"]
