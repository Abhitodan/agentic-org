"""Acceptance-Trace Lock (ATL) / Criterion-Coupled Completion (C³).

COMPLETED is refused unless every charter acceptance-criterion ID is coupled
to a named, passing, fresh test oracle seal — suite green alone is not enough.
"""

from .criteria import AcceptanceCriterion, parse_acceptance_criteria
from .lock import ATLDecision, evaluate_atl, unlocked_suite_green_allows_completed
from .seal import OracleSeal, mint_seal, verify_seal_against_repo
from .trace import AcceptanceTrace, build_acceptance_trace, load_linkage, save_linkage

__all__ = [
    "ATLDecision",
    "AcceptanceCriterion",
    "AcceptanceTrace",
    "OracleSeal",
    "build_acceptance_trace",
    "evaluate_atl",
    "load_linkage",
    "mint_seal",
    "parse_acceptance_criteria",
    "save_linkage",
    "unlocked_suite_green_allows_completed",
    "verify_seal_against_repo",
]
