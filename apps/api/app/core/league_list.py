"""Resolve distinct league names from a players_* DuckDB view."""

from __future__ import annotations

import duckdb

from app.core.config import LEAGUE_POWER_BASE
from app.core.duckdb_pool import list_views


def sort_leagues_by_power(leagues: list[str]) -> list[str]:
    """Descending league power (stronger first); unknown names last, then A–Z."""

    def key(name: str) -> tuple[int, float, str]:
        s = str(name).strip()
        power = LEAGUE_POWER_BASE.get(s)
        if power is not None:
            return (0, -float(power), s)
        return (1, 0.0, s)

    uniq = list(dict.fromkeys(leagues))
    return sorted(uniq, key=key)


def distinct_leagues_in_view(conn: duckdb.DuckDBPyConnection, view: str) -> list[str]:
    if view not in list_views():
        return []

    col_rows = conn.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'main' AND table_name = ?
        """,
        [view],
    ).fetchall()
    by_lower = {str(r[0]).lower(): r[0] for r in col_rows}

    for key in ("league", "competition"):
        orig = by_lower.get(key)
        if orig is None:
            continue
        esc = str(orig).replace('"', '""')
        try:
            rows = conn.execute(
                f'SELECT DISTINCT "{esc}" AS v FROM {view} '
                f'WHERE "{esc}" IS NOT NULL AND trim(cast("{esc}" AS VARCHAR)) <> \'\' '
                f"ORDER BY 1"
            ).fetchall()
        except Exception:
            continue
        vals = [r[0] for r in rows if r[0] is not None]
        if key == "competition" and len(vals) > 120:
            continue
        if vals:
            return sort_leagues_by_power([str(v) for v in vals])
    return []
