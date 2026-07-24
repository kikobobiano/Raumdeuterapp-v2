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
from app.core.screener_composite import (
    CompositeInput,
    MAX_CANDIDATES,
    component_select_exprs,
    merge_component_lists,
    score_candidates,
)
from app.schemas import (
    BarRankingRequest,
    BarRankingResponse,
    BarRankingRow,
    CompositeComponent,
)

router = APIRouter(prefix="/bar/ranking", tags=["bar"])


def _to_inputs(comps: list[CompositeComponent]) -> list[CompositeInput]:
    return [(c.metric, c.mode, c.basis, c.weight) for c in comps]


def _slot_composites(req: BarRankingRequest) -> list[list[CompositeInput]]:
    if not req.composites:
        return [[] for _ in req.metrics]
    return [_to_inputs(slot) for slot in req.composites]


@router.post("", response_model=BarRankingResponse)
def bar_ranking(req: BarRankingRequest) -> BarRankingResponse:
    view = view_name(req.filters.season)
    if view not in list_views():
        raise HTTPException(404, f"season {req.filters.season} not loaded")

    modes = list(req.modes) + ["as_is"] * (len(req.metrics) - len(req.modes))
    modes = modes[: len(req.metrics)]
    slots = _slot_composites(req)
    has_composite = any(bool(s) for s in slots)

    with duckdb_session() as conn:
        allowed = set(selectable_metric_names(conn, view))
        for i, m in enumerate(req.metrics):
            if slots[i]:
                for c in slots[i]:
                    if c[0] not in allowed:
                        raise HTTPException(400, f"Unknown or unavailable metric: {c[0]}")
            elif m not in allowed:
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
            f"{int(req.filters.season)} AS season",
            player_image_select_sql(conn, view),
        ]
        for i, (m, mode) in enumerate(zip(req.metrics, modes, strict=True)):
            if slots[i]:
                select_parts.append("CAST(NULL AS DOUBLE) AS _m{0}".format(i))
            else:
                select_parts.append(f"({metric_sql_expr(m, mode)}) AS _m{i}")

        merged = merge_component_lists(*slots)
        select_exprs, metric_aliases = component_select_exprs(merged)
        for alias, expr in select_exprs.items():
            select_parts.append(f"({expr}) AS {alias}")

        if has_composite:
            sql = f"""
                SELECT {", ".join(select_parts)}
                FROM {view}
                {where}
                LIMIT {MAX_CANDIDATES}
            """
            raw = fetch_all_dicts(conn, sql, params)
            for i, comps in enumerate(slots):
                if not comps:
                    continue
                scores = score_candidates(
                    conn,
                    filters=req.filters,
                    components=comps,
                    candidates=raw,
                    metric_aliases=metric_aliases,
                )
                for rec, score in zip(raw, scores, strict=True):
                    rec[f"_m{i}"] = score

            # Combined / single-metric sort in Python, then page.
            n = len(req.metrics)
            max_abs = []
            for i in range(n):
                vals = [
                    abs(float(rec[f"_m{i}"]))
                    for rec in raw
                    if rec.get(f"_m{i}") is not None and rec.get(f"_m{i}") == rec.get(f"_m{i}")
                ]
                max_abs.append(max(vals) if vals else 1e-9)

            def sort_key(rec: dict) -> tuple:
                if req.sort_combined:
                    total = 0.0
                    any_v = False
                    for i in range(n):
                        v = rec.get(f"_m{i}")
                        if v is None or v != v:
                            continue
                        any_v = True
                        total += abs(float(v)) / max_abs[i]
                    return (not any_v, -total if req.sort_desc else total)
                # sort_by real metric only in non-combined mode (existing)
                return (True, 0.0)

            if req.sort_combined:
                raw.sort(key=sort_key)
            raw = raw[: int(req.limit)]
            metric_max_abs = {req.metrics[i]: max_abs[i] for i in range(n)} if req.sort_combined else None
        elif req.sort_combined:
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
            metric_max_abs = {req.metrics[i]: mx_vals[i] for i in range(n)}

            combo_ordered = " + ".join(
                f"ABS(COALESCE(base._m{i}, 0)) / {mx_vals[i]:.16g}"
                for i in range(n)
            )
            direction = "DESC" if req.sort_desc else "ASC"
            sql = f"""
                WITH base AS (
                    SELECT {", ".join(select_parts)}
                    FROM {view}
                    {where}
                )
                SELECT base.*
                FROM base
                ORDER BY ({combo_ordered}) {direction} NULLS LAST
                LIMIT {int(req.limit)}
            """
            raw = fetch_all_dicts(conn, sql, params)
        else:
            direction = "DESC" if req.sort_desc else "ASC"
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
            metric_max_abs = None

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

    labels: dict[str, str] = {}
    for i, (m, mode) in enumerate(zip(req.metrics, modes, strict=True)):
        if slots[i]:
            labels[m] = m if not m.startswith("ci:") else "Composite"
        else:
            labels[m] = format_mode_label(m, mode)

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
