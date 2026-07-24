"""League style fit — cosine similarity of player vs league style centroids.

Port of ``utils/team_profile_scoring.compute_league_style_fit`` and
``utils/player_fingerprint.player_raw_style_vector``, matching
``pages/13_Performance_Translation`` “League Style Fit” table.
"""
from __future__ import annotations

from typing import Any, Mapping, MutableMapping, Sequence

import numpy as np
import pandas as pd

from app.core.duckdb_pool import fetch_all_dicts, list_views
from app.core.metrics_catalog import column_names_in_view

# Mirror ``transformation/team_profiles.RAW_FEATURE_SPEC`` + composites.
RAW_FEATURE_SPEC: Mapping[str, str] = {
    "goals_p90": "Goals per 90",
    "xg_p90": "xG per 90",
    "shots_p90": "Shots per 90",
    "shot_assists_p90": "Shot assists per 90",
    "touches_in_box_p90": "Touches in box per 90",
    "passes_p90": "Passes per 90",
    "pass_accuracy": "Accurate passes, %",
    "progressive_passes_p90": "Progressive passes per 90",
    "through_passes_p90": "Through passes per 90",
    "long_passes_p90": "Long passes per 90",
    "key_passes_p90": "Key passes per 90",
    "crosses_p90": "Crosses per 90",
    "cross_accuracy": "Accurate crosses, %",
    "dribbles_p90": "Dribbles per 90",
    "dribble_success": "Successful dribbles, %",
    "progressive_runs_p90": "Progressive runs per 90",
    "accelerations_p90": "Accelerations per 90",
    "defensive_duels_p90": "Defensive duels per 90",
    "interceptions_p90": "Interceptions per 90",
    "padj_interceptions": "PAdj Interceptions",
    "aerial_duels_p90": "Aerial duels per 90",
    "aerial_won_pct": "Aerial duels won, %",
}

STYLE_FEATURES: tuple[str, ...] = (
    "directness",
    "cross_reliance",
    "build_up_length_proxy",
    "press_intensity_proxy",
    "vertical_progression",
    "width_usage",
    "shot_concentration",
)

WYSCOUT_STYLE_COLUMNS: tuple[str, ...] = tuple(sorted(set(RAW_FEATURE_SPEC.values())))


def _safe_div(num: pd.Series, den: pd.Series) -> pd.Series:
    num = pd.to_numeric(num, errors="coerce")
    den = pd.to_numeric(den, errors="coerce")
    out = num / den
    out[(den == 0) | ~np.isfinite(out)] = np.nan
    return out


def compute_composite_features(raw: pd.DataFrame) -> pd.DataFrame:
    """Add ``*_raw`` composite columns (same as ``transformation.team_profiles``)."""
    if raw.empty:
        out = raw.copy()
        for name in ("dominance_index", *STYLE_FEATURES):
            out[f"{name}_raw"] = np.nan
        return out

    out = raw.copy()
    out["directness_raw"] = _safe_div(out["progressive_passes_p90"], out["passes_p90"])
    out["cross_reliance_raw"] = _safe_div(
        out["crosses_p90"], out["shot_assists_p90"] + out["crosses_p90"]
    )
    long_share = _safe_div(out["long_passes_p90"], out["passes_p90"])
    out["build_up_length_proxy_raw"] = 1.0 - long_share
    out["width_usage_raw"] = _safe_div(out["crosses_p90"], out["progressive_passes_p90"])
    out["shot_concentration_raw"] = _safe_div(out["shots_p90"], out["touches_in_box_p90"])
    out["dominance_index_raw"] = pd.to_numeric(out["xg_p90"], errors="coerce") + 0.3 * pd.to_numeric(
        out["passes_p90"], errors="coerce"
    )
    out["press_intensity_proxy_raw"] = pd.to_numeric(
        out["interceptions_p90"], errors="coerce"
    ) + pd.to_numeric(out["defensive_duels_p90"], errors="coerce")
    out["vertical_progression_raw"] = pd.to_numeric(
        out["progressive_runs_p90"], errors="coerce"
    ) + pd.to_numeric(out["progressive_passes_p90"], errors="coerce")
    return out


def _val(row: Mapping[str, Any], col: str) -> float:
    if col not in row:
        return float("nan")
    try:
        v = float(row[col])  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return float("nan")
    return v if np.isfinite(v) else float("nan")


def player_raw_style_vector(player: Mapping[str, Any]) -> pd.Series:
    """Seven style composites on the same scale as ``team_profiles.*_raw``."""
    row: dict[str, float] = {}
    for out_col, wyscout_col in RAW_FEATURE_SPEC.items():
        row[out_col] = _val(player, wyscout_col)
    one = pd.DataFrame([row])
    out = compute_composite_features(one)
    data: dict[str, float] = {}
    for d in STYLE_FEATURES:
        col = f"{d}_raw"
        if col not in out.columns:
            data[d] = float("nan")
            continue
        v = out[col].iloc[0]
        data[d] = float(v) if pd.notna(v) and np.isfinite(v) else float("nan")
    return pd.Series(data, index=list(STYLE_FEATURES))


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na < 1e-12 or nb < 1e-12:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def compute_league_style_fit(
    *,
    player: Mapping[str, Any],
    profiles: pd.DataFrame,
    target_leagues: Sequence[str],
    season: int,
) -> list[dict[str, Any]]:
    """Return one row per target league: league, season, style_fit, n_teams, minutes_weighted.

    Z-scoring across all teams in *target_leagues* for the season (legacy behaviour).
    Sorted by ``style_fit`` descending.
    """
    cols_out = ("league", "season", "style_fit", "n_teams", "minutes_weighted")
    if profiles is None or profiles.empty:
        return []

    pool = profiles[
        (profiles["season"] == int(season)) & (profiles["league"].isin(list(target_leagues)))
    ].copy()
    if pool.empty:
        return []

    raw_cols = [f"{d}_raw" for d in STYLE_FEATURES]
    if not all(c in pool.columns for c in raw_cols):
        return []

    p_raw = player_raw_style_vector(player)

    mu: dict[str, float] = {}
    sd: dict[str, float] = {}
    for d in STYLE_FEATURES:
        col = f"{d}_raw"
        vals = pd.to_numeric(pool[col], errors="coerce")
        mu[d] = float(vals.mean(skipna=True)) if vals.notna().any() else 0.0
        s = float(vals.std(ddof=0, skipna=True)) if vals.notna().sum() > 1 else 0.0
        sd[d] = s if np.isfinite(s) and s >= 1e-12 else 0.0

    def zvec(raw: MutableMapping[str, float] | pd.Series) -> np.ndarray:
        out = np.zeros(len(STYLE_FEATURES), dtype=float)
        for i, d in enumerate(STYLE_FEATURES):
            src = raw.get(d, np.nan) if isinstance(raw, dict) else raw.get(d, np.nan)
            v = float(src) if pd.notna(src) else float("nan")
            if not np.isfinite(v):
                continue
            if sd[d] < 1e-12:
                out[i] = 0.0
            else:
                out[i] = (v - mu[d]) / sd[d]
        return out

    pz = zvec(p_raw)
    wcol = "minutes_weighted" if "minutes_weighted" in pool.columns else None
    rows: list[dict[str, Any]] = []

    for league, g in pool.groupby("league", sort=False):
        g2 = g.copy()
        if wcol is not None:
            w = pd.to_numeric(g2[wcol], errors="coerce").fillna(0.0).to_numpy(dtype=float)
            if float(np.sum(w)) <= 0.0:
                w = np.ones(len(g2), dtype=float)
        else:
            w = np.ones(len(g2), dtype=float)

        cen: dict[str, float] = {}
        for d in STYLE_FEATURES:
            col = f"{d}_raw"
            vals = pd.to_numeric(g2[col], errors="coerce").to_numpy(dtype=float)
            mask = np.isfinite(vals) & np.isfinite(w)
            if not mask.any():
                cen[d] = float("nan")
                continue
            vw = w[mask]
            vv = vals[mask]
            cen[d] = float(np.sum(vv * vw) / np.sum(vw))

        cz = zvec(cen)
        fit = _cosine(pz, cz)

        rows.append({
            "league": league,
            "season": int(season),
            "style_fit": float(fit),
            "n_teams": int(len(g2)),
            "minutes_weighted": float(np.sum(w)) if wcol is not None else float(len(g2)),
        })

    if not rows:
        return []
    rows.sort(key=lambda r: r["style_fit"], reverse=True)
    return rows


def _qident(name: str) -> str:
    if any(c in name for c in ('"', ";", "--")):
        raise ValueError(f"invalid column name: {name}")
    return f'"{name}"'


def compute_team_style_fit(
    *,
    player: Mapping[str, Any],
    profiles: pd.DataFrame,
    target_team: str,
    season: int,
) -> float | None:
    """Cosine similarity of player style vector vs a single team's centroid.

    Z-scoring is computed across ALL teams in ``profiles`` for the season — so
    a player who matches the target team well *relative to the league pool*
    scores high. Returns None when data is missing.
    """
    if profiles is None or profiles.empty:
        return None
    pool = profiles[profiles["season"] == int(season)].copy()
    if pool.empty:
        return None
    raw_cols = [f"{d}_raw" for d in STYLE_FEATURES]
    if not all(c in pool.columns for c in raw_cols):
        return None

    p_raw = player_raw_style_vector(player)

    mu: dict[str, float] = {}
    sd: dict[str, float] = {}
    for d in STYLE_FEATURES:
        col = f"{d}_raw"
        vals = pd.to_numeric(pool[col], errors="coerce")
        mu[d] = float(vals.mean(skipna=True)) if vals.notna().any() else 0.0
        s = float(vals.std(ddof=0, skipna=True)) if vals.notna().sum() > 1 else 0.0
        sd[d] = s if np.isfinite(s) and s >= 1e-12 else 0.0

    def zvec(raw: MutableMapping[str, float] | pd.Series) -> np.ndarray:
        out = np.zeros(len(STYLE_FEATURES), dtype=float)
        for i, d in enumerate(STYLE_FEATURES):
            src = raw.get(d, np.nan) if isinstance(raw, dict) else raw.get(d, np.nan)
            v = float(src) if pd.notna(src) else float("nan")
            if not np.isfinite(v):
                continue
            if sd[d] < 1e-12:
                out[i] = 0.0
            else:
                out[i] = (v - mu[d]) / sd[d]
        return out

    team_rows = pool[pool["team"] == target_team] if "team" in pool.columns else pd.DataFrame()
    if team_rows.empty and "club" in pool.columns:
        team_rows = pool[pool["club"] == target_team]
    if team_rows.empty:
        return None

    cen: dict[str, float] = {}
    for d in STYLE_FEATURES:
        col = f"{d}_raw"
        vals = pd.to_numeric(team_rows[col], errors="coerce")
        cen[d] = float(vals.mean(skipna=True)) if vals.notna().any() else float("nan")

    pz = zvec(p_raw)
    cz = zvec(cen)
    return _cosine(pz, cz)


def translation_style_fit_rows(
    conn: Any,
    *,
    player_base: Mapping[str, Any],
    player_id: int,
    src_view: str,
    target_leagues: list[str],
    target_season: int,
) -> list[dict[str, Any]]:
    """Load team profiles + Wyscout style columns; return ``compute_league_style_fit`` rows."""
    if "team_profiles" not in list_views() or not target_leagues:
        return []

    cols_allow = column_names_in_view(conn, src_view)
    wanted = [c for c in WYSCOUT_STYLE_COLUMNS if c in cols_allow]
    extra: dict[str, Any] = {}
    if wanted:
        sel = ", ".join(_qident(c) for c in wanted)
        rows = fetch_all_dicts(
            conn,
            f"SELECT {sel} FROM {src_view} WHERE \"Wyscout id\" = ? LIMIT 1",
            [player_id],
        )
        if rows:
            extra = rows[0]

    merged: dict[str, Any] = dict(player_base)
    merged.update(extra)

    placeholders = ",".join(["?"] * len(target_leagues))
    prof_rows = fetch_all_dicts(
        conn,
        f"""SELECT league, season, minutes_weighted,
                  directness_raw, cross_reliance_raw, build_up_length_proxy_raw,
                  press_intensity_proxy_raw, vertical_progression_raw,
                  width_usage_raw, shot_concentration_raw
            FROM team_profiles
            WHERE season = ? AND league IN ({placeholders})""",
        [target_season, *target_leagues],
    )
    if not prof_rows:
        return []

    profiles = pd.DataFrame(prof_rows)
    return compute_league_style_fit(
        player=merged,
        profiles=profiles,
        target_leagues=target_leagues,
        season=target_season,
    )
