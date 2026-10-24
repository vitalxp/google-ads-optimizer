from __future__ import annotations

from datetime import date, timedelta


_PRESET_DAYS = {7: "LAST_7_DAYS", 14: "LAST_14_DAYS", 30: "LAST_30_DAYS"}


def date_range_clause(lookback_days: int) -> str:
    """Build a GAQL segments.date predicate.

    Prefers named presets; otherwise uses an inclusive BETWEEN window.
    """
    if lookback_days in _PRESET_DAYS:
        return f"segments.date DURING {_PRESET_DAYS[lookback_days]}"
    end = date.today()
    start = end - timedelta(days=max(lookback_days - 1, 0))
    return f"segments.date BETWEEN '{start.isoformat()}' AND '{end.isoformat()}'"
