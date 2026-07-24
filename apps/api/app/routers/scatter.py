from fastapi import APIRouter, HTTPException

from app.core.duckdb_pool import duckdb_session, fetch_all_dicts, list_views
from app.core.filters import build_where, view_name
from app.core.metric_modes import format_mode_label
from app.core.metric_sql import metric_sql_expr
from app.core.metrics_catalog import column_names_in_view, selectable_metric_names
from app.core.player_age import player_age_sql
from app.core.player_image import player_image_select_sql
from app.core.screener_composite import (
    CompositeInput,
    component_select_exprs,
    merge_component_lists,
    score_candidates,
)
from app.core.sql_ident import q_ident
from app.schemas import CompositeComponent, ScatterRequest, ScatterResponse

router = APIRouter(prefix="/scatter", tags=["scatter"])


def _q(name: str) -> str:
    """Quote column name — HTTP 400 on invalid identifiers (scatter user input)."""
    try:
        return q_ident(name)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


def _ensure_metrics_allowed(conn, view: str, names: list[str]) -> None:
    allowed = set(selectable_metric_names(conn, view))
    for m in names:
        if m and m not in allowed:
            raise HTTPException(400, f"Unknown or unavailable metric: {m}")


def _to_inputs(comps: list[CompositeComponent]) -> list[CompositeInput]:
    return [(c.metric, c.mode, c.basis, c.weight) for c in comps]


@router.post("", response_model=ScatterResponse)
def scatter(req: ScatterRequest) -> ScatterResponse:
    view = view_name(req.filters.season)
    if view not in list_views():
        raise HTTPException(404, f"season {req.filters.season} not loaded")

    x_comp = _to_inputs(req.x_composite)
    y_comp = _to_inputs(req.y_composite)

    to_check: list[str] = []
    if not x_comp:
        to_check.append(req.x_metric)
    if not y_comp:
        to_check.append(req.y_metric)
    if req.size_metric:
        to_check.append(req.size_metric)
    for c in [*req.x_composite, *req.y_composite]:
        to_check.append(c.metric)

    with duckdb_session() as conn:
        _ensure_metrics_allowed(conn, view, to_check)
        vcols = column_names_in_view(conn, view)
        where_sql, params = build_where(req.filters, cols=vcols)
        where = f"WHERE {where_sql}" if where_sql else ""

        age_sel = player_age_sql(vcols, req.filters.season)
        cols = [
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
        if not x_comp:
            cols.append(f"({metric_sql_expr(req.x_metric, req.x_mode)}) AS x")
        else:
            cols.append("CAST(NULL AS DOUBLE) AS x")
        if not y_comp:
            cols.append(f"({metric_sql_expr(req.y_metric, req.y_mode)}) AS y")
        else:
            cols.append("CAST(NULL AS DOUBLE) AS y")
        if req.size_metric:
            cols.append(f"({metric_sql_expr(req.size_metric, 'as_is')}) AS size")

        merged = merge_component_lists(x_comp, y_comp)
        select_exprs, metric_aliases = component_select_exprs(merged)
        for alias, expr in select_exprs.items():
            cols.append(f"({expr}) AS {alias}")

        sql = f"""
            SELECT {', '.join(cols)}
            FROM {view}
            {where}
        """
        raw = fetch_all_dicts(conn, sql, params)

        if x_comp:
            xs = score_candidates(
                conn,
                filters=req.filters,
                components=x_comp,
                candidates=raw,
                metric_aliases=metric_aliases,
            )
            for rec, score in zip(raw, xs, strict=True):
                rec["x"] = score
        if y_comp:
            ys = score_candidates(
                conn,
                filters=req.filters,
                components=y_comp,
                candidates=raw,
                metric_aliases=metric_aliases,
            )
            for rec, score in zip(raw, ys, strict=True):
                rec["y"] = score

    points: list[dict] = []
    for rec in raw:
        x, y = rec.get("x"), rec.get("y")
        if x is None or y is None:
            continue
        if isinstance(x, float) and x != x:
            continue
        if isinstance(y, float) and y != y:
            continue
        points.append(rec)

    x_label = req.x_label or (
        "Composite (X)" if x_comp else format_mode_label(req.x_metric, req.x_mode)
    )
    y_label = req.y_label or (
        "Composite (Y)" if y_comp else format_mode_label(req.y_metric, req.y_mode)
    )

    return ScatterResponse(
        points=points,
        x_metric=req.x_metric,
        y_metric=req.y_metric,
        x_label=x_label,
        y_label=y_label,
        size_metric=req.size_metric,
        n=len(points),
    )
