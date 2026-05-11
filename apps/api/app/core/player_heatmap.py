"""Look up a stored player heatmap from the DuckDB pool.

No FastAPI imports — pure data access. Routers wrap this in HTTP semantics.
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb

from app.core.duckdb_pool import list_views


@dataclass(frozen=True)
class HeatmapData:
    wyscout_id: int
    competition_id: int
    competition: str
    season: int
    points: list[dict]
    max_count: int


def fetch_heatmap(
    conn: duckdb.DuckDBPyConnection,
    *,
    wyscout_id: int,
    season: int,
    competition_id: int | None = None,
) -> HeatmapData | None:
    """Return a :class:`HeatmapData` or ``None`` when the view / row is missing."""
    view = f"heatmaps_{season}"
    if view not in list_views():
        return None

    if competition_id is not None:
        sql = (
            f'SELECT wyscout_id, competition_id, competition, points '
            f'FROM "{view}" '
            f"WHERE wyscout_id = ? AND competition_id = ? "
            f"LIMIT 1"
        )
        params = [int(wyscout_id), int(competition_id)]
    else:
        sql = (
            f'SELECT wyscout_id, competition_id, competition, points '
            f'FROM "{view}" '
            f"WHERE wyscout_id = ? "
            f"ORDER BY competition_id ASC "
            f"LIMIT 1"
        )
        params = [int(wyscout_id)]

    row = conn.execute(sql, params).fetchone()
    if row is None:
        return None

    raw_points = row[3] or []
    points: list[dict] = []
    max_count = 0
    for p in raw_points:
        if isinstance(p, dict):
            x, y, c = p.get("x"), p.get("y"), p.get("count")
        else:
            x, y, c = p[0], p[1], p[2]
        if x is None or y is None or c is None:
            continue
        cint = int(c)
        points.append({"x": float(x), "y": float(y), "count": cint})
        if cint > max_count:
            max_count = cint

    return HeatmapData(
        wyscout_id=int(row[0]),
        competition_id=int(row[1]),
        competition=str(row[2]) if row[2] is not None else "",
        season=int(season),
        points=points,
        max_count=int(max_count),
    )
