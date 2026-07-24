from fastapi import APIRouter, HTTPException

from app.core.club_logos import club_logo_select_sql, normalize_club_logo
from app.core.duckdb_pool import duckdb_session, list_views
from app.core.filters import build_where, view_name
from app.core.metric_sql import metric_sql_expr
from app.core.metrics_catalog import column_names_in_view, selectable_metric_names
from app.core.player_age import player_age_sql
from app.core.screener_composite import (
    CompositeInput,
    fetch_screener_candidates,
    score_candidates,
)
from app.core.screener_seasons import assert_seasons_loaded, resolve_screener_seasons
from app.schemas import ScreenerRequest, ScreenerResponse, ScreenerRow

router = APIRouter(prefix="/screener", tags=["screener"])


def _validate_metrics(req: ScreenerRequest, allowed: set[str]) -> None:
    for c in req.criteria:
        if c.metric not in allowed:
            raise HTTPException(400, f"Unknown or unavailable metric: {c.metric}")
    if req.sort_by and req.sort_by not in allowed:
        raise HTTPException(400, f"Unknown or unavailable metric: {req.sort_by}")
    for comp in req.composite:
        if comp.metric not in allowed:
            raise HTTPException(400, f"Unknown or unavailable metric: {comp.metric}")


def _score_matches(score: float | None, operator: str, value: float) -> bool:
    if score is None:
        return False
    if operator == ">=":
        return score >= value
    if operator == "<=":
        return score <= value
    if operator == ">":
        return score > value
    if operator == "<":
        return score < value
    if operator == "=":
        return score == value
    if operator == "!=":
        return score != value
    return False


def _criteria_sql(req: ScreenerRequest) -> tuple[str, list]:
    parts: list[str] = []
    params: list = []
    for c in req.criteria:
        expr = metric_sql_expr(c.metric, c.mode)
        parts.append(f"({expr}) {c.operator} ?")
        params.append(c.value)
    return (" AND ".join(parts), params) if parts else ("", params)


def _allowed_metrics_intersection(conn, seasons: list[int]) -> set[str]:
    sets = [set(selectable_metric_names(conn, view_name(s))) for s in seasons]
    if not sets:
        return set()
    out = sets[0]
    for s in sets[1:]:
        out &= s
    return out


def _rows_from_records(
    records: list[dict],
    *,
    criteria: ScreenerRequest,
    composites: list[float | None] | None = None,
) -> list[ScreenerRow]:
    rows: list[ScreenerRow] = []
    for i, rec in enumerate(records):
        metrics: dict[str, float | None] = {}
        for j, c in enumerate(criteria.criteria):
            v = rec.pop(f"_c{j}", None)
            metrics[c.metric] = float(v) if v is not None and v == v else None
        rec.pop("_sort", None)
        for k in list(rec):
            if k.startswith("_comp"):
                rec.pop(k, None)
        composite = composites[i] if composites is not None else None
        season_raw = rec.get("season")
        if season_raw is None:
            raise HTTPException(500, "screener row missing season")
        rows.append(
            ScreenerRow(
                season=int(season_raw),
                metrics=metrics,
                composite=composite,
                wyscout_id=rec.get("wyscout_id"),
                club_logo=rec.get("club_logo"),
                player=rec.get("player") or "",
                club=rec.get("club"),
                league=rec.get("league"),
                position=rec.get("position"),
                age=rec.get("age"),
                minutes=rec.get("minutes"),
            )
        )
    return rows


def _branch_select_sql(
    conn,
    *,
    season: int,
    req: ScreenerRequest,
    criteria_sql: str,
    criteria_params: list,
) -> tuple[str, list]:
    view = view_name(season)
    vcols = column_names_in_view(conn, view)
    where_sql, params = build_where(req.filters, cols=vcols, season=season)
    if criteria_sql:
        where_sql = (where_sql + " AND " if where_sql else "") + criteria_sql
        params = [*params, *criteria_params]
    where = f"WHERE {where_sql}" if where_sql else ""
    age_sel = player_age_sql(vcols, season)

    base_cols = [
        f"{int(season)} AS season",
        club_logo_select_sql(conn, view, season),
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

    if req.sort_by:
        sort_expr = metric_sql_expr(req.sort_by, req.sort_mode)
        select_parts.append(f"({sort_expr}) AS _sort")

    sql = f"""
        SELECT {", ".join(select_parts)}
        FROM {view}
        {where}
    """
    return sql, params


@router.post("", response_model=ScreenerResponse)
def screener(req: ScreenerRequest) -> ScreenerResponse:
    try:
        effective = resolve_screener_seasons(req.seasons, req.filters.season)
        assert_seasons_loaded(effective, list_views())
    except ValueError as e:
        raise HTTPException(404, f"season {e} not loaded") from e

    if req.composite_criteria is not None and not req.composite:
        raise HTTPException(400, "composite_criteria requires composite components")

    with duckdb_session() as conn:
        allowed = _allowed_metrics_intersection(conn, effective)
        _validate_metrics(req, allowed)
        criteria_sql, criteria_params = _criteria_sql(req)

        if req.composite:
            components: list[CompositeInput] = [
                (c.metric, c.mode, c.basis, c.weight) for c in req.composite
            ]
            criteria_metrics = [(c.metric, c.mode) for c in req.criteria]
            records, _raw_total, metric_aliases = fetch_screener_candidates(
                conn,
                seasons=effective,
                filters=req.filters,
                criteria_sql=criteria_sql,
                criteria_params=criteria_params,
                criteria_metrics=criteria_metrics,
                composite_components=components,
                sort_by=req.sort_by,
                sort_mode=req.sort_mode,
            )
            composites = score_candidates(
                conn,
                filters=req.filters,
                components=components,
                candidates=records,
                metric_aliases=metric_aliases,
            )
            indexed = list(zip(composites, records, strict=True))
            if req.composite_criteria is not None:
                cc = req.composite_criteria
                indexed = [
                    item
                    for item in indexed
                    if _score_matches(item[0], cc.operator, cc.value)
                ]
            total = len(indexed)

            def sort_key(item: tuple[float | None, dict]) -> tuple:
                comp, rec = item
                if req.sort_by_composite:
                    return (comp is None, -(comp or 0.0) if req.sort_desc else (comp or 0.0))
                if req.sort_by:
                    v = rec.get("_sort")
                    if v is None:
                        return (True, 0.0)
                    return (False, -float(v) if req.sort_desc else float(v))
                minutes = rec.get("minutes")
                return (minutes is None, -(minutes or 0) if req.sort_desc else (minutes or 0))

            indexed.sort(key=sort_key)
            sliced = indexed[req.offset : req.offset + req.limit]
            page_records = [rec for _comp, rec in sliced]
            page_composites = [comp for comp, _rec in sliced]
            rows = _rows_from_records(
                page_records,
                criteria=req,
                composites=page_composites,
            )
            return ScreenerResponse(rows=rows, total=total)

        branch_sqls: list[str] = []
        all_params: list = []
        for season in effective:
            sql, params = _branch_select_sql(
                conn,
                season=season,
                req=req,
                criteria_sql=criteria_sql,
                criteria_params=criteria_params,
            )
            branch_sqls.append(sql)
            all_params.extend(params)

        union_sql = " UNION ALL ".join(f"({b})" for b in branch_sqls)
        if req.sort_by:
            sort_clause = f"ORDER BY _sort {'DESC' if req.sort_desc else 'ASC'} NULLS LAST"
        else:
            sort_clause = "ORDER BY minutes DESC NULLS LAST"

        sql = f"""
            SELECT * FROM (
                {union_sql}
            ) AS screener_u
            {sort_clause}
            LIMIT {int(req.limit)}
            OFFSET {int(req.offset)}
        """
        result = conn.execute(sql, all_params)
        desc = result.description
        col_names = [d[0] for d in desc] if desc else []
        raw_rows = result.fetchall()

        count_sql = f"SELECT COUNT(*) FROM ({union_sql}) AS screener_u"
        total = int(conn.execute(count_sql, all_params).fetchone()[0])

    page_records = [dict(zip(col_names, tup, strict=True)) for tup in raw_rows]
    for rec in page_records:
        rec["club_logo"] = normalize_club_logo(rec.get("club_logo"))
    rows = _rows_from_records(page_records, criteria=req)
    return ScreenerResponse(rows=rows, total=total)
