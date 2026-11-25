# =============================================================================
# FILE PURPOSE:
# This file turns the 'src/' directory into an importable Python package.
# It re-exports all primary TimeGuard helpers (time_budget, time_guarded, etc.)
# so you can import them cleanly with:
#   from src.timeguard import time_budget, time_guarded
# =============================================================================

from .timeguard import (
    is_timeguard_supported,
    get_budget_ms,
    set_budget_ms,
    time_budget,
    time_guarded,
)

__all__ = [
    "is_timeguard_supported",
    "get_budget_ms",
    "set_budget_ms",
    "time_budget",
    "time_guarded",
]
