"""Secret redaction for audit payloads (Phase 1)."""

from __future__ import annotations

import re
from typing import Any

_REDACTED = "***REDACTED***"

_SIMPLE: list[re.Pattern[str]] = [
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9\-._~+/]+=*"),
]

_KV = re.compile(
    r"(?i)((?:api[_-]?key|access[_-]?token|secret|password|authorization)"
    r"\s*[:=]\s*)([^\s'\"&,;]{8,})"
)


def redact_text(text: str) -> str:
    out = text
    for pat in _SIMPLE:
        out = pat.sub(_REDACTED, out)
    out = _KV.sub(rf"\1{_REDACTED}", out)
    return out


def redact_obj(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {str(k): redact_obj(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_obj(v) for v in value]
    if isinstance(value, tuple):
        return tuple(redact_obj(v) for v in value)
    return value
