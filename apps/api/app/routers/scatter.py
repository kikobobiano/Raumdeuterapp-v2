from fastapi import APIRouter, HTTPException

from app.core.duckdb_pool import duckdb_session, fetch_all_dicts, list_views
from app.core.filters import build_where, view_name
from app.core.metric_modes import format_mode_label
from app.core.metric_sql import metric_sql_expr
from app.core.metrics_catalog import column_names_in_view, selectable_metric_names
from app.core.player_age import player_age_sql
from app.core.player_image import player_image_select_sql
from app.core.sql_ident import q_ident
from app.schemas import ScatterRequest, ScatterResponse

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


@router.post("", response_model=ScatterResponse)
def scatter(req: ScatterRequest) -> ScatterResponse:
    view = view_name(req.filters.season)
    if view not in list_views():
        raise HTTPException(404, f"season {req.filters.season} not loaded")

    to_check = [req.x_metric, req.y_metric]
    if req.size_metric:
        to_check.append(req.size_metric)

    where_sql, params = build_where(req.filters)
    where = f"WHERE {where_sql}" if where_sql else ""

    with duckdb_session() as conn:
        _ensure_metrics_allowed(conn, view, to_check)

        x_expr = metric_sql_expr(req.x_metric, req.x_mode)
        y_expr = metric_sql_expr(req.y_metric, req.y_mode)
        vcols = column_names_in_view(conn, view)
        age_sel = player_age_sql(vcols, req.filters.season)
        cols = [
            '"Wyscout id" AS wyscout_id',
            '"Player" AS player',
            "club",
            "league",
            '"Primary position" AS position',
            f"({age_sel}) AS age",
            '"Minutes played" AS minutes',
            f"{x_expr} AS x",
            f"{y_expr} AS y",
            player_image_select_sql(conn, view),
        ]
        if req.size_metric:
            cols.append(f"{metric_sql_expr(req.size_metric, 'as_is')} AS size")

        sql = f"""
            SELECT {', '.join(cols)}
            FROM {view}
            {where}
        """
        raw = fetch_all_dicts(conn, sql, params)

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
    return ScatterResponse(
        points=points,
        x_metric=req.x_metric,
        y_metric=req.y_metric,
        x_label=format_mode_label(req.x_metric, req.x_mode),
        y_label=format_mode_label(req.y_metric, req.y_mode),
        size_metric=req.size_metric,
        n=len(points),
    )
