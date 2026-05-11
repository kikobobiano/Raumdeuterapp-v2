from fastapi import APIRouter, HTTPException

from app.core.club_logos import club_logo_select_sql, normalize_club_logo
from app.core.duckdb_pool import duckdb_session, list_views
from app.core.filters import build_where, view_name
from app.core.metric_sql import metric_sql_expr
from app.core.metrics_catalog import column_names_in_view, selectable_metric_names
from app.core.player_age import player_age_sql
from app.schemas import ScreenerRequest, ScreenerResponse, ScreenerRow

router = APIRouter(prefix="/screener", tags=["screener"])


@router.post("", response_model=ScreenerResponse)
def screener(req: ScreenerRequest) -> ScreenerResponse:
    view = view_name(req.filters.season)
    if view not in list_views():
        raise HTTPException(404, f"season {req.filters.season} not loaded")

    with duckdb_session() as conn:
        allowed = set(selectable_metric_names(conn, view))
        for c in req.criteria:
            if c.metric not in allowed:
                raise HTTPException(400, f"Unknown or unavailable metric: {c.metric}")
        if req.sort_by and req.sort_by not in allowed:
            raise HTTPException(400, f"Unknown or unavailable metric: {req.sort_by}")

        where_sql, params = build_where(req.filters)

        for c in req.criteria:
            expr = metric_sql_expr(c.metric, c.mode)
            where_sql = (where_sql + " AND " if where_sql else "") + f"({expr}) {c.operator} ?"
            params.append(c.value)

        where = f"WHERE {where_sql}" if where_sql else ""

        vcols = column_names_in_view(conn, view)
        age_sel = player_age_sql(vcols, req.filters.season)

        base_cols = [
            club_logo_select_sql(conn, view, req.filters.season),
            '"Wyscout id" AS wyscout_id',
            '"Player" AS player',
            "club",
            "league",
            '"Primary position" AS position',
            f"({age_sel}) AS age",
            '"Minutes played" AS minutes',
        ]

        select_parts = [*base_cols]
        for i, c in enumerate(req.criteria):
            expr = metric_sql_expr(c.metric, c.mode)
            select_parts.append(f"({expr}) AS _c{i}")

        sort_alias: str | None = None
        if req.sort_by:
            sort_expr = metric_sql_expr(req.sort_by, req.sort_mode)
            sort_alias = "_sort"
            select_parts.append(f"({sort_expr}) AS {sort_alias}")

        if sort_alias:
            sort_clause = f"ORDER BY {sort_alias} {'DESC' if req.sort_desc else 'ASC'} NULLS LAST"
        else:
            sort_clause = 'ORDER BY "Minutes played" DESC NULLS LAST'

        sql_cols = ", ".join(select_parts)
        sql = f"""
            SELECT {sql_cols}
            FROM {view}
            {where}
            {sort_clause}
            LIMIT {int(req.limit)}
            OFFSET {int(req.offset)}
        """
        # fetchdf() can hit DuckDB internal errors (e.g. datetime conversion) on Linux/arm64;
        # fetchall() avoids the pandas materialization path.
        result = conn.execute(sql, params)
        desc = result.description
        col_names = [d[0] for d in desc] if desc else []
        raw_rows = result.fetchall()

        count_sql = f"SELECT COUNT(*) FROM {view} {where}"
        total = int(conn.execute(count_sql, params).fetchone()[0])

    rows: list[ScreenerRow] = []
    for tup in raw_rows:
        rec = dict(zip(col_names, tup, strict=True))
        metrics: dict[str, float | None] = {}
        for i, c in enumerate(req.criteria):
            v = rec.pop(f"_c{i}", None)
            if v is not None and v == v:
                metrics[c.metric] = float(v)
            else:
                metrics[c.metric] = None
        rec.pop("_sort", None)
        rec["club_logo"] = normalize_club_logo(rec.get("club_logo"))
        rows.append(ScreenerRow(metrics=metrics, **rec))

    return ScreenerResponse(rows=rows, total=total)
