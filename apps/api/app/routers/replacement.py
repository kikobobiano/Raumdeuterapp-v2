"""Vector similarity replacement finder — port of legacy pages/12_Replacement_Finder.

Cosine similarity on z-scored combined features (game-area indices + per-90).

When leagues are restricted on the request, mean/std used for scaling are computed on the
widened pool (~ same season(s), roles/contract/minutes/etc., **all leagues**). Cosine
similarity is then evaluated **only for rows that satisfy the original filters**
(e.g. Big 5 only); returned candidates are a subset of that narrow pool.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException

from app.core.config import AREA_INDEX_COLS, GAME_AREAS_COLS
from app.core.duckdb_pool import duckdb_session, fetch_all_dicts, list_views
from app.core.filters import PlayerFilters, age_filter_parts, build_where, view_name
from app.core.sql_ident import q_ident as _q
from app.core.club_logos import club_logo_select_sql, normalize_club_logo
from app.core.metrics_catalog import column_names_in_view
from app.core.player_age import player_age_sql
from app.core.player_image import player_image_select_sql
from app.schemas import (
    REPLACEMENT_METHOD_DEFAULT,
    REPLACEMENT_PROFILE_DEFAULT,
    ReplacementCandidate,
    ReplacementRequest,
    ReplacementResponse,
)

router = APIRouter(prefix="/replacement", tags=["replacement"])

_COMBINED_FEATURES: list[str] = AREA_INDEX_COLS + GAME_AREAS_COLS


def _cosine_similarity(target: np.ndarray, pool: np.ndarray) -> np.ndarray:
    tn = np.linalg.norm(target)
    pn = np.linalg.norm(pool, axis=1)
    pn = np.where(pn == 0, 1.0, pn)
    if tn == 0:
        return np.zeros(len(pool))
    return (pool @ target) / (pn * tn)


def _feat_array(rows: list[dict], feature_cols: list[str]) -> np.ndarray:
    if not rows:
        return np.empty((0, len(feature_cols)), dtype=float)
    xf = pd.DataFrame(rows)[feature_cols].apply(pd.to_numeric, errors="coerce")
    return xf.to_numpy(dtype=float)


def _fill_and_scale_similarity_rows(
    target_row: dict,
    cand_rows: list[dict],
    *,
    norm_rows: list[dict],
    features: list[str],
) -> np.ndarray:
    """Cosine similarities using mean/std fitted on ``norm_rows`` only (excluding target).

    When ``candidate_filters.leagues`` is set, ``norm_rows`` should drop the league
    constraint so scale matches pools like Replacement Finder (`leagues: null`) while still
    ranking only within the narrower league filter.
    """
    norm_mat = _feat_array(norm_rows, features)
    if norm_mat.size == 0:
        raise HTTPException(
            status_code=500,
            detail="replacement normalisation pool is empty — check filters / data load",
        )
    col_mean = np.nanmean(norm_mat, axis=0)
    col_mean = np.nan_to_num(col_mean, nan=0.0)
    norm_filled = np.where(np.isnan(norm_mat), col_mean, norm_mat)

    stds = np.nanstd(norm_filled, axis=0)
    stds = np.where(stds == 0, 1.0, stds)

    tvec = _feat_array([target_row], features)[0]
    tvec = np.where(np.isnan(tvec), col_mean, tvec)

    cand_mat = _feat_array(cand_rows, features)
    cand_filled = np.where(np.isnan(cand_mat), col_mean, cand_mat)

    tz = (tvec - col_mean) / stds
    cz = (cand_filled - col_mean) / stds
    return _cosine_similarity(tz, cz)


def _collect_candidate_rows(
    conn,
    *,
    seasons: list[int],
    where_sql: str,
    params: list[Any],
    features: list[str],
    filters: PlayerFilters | None = None,
) -> list[dict]:
    feat_cols = ", ".join(_q(c) for c in features)
    out: list[dict] = []
    for cs in seasons:
        cand_view = view_name(cs)
        vcols = column_names_in_view(conn, cand_view)
        age_sel = player_age_sql(vcols, cs)
        logo_c = club_logo_select_sql(conn, cand_view, cs)
        img_c = player_image_select_sql(conn, cand_view)
        parts = [where_sql] if where_sql else []
        query_params = list(params)
        if filters is not None:
            age_parts, age_params = age_filter_parts(filters, vcols, season=cs)
            parts.extend(age_parts)
            query_params.extend(age_params)
        where_clause = f"WHERE {' AND '.join(parts)}" if parts else ""
        cand_sql = f"""
            SELECT "Wyscout id" AS wyscout_id, "Player" AS player, club, league,
                   "Primary position" AS position, ({age_sel}) AS age, "Minutes played" AS minutes,
                   {logo_c},
                   {img_c},
                   {feat_cols}
            FROM {cand_view}
            {where_clause}
        """
        for row in fetch_all_dicts(conn, cand_sql, query_params):
            row["_candidate_season"] = cs
            out.append(row)
    return out


@router.post("", response_model=ReplacementResponse)
def replacement(req: ReplacementRequest) -> ReplacementResponse:
    features = _COMBINED_FEATURES
    profile = REPLACEMENT_PROFILE_DEFAULT
    method = REPLACEMENT_METHOD_DEFAULT

    target_view = view_name(req.target_season)
    if target_view not in list_views():
        raise HTTPException(404, f"target_season {req.target_season} not loaded")

    for cs in req.candidate_seasons:
        if view_name(cs) not in list_views():
            raise HTTPException(404, f"candidate season {cs} not loaded")

    with duckdb_session() as conn:
        feat_cols = ", ".join(_q(c) for c in features)
        logo_target = club_logo_select_sql(conn, target_view, req.target_season)
        img_target = player_image_select_sql(conn, target_view)
        tvcols = column_names_in_view(conn, target_view)
        age_sel = player_age_sql(tvcols, req.target_season)

        target_sql = f"""
            SELECT "Wyscout id" AS wyscout_id, "Player" AS player, club, league,
                   "Primary position" AS position, ({age_sel}) AS age, "Minutes played" AS minutes,
                   {logo_target},
                   {img_target},
                   {feat_cols}
            FROM {target_view}
            WHERE "Wyscout id" = ?
            LIMIT 1
        """
        target_rows = fetch_all_dicts(conn, target_sql, [req.target_player_id])
        if not target_rows:
            raise HTTPException(404, "target player not found in target season")

        target = target_rows[0]

        f = req.candidate_filters
        ref_view = view_name(f.season)
        ref_cols = column_names_in_view(conn, ref_view)
        narrow_where, narrow_params = build_where(f, cols=ref_cols, include_age=False)

        widen_leagues_for_norm = bool(f.leagues)
        norm_f = f.model_copy(update={"leagues": None}) if widen_leagues_for_norm else f
        norm_where, norm_params = build_where(norm_f, cols=ref_cols, include_age=False)

        cand_rows = _collect_candidate_rows(
            conn,
            seasons=req.candidate_seasons,
            where_sql=narrow_where,
            params=narrow_params,
            features=features,
            filters=f,
        )

        norm_rows = (
            _collect_candidate_rows(
                conn,
                seasons=req.candidate_seasons,
                where_sql=norm_where,
                params=norm_params,
                features=features,
                filters=norm_f,
            )
            if widen_leagues_for_norm
            else cand_rows
        )

    if not cand_rows:
        return ReplacementResponse(
            target=None, candidates=[], n=0, profile=profile, method=method,
        )

    df = pd.DataFrame(cand_rows)
    scores_arr = _fill_and_scale_similarity_rows(
        target,
        cand_rows,
        norm_rows=norm_rows,
        features=features,
    )

    candidates_df = df.copy()
    candidates_df["similarity"] = scores_arr

    # Drop self if present
    candidates_df = candidates_df[candidates_df["wyscout_id"] != req.target_player_id]
    candidates_df = candidates_df.sort_values("similarity", ascending=False)
    candidates_df = candidates_df.drop_duplicates(subset=["wyscout_id"], keep="first")
    candidates_df = candidates_df.head(req.limit)

    cand_out: list[ReplacementCandidate] = []
    for _, row in candidates_df.iterrows():
        cs = row.get("_candidate_season")
        cand_out.append(
            ReplacementCandidate(
                wyscout_id=int(row["wyscout_id"]) if pd.notna(row["wyscout_id"]) else None,
                player=str(row["player"]),
                club=row.get("club") if pd.notna(row.get("club")) else None,
                league=row.get("league") if pd.notna(row.get("league")) else None,
                position=row.get("position") if pd.notna(row.get("position")) else None,
                age=int(row["age"]) if pd.notna(row["age"]) else None,
                minutes=int(row["minutes"]) if pd.notna(row["minutes"]) else None,
                similarity=float(row["similarity"]),
                candidate_season=int(cs) if cs is not None and pd.notna(cs) else None,
                club_logo=normalize_club_logo(row.get("club_logo")),
                player_image_url=(row.get("player_image_url") or None) if pd.notna(row.get("player_image_url")) else None,
            )
        )

    target_summary = ReplacementCandidate(
        wyscout_id=target.get("wyscout_id"),
        player=str(target["player"]),
        club=target.get("club"),
        league=target.get("league"),
        position=target.get("position"),
        age=target.get("age"),
        minutes=target.get("minutes"),
        similarity=1.0,
        club_logo=normalize_club_logo(target.get("club_logo")),
        player_image_url=target.get("player_image_url") or None,
    )

    return ReplacementResponse(
        target=target_summary,
        candidates=cand_out,
        n=len(cand_out),
        profile=profile,
        method=method,
    )
