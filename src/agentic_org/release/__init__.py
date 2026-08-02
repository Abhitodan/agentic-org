"""Auto-merge and release helpers (test-gated)."""

from .merge import MergeResult, merge_agent_branch
from .release import ReleaseResult, create_release

__all__ = [
    "MergeResult", "merge_agent_branch",
    "ReleaseResult", "create_release",
]
