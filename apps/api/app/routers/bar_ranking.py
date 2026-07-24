"""Top-N horizontal bar ranking — screener-style filters with up to 3 metrics."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.club_logos import club_logo_select_sql, normalize_club_logo
from app.core.duckdb_pool import duckdb_session, fetch_all_dicts, list_views
from app.core.filters import build_where, view_name
from app.core.metric_modes import format_mode_label
from app.core.metric_sql import metric_sql_expr
from app.core.metrics_catalog import column_names_in_view, selectable_metric_names
from app.core.player_age import player_age_sql
from app.core.player_image import player_image_select_sql
from app.schemas import BarRankingRequest, BarRankingResponse, BarRankingRow

router = APIRouter(prefix="/bar/ranking", tags=["bar"])


@router.post("", response_model=BarRankingResponse)
def bar_ranking(req: BarRankingRequest) -> BarRankingResponse:
    view = view_name(req.filters.season)
    if view not in list_views():
        raise HTTPException(404, f"season {req.filters.season} not loaded")

    modes = list(req.modes) + ["as_is"] * (len(req.metrics) - len(req.modes))
    modes = modes[: len(req.metrics)]

    with duckdb_session() as conn:
        allowed = set(selectable_metric_names(conn, view))
        for m in req.metrics:
            if m not in allowed:
                raise HTTPException(400, f"Unknown or unavailable metric: {m}")
        if not req.sort_combined:
            name = (req.sort_by or "").strip()
            if not name or name not in allowed:
                raise HTTPException(400, f"Unknown or unavailable sort metric: {req.sort_by!r}")

        vcols = column_names_in_view(conn, view)
        where_sql, params = build_where(req.filters, cols=vcols)
        where = f"WHERE {where_sql}" if where_sql else ""

        age_sel = player_age_sql(vcols, req.filters.season)

        select_parts = [
            club_logo_select_sql(conn, view, req.filters.season),
            '"Wyscout id" AS wyscout_id',
            '"Player" AS player',
            "club",
            "league",
            '"Primary position" AS position',
            f"({age_sel}) AS age",
            '"Minutes played" AS minutes',
            player_image_select_sql(conn, view),
        ]
        for i, (m, mode) in enumerate(zip(req.metrics, modes, strict=True)):
            select_parts.append(f"({metric_sql_expr(m, mode)}) AS _m{i}")

        inner_select = ", ".join(select_parts)
        direction = "DESC" if req.sort_desc else "ASC"

        metric_max_abs: dict[str, float] | None = None

        if req.sort_combined:
            n = len(req.metrics)
            bound_cols = [
                f"COALESCE(NULLIF(MAX(ABS(COALESCE(_m{i}, 0))), 0), 1e-9) AS mx{i}"
                for i in range(n)
            ]
            metric_only = ", ".join(
                f"({metric_sql_expr(m, mode)}) AS _m{i}"
                for i, (m, mode) in enumerate(zip(req.metrics, modes, strict=True))
            )
            bounds_sql = f"""
                SELECT {", ".join(bound_cols)}
                FROM (SELECT {metric_only} FROM {view} {where}) t
            """
            mx_rows = fetch_all_dicts(conn, bounds_sql, params)
            mx_one_dict = mx_rows[0] if mx_rows else {}
            mx_vals = [
                float((mx_one_dict or {}).get(f"mx{i}") or 1e-9)
                for i in range(n)
            ]
            metric_max_abs = {
                req.metrics[i]: mx_vals[i]
                for i in range(n)
            }

            combo_ordered = " + ".join(
                f"ABS(COALESCE(base._m{i}, 0)) / {mx_vals[i]:.16g}"
                for i in range(n)
            )
            sql = f"""
                WITH base AS (
                    SELECT {inner_select}
                    FROM {view}
                    {where}
                )
                SELECT base.*
                FROM base
                ORDER BY ({combo_ordered}) {direction} NULLS LAST
                LIMIT {int(req.limit)}
            """
        else:
            sort_alias = "_sort"
            sort_key = req.sort_by.strip()
            select_ordered = [
                *select_parts,
                f"({metric_sql_expr(sort_key, req.sort_mode)}) AS {sort_alias}",
            ]
            sql = f"""
                SELECT {", ".join(select_ordered)}
                FROM {view}
                {where}
                ORDER BY {sort_alias} {direction} NULLS LAST
                LIMIT {int(req.limit)}
            """
        raw = fetch_all_dicts(conn, sql, params)

    rows: list[BarRankingRow] = []
    for i, rec in enumerate(raw):
        values: dict[str, float | None] = {}
        for idx, m in enumerate(req.metrics):
            v = rec.get(f"_m{idx}")
            values[m] = float(v) if (v is not None and v == v) else None
        rows.append(
            BarRankingRow(
                rank=i + 1,
                wyscout_id=rec.get("wyscout_id"),
                player=str(rec.get("player") or ""),
                club=rec.get("club"),
                league=rec.get("league"),
                position=rec.get("position"),
                age=rec.get("age"),
                minutes=rec.get("minutes"),
                club_logo=normalize_club_logo(rec.get("club_logo")),
                player_image_url=rec.get("player_image_url") or None,
                values=values,
            )
        )

    labels = {
        m: format_mode_label(m, mode)
        for m, mode in zip(req.metrics, modes, strict=True)
    }

    return BarRankingResponse(
        rows=rows,
        metrics=req.metrics,
        labels=labels,
        sort_combined=req.sort_combined,
        sort_by=req.sort_by.strip() if not req.sort_combined else "__combined__",
        sort_mode=req.sort_mode,
        n=len(rows),
        metric_max_abs=metric_max_abs,
    )
