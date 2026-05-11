"""TM ``transfer_season`` ↔ Wyscout parquet ``{start_year}_all_leagues`` naming."""

from __future__ import annotations

import math
import re
from typing import Any


_TM_SEASON_TWO = re.compile(r"^\s*(\d{2})\s*/\s*(\d{2})\s*$")
_TM_SEASON_FULL = re.compile(r"^\s*(\d{4})\s*/\s*(\d{4})\s*$")


def transfer_season_to_start_year(raw: Any) -> int | None:
    """Map TM ``transfer_season`` column to parquet start year ``Y``.

    Examples
    --------
    ``"25/26"`` → ``2025`` (same convention as Wyscout filenames token ``YY-YY+1``).
    ``"2025/2026"`` → ``2025``.
    """
    if raw is None:
        return None
    if isinstance(raw, float) and math.isnan(raw):
        return None
    s = str(raw).strip()
    if not s:
        return None

    m = _TM_SEASON_TWO.match(s)
    if m:
        yy = int(m.group(1))
        return 2000 + yy if yy <= 99 else yy

    m = _TM_SEASON_FULL.match(s)
    if m:
        return int(m.group(1))

    # Plain 4-digit year fallback
    if s.isdigit() and len(s) == 4:
        y = int(s)
        if 1990 <= y <= 2120:
            return y

    return None
