"""Build team profiles from per-player Wyscout data.

Pure functions — no I/O, no caching. Consumers (scripts/build_team_profiles.py,
tests) handle loading and persistence.
"""
from __future__ import annotations

from typing import Callable, Iterable, Mapping

import numpy as np
import pandas as pd

# Mapping: output_col -> source Wyscout column name.
RAW_FEATURE_SPEC: Mapping[str, str] = {
    # Offensive volume
    "goals_p90": "Goals per 90",
    "xg_p90": "xG per 90",
    "shots_p90": "Shots per 90",
    "shot_assists_p90": "Shot assists per 90",
    "touches_in_box_p90": "Touches in box per 90",
    # Creation & circulation
    "passes_p90": "Passes per 90",
    "pass_accuracy": "Accurate passes, %",
    "progressive_passes_p90": "Progressive passes per 90",
    "through_passes_p90": "Through passes per 90",
    "long_passes_p90": "Long passes per 90",
    "key_passes_p90": "Key passes per 90",
    "crosses_p90": "Crosses per 90",
    "cross_accuracy": "Accurate crosses, %",
    # Vertical drive
    "dribbles_p90": "Dribbles per 90",
    "dribble_success": "Successful dribbles, %",
    "progressive_runs_p90": "Progressive runs per 90",
    "accelerations_p90": "Accelerations per 90",
    # Defensive activity
    "defensive_duels_p90": "Defensive duels per 90",
    "interceptions_p90": "Interceptions per 90",
    "padj_interceptions": "PAdj Interceptions",
    "aerial_duels_p90": "Aerial duels per 90",
    "aerial_won_pct": "Aerial duels won, %",
}


def aggregate_team_raw_features(
    df: pd.DataFrame,
    *,
    season: int,
    spec: Mapping[str, str] = RAW_FEATURE_SPEC,
) -> pd.DataFrame:
    """Weighted-by-minutes aggregation of per-player metrics into per-team rows.

    Returns one row per (team, league) with keys team/league/season/minutes_weighted
    plus one column per ``spec`` key. Missing source columns yield NaN (not dropped).
    """
    if df.empty:
        return pd.DataFrame(
            columns=["team", "league", "season", "minutes_weighted", *spec.keys()]
        )

    work = df.copy()
    work["_minutes"] = pd.to_numeric(work["Minutes played"], errors="coerce").fillna(0)

    grouped_rows: list[dict] = []
    for (team, league), sub in work.groupby(["Team", "league"], dropna=False):
        w = sub["_minutes"].to_numpy(dtype=float)
        tot = float(w.sum())
        row: dict = {
            "team": team,
            "league": league,
            "season": int(season),
            "minutes_weighted": tot,
        }
        for out_col, src_col in spec.items():
            if src_col in sub.columns and tot > 0:
                vals = pd.to_numeric(sub[src_col], errors="coerce").to_numpy(dtype=float)
                mask = np.isfinite(vals)
                if mask.any():
                    row[out_col] = float(np.sum(vals[mask] * w[mask]) / np.sum(w[mask]))
                else:
                    row[out_col] = np.nan
            else:
                row[out_col] = np.nan
        grouped_rows.append(row)

    return pd.DataFrame(grouped_rows)


# Names of composite features (without the _raw / _z suffix).
COMPOSITE_FEATURES: tuple[str, ...] = (
    "dominance_index",
    "directness",
    "cross_reliance",
    "build_up_length_proxy",
    "press_intensity_proxy",
    "vertical_progression",
    "width_usage",
    "shot_concentration",
)

# Subset of composites used for style (excludes level proxies).
STYLE_FEATURES: tuple[str, ...] = (
    "directness",
    "cross_reliance",
    "build_up_length_proxy",
    "press_intensity_proxy",
    "vertical_progression",
    "width_usage",
    "shot_concentration",
)


def _safe_div(num: pd.Series, den: pd.Series) -> pd.Series:
    num = pd.to_numeric(num, errors="coerce")
    den = pd.to_numeric(den, errors="coerce")
    out = num / den
    out[(den == 0) | ~np.isfinite(out)] = np.nan
    return out


def compute_composite_features(raw: pd.DataFrame) -> pd.DataFrame:
    """Add composite features (``*_raw`` columns only) to the raw team frame.

    Z-normalization is applied separately by :func:`normalize_composites_by_league_season`.
    """
    if raw.empty:
        out = raw.copy()
        for name in COMPOSITE_FEATURES:
            out[f"{name}_raw"] = np.nan
        return out

    out = raw.copy()
    # directness
    out["directness_raw"] = _safe_div(out["progressive_passes_p90"], out["passes_p90"])
    # cross_reliance
    out["cross_reliance_raw"] = _safe_div(
        out["crosses_p90"], out["shot_assists_p90"] + out["crosses_p90"]
    )
    # build_up_length_proxy = 1 - (long_passes_p90 / passes_p90)
    long_share = _safe_div(out["long_passes_p90"], out["passes_p90"])
    out["build_up_length_proxy_raw"] = 1.0 - long_share
    # width_usage
    out["width_usage_raw"] = _safe_div(out["crosses_p90"], out["progressive_passes_p90"])
    # shot_concentration
    out["shot_concentration_raw"] = _safe_div(
        out["shots_p90"], out["touches_in_box_p90"]
    )
    # dominance_index_raw, press_intensity_proxy_raw, vertical_progression_raw
    # are scale-dependent — written raw and then z-normalized in next step.
    out["dominance_index_raw"] = (
        pd.to_numeric(out["xg_p90"], errors="coerce")
        + 0.3 * pd.to_numeric(out["passes_p90"], errors="coerce")
    )
    out["press_intensity_proxy_raw"] = pd.to_numeric(
        out["interceptions_p90"], errors="coerce"
    ) + pd.to_numeric(out["defensive_duels_p90"], errors="coerce")
    out["vertical_progression_raw"] = pd.to_numeric(
        out["progressive_runs_p90"], errors="coerce"
    ) + pd.to_numeric(out["progressive_passes_p90"], errors="coerce")
    return out


def normalize_composites_by_league_season(df: pd.DataFrame) -> pd.DataFrame:
    """Add ``<feat>_z`` column for each composite feature, grouped by (league, season).

    Uses population std (ddof=0). Single-item groups or zero-variance groups yield 0.
    """
    if df.empty:
        out = df.copy()
        for name in COMPOSITE_FEATURES:
            out[f"{name}_z"] = np.nan
        return out

    out = df.copy()
    for name in COMPOSITE_FEATURES:
        src = f"{name}_raw"
        dst = f"{name}_z"
        if src not in out.columns:
            out[dst] = np.nan
            continue

        def _zscore(g: pd.Series) -> pd.Series:
            vals = pd.to_numeric(g, errors="coerce")
            mu = vals.mean(skipna=True)
            sd = vals.std(ddof=0, skipna=True)
            if not np.isfinite(sd) or sd < 1e-12:
                return pd.Series(np.zeros(len(vals)), index=vals.index)
            return (vals - mu) / sd

        out[dst] = (
            out.groupby(["league", "season"])[src]
            .transform(_zscore)
        )
    return out


def build_team_profiles(
    *,
    seasons: Iterable[int],
    loader: Callable[[int], pd.DataFrame],
    min_team_minutes: float = 0.0,
    spec: Mapping[str, str] = RAW_FEATURE_SPEC,
) -> pd.DataFrame:
    """Build the full team_profiles frame for all *seasons*.

    *loader(season_year)* returns a per-player dataframe with at least the
    columns in *spec* plus ``Team``, ``league``, ``Minutes played``.
    """
    parts: list[pd.DataFrame] = []
    for season in seasons:
        df = loader(int(season))
        if df is None or df.empty:
            continue
        raw = aggregate_team_raw_features(df, season=int(season), spec=spec)
        if raw.empty:
            continue
        raw = raw[raw["minutes_weighted"] >= float(min_team_minutes)].copy()
        if raw.empty:
            continue
        parts.append(raw)
    if not parts:
        return pd.DataFrame()

    combined = pd.concat(parts, ignore_index=True)
    with_comp = compute_composite_features(combined)
    normalized = normalize_composites_by_league_season(with_comp)
    # Stable ordering for readability
    return normalized.sort_values(["season", "league", "team"]).reset_index(drop=True)
