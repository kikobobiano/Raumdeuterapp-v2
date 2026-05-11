# -*- coding: utf-8 -*-
"""
Build per-season merged player CSVs with game-area indices and quality scores.

Paths resolve from this file (expects repo root one level above transformation/).
  python transformation/new_performance_index.py

Rankings / Best XI gate each ``PERFORMANCE_WEIGHTS_HYBRID`` archetype to the matching
Wyscout roles via ``utils.transforms.PERFORMANCE_ARCHETYPE_ROLE_FILTER`` and
``mask_rows_for_performance_archetype_roles`` (e.g. Ball Playing CB ⇒ Defenders only).
Batch exports can reuse the same helpers if you need role-scoped subsets.
"""

# --- Notes (from former notebook markdown) ---
# ### Fórmula do índice por área (`AREA_INDEX_METHOD = "zscore_tanh"`)
# 
# Para cada época, a amostra é a concatenação de **todas as ligas**.
# 
# 1. **Winsorização global** de cada métrica $m$ nos quantis $(p_{lo}, p_{hi})$ (ex.: 1% e 99%).
# 2. **Z-score global**: $z_{i,m} = (x_{i,m} - \mu_m) / \sigma_m$ (com $\sigma_m$ mínimo para evitar divisão por zero).
# 3. **Compósito da área** $A$ (pesos $w_m$, incluindo pesos negativos p.ex. golos sofridos):
#    $$S_{i,A} = \frac{\sum_m w_m \, z_{i,m}}{\sum_m |w_m|}$$
#    só entram termos com $z_{i,m}$ finito; o denominador usa somente os $|w_m|$ dessas métricas.
# 4. **Ponderação por liga** (ground_defense, aerial_play, distribution com força extra):
#    $\lambda^{\mathrm{eff}} = 1 + (\lambda_\ell-1)\cdot\mathrm{strength}_A$; restantes $\mathrm{strength}=1$.
#    $S'_{i,A} = \lambda^{\mathrm{eff}} \, S_{i,A}$.
# 5. **Escala 0–100 suave** (sem cap duro em 100):
#    $$\text{Index}_{i,A} = 50 + 50 \tanh\!\left(\frac{S'_{i,A}}{\tau}\right)$$
#    com $\tau =$ `AREA_INDEX_TANH_TAU` (default 2.5).
# 
# O fluxo antigo (`percentile_cap`) mantém percentis globais × $\lambda$ com `min(..., 100)`.

import os
import re
import glob
import math
import numpy as np
import pandas as pd

# =============================
# 1 CONFIG YOU ALREADY UPDATED
# =============================

# Implied xG per penalty attempt when stripping pens from total xG (Wyscout CSVs).
PENALTY_XG_PER_ATTEMPT = 0.77

# --- Sub-segment metric weights: pillar -> subsegment -> { Wyscout column: weight } ---
SUBSEGMENT_METRIC_WEIGHTS: dict[str, dict[str, dict[str, float]]] = {
    "finishing": {
        "shot_volume": {"Shots per 90": 1.0},
        "shot_quality": {"Shots on target, %": 0.5, "xG per shot per 90": 0.5},
        "conversion": {"Non-penalty goals per 90": 0.7, "Goal conversion, %": 0.3},
        "movement": {"NPxG per 90": 1.0},
    },
    "assistance": {
        "open_play_chance": {
            "xA per 90": 0.4,
            "Shot assists per 90": 0.3,
            "Key passes per 90": 0.3,
        },
        "penetration": {
            "Passes to penalty area per 90": 0.4,
            "Through passes per 90": 0.3,
            "Deep completions per 90": 0.3,
        },
        "link_up": {
            "Offensive duels minus dribbles per 90": 0.8,
            "Back passes per 90": 0.2,
        },
    },
    "take_ons": {
        "dribble_carry": {"Dribbles per 90": 0.6, "Successful dribbles, %": 0.4},
        "progressive_carry": {"Progressive runs per 90": 0.6, "Accelerations per 90": 0.4},
        "duel_wing_play": {"Fouls suffered per 90": 1.0},
    },
    "distribution": {
        "involvement": {"Passes per 90": 0.5, "Received passes per 90": 0.5},
        "safety": {"Accurate passes, %": 1.0},
        "progression": {"Progressive passes per 90": 1.0},
        "variation": {
            "Long passes per 90": 0.5,
            "Accurate long passes, %": 0.3,
            "Average long pass length, m": 0.2,
        },
        "creation": {
            "Passes to final third per 90": 0.6,
            "Third assists per 90": 0.2,
            "Second assists per 90": 0.2,
        },
    },
    "ground_defense": {
        "duels": {"Defensive duels per 90": 0.3, "Defensive duels won, %": 0.7},
        "positioning": {"PAdj Interceptions": 0.65, "Shots blocked per 90": 0.35},
        "tackling": {"PAdj Sliding tackles": 1.0},
        # Softer than -1.0: outfielders inherit team concede rate; full weight over-penalises CBs.
        "team_context": {"Team GK conceded per 90": -0.65},
    },
    "aerial_play": {
        "overall": {"Aerial duels per 90": 0.45, "Aerial duels won, %": 0.55},
    },
    "miscellaneous": {
        "aggression": {"Fouls per 90": 1.0},
        "crossing": {"Crosses per 90": 0.4, "Accurate crosses, %": 0.6},
        "crossing_variation": {
            "Crosses to goalie box per 90": 0.5,
            "Deep completed crosses per 90": 0.5,
        },
    },
    "gk_shot_stopping": {
        "overall": {
            "Save rate, %": 0.25,
            "Prevented goals per 90": 0.3,
            "Conceded goals per 90": -0.45,
        },
    },
    "gk_distribution": {
        "overall": {
            "Accurate long passes, %": 0.05,
            "Long passes per 90": 0.05,
            "Progressive passes per 90": 0.05,
            "Back passes received as GK per 90": 0.05,
            "Passes per 90": 0.05,
            "Accurate progressive passes, %": 0.05,
            "Save rate, %": 0.2,
            "Prevented goals per 90": 0.25,
            "Conceded goals per 90": -0.25,
        },
    },
}

# Rollup of sub-segment indices into the six outfield game-area columns (+ aerial).
SUBSEGMENT_ROLLUP_ALPHA: dict[str, dict[str, float]] = {
    "finishing": {
        "shot_volume": 0.1,
        "shot_quality": 0.2,
        "conversion": 0.4,
        "movement": 0.3,
    },
    "assistance": {"open_play_chance": 0.4, "penetration": 0.4, "link_up": 0.2},
    "take_ons": {"dribble_carry": 0.5, "progressive_carry": 0.4, "duel_wing_play": 0.1},
    "distribution": {
        "involvement": 0.3,
        "safety": 0.15,
        "progression": 0.3,
        "variation": 0.1,
        "creation": 0.15,
    },
    # Emphasise individual duels / positioning / tackling vs team GK concede (shared noise for CBs).
    "ground_defense": {
        "duels": 0.4,
        "positioning": 0.22,
        "tackling": 0.05,
        "team_context": 0.23,
    },
    "aerial_play": {"overall": 1.0},
}

# Game-area keys used for team impact and legacy percentiles (flat merge).
game_areas = [
    "finishing",
    "assistance",
    "take_ons",
    "distribution",
    "ground_defense",
    "aerial_play",
    "gk_shot_stopping",
    "gk_distribution",
]

# --- z-score bundle weights for extra “quality” columns (not performance sub-indices) ---
weights: dict = {}
weights["link_up_play"] = {
    # Interaction
    "Offensive duels per 90": 0.13,
    "Offensive duels won, %": 0.09,

    # Receiving/support
    "Received passes per 90": 0.12,
    "Received long passes per 90": 0.04,

    # Circulation
    "Passes per 90": 0.10,
    "Accurate passes, %": 0.06,
    "Back passes per 90": 0.03,

    # Creativity / chance creation
    "xA per 90": 0.12,
    "Assists per 90": 0.10,
    "Shot assists per 90": 0.04,
    "Second assists per 90": 0.03,

    # Penetrative passes
    "Key passes per 90": 0.12,
    "Accurate passes to final third, %": 0.07,
}

weights["finishing_quality"] = {
    # Shot volume & frequency
    "Shots per 90": 0.15,

    # Accuracy & shot selection
    "Shots on target, %": 0.13,
    "xG per 90": 0.14,
    "xG per shot per 90": 0.16,

    # Finishing effectiveness
    "Goal conversion, %": 0.12,

    # Shot variety / bonus
    "Non-penalty goals per 90": 0.22,
    "Head goals per 90": 0.08,
}

weights["dribling_quality"] = {
    "Dribbles per 90": 0.30,
    "Successful dribbles, %": 0.15,
    "Offensive duels per 90": 0.10,
    "Progressive runs per 90": 0.25,
    'Accelerations per 90': 0.2
}

weights["distribution_quality"] = {
    "Passes per 90": 0.30,
    "Accurate passes, %": 0.25,
    "Progressive passes per 90": 0.30,
    'Vertical passes per 90':0.05,
    'Long passes per 90':0.05,
    'Received passes per 90':0.05,
}

weights["aerial_play_quality"] = {
    "Aerial duels per 90": 0.45,
    "Aerial duels won, %": 0.55,
}

weights["ground_defense_quality"] = {
    "Successful defensive actions per 90": 0.20,
    "Defensive duels per 90": 0.2,
    "Defensive duels won, %": 0.3,
    "PAdj Interceptions": 0.1,
    "Shots blocked per 90": 0.15,
    "PAdj Sliding tackles": 0.05
}

weights["creativity_quality"] = {
    "xA per 90": 0.15,
    "Assists per 90": 0.2,
    "Shot assists per 90": 0.10,
    "Second assists per 90": 0.05,
    "Key passes per 90": 0.15,
    "Accurate passes to final third, %": 0.05,
    "Passes to penalty area per 90": 0.1,
    "Deep completions per 90": 0.1,
    "Through passes per 90": 0.1,
}

weights["gk_shot_saving"] = {
    "Save rate, %": 0.3,
    "Prevented goals per 90": 0.35,
    "Conceded goals per 90": -0.35,
}

weights["gk_ball_playing"] = {
    "Save rate, %": 0.2,
    "Prevented goals per 90": 0.25,
    "Conceded goals per 90": -0.25,
    "Accurate long passes, %": 0.05,
    "Long passes per 90": 0.05,
    "Progressive passes per 90": 0.05,
    "Back passes received as GK per 90": 0.05,
    "Passes per 90": 0.05,
    "Accurate progressive passes, %": 0.05,
}

# Allowed leagues to process (only files/leagues in this array will be processed)
ALLOWED_LEAGUES = [
    "Premier League",
    "Serie A",
    "La Liga",
    "Bundesliga",
    "Ligue 1",
    "Championship",
    "Belgian Pro League",
    "Primeira Liga",
    "Brasileirão",
    "Eredivisie",
    "Argentina LPF",
    "MLS",
    "Liga de Expansión MX",
    "1. HNL",
    "J1",
    "Ekstraklasa",
    "Superliga",    
    "Serie B",
    "Allsvenskan",
    "Süper Lig",
    "La Liga 2",
    "2. Bundesliga",
    "Russian Premier League",
    "Swiss Super League",
    "Austrian Bundesliga",
    "Eliteserien",
    "Greek Super League",
    "Ukrainian Premier League",
    "Scottish Premiership",
    "Saudi Pro League",
    "Ligue 2",
    "Portuguese Segunda Liga",
    "Chilean Primera Division",
    "Veikkausliiga",
    "Portuguese Liga 3",
    "Campeonato de Portugal"
]

# Known leagues (extend/adjust values as you like).
# Any *new* league found in filenames that isn't here gets the median of known values.
league_power_base = {
    "Premier League": 93.0,
    "Serie A": 87.0,
    "La Liga": 87.0,
    "Bundesliga": 86.3,
    "Ligue 1": 85.5,
    "Championship": 80.9,
    "Belgian Pro League": 80.5,
    "Primeira Liga": 79.8,
    "Brasileirão": 79.4,
    "Eredivisie": 78.8,
    "Argentina LPF": 78.6,
    "MLS": 78.5,
    "Liga de Expansión MX": 78.5,
    "J1": 77.9,
    "1. HNL": 77.8,
    "Ekstraklasa": 77.6,
    "Superliga": 77.6,    
    "Serie B": 76.4,
    "Allsvenskan": 76.3,
    "Süper Lig": 76.2,
    "La Liga 2": 76.2,
    "2. Bundesliga": 76.2,
    "Russian Premier League": 76.1,
    "Swiss Super League": 76.1,
    "Austrian Bundesliga": 76.1,
    "Eliteserien": 75.9,
    "Greek Super League": 75.0,
    "Ukrainian Premier League": 75.0,
    "Scottish Premiership": 74.5,
    "Saudi Pro League": 74.0,
    "Ligue 2": 74.0,
    "Portuguese Segunda Liga": 70.5,
    "Chilean Primera Division":72.0,
    "Veikkausliiga": 68.0,
    "Portuguese Liga 3": 65.0,
    "Campeonato de Portugal": 59.0,
}

# Normalization range for league power factors (used to scale the final area index)
LEAGUE_POWER_MIN, LEAGUE_POWER_MAX = 0.70, 1.20

# If your inputs are RAW Wyscout columns, keep this True so we compute percentiles.
# If your inputs are already percentiles (0–100), set to False.
compute_percentiles = True

# --- Índice por área (finishing_index, distribution_index, …) ---
# "zscore_tanh" (recomendado): z global por métrica → média ponderada (|w|) → × fator de liga → tanh para 0–100.
# "percentile_cap": percentil global × fator de liga, cap em 100 (fluxo antigo).
AREA_INDEX_METHOD = "zscore_tanh"
AREA_INDEX_TANH_TAU = 2.5
# Slightly sharper tanh only for ground_defense sub-segments so elite defensive profiles
# can reach higher ``*_index`` values under the same z-scores (rollup was plateauing ~low-mid 70s).
GROUND_DEFENSE_TANH_TAU = 1.35
ZSCORE_WINSOR_LO, ZSCORE_WINSOR_HI = 0.01, 0.99
ZSCORE_MIN_STD = 1e-6

# Winsor / z-score calibration and all columns ending in _index use only players above this minutes threshold
# (strictly greater: 400.0 means someone with exactly 400 minutes is excluded).
INDEX_CALIBRATION_MIN_MINUTES = 200.0

# League power: λ_eff = 1 + (λ - 1) * strength. strength > 1 amplifica bónus/penalização da liga.
LEAGUE_POWER_STRENGTH_DEFAULT = 2
LEAGUE_POWER_STRENGTH_GROUND_DEFENSE = 3
LEAGUE_POWER_STRENGTH_AERIAL_PLAY = 2
LEAGUE_POWER_STRENGTH_DISTRIBUTION = 2

# ==============
# 2) UTILITIES
# ==============

def season_token_from_filename(filename_no_ext: str) -> str:
    """
    Examples:
      'Belgian Pro League 24-25' -> '24-25'
      'Allsvenskan 2025' -> '25-26'  (single-year -> YY-(YY+1))
      'Allsvenskan 2024' -> '24-25'
    """
    # Try to capture trailing "NN-NN"
    m = re.search(r'(\d{2})[-_](\d{2})$', filename_no_ext)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    # Try to capture trailing 4-digit year
    m = re.search(r'(20\d{2})$', filename_no_ext)
    if m:
        yy = int(m.group(1)) % 100
        return f"{yy:02d}-{(yy + 1) % 100:02d}"

    raise ValueError(f"Could not parse season token from '{filename_no_ext}'")

def league_from_filename(filename_no_ext: str, season_token: str) -> str:
    """
    Get league name from filename by removing trailing season token.
    E.g. 'Belgian Pro League 24-25' -> 'Belgian Pro League'
         'Allsvenskan 2025'        -> 'Allsvenskan'
    """
    league = filename_no_ext.strip()
    league = re.sub(rf'\s*{re.escape(season_token)}$', '', league).strip()
    # Also remove stray 4-digit year if present
    league = re.sub(r'(20\d{2})$', '', league).strip()
    return league

def start_year_from_season(season_token: str) -> int:
    # '24-25' -> 2024
    start_yy = int(season_token.split('-')[0])
    return 2000 + start_yy

def normalize_league_powers(all_leagues_in_files, base_map):
    """
    Return normalized factors in [LEAGUE_POWER_MIN, LEAGUE_POWER_MAX]
    for every league encountered in files. Unknown leagues get the median of known values.
    """
    known_vals = list(base_map.values())
    median_val = float(np.median(known_vals)) if known_vals else 80.0

    # Fill missing leagues with the median
    full_map = dict(base_map)
    for lg in sorted(set(all_leagues_in_files)):
        if lg not in full_map:
            full_map[lg] = median_val

    old_min, old_max = min(full_map.values()), max(full_map.values())
    if math.isclose(old_min, old_max):
        # Avoid div-by-zero: everyone gets the midpoint
        return {k: (LEAGUE_POWER_MIN + LEAGUE_POWER_MAX) / 2 for k in full_map}

    return {
        k: LEAGUE_POWER_MIN + (v - old_min) * (LEAGUE_POWER_MAX - LEAGUE_POWER_MIN) / (old_max - old_min)
        for k, v in full_map.items()
    }


def effective_league_factor(lf: float, strength: float = 1.0) -> float:
    """λ_eff = 1 + (λ - 1) * strength."""
    if lf is None or pd.isna(lf):
        return np.nan
    return float(1.0 + (float(lf) - 1.0) * float(strength))


def league_strength_for_pillar(pillar: str) -> float:
    if pillar == "ground_defense":
        return LEAGUE_POWER_STRENGTH_GROUND_DEFENSE
    if pillar == "aerial_play":
        return LEAGUE_POWER_STRENGTH_AERIAL_PLAY
    if pillar in ("distribution", "gk_distribution"):
        return LEAGUE_POWER_STRENGTH_DISTRIBUTION
    return LEAGUE_POWER_STRENGTH_DEFAULT


def league_strength_for_area(area: str) -> float:
    """Backward-compatible name; uses pillar strength rules."""
    return league_strength_for_pillar(area)


def index_calibration_minutes_eligible(df: pd.DataFrame) -> pd.Series:
    """True for rows used to calibrate index z-scores and that receive finite ``*_index`` values."""
    if "Minutes played" not in df.columns:
        return pd.Series(True, index=df.index, dtype=bool)
    mins = pd.to_numeric(df["Minutes played"], errors="coerce")
    return (mins > INDEX_CALIBRATION_MIN_MINUTES) & mins.notna()


def mask_index_columns_for_ineligible(df: pd.DataFrame, eligible: pd.Series) -> None:
    """Set every column whose name ends with ``_index`` to NaN where ``eligible`` is False (in-place)."""
    if bool(eligible.all()):
        return
    bad = ~eligible.reindex(df.index).fillna(False)
    for c in df.columns:
        if c.endswith("_index"):
            df.loc[bad, c] = np.nan


def attach_team_gk_conceded_per_90(df: pd.DataFrame) -> pd.DataFrame:
    """
    Por (época, liga, clube): soma dos golos sofridos pelos GR e minutos dos GR;
    taxa = total concedidos / (soma minutos / 90). Menos é melhor → peso negativo no ground_defense.
    """
    out = df.copy()
    need = {"club", "Conceded goals", "Minutes played", "Position"}
    if not need.issubset(out.columns):
        out["Team GK conceded per 90"] = np.nan
        return out
    gk_mask = out["Position"].astype(str).str.contains("GK", case=False, na=False)
    if not gk_mask.any():
        out["Team GK conceded per 90"] = np.nan
        return out
    gks = out.loc[gk_mask, ["season_year", "league", "club", "Conceded goals", "Minutes played"]].copy()
    gks["Conceded goals"] = pd.to_numeric(gks["Conceded goals"], errors="coerce").fillna(0.0)
    gks["Minutes played"] = pd.to_numeric(gks["Minutes played"], errors="coerce").fillna(0.0)
    agg = (
        gks.groupby(["season_year", "league", "club"], dropna=False)
        .agg(_gk_cg=("Conceded goals", "sum"), _gk_min=("Minutes played", "sum"))
        .reset_index()
    )
    agg["Team GK conceded per 90"] = np.where(
        agg["_gk_min"] > 0,
        agg["_gk_cg"] / (agg["_gk_min"] / 90.0),
        np.nan,
    )
    return out.merge(
        agg[["season_year", "league", "club", "Team GK conceded per 90"]],
        on=["season_year", "league", "club"],
        how="left",
    )


def add_npxg_columns(
    df: pd.DataFrame,
    *,
    penalty_xg: float = PENALTY_XG_PER_ATTEMPT,
) -> pd.DataFrame:
    """
    Non-penalty expected goals: total xG minus ``penalty_xg`` × penalties taken.

    Uses column ``xG`` when present; otherwise reconstructs totals from
    ``xG per 90`` × ``Minutes played`` / 90. Missing ``Penalties taken`` → 0.
    """
    out = df.copy()
    if "Minutes played" not in out.columns:
        return out
    mins = pd.to_numeric(out["Minutes played"], errors="coerce")
    if "Penalties taken" in out.columns:
        pens = pd.to_numeric(out["Penalties taken"], errors="coerce").fillna(0.0)
    else:
        pens = pd.Series(0.0, index=out.index, dtype=float)

    if "xG" in out.columns:
        xg_total = pd.to_numeric(out["xG"], errors="coerce")
    elif "xG per 90" in out.columns:
        xg_per_90 = pd.to_numeric(out["xG per 90"], errors="coerce")
        xg_total = xg_per_90 * mins / 90.0
    else:
        return out

    out["NPxG"] = xg_total - penalty_xg * pens
    out["NPxG per 90"] = np.where(mins > 0, out["NPxG"] * 90.0 / mins, np.nan)
    return out


def add_derived_metrics_for_indices(df: pd.DataFrame) -> pd.DataFrame:
    """Columns required by sub-segment weights (must run after NPxG if movement uses it)."""
    out = df.copy()
    od = pd.to_numeric(out.get("Offensive duels per 90", np.nan), errors="coerce")
    dr = pd.to_numeric(out.get("Dribbles per 90", np.nan), errors="coerce")
    out["Offensive duels minus dribbles per 90"] = od - dr

    if "xG per shot per 90" not in out.columns:
        if "xG per 90" in out.columns and "Shots per 90" in out.columns:
            nn = len(out)
            xg = pd.to_numeric(out["xG per 90"], errors="coerce").to_numpy(dtype=float, copy=False)
            sh = pd.to_numeric(out["Shots per 90"], errors="coerce").to_numpy(dtype=float, copy=False)
            out["xG per shot per 90"] = np.divide(
                xg,
                sh,
                out=np.full(nn, np.nan, dtype=float),
                where=np.isfinite(xg) & np.isfinite(sh) & (sh > 0.0),
            )
        else:
            out["xG per shot per 90"] = np.nan
    return out


def subsegment_output_column_name(pillar: str, sub_name: str) -> str:
    if pillar == "miscellaneous":
        return f"{sub_name}_index"
    if pillar == "aerial_play" and sub_name == "overall":
        return "aerial_play_index"
    if pillar == "gk_shot_stopping" and sub_name == "overall":
        return "shot_stopping_index"
    if pillar == "gk_distribution" and sub_name == "overall":
        return "gk_distribution_index"
    return f"{pillar}_{sub_name}_index"


def compute_subsegment_indices_zscore_tanh(
    df: pd.DataFrame,
    subsegment_metric_weights: dict[str, dict[str, dict[str, float]]],
    league_power_map: dict,
    *,
    tau: float = 2.5,
    winsor_lo: float = 0.01,
    winsor_hi: float = 0.99,
    min_std: float = 1e-6,
    fit_mask: np.ndarray | None = None,
) -> tuple[pd.DataFrame, dict[tuple[str, str], str]]:
    metrics: set[str] = set()
    for _pillar, subs in subsegment_metric_weights.items():
        for _sn, mw in subs.items():
            metrics.update(mw.keys())
    out = add_winsorized_z_columns(
        df,
        sorted(metrics),
        winsor_lo=winsor_lo,
        winsor_hi=winsor_hi,
        min_std=min_std,
        fit_mask=fit_mask,
    )
    lf = out["league"].map(league_power_map).to_numpy(dtype=float)
    n = len(out)
    sub_index_map: dict[tuple[str, str], str] = {}

    for pillar, subs in subsegment_metric_weights.items():
        st = league_strength_for_pillar(pillar)
        tau_p = GROUND_DEFENSE_TANH_TAU if pillar == "ground_defense" else tau
        for sub_name, mweights in subs.items():
            cols: list[str] = []
            wts: list[float] = []
            for col_name, w in mweights.items():
                zc = f"{col_name}_z"
                if zc in out.columns:
                    cols.append(zc)
                    wts.append(float(w))
            out_col = subsegment_output_column_name(pillar, sub_name)
            sub_index_map[(pillar, sub_name)] = out_col
            if not cols:
                out[out_col] = np.nan
                continue
            wrow = np.array(wts, dtype=float)
            zm = out[cols].to_numpy(dtype=float)
            finite = np.isfinite(zm)
            wb = np.broadcast_to(wrow, zm.shape)
            num = np.sum(np.where(finite, zm * wb, 0.0), axis=1)
            den = np.sum(np.where(finite, np.abs(wb), 0.0), axis=1)
            s = np.divide(num, den, out=np.full(n, np.nan, dtype=float), where=den > 0)
            lf_area = 1.0 + (lf - 1.0) * st
            s_prime = s * lf_area
            out[out_col] = 50.0 + 50.0 * np.tanh(s_prime / tau_p)

    return out, sub_index_map


def rollup_game_area_indices(
    df: pd.DataFrame,
    sub_index_map: dict[tuple[str, str], str],
    rollup_alphas: dict[str, dict[str, float]],
) -> pd.DataFrame:
    out = df
    n = len(out)
    for pillar, alphas in rollup_alphas.items():
        if pillar == "aerial_play":
            continue
        weighted = np.zeros(n, dtype=float)
        denom = np.zeros(n, dtype=float)
        for sub_name, a in alphas.items():
            col = sub_index_map.get((pillar, sub_name))
            if not col or col not in out.columns:
                continue
            v = pd.to_numeric(out[col], errors="coerce").to_numpy(dtype=float)
            m = np.isfinite(v)
            weighted[m] += a * v[m]
            denom[m] += a
        out[f"{pillar}_index"] = np.divide(
            weighted,
            denom,
            out=np.full(n, np.nan, dtype=float),
            where=denom > 0,
        )
    return out


def merge_submetrics_for_percentile_area(pillar: str) -> dict[str, float]:
    merged: dict[str, float] = {}
    subs = SUBSEGMENT_METRIC_WEIGHTS.get(pillar, {})
    alphas = SUBSEGMENT_ROLLUP_ALPHA.get(pillar, {})
    for sub_name, mweights in subs.items():
        a = alphas.get(sub_name, 0.0)
        for m, w in mweights.items():
            merged[m] = merged.get(m, 0.0) + a * float(w)
    return merged


def to_percentile(series: pd.Series) -> pd.Series:
    """
    Convert numeric series to percentiles [0..100]. NaNs preserved.
    """
    s = pd.to_numeric(series, errors="coerce")
    return s.rank(pct=True, method="average") * 100

def ensure_percentile_columns(df: pd.DataFrame, cols: list[str], suffix="_percentile") -> pd.DataFrame:
    """
    For each raw column in `cols`, compute a percentile column with suffix.
    If the column already looks like a percentile (0..100), you can set compute_percentiles=False.
    """
    out = df.copy()
    for c in cols:
        pct_col = f"{c}{suffix}"
        if compute_percentiles:
            out[pct_col] = to_percentile(out[c])
        else:
            # If already a percentile column exists, just ensure name
            if c in out.columns and pct_col not in out.columns:
                out[pct_col] = out[c]
    return out

def weighted_area_index(row: pd.Series, area: str, area_weights: dict, league_factor: float, suffix="_percentile") -> float:
    """
    area_weights: { raw_col_name: weight, ... }  (weights will be normalized)
    Uses the *_percentile columns.
    """
    cols = list(area_weights.keys())
    vals = []
    wts = []
    for col in cols:
        pct_col = f"{col}{suffix}"
        v = row.get(pct_col, np.nan)
        if pd.isna(v):
            # If any metric is NaN, we skip it AND its weight (partial average).
            # If you prefer strict NaN, flip to: return np.nan
            continue
        vals.append(float(v))
        wts.append(float(area_weights[col]))

    if not vals:
        return np.nan

    den = sum(abs(w) for w in wts)
    if den <= 0:
        return np.nan
    wts = [w / den for w in wts]
    area_score = sum(v * w for v, w in zip(vals, wts))  # still in 0..100
    lf_eff = effective_league_factor(league_factor, league_strength_for_area(area))
    return min(area_score * lf_eff, 100.0)


def add_winsorized_z_columns(
    df: pd.DataFrame,
    metric_cols: list[str],
    *,
    winsor_lo: float = 0.01,
    winsor_hi: float = 0.99,
    min_std: float = 1e-6,
    suffix: str = "_z",
    fit_mask: np.ndarray | None = None,
) -> pd.DataFrame:
    """Winsoriza cada métrica e adiciona m_z. Se ``fit_mask`` (bool, len=len(df)) for dado,
    quantis/μ/σ vêm só das linhas True; z-scores calculam-se para todas as linhas."""
    out = df.copy()
    n = len(out)
    cal = fit_mask if fit_mask is not None else np.ones(n, dtype=bool)
    cal = np.asarray(cal, dtype=bool)
    for m in metric_cols:
        if m not in out.columns:
            continue
        s = pd.to_numeric(out[m], errors="coerce")
        v = s.to_numpy(dtype=float, copy=False)
        finite = np.isfinite(v)
        use = cal & finite
        cal_vals = v[use]
        if cal_vals.size == 0:
            cal_vals = v[finite]
        if cal_vals.size == 0:
            out[f"{m}{suffix}"] = np.nan
            continue
        lo_f, hi_f = np.nanquantile(cal_vals, [winsor_lo, winsor_hi])
        if not np.isfinite(lo_f) or not np.isfinite(hi_f) or lo_f >= hi_f:
            x = s
        else:
            x = s.clip(lo_f, hi_f)
        xb = x.to_numpy(dtype=float, copy=False)
        mu_t = np.nanmean(xb[cal & np.isfinite(xb)])
        if not np.isfinite(mu_t):
            mu_t = float(np.nanmean(xb))
        sig_t = float(np.nanstd(xb[cal & np.isfinite(xb)], ddof=0))
        if not np.isfinite(sig_t) or sig_t < min_std:
            sig_t = min_std
        out[f"{m}{suffix}"] = (x - mu_t) / sig_t
    return out


def game_area_indices_zscore_tanh(
    df: pd.DataFrame,
    game_areas: list[str],
    weights: dict,
    league_power_map: dict,
    *,
    tau: float = 2.5,
    winsor_lo: float = 0.01,
    winsor_hi: float = 0.99,
    min_std: float = 1e-6,
    fit_mask: np.ndarray | None = None,
) -> pd.DataFrame:
    """
    Fórmula por área A e jogador i (época = amostra completa concatenada):

      z_{i,m} = (x_{i,m} - μ_m) / σ_m   com x winsorizado globalmente em [p_lo, p_hi]

      S_{i,A} = (Σ_m w_{m} · z_{i,m}) / (Σ_m |w_{m}|)   só métricas finitas; pesos |·| como em GK com w negativo

      λ_eff = 1 + (λ_{liga(i)} - 1) · strength_A   (strength > 1 p/ ground_defense, aerial_play, distribution)

      S'_{i,A} = λ_eff · S_{i,A}

      Index_{i,A} = 50 + 50 · tanh(S'_{i,A} / τ)   contínuo em (0, 100), sem cap duro em 100
    """
    metrics = set()
    for area in game_areas:
        metrics.update(weights.get(area, {}).keys())
    out = add_winsorized_z_columns(
        df,
        sorted(metrics),
        winsor_lo=winsor_lo,
        winsor_hi=winsor_hi,
        min_std=min_std,
        fit_mask=fit_mask,
    )
    lf = out["league"].map(league_power_map).to_numpy(dtype=float)
    n = len(out)

    for area in game_areas:
        area_w = weights.get(area, {})
        if not area_w:
            out[f"{area}_index"] = np.nan
            continue
        cols, wts = [], []
        for col_name, w in area_w.items():
            zc = f"{col_name}_z"
            if zc in out.columns:
                cols.append(zc)
                wts.append(float(w))
        if not cols:
            out[f"{area}_index"] = np.nan
            continue

        wrow = np.array(wts, dtype=float)
        zm = out[cols].to_numpy(dtype=float)
        finite = np.isfinite(zm)
        wb = np.broadcast_to(wrow, zm.shape)
        num = np.sum(np.where(finite, zm * wb, 0.0), axis=1)
        den = np.sum(np.where(finite, np.abs(wb), 0.0), axis=1)
        s = np.divide(num, den, out=np.full(n, np.nan, dtype=float), where=den > 0)
        st = league_strength_for_area(area)
        lf_area = 1.0 + (lf - 1.0) * st
        s_prime = s * lf_area
        out[f"{area}_index"] = 50.0 + 50.0 * np.tanh(s_prime / tau)

    return out


def compute_zscore_index(
    df,
    metric_weights,
    new_col_name,
    *,
    fit_mask: pd.Series | None = None,
):
    n = len(df)
    weighted_sum = np.zeros(n, dtype=float)
    tw = float(sum(abs(w) for w in metric_weights.values()))
    if tw <= 0.0:
        df[new_col_name] = np.nan
        return df

    cal = None
    if fit_mask is not None:
        cal = fit_mask.reindex(df.index).fillna(False).to_numpy(dtype=bool)

    for metric, weight in metric_weights.items():
        if metric not in df.columns:
            print(f"⚠️ Missing metric in data: {metric}")
            continue
        vals = pd.to_numeric(df[metric], errors="coerce").to_numpy(dtype=float, copy=False)
        finite = np.isfinite(vals)
        if cal is not None:
            cal_vals = vals[cal & finite]
            if cal_vals.size == 0:
                cal_vals = vals[finite]
        else:
            cal_vals = vals[finite]
        mean = float(np.nanmean(cal_vals)) if cal_vals.size else float("nan")
        std = float(np.nanstd(cal_vals, ddof=0)) if cal_vals.size else float("nan")
        w = float(weight)
        if not np.isfinite(std) or std < 1e-15:
            z = np.zeros(n, dtype=float)
        else:
            z = np.divide(
                vals - mean,
                std,
                out=np.zeros(n, dtype=float),
                where=finite,
            )
        weighted_sum += z * w

    df[new_col_name] = weighted_sum / tw
    if cal is not None:
        df.loc[~fit_mask.reindex(df.index).fillna(False), new_col_name] = np.nan
    return df


def main() -> None:
    # ===========================
    # 3 BUILD SEASONAL DATASETS
    # ===========================

    import sys
    from pathlib import Path

    _sf = Path(__file__).resolve()
    for _repo in _sf.parents:
        if (_repo / "utils" / "repo_root.py").is_file():
            sr = str(_repo)
            if sr not in sys.path:
                sys.path.insert(0, sr)
            break
    else:
        raise RuntimeError("Cannot resolve monorepo root (missing utils/repo_root.py).")

    from utils.repo_root import repo_root

    _REPO_ROOT = os.fspath(repo_root(_sf))
    INPUT_DIR = os.path.join(_REPO_ROOT, "data", "players", "wyscout")
    OUTPUT_DIR = os.path.join(_REPO_ROOT, "data", "players", "all")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Collect all files
    files = sorted(glob.glob(os.path.join(INPUT_DIR, "*.csv")))

    # Group files by season token
    season_groups = {}  # token -> list[(league, path)]
    all_leagues_seen = set()

    for path in files:
        fname = os.path.basename(path)
        name_no_ext = os.path.splitext(fname)[0]

        try:
            season_token = season_token_from_filename(name_no_ext)
        except ValueError:
            # Skip files that don't follow the pattern
            continue

        league = league_from_filename(name_no_ext, season_token)
    
        # Only process leagues that are in ALLOWED_LEAGUES
        if league not in ALLOWED_LEAGUES:
            print(f"⚠️ Skipping {league} (not in ALLOWED_LEAGUES)")
            continue
    
        all_leagues_seen.add(league)
        season_groups.setdefault(season_token, []).append((league, path))

    # Normalize league powers for *all* leagues found
    normalized_league_power = normalize_league_powers(all_leagues_seen, league_power_base)

    # ===========================
    # 4 PROCESS EACH SEASON
    # ===========================

    for season_token, items in sorted(season_groups.items()):
        # Read and concat all leagues for this season
        season_frames = []
        for league, path in items:
            df_league = pd.read_csv(path)

            # Make sure we carry a standard "league" and "season"
            df_league["league"] = league
            df_league["season_token"] = season_token
            df_league["season_year"] = start_year_from_season(season_token)  # e.g. 2024 for 24-25

            # Wyscout has both "Team" and "Team within selected timeframe". Keep "Team" as club.
            if "Team within selected timeframe" in df_league.columns and "club" not in df_league.columns:
                df_league.rename(columns={"Team within selected timeframe": "club"}, inplace=True)

            season_frames.append(df_league)

        season_df = pd.concat(season_frames, ignore_index=True)
        season_df = attach_team_gk_conceded_per_90(season_df)
        season_df = add_npxg_columns(season_df)
        season_df = add_derived_metrics_for_indices(season_df)

        all_metric_cols = sorted(
            {m for _p, subs in SUBSEGMENT_METRIC_WEIGHTS.items() for _s, mw in subs.items() for m in mw}
        )

        _min_elig = index_calibration_minutes_eligible(season_df)

        if AREA_INDEX_METHOD == "percentile_cap":
            season_df = ensure_percentile_columns(season_df, all_metric_cols, suffix="_percentile")
            pct_weight_map: dict[str, dict[str, float]] = {}
            for p in ("finishing", "assistance", "take_ons", "distribution", "ground_defense", "aerial_play"):
                pct_weight_map[p] = merge_submetrics_for_percentile_area(p)
            for misc_sub, mw in SUBSEGMENT_METRIC_WEIGHTS["miscellaneous"].items():
                pct_weight_map[misc_sub] = dict(mw)
            pct_weight_map["gk_shot_stopping"] = dict(
                SUBSEGMENT_METRIC_WEIGHTS["gk_shot_stopping"]["overall"]
            )
            pct_weight_map["gk_distribution"] = dict(
                SUBSEGMENT_METRIC_WEIGHTS["gk_distribution"]["overall"]
            )
            pct_output_col = {
                "gk_shot_stopping": "shot_stopping_index",
                "gk_distribution": "gk_distribution_index",
            }

            for area, area_w in pct_weight_map.items():
                if not area_w:
                    continue

                def _row_area(r, _area=area, _w=area_w):
                    lg = r.get("league", None)
                    lf = normalized_league_power.get(lg, np.nan)
                    if pd.isna(lf):
                        return np.nan
                    return weighted_area_index(
                        r, _area, _w, league_factor=lf, suffix="_percentile"
                    )

                out_col = pct_output_col.get(area, f"{area}_index")
                season_df[out_col] = season_df.apply(_row_area, axis=1)
            mask_index_columns_for_ineligible(season_df, _min_elig)
        elif AREA_INDEX_METHOD == "zscore_tanh":
            season_df, _submap = compute_subsegment_indices_zscore_tanh(
                season_df,
                SUBSEGMENT_METRIC_WEIGHTS,
                normalized_league_power,
                tau=AREA_INDEX_TANH_TAU,
                winsor_lo=ZSCORE_WINSOR_LO,
                winsor_hi=ZSCORE_WINSOR_HI,
                min_std=ZSCORE_MIN_STD,
                fit_mask=_min_elig.to_numpy(),
            )
            mask_index_columns_for_ineligible(season_df, _min_elig)
            season_df = rollup_game_area_indices(
                season_df, _submap, SUBSEGMENT_ROLLUP_ALPHA
            )
        else:
            raise ValueError(f"Unknown AREA_INDEX_METHOD: {AREA_INDEX_METHOD!r}")

        # De-fragment after many index columns (sub-segments + rollups).
        season_df = season_df.copy()

        # Advanced metrics
        season_df['Expected Offensive Output per 90'] =  season_df['xA per 90'] + season_df['xG per 90']
        season_df['Offensive Output per 90'] =  season_df['Assists per 90'] + season_df['Goals per 90']
        season_df['Ball Progression per 90'] =  season_df['Progressive runs per 90'] + season_df['Progressive passes per 90']
        season_df['Ball Winning Actions per 90'] =  season_df['Interceptions per 90'] + season_df['Sliding tackles per 90']+ season_df['Successful defensive actions per 90']
        _n = len(season_df)
        _tib = pd.to_numeric(season_df["Touches in box per 90"], errors="coerce").to_numpy(
            dtype=float, copy=False
        )
        _sh = pd.to_numeric(season_df["Shots per 90"], errors="coerce").to_numpy(dtype=float, copy=False)
        season_df["Touches in box per shot per 90"] = np.divide(
            _tib,
            _sh,
            out=np.full(_n, np.nan, dtype=float),
            where=np.isfinite(_tib) & np.isfinite(_sh) & (_sh > 0.0),
        )
        if "xG per shot per 90" not in season_df.columns:
            _xg = pd.to_numeric(season_df["xG per 90"], errors="coerce").to_numpy(dtype=float, copy=False)
            season_df["xG per shot per 90"] = np.divide(
                _xg,
                _sh,
                out=np.full(_n, np.nan, dtype=float),
                where=np.isfinite(_xg) & np.isfinite(_sh) & (_sh > 0.0),
            )
    
        # % Team Impact versions of selected metrics (per season_year/league/club)
        team_impact_metrics = [
            'Goals per 90','xG per 90','Shots per 90','Shots on target, %',
            'Assists per 90','Second assists per 90','Smart passes per 90','xA per 90',
            'Passes to penalty area per 90','Through passes per 90',
            'Dribbles per 90','Successful dribbles, %','Offensive duels per 90',
            'Progressive runs per 90','Accelerations per 90',
            'Passes per 90','Accurate passes, %','Vertical passes per 90','Progressive passes per 90',
            'Successful defensive actions per 90','Defensive duels per 90','Defensive duels won, %',
            'PAdj Interceptions','Shots blocked per 90','PAdj Sliding tackles',
            'Aerial duels per 90','Aerial duels won, %',
            'Expected Offensive Output per 90','Offensive Output per 90',
            'Ball Progression per 90','Ball Winning Actions per 90',
            'Touches in box per shot per 90','xG per shot per 90',
            'NPxG per 90',
        ]

        group_cols = ['season_year', 'league', 'club']
        impact_blocks: dict[str, np.ndarray] = {}
        for col in team_impact_metrics:
            if col not in season_df.columns:
                continue
            team_total = season_df.groupby(group_cols)[col].transform('sum')
            tt = team_total.to_numpy(dtype=float, copy=False)
            vals = pd.to_numeric(season_df[col], errors="coerce").to_numpy(dtype=float, copy=False)
            safe_den = np.isfinite(tt) & (tt != 0.0)
            impact_blocks[f"{col} - % Team Impact"] = np.divide(
                vals * 100.0,
                tt,
                out=np.full(len(season_df), np.nan, dtype=float),
                where=safe_den,
            )
        if impact_blocks:
            season_df = pd.concat(
                [season_df, pd.DataFrame(impact_blocks, index=season_df.index)],
                axis=1,
            )

        season_df = compute_zscore_index(
            season_df, weights["link_up_play"], "LinkUp Play Quality", fit_mask=_min_elig
        )
        season_df = compute_zscore_index(
            season_df, weights["finishing_quality"], "Finishing Quality", fit_mask=_min_elig
        )
        season_df = compute_zscore_index(
            season_df, weights["dribling_quality"], "Dribling Quality", fit_mask=_min_elig
        )
        season_df = compute_zscore_index(
            season_df, weights["distribution_quality"], "Distribution Quality", fit_mask=_min_elig
        )
        season_df = compute_zscore_index(
            season_df, weights["aerial_play_quality"], "Aerial Play Quality", fit_mask=_min_elig
        )
        season_df = compute_zscore_index(
            season_df, weights["ground_defense_quality"], "Ground Defense Quality", fit_mask=_min_elig
        )
        season_df = compute_zscore_index(
            season_df, weights["creativity_quality"], "Creativity Quality", fit_mask=_min_elig
        )

        # GK-specific z-score indexes (computed only among GKs)
        gk_mask = season_df['Primary position'] == 'GK'
        season_df["GK Shot Saving Quality"] = np.nan
        season_df["GK Ball Playing Quality"] = np.nan
        if gk_mask.any():
            gk_df = season_df.loc[gk_mask].copy()
            gk_elig = _min_elig.reindex(gk_df.index).fillna(False)
            gk_df = compute_zscore_index(
                gk_df, weights["gk_shot_saving"], "GK Shot Saving Quality", fit_mask=gk_elig
            )
            gk_df = compute_zscore_index(
                gk_df, weights["gk_ball_playing"], "GK Ball Playing Quality", fit_mask=gk_elig
            )
            season_df.loc[gk_mask, "GK Shot Saving Quality"] = gk_df["GK Shot Saving Quality"]
            season_df.loc[gk_mask, "GK Ball Playing Quality"] = gk_df["GK Ball Playing Quality"]

        # Precomputed max performance (eligible position types); same formula as Rankings.
        import importlib
        import sys

        if str(_REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(_REPO_ROOT))
        import utils.transforms as _transforms_perf

        importlib.reload(_transforms_perf)
        season_df["performance_index"] = _transforms_perf.performance_index_max_series(season_df)
        season_df.loc[~_min_elig.reindex(season_df.index).fillna(False), "performance_index"] = np.nan
        season_df = season_df.copy()

        # Save per-season file named with the *start year* (e.g., 2024 for 24-25)
        start_year = start_year_from_season(season_token)
        out_path = os.path.join(
            OUTPUT_DIR,
            f"{start_year}_all_leagues.csv",
        )
        season_df.to_csv(out_path, index=False)
        print(f"Saved: {out_path}")



if __name__ == "__main__":
    main()
