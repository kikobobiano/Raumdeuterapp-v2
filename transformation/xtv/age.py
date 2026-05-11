"""Season age aligned with FastAPI ``player_age.player_age_for_season`` rule."""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

AGE_REFERENCE_MONTH = 7
AGE_REFERENCE_DAY = 1


def _parse_birth(val: Any) -> date | None:
    if val is None:
        return None
    if isinstance(val, float) and val != val:
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        t = val.strip()
        if len(t) >= 10 and t[4] == "-" and t[7] == "-":
            try:
                return date(int(t[:4]), int(t[5:7]), int(t[8:10]))
            except ValueError:
                return None
        try:
            return date.fromisoformat(t[:10])
        except ValueError:
            return None
    return None


def player_age_parquet_row(rec: dict[str, Any], season_start_year: int) -> float | None:
    """Birthday-derived age at 1 Jul `season_start_year`, else parquet ``Age``."""

    bd = _parse_birth(rec.get("Birthday"))
    if bd is not None:
        anchor = date(season_start_year, AGE_REFERENCE_MONTH, AGE_REFERENCE_DAY)
        y = anchor.year - bd.year
        if (anchor.month, anchor.day) < (bd.month, bd.day):
            y -= 1
        return float(y)
    raw = rec.get("Age")
    if raw is None:
        return None
    if isinstance(raw, float) and math.isnan(raw):
        return None
    try:
        return float(int(float(raw)))
    except (TypeError, ValueError):
        return None
