"""ID and time helpers. All IDs are prefixed UUIDs for auditability."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:20]}"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")
