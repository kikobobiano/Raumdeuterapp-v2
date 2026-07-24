"""Scouting Discover endpoint — cohort z-scores + PCA + k-means + club fit."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException

from app.core.club_logos import club_logo_select_sql, normalize_club_logo
from app.core.duckdb_pool import duckdb_session, fetch_all_dicts, list_views
from app.core.filters import build_where, view_name
from app.core.league_style_fit import (
    STYLE_FEATURES,
    WYSCOUT_STYLE_COLUMNS,
    compute_team_style_fit,
)
from app.core.metric_modes import format_selectbox_option_display
from app.core.metric_sql import metric_sql_expr
from app.core.metrics_catalog import column_names_in_view, selectable_metric_names
from app.core.player_age import player_age_sql
from app.core.player_image import player_image_select_sql
from app.core.scouting_archetype import cluster_labels, kmeans, pca, silhouette
from app.core.scouting_cohort import (
    cohort_stats,
    cohort_where_for_player_set,
    percentile_rank,
    shrunk_zscore,
)
from app.core.scouting_standouts import compute_standouts
from app.schemas import (
    DiscoverClusterSummary,
    DiscoverCohortInfo,
    DiscoverMetricValue,
    DiscoverPCAInfo,
    DiscoverRequest,
    DiscoverResponse,
    DiscoverRow,
    StandoutRequest,
    StandoutResponse,
)

router = APIRouter(prefix="/scouting", tags=["scouting"])


@router.post("/discover", response_model=DiscoverResponse)
def discover(req: DiscoverRequest) -> DiscoverResponse:
    view = view_name(req.filters.season)
    if view not in list_views():
        raise HTTPException(404, f"season {req.filters.season} not loaded")

    with duckdb_session() as conn:
        vcols = column_names_in_view(conn, view)
        allowed = set(selectable_metric_names(conn, view))
        for spec in req.metrics:
            if spec.metric not in allowed:
                raise HTTPException(400, f"Unknown or unavailable metric: {spec.metric}")

        # Candidate selection (the user's filters as-is).
        where_sql, where_params = build_where(req.filters, cols=vcols)
        where_clause = f"WHERE {where_sql}" if where_sql else ""

        age_sel = player_age_sql(vcols, req.filters.season)
        logo_sel = club_logo_select_sql(conn, view, req.filters.season)
        photo_sel = player_image_select_sql(conn, view)
        has_passport = "Passport country" in vcols
        has_height = "Height" in vcols
        has_foot = "Foot" in vcols
        has_contract = "Contract expires" in vcols
        has_xtv = "x_tv_eur" in vcols

        base_cols = [
            logo_sel,
            photo_sel,
            '"Wyscout id" AS wyscout_id',
            '"Player" AS player',
            "club",
            "league",
            '"Primary position" AS position',
            f"({age_sel}) AS age",
            '"Minutes played" AS minutes',
            ('"Passport country" AS passport_country' if has_passport else "CAST(NULL AS VARCHAR) AS passport_country"),
            ('try_cast("Height" AS INTEGER) AS height' if has_height else "CAST(NULL AS INTEGER) AS height"),
            ('"Foot" AS foot' if has_foot else "CAST(NULL AS VARCHAR) AS foot"),
            (
                'CAST("Contract expires" AS VARCHAR) AS contract_expires'
                if has_contract
                else "CAST(NULL AS VARCHAR) AS contract_expires"
            ),
            ('CAST("x_tv_eur" AS DOUBLE) AS x_tv_eur' if has_xtv else "CAST(NULL AS DOUBLE) AS x_tv_eur"),
        ]
        metric_aliases: list[str] = []
        for i, spec in enumerate(req.metrics):
            expr = metric_sql_expr(spec.metric, spec.mode)
            alias = f"_m{i}"
            base_cols.append(f"({expr}) AS {alias}")
            metric_aliases.append(alias)

        sql = f"SELECT {', '.join(base_cols)} FROM {view} {where_clause}"
        result = conn.execute(sql, where_params)
        desc = result.description
        col_names = [d[0] for d in desc] if desc else []
        raw_rows = result.fetchall()
        if not raw_rows:
            return DiscoverResponse(
                rows=[],
                total=0,
                cohort=DiscoverCohortInfo(
                    n=0,
                    tier_used=req.cohort_tier,
                    min_minutes=req.filters.minutes_min or 600,
                    fallback_applied=False,
                ),
                metric_labels={s.metric: format_selectbox_option_display(s.metric) for s in req.metrics},
            )

        records = [dict(zip(col_names, tup, strict=True)) for tup in raw_rows]

        # Cohort z-score baseline (separate query, independent pool).
        metrics_with_mode = [(s.metric, s.mode) for s in req.metrics]
        cohort = cohort_stats(
            conn,
            filters=req.filters,
            tier=req.cohort_tier,
            metrics_with_mode=metrics_with_mode,
        )
        fallback_applied = cohort["tier_used"] != req.cohort_tier

        # Build the player z/percentile matrix.
        z_matrix = np.full((len(records), len(req.metrics)), np.nan, dtype=float)
        percentile_matrix: np.ndarray | None = None
        if req.normalization == "percentile":
            percentile_matrix = np.full((len(records), len(req.metrics)), np.nan, dtype=float)
            ch_where, ch_params = cohort_where_for_player_set(req.filters, tier=cohort["tier_used"])

        for j, spec in enumerate(req.metrics):
            mu = cohort["means"].get(spec.metric)
            sd = cohort["sds"].get(spec.metric)
            for i, rec in enumerate(records):
                raw_v = rec.get(metric_aliases[j])
                v = float(raw_v) if raw_v is not None else None
                z = shrunk_zscore(
                    v,
                    mean=mu,
                    sd=sd,
                    player_minutes=rec.get("minutes"),
                )
                z_matrix[i, j] = z if z is not None else np.nan
                if percentile_matrix is not None and v is not None:
                    p = percentile_rank(
                        conn,
                        view=view,
                        where_sql=ch_where,
                        where_params=ch_params,
                        metric=spec.metric,
                        mode=spec.mode,
                        value=v,
                    )
                    percentile_matrix[i, j] = p if p is not None else np.nan

        # Composite score = weighted sum of z (or percentile mapped to ~z scale).
        weights = np.array([s.weight for s in req.metrics], dtype=float)
        wsum = float(np.sum(np.abs(weights))) or 1.0
        if req.normalization == "percentile" and percentile_matrix is not None:
            # Map percentile [0,1] → centered ranks ~[-1.7, 1.7].
            score_matrix = (percentile_matrix - 0.5) * np.sqrt(12.0)
        else:
            score_matrix = z_matrix
        masked = np.where(np.isnan(score_matrix), 0.0, score_matrix)
        composite = (masked @ weights) / wsum

        # Threshold filter (per-metric z ≥ threshold).
        keep_mask = np.ones(len(records), dtype=bool)
        for j, spec in enumerate(req.metrics):
            if spec.threshold_z is not None:
                col = z_matrix[:, j]
                keep_mask &= np.where(np.isnan(col), False, col >= spec.threshold_z)

        # Club style fit.
        style_fits: list[float | None] = [None] * len(records)
        if req.club_fit_team and "team_profiles" in list_views():
            prof_rows = fetch_all_dicts(
                conn,
                """SELECT team, season, minutes_weighted,
                          directness_raw, cross_reliance_raw, build_up_length_proxy_raw,
                          press_intensity_proxy_raw, vertical_progression_raw,
                          width_usage_raw, shot_concentration_raw
                   FROM team_profiles
                   WHERE season = ?""",
                [req.filters.season],
            )
            if prof_rows:
                profiles = pd.DataFrame(prof_rows)
                # Player style needs Wyscout raw style columns — pull once per player.
                wanted = [c for c in WYSCOUT_STYLE_COLUMNS if c in vcols]
                style_lookup: dict[int, dict[str, Any]] = {}
                if wanted:
                    pids = [int(r["wyscout_id"]) for r in records if r.get("wyscout_id") is not None]
                    if pids:
                        ph = ",".join(["?"] * len(pids))
                        sel = ", ".join(f'"{c}"' for c in wanted)
                        style_rows = fetch_all_dicts(
                            conn,
                            f'SELECT "Wyscout id" AS wid, {sel} FROM {view} WHERE "Wyscout id" IN ({ph})',
                            pids,
                        )
                        for sr in style_rows:
                            style_lookup[int(sr["wid"])] = sr
                for i, rec in enumerate(records):
                    wid = rec.get("wyscout_id")
                    if wid is None:
                        continue
                    style_row = style_lookup.get(int(wid)) or {}
                    fit = compute_team_style_fit(
                        player=style_row,
                        profiles=profiles,
                        target_team=req.club_fit_team,
                        season=req.filters.season,
                    )
                    style_fits[i] = fit
                    if fit is not None:
                        composite[i] = composite[i] * (1.0 + req.club_fit_weight * fit)

        # PCA + k-means on the kept rows.
        kept_idx = np.where(keep_mask)[0]
        pca_info: DiscoverPCAInfo | None = None
        clusters: list[DiscoverClusterSummary] = []
        sil: float | None = None
        cluster_assignment = np.full(len(records), -1, dtype=int)
        pca_scores = np.zeros((len(records), 3), dtype=float)
        if req.archetype == "pca_kmeans" and len(kept_idx) >= 4:
            sub_z = z_matrix[kept_idx]
            pca_out = pca(sub_z, k=3)
            scores = pca_out["scores"]
            loadings = pca_out["loadings"]
            explained = pca_out["explained"]
            pca_info = DiscoverPCAInfo(
                explained_variance=explained,
                loadings=loadings.tolist(),
            )
            pca_scores[kept_idx, :] = scores
            km = kmeans(scores, k=req.k_clusters, seed=42)
            labels_arr = km["labels"]
            cluster_assignment[kept_idx] = labels_arr
            sil = silhouette(scores, labels_arr)
            metric_names = [format_selectbox_option_display(s.metric) for s in req.metrics]
            # Cluster centers in z-space (recompute means per cluster in original z-matrix).
            centers_z = np.zeros((int(labels_arr.max()) + 1 if labels_arr.size else 0, sub_z.shape[1]))
            for c_id in range(centers_z.shape[0]):
                mask = labels_arr == c_id
                if mask.any():
                    centers_z[c_id] = np.nanmean(sub_z[mask], axis=0)
            names = cluster_labels(centers_z, metric_names, top_k=2)
            for c_id, lbl in enumerate(names):
                clusters.append(
                    DiscoverClusterSummary(
                        cluster_id=c_id,
                        label=lbl,
                        n_members=int((labels_arr == c_id).sum()),
                    )
                )

        # Build rows for the kept set, ordered by composite descending.
        order = np.argsort(-composite[kept_idx])
        ordered_idx = kept_idx[order]
        total_kept = int(ordered_idx.size)
        sliced = ordered_idx[req.offset : req.offset + req.limit]

        out_rows: list[DiscoverRow] = []
        for i in sliced:
            rec = records[int(i)]
            metric_values = []
            for j, spec in enumerate(req.metrics):
                raw_v = rec.get(metric_aliases[j])
                metric_values.append(
                    DiscoverMetricValue(
                        metric=spec.metric,
                        value=float(raw_v) if raw_v is not None else None,
                        z=(float(z_matrix[i, j]) if not np.isnan(z_matrix[i, j]) else None),
                        percentile=(
                            float(percentile_matrix[i, j])
                            if percentile_matrix is not None and not np.isnan(percentile_matrix[i, j])
                            else None
                        ),
                    )
                )
            cid = int(cluster_assignment[i]) if cluster_assignment[i] >= 0 else None
            out_rows.append(
                DiscoverRow(
                    wyscout_id=rec.get("wyscout_id"),
                    player=rec.get("player") or "",
                    club=rec.get("club"),
                    club_logo=normalize_club_logo(rec.get("club_logo")),
                    league=rec.get("league"),
                    position=rec.get("position"),
                    age=rec.get("age"),
                    minutes=rec.get("minutes"),
                    height=rec.get("height"),
                    foot=rec.get("foot"),
                    passport_country=rec.get("passport_country"),
                    contract_expires=rec.get("contract_expires"),
                    x_tv_eur=rec.get("x_tv_eur"),
                    player_image_url=rec.get("player_image_url"),
                    composite_score=float(composite[i]),
                    style_fit=style_fits[int(i)],
                    cluster_id=cid,
                    pca_x=float(pca_scores[i, 0]) if pca_info else None,
                    pca_y=float(pca_scores[i, 1]) if pca_info else None,
                    pca_z=float(pca_scores[i, 2]) if pca_info else None,
                    metric_values=metric_values,
                )
            )

    return DiscoverResponse(
        rows=out_rows,
        total=total_kept,
        cohort=DiscoverCohortInfo(
            n=int(cohort["n"]),
            tier_used=cohort["tier_used"],
            min_minutes=req.filters.minutes_min or 600,
            fallback_applied=fallback_applied,
        ),
        pca=pca_info,
        clusters=clusters,
        silhouette=sil,
        metric_labels={s.metric: format_selectbox_option_display(s.metric) for s in req.metrics},
    )


@router.post("/standouts", response_model=StandoutResponse)
def standouts(req: StandoutRequest) -> StandoutResponse:
    """Rank players who perform furthest above the selected league's average."""
    view = view_name(req.filters.season)
    if view not in list_views():
        raise HTTPException(404, f"season {req.filters.season} not loaded")

    with duckdb_session() as conn:
        if req.signal == "metrics":
            allowed = set(selectable_metric_names(conn, view))
            for spec in req.metrics:
                if spec.metric not in allowed:
                    raise HTTPException(400, f"Unknown or unavailable metric: {spec.metric}")

        result = compute_standouts(
            conn,
            filters=req.filters,
            signal=req.signal,
            metrics=[(s.metric, s.mode, s.weight) for s in req.metrics],
            min_standout_z=req.min_standout_z,
            limit=req.limit,
        )

    return StandoutResponse(**result)
