"""Season-aligned player age from parquet identity columns.

Wyscout ``Age`` on snapshots can drift vs historical seasons (TM enrichment,
mixed extract dates). When ``Birthday`` exists we use age at **1 July** of the
season start year (``players_{season}`` → ``season`` = first calendar year of
the campaign). Legacy callers fall back to raw ``Age`` when birthday missing or
unparsable.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any


AGE_REFERENCE_MONTH = 7
AGE_REFERENCE_DAY = 1


def season_start_year_from_view(view: str) -> int:
    """Parse ``players_{YYYY}`` → ``YYYY``. Raises if the view name is not season-scoped."""

    prefix = "players_"
    if not view.startswith(prefix):
        raise ValueError(f"expected '{prefix}<year>' view, got {view!r}")
    tail = view.removeprefix(prefix)
    if not tail.isdigit():
        raise ValueError(f"expected '{prefix}<year>' view, got {view!r}")
    y = int(tail)
    if not (1900 <= y <= 2100):
        raise ValueError(f"season year out of range: {y}")
    return y


def _qualified(col: str, table_alias: str | None) -> str:
    if table_alias:
        return f'{table_alias}."{col}"'
    return f'"{col}"'


def player_age_sql(
    cols: set[str],
    season_start_year: int,
    *,
    table_alias: str | None = None,
) -> str:
    """DuckDB expression for integer age at season anchor (validated calendar year only).

    ``season_start_year`` is interpolated as an integer literal (not user SQL).
    """

    if not isinstance(season_start_year, int) or not (1900 <= season_start_year <= 2100):
        raise ValueError("season_start_year must be int in [1900, 2100]")

    age_col = _qualified("Age", table_alias)
    if "Birthday" not in cols:
        return f"CAST({age_col} AS INTEGER)"

    bd_col = _qualified("Birthday", table_alias)
    mk = (
        f"CAST(make_date({season_start_year}, {AGE_REFERENCE_MONTH}, "
        f"{AGE_REFERENCE_DAY}) AS DATE)"
    )
    return (
        "CASE WHEN try_cast(" + bd_col + " AS DATE) IS NOT NULL THEN ( "
        f"year({mk}) - year(CAST({bd_col} AS DATE)) "
        "- CASE WHEN strftime(CAST(" + bd_col + " AS DATE), '%m%d') > "
        f"strftime({mk}, '%m%d') THEN 1 ELSE 0 END "
        f") ELSE CAST({age_col} AS INTEGER) END"
    )


def age_at_anchor_date(birth: date, anchor: date) -> int:
    y = anchor.year - birth.year
    if (anchor.month, anchor.day) < (birth.month, birth.day):
        y -= 1
    return y


def parse_birthday_value(val: Any) -> date | None:
    if val is None:
        return None
    if isinstance(val, float) and math.isnan(val):
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        s = val.strip()
        if len(s) >= 10 and s[4] == "-" and s[7] == "-":
            try:
                return date(int(s[:4]), int(s[5:7]), int(s[8:10]))
            except ValueError:
                pass
        try:
            return date.fromisoformat(s[:10])
        except ValueError:
            return None
    return None


def coerce_int_age(raw: Any) -> int | None:
    if raw is None:
        return None
    if isinstance(raw, float) and math.isnan(raw):
        return None
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return None


def player_age_for_season(rec: dict[str, Any], season_start_year: int) -> int | None:
    """Python twin of :func:`player_age_sql` for full-row dicts (e.g. profile ``SELECT *``)."""

    if not isinstance(season_start_year, int) or not (1900 <= season_start_year <= 2100):
        raise ValueError("season_start_year must be int in [1900, 2100]")

    bd = parse_birthday_value(rec.get("Birthday"))
    if bd is not None:
        anchor = date(season_start_year, AGE_REFERENCE_MONTH, AGE_REFERENCE_DAY)
        return age_at_anchor_date(bd, anchor)
    return coerce_int_age(rec.get("Age"))
