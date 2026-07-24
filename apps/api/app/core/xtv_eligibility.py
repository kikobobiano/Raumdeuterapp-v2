"""Leagues where xTV is not offered (model / mapping coverage too thin)."""

from __future__ import annotations

from app.core.config import LEAGUES_WITHOUT_XTV


def league_supports_xtv(league: str | None) -> bool:
    if league is None:
        return True
    return league.strip() not in LEAGUES_WITHOUT_XTV


def xtv_parquet_sql(cols: set[str], league_ref: str = "league") -> str:
    """Row-level xTV for SQL aggregates; null in ineligible leagues."""
    if "x_tv_eur" not in cols:
        return "CAST(NULL AS DOUBLE)"
    if not LEAGUES_WITHOUT_XTV:
        return 'CAST("x_tv_eur" AS DOUBLE)'
    in_list = ", ".join(
        "'" + lg.replace("'", "''") + "'" for lg in sorted(LEAGUES_WITHOUT_XTV)
    )
    return (
        f'CASE WHEN {league_ref} IN ({in_list}) THEN NULL '
        f'ELSE CAST("x_tv_eur" AS DOUBLE) END'
    )
