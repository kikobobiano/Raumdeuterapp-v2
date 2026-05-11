"""Data transformation and computation helpers."""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Union

import numpy as np
import pandas as pd

from .config import (
    AREA_INDEX_COLS,
    BASE_TOKEN_RE,
    LEAGUE_POWER_BASE,
    LEAGUE_POWER_MAX_ADJUSTED,
    LEAGUE_POWER_MIN_ADJUSTED,
    ROLE_PRIORITY,
    TOKEN_TO_ROLES,
)


# ---------------------------------------------------------------------------
# League power adjustment
# ---------------------------------------------------------------------------

def get_league_base_power(league_name: Union[str, float, None]) -> Optional[float]:
    """Raw strength score from ``LEAGUE_POWER_BASE`` (higher = stronger league).

    Returns ``None`` if the league is missing or not listed (unknown tier).
    """
    if league_name is None or (isinstance(league_name, float) and np.isnan(league_name)):
        return None
    key = str(league_name).strip()
    if not key:
        return None
    return LEAGUE_POWER_BASE.get(key)


def default_target_leagues_by_power(
    *,
    source_league: str,
    leagues_in_target_season: List[str],
    max_leagues: int = 6,
) -> List[str]:
    """Pick default target leagues for performance translation (ordered list, cap *max_leagues*).

    Puts the player's league first when it appears in the pool, then up to five others with
    **strictly higher** ``LEAGUE_POWER_BASE`` scores (**weakest-to-strongest** among that group;
    ties broken by name).     If there are not enough leagues above, continues with **strictly lower** power, ordered
    **strongest-to-weakest** (still closest tiers to the player’s league first). Leagues in the pool
    without a power entry are only used
    after the ranked ones, then any remaining names, so the result can still reach *max_leagues*.
    """
    cap = max(1, int(max_leagues))
    pool = {str(lg).strip() for lg in leagues_in_target_season if str(lg).strip()}
    if not pool:
        return []

    pairs: List[tuple[str, float]] = [
        (lg, float(get_league_base_power(lg)))
        for lg in pool
        if get_league_base_power(lg) is not None
    ]
    pw = get_league_base_power(str(source_league or "").strip())
    if pw is None:
        return sorted(pool)[:cap]

    pvf = float(pw)
    above = [
        lg
        for lg, p in sorted(
            (x for x in pairs if x[1] > pvf),
            key=lambda x: (x[1], x[0]),
        )
    ]
    below = [
        lg
        for lg, p in sorted(
            (x for x in pairs if x[1] < pvf),
            key=lambda x: (-x[1], x[0]),
        )
    ]

    out: List[str] = []
    seen: set[str] = set()
    src = str(source_league or "").strip()
    if src and src in pool:
        out.append(src)
        seen.add(src)

    def extend_from(candidates: List[str]) -> None:
        for lg in candidates:
            if len(out) >= cap:
                return
            if lg not in seen:
                out.append(lg)
                seen.add(lg)

    extend_from(above)
    extend_from(below)
    if len(out) < cap:
        unmapped = sorted(lg for lg in pool if get_league_base_power(lg) is None)
        extend_from(unmapped)
    if len(out) < cap:
        extend_from(sorted(pool))

    return out[:cap]


def get_league_power_multiplier(league_name: str) -> float:
    """Multiplicative factor for a league (higher power -> closer to max)."""
    if league_name not in LEAGUE_POWER_BASE:
        return 1.0

    league_power = LEAGUE_POWER_BASE[league_name]
    min_power = min(LEAGUE_POWER_BASE.values())
    max_power = max(LEAGUE_POWER_BASE.values())

    if max_power == min_power:
        return 1.0

    normalized = (league_power - min_power) / (max_power - min_power)
    return LEAGUE_POWER_MIN_ADJUSTED + normalized * (LEAGUE_POWER_MAX_ADJUSTED - LEAGUE_POWER_MIN_ADJUSTED)


def apply_league_power_adjustment(df: pd.DataFrame, metric_cols: List[str]) -> pd.DataFrame:
    """Multiply selected metrics by the league power multiplier."""
    work = df.copy()
    if "league" not in work.columns:
        return work

    work["_league_multiplier_"] = work["league"].apply(get_league_power_multiplier)
    for metric in metric_cols:
        if metric in work.columns:
            work[metric] = work[metric] * work["_league_multiplier_"]
    return work.drop(columns=["_league_multiplier_"])


# ---------------------------------------------------------------------------
# Position / role mapping
# ---------------------------------------------------------------------------

def _first_base_token(token_str: str) -> Optional[str]:
    m = BASE_TOKEN_RE.search(token_str)
    return m.group(1) if m else None


def map_position_to_role(position_value: str) -> Optional[str]:
    """Map a Position string to one of the roles."""
    if not isinstance(position_value, str) or not position_value.strip():
        return None

    tokens = [p.strip() for p in position_value.split(",") if p.strip()]
    if not tokens:
        return None

    base = _first_base_token(tokens[0])
    if base and base in TOKEN_TO_ROLES:
        roles = TOKEN_TO_ROLES[base]
        for r in ROLE_PRIORITY:
            if r in roles:
                return r

    for tk in tokens[1:]:
        base = _first_base_token(tk)
        if base and base in TOKEN_TO_ROLES:
            roles = TOKEN_TO_ROLES[base]
            for r in ROLE_PRIORITY:
                if r in roles:
                    return r
    return None


def row_position_string(row: pd.Series) -> str:
    """Use detailed ``Position`` when present; otherwise ``Primary position`` (Wyscout)."""
    raw = row.get("Position", "")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    pp = row.get("Primary position", "")
    if pp is None or (isinstance(pp, float) and np.isnan(pp)):
        return ""
    s = str(pp).strip()
    return s


def classify_position_type(row: pd.Series) -> Optional[str]:
    """Classify a player into specific position types based on Position column."""
    position = row_position_string(row)
    if not position:
        return None

    if "GK" in position.upper():
        return "Goalkeeper"

    role = map_position_to_role(position)
    if role is None:
        return None

    position_upper = position.upper()
    tokens = [p.strip() for p in position.split(",") if p.strip()]

    if role == "Forward":
        return "Poacher"

    if role == "Winger":
        if any(t in position_upper for t in ["LWF", "RWF", "WF"]):
            return "Inside Forward"
        return "Traditional Winger"

    if role == "Attacking Midfielder":
        return "Attacking Midfielder"

    if role == "Midfielder":
        is_dmf = any("DMF" in t.upper() for t in tokens)
        if is_dmf:
            return "Defensive Midfielder"
        return "Playmaker"

    if role == "Fullback":
        if any(t in position_upper for t in ["LWB", "RWB", "WB"]):
            return "Attacking Fullback"
        return "Complete Fullback"

    if role == "Defender":
        base = _first_base_token(position.split(",")[0] if position else "")
        if base not in ["CB", "LCB", "RCB"]:
            return None
        return "Ball Playing Center Back"

    return None


# ---------------------------------------------------------------------------
# Performance index (hybrid: whole game areas + sub-segment columns)
# ---------------------------------------------------------------------------

def _nanmax_rows_ignore_all_nan(a: np.ndarray) -> np.ndarray:
    """Per-row max ignoring NaN; all-NaN rows -> NaN (avoids ``np.nanmax`` / empty-slice warnings)."""
    a = np.asarray(a, dtype=float)
    n = a.shape[0]
    out = np.empty(n, dtype=float)
    for i in range(n):
        row = a[i]
        best = -np.inf
        seen = False
        for j in range(row.shape[0]):
            v = row[j]
            if np.isfinite(v):
                seen = True
                if v > best:
                    best = v
        out[i] = float(best) if seen else np.nan
    return out


PERFORMANCE_WEIGHTS_HYBRID: Dict[str, Dict[str, float]] = {
    "Goalkeeper": {"shot_stopping": 0.95, "gk_distribution": 0.05},
    "Ball Playing Goalkeeper": {"shot_stopping": 0.65, "gk_distribution": 0.35},
    "Complete Forward": { #feito
        "finishing": 0.35,
        "assistance": 0.25,
        "take_ons": 0.2,
        "distribution": 0.10,
        "ground_defense": 0.05,
        "aerial_play": 0.05
    },
    "Poacher": { #feito
        "finishing": 0.74,
        "assistance": 0.16,
        "take_ons": 0.08,
        "aerial_play": 0.02,
    },
    "Target Man": { #feito
        "finishing": 0.4,
        "assistance": 0.10,
        "take_ons": 0.05,
        "distribution": 0.05,
        "aerial_play": 0.4
    },
    "Deep Lying Forward": {
        "finishing": 0.3,
        "assistance": 0.25,
        "take_ons": 0.15,
        "link_up": 0.3,
    },
    "Winger": { #feito
        "crossing": 0.15,
        "assistance": 0.35,
        "take_ons": 0.35,
        "finishing": 0.1,
        "distribution": 0.05
    },
    "Inside Forward": { #feito
        "assistance": 0.15,
        "take_ons": 0.4,
        "finishing": 0.4,
        "distribution": 0.05,
    },
    "Box-to-Box Midfielder": { #feito
        "progressive_carry": 0.5,
        "finishing": 0.1,
        "ground_defense": 0.2,
        "assistance": 0.1,
        "safety": 0.1,
    },
    "Defensive Midfielder": { #feito
        "duels": 0.35,
        "positioning": 0.15,
        "tackling": 0.05,
        "team_context": 0.15,
        # "ground_defense": 0.7,
        "distribution": 0.1,
        "aerial_play": 0.15,
        "aggression": 0.05,
    },
    "Attacking Midfielder": { #feito
        "finishing": 0.25,
        "assistance": 0.45,
        "take_ons": 0.15,
        "distribution": 0.15,
    },
    "Playmaker": { #feito 
        "assistance": 0.12,
        "take_ons": 0.03,
        "distribution": 0.85
    },
    "Complete Fullback": { 
        "crossing": 0.10,
        "crossing_variation": 0.1,
        "distribution": 0.05,
        "ground_defense": 0.2,
        "assistance": 0.3,
        "take_ons": 0.10,
        "finishing": 0.15,
    },
    "Attacking Fullback": { 
        "crossing": 0.1,
        "crossing_variation": 0.1,
        "ground_defense": 0.1,
        "assistance": 0.25,
        "take_ons": 0.25,
        "finishing": 0.2,
    },
    "Defensive Fullback": { 
        "crossing": 0.1,
        "ground_defense": 0.5,
        "assistance": 0.1,
        "take_ons": 0.1,
        "distribution": 0.1,
        "aerial_play": 0.1,
    },
    "Ball Playing Center Back": { #feito 
        "ground_defense": 0.43,
        "aerial_play": 0.05,
        "distribution": 0.52,
    },
    "Stopper Center Back": { 
        "distribution": 0.2,
        "aerial_play": 0.4,
        "ground_defense": 0.4
    },
}

_PERFORMANCE_WEIGHTS = PERFORMANCE_WEIGHTS_HYBRID

# Shorthand keys in ``PERFORMANCE_WEIGHTS_HYBRID`` → column stem before ``_index`` (matches
# ``subsegment_output_column_name`` in ``transformation/new_performance_index.py``). Keys
# omitted here use themselves as stem (e.g. ``finishing`` → ``finishing_index`` roll-up).
# You may also use full stems directly in the hybrid dict (e.g. ``take_ons_progressive_carry``).
PERFORMANCE_WEIGHT_KEY_TO_INDEX_STEM: Dict[str, str] = {
    "progressive_carry": "take_ons_progressive_carry",
    "link_up": "assistance_link_up",
    "crossing": "crossing",
    "crossing_variation": "crossing_variation",
    "duels": "ground_defense_duels",
    "positioning": "ground_defense_positioning",
    "tackling": "ground_defense_tackling",
    "team_context": "ground_defense_team_context",
    "safety": "distribution_safety",
    "aggression": "aggression",
    # Optional explicit finishing / assistance / distribution subs (use if you split roll-ups):
    "shot_volume": "finishing_shot_volume",
    "shot_quality": "finishing_shot_quality",
    "conversion": "finishing_conversion",
    "movement": "finishing_movement",
    "open_play_chance": "assistance_open_play_chance",
    "penetration": "assistance_penetration",
    "involvement": "distribution_involvement",
    "progression": "distribution_progression",
    "variation": "distribution_variation",
    "creation": "distribution_creation",
    "dribble_carry": "take_ons_dribble_carry",
    "duel_wing_play": "take_ons_duel_wing_play",
}

# Generalists: blend role-weighted index with unweighted mean of sub-indices so "good everywhere,
# elite nowhere" profiles are not capped ~mid vs specialists. α closer to 1.0 = nearer legacy behaviour.
GENERALIST_PERFORMANCE_ARCHETYPES: frozenset[str] = frozenset(
    {
        "Box-to-Box Midfielder",
        "Complete Fullback",
        "Attacking Fullback",
        "Defensive Fullback",
    }
)
# Weight on legacy role-weighted index vs cohort-relative term (1−α on rel_simple).
GENERALIST_BLEND_WEIGHTED = 0.48
# Extra points (0..MAX) when sub-indices are level (low CV). Tuned vs GENERALIST_BALANCE_CV_REF.
GENERALIST_BALANCE_BOOST_MAX = 13.0
# std/mean above this → no balance bonus (typical generalist B2B is ~0.06–0.15).
GENERALIST_BALANCE_CV_REF = 0.2


def _generalist_cohort_role_for_archetype(position_type: str) -> Optional[str]:
    """Wyscout role used to subset rows when building cohort stats for the generalist blend."""
    if position_type == "Box-to-Box Midfielder":
        return "Midfielder"
    if position_type in (
        "Complete Fullback",
        "Attacking Fullback",
        "Defensive Fullback",
    ):
        return "Fullback"
    return None


def _rowwise_cv_balance_weight(values: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Per-row weight in [0, 1]: 1 ≈ same level on all pillars (low coefficient of variation)."""
    n = int(values.shape[0])
    n_valid = valid.sum(axis=1).astype(np.float64)
    sum_v = np.where(valid, values, 0.0).sum(axis=1)
    pillar_mean = np.divide(
        sum_v,
        n_valid,
        out=np.full(n, np.nan, dtype=float),
        where=n_valid > 0,
    )
    sumsq = np.where(valid, values * values, 0.0).sum(axis=1)
    ex2 = np.divide(
        sumsq,
        n_valid,
        out=np.full(n, np.nan, dtype=float),
        where=n_valid > 0,
    )
    # Population std over valid pillars; skip rows with <2 points (avoids numpy dof warnings).
    var = ex2 - pillar_mean**2
    var = np.where(n_valid >= 2, np.maximum(var, 0.0), np.nan)
    pillar_std = np.sqrt(var)
    with np.errstate(invalid="ignore", divide="ignore"):
        cv = pillar_std / np.maximum(pillar_mean, 1e-6)
    ok = (n_valid >= 2) & np.isfinite(cv) & np.isfinite(pillar_mean) & (pillar_mean > 1e-6)
    bw = np.clip(1.0 - cv / GENERALIST_BALANCE_CV_REF, 0.0, 1.0)
    return np.where(ok, bw, 0.0)


def _performance_index_column_name(weight_key: str) -> str:
    """Resolve hybrid weight key to a dataframe column ending in ``_index``."""
    stem = PERFORMANCE_WEIGHT_KEY_TO_INDEX_STEM.get(weight_key, weight_key)
    return f"{stem}_index"


def eligible_performance_position_types(row: pd.Series) -> List[str]:
    """Archetypes over which :func:`performance_index_max_series` takes the row-wise maximum.

    Same role resolution as :func:`classify_position_type` (via :func:`row_position_string`).
    This can exceed the single classified type (e.g. any forward archetype for strikers).
    """
    position = row_position_string(row)
    if not position:
        return []

    if "GK" in position.upper():
        return ["Goalkeeper", "Ball Playing Goalkeeper"]

    role = map_position_to_role(position)
    if role is None:
        return []

    tokens = [p.strip() for p in position.split(",") if p.strip()]

    if role == "Forward":
        return ["Complete Forward", "Poacher", "Target Man", "Deep Lying Forward"]
    if role == "Winger":
        return [
            "Winger",
            "Inside Forward"
        ]
    if role == "Attacking Midfielder":
        return ["Attacking Midfielder", "Playmaker"]
    if role == "Midfielder":
        if any("DMF" in t.upper() for t in tokens):
            return ["Defensive Midfielder", "Playmaker", "Box-to-Box Midfielder"]
        return ["Box-to-Box Midfielder", "Attacking Midfielder", "Playmaker"]
    if role == "Fullback":
        return ["Complete Fullback", "Attacking Fullback", "Defensive Fullback"]
    if role == "Defender":
        return ["Ball Playing Center Back", "Stopper Center Back"]
    return []


# Wyscout coarse role (:func:`map_position_to_role`) required when scoring / ranking by archetype.
# Mirrors which roles may use each profile in :func:`eligible_performance_position_types`.
PERFORMANCE_ARCHETYPE_ROLE_FILTER: dict[str, frozenset[str]] = {
    "Goalkeeper": frozenset({"Goalkeeper"}),
    "Ball Playing Goalkeeper": frozenset({"Goalkeeper"}),
    "Complete Forward": frozenset({"Forward"}),
    "Poacher": frozenset({"Forward"}),
    "Target Man": frozenset({"Forward"}),
    "Deep Lying Forward": frozenset({"Forward"}),
    "Winger": frozenset({"Winger", "Attacking Midfielder"}),
    "Inside Forward": frozenset({"Winger", "Attacking Midfielder"}),
    "Box-to-Box Midfielder": frozenset({"Midfielder"}),
    "Defensive Midfielder": frozenset({"Midfielder"}),
    "Playmaker": frozenset({"Midfielder", "Attacking Midfielder"}),
    "Attacking Midfielder": frozenset({"Attacking Midfielder", "Midfielder"}),
    "Complete Fullback": frozenset({"Fullback"}),
    "Attacking Fullback": frozenset({"Fullback"}),
    "Defensive Fullback": frozenset({"Fullback"}),
    "Ball Playing Center Back": frozenset({"Defender"}),
    "Stopper Center Back": frozenset({"Defender"}),
}


def wyscout_roles_union_for_performance_archetypes(archetypes: Iterable[str]) -> Optional[frozenset[str]]:
    """Union of Wyscout roles for *archetypes*. Unknown name in the list → ``None`` (no gating)."""
    arch = [a for a in archetypes if a]
    if not arch:
        return None
    acc: set[str] = set()
    for a in arch:
        r = PERFORMANCE_ARCHETYPE_ROLE_FILTER.get(a)
        if r is None:
            return None
        acc |= r
    return frozenset(acc)


def mask_rows_for_performance_archetype_roles(df: pd.DataFrame, archetypes: Iterable[str]) -> pd.Series:
    """True where ``map_position_to_role`` is in the allowed set for *archetypes*; all True if unset."""
    roles = wyscout_roles_union_for_performance_archetypes(archetypes)
    if roles is None or df.empty:
        return pd.Series(True, index=df.index, dtype=bool)

    def _row_ok(row: pd.Series) -> bool:
        rr = map_position_to_role(row_position_string(row))
        return bool(rr in roles) if rr is not None else False

    return df.apply(_row_ok, axis=1)


def performance_index_series(df: pd.DataFrame, position_type: str) -> pd.Series:
    """Vectorized weighted performance index (hybrid area + sub-segment columns).

    For :data:`GENERALIST_PERFORMANCE_ARCHETYPES`, mixes the weighted index with a cohort
    term: per-pillar means use only **Midfielder** rows for ``Box-to-Box Midfielder`` and
    only **Fullback** rows for fullback archetypes. The blend applies **only** to rows in
    that same role; others keep the weighted index. The cohort-relative term uses
    ``mat[i,k] / mu_k`` rescaled to the cohort's mean level.

    Rows in that role also get a **balance boost**: low variation across the same sub-index
    pillars defined for that archetype in ``PERFORMANCE_WEIGHTS_HYBRID`` (not radar game-area
    columns) rewards even profiles on those segments.
    """
    if df is None or len(df) == 0:
        return pd.Series(dtype=float)
    if position_type not in PERFORMANCE_WEIGHTS_HYBRID:
        return pd.Series(np.nan, index=df.index, dtype=float)

    weights_map = PERFORMANCE_WEIGHTS_HYBRID[position_type]
    keys = list(weights_map.keys())
    w = np.asarray([weights_map[k] for k in keys], dtype=np.float64)
    w_sum = float(np.sum(w))
    if w_sum > 0.0:
        w = w / w_sum
    cols = [_performance_index_column_name(k) for k in keys]
    n = len(df)
    parts: list[np.ndarray] = []
    for c in cols:
        if c in df.columns:
            parts.append(pd.to_numeric(df[c], errors="coerce").to_numpy(dtype=np.float64, copy=False))
        else:
            parts.append(np.full(n, np.nan, dtype=np.float64))
    mat = np.column_stack(parts)
    valid = ~np.isnan(mat)
    weighted = np.where(valid, mat * w, 0.0)
    w_per_row = (valid.astype(np.float64) * w).sum(axis=1)
    num = weighted.sum(axis=1)
    out_weighted = np.divide(
        num,
        w_per_row,
        out=np.full(n, np.nan, dtype=float),
        where=w_per_row > 0.0,
    )

    if position_type not in GENERALIST_PERFORMANCE_ARCHETYPES:
        return pd.Series(out_weighted, index=df.index, dtype=float)

    cohort_role = _generalist_cohort_role_for_archetype(position_type)
    row_roles = df.apply(
        lambda r: map_position_to_role(row_position_string(r)),
        axis=1,
    ).to_numpy(dtype=object)
    role_mask = np.fromiter(
        (r == cohort_role for r in row_roles),
        dtype=bool,
        count=n,
    )

    n_keys = mat.shape[1]
    mu = np.empty(n_keys, dtype=np.float64)
    for k in range(n_keys):
        col = mat[role_mask, k]
        if col.size == 0 or not np.any(np.isfinite(col)):
            mu[k] = np.nan
        else:
            mu[k] = float(np.mean(col[np.isfinite(col)]))
    safe_mu = np.where(np.isfinite(mu) & (np.abs(mu) > 1e-9), mu, np.nan)
    _fin_mu = safe_mu[np.isfinite(safe_mu)]
    scale = float(np.mean(_fin_mu)) if _fin_mu.size > 0 else float("nan")

    if not np.isfinite(scale) or scale <= 0.0 or not np.any(role_mask):
        count = valid.sum(axis=1)
        sum_valid = np.where(valid, mat, 0.0).sum(axis=1)
        rel_simple = np.divide(
            sum_valid,
            count.astype(np.float64),
            out=np.full(n, np.nan, dtype=float),
            where=count > 0,
        )
    else:
        ratios = mat / safe_mu
        ratios = np.where(valid & np.isfinite(safe_mu), ratios, np.nan)
        _cnt_r = np.sum(np.isfinite(ratios), axis=1).astype(np.float64)
        _sum_r = np.nansum(ratios, axis=1)
        rel_simple = np.divide(
            _sum_r * scale,
            _cnt_r,
            out=np.full(n, np.nan, dtype=float),
            where=_cnt_r > 0,
        )

    a = GENERALIST_BLEND_WEIGHTED
    blended = a * out_weighted + (1.0 - a) * rel_simple
    blended = np.where(np.isfinite(blended), blended, out_weighted)
    base = np.where(role_mask, blended, out_weighted)

    balance_w = _rowwise_cv_balance_weight(mat, valid)
    boost = GENERALIST_BALANCE_BOOST_MAX * balance_w
    boost = np.where(role_mask, boost, 0.0)
    out = np.clip(base + boost, 0.0, 100.0)
    out = np.where(np.isfinite(out_weighted), out, np.nan)
    return pd.Series(out, index=df.index, dtype=float)


def performance_index_series_max_over_types(df: pd.DataFrame, types: List[str]) -> pd.Series:
    """Row-wise maximum of :func:`performance_index_series` over the given position types."""
    if df is None or len(df) == 0 or not types:
        return pd.Series(np.nan, index=df.index, dtype=float)
    mats = [performance_index_series(df, t).to_numpy(dtype=float) for t in types]
    arr = np.column_stack(mats)
    return pd.Series(_nanmax_rows_ignore_all_nan(arr), index=df.index, dtype=float)


def performance_index_max_series(df: pd.DataFrame) -> pd.Series:
    """Max of :func:`performance_index_series` over :func:`eligible_performance_position_types` per row."""
    if df is None or len(df) == 0:
        return pd.Series(dtype=float)
    type_order = list(PERFORMANCE_WEIGHTS_HYBRID.keys())
    mat = np.column_stack([performance_index_series(df, t).to_numpy(dtype=float) for t in type_order])
    n = len(df)
    masked = np.full_like(mat, np.nan, dtype=float)
    for i in range(n):
        elig = eligible_performance_position_types(df.iloc[i])
        idxs = [type_order.index(t) for t in elig if t in type_order]
        if not idxs:
            continue
        masked[i, idxs] = mat[i, idxs]
    return pd.Series(_nanmax_rows_ignore_all_nan(masked), index=df.index, dtype=float)


def calculate_performance_index(row: pd.Series, position_type: str) -> float:
    """Weighted performance index for one row and one position type."""
    val = performance_index_series(row.to_frame().T, position_type).iloc[0]
    return float(val) if pd.notna(val) else np.nan


def calculate_performance_index_max(row: pd.Series) -> float:
    """Max performance index over eligible position types for this row."""
    val = performance_index_max_series(row.to_frame().T).iloc[0]
    return float(val) if pd.notna(val) else np.nan


# ---------------------------------------------------------------------------
# Percentiles
# ---------------------------------------------------------------------------

def to_percentile(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    return s.rank(pct=True, method="average") * 100


def _apply_percentiles_frame(frame: pd.DataFrame, metrics: List[str], suffix: str) -> pd.DataFrame:
    for m in metrics:
        colname = f"{m}{suffix}"
        if m in frame.columns:
            frame[colname] = to_percentile(frame[m])
        else:
            frame[colname] = np.nan
    return frame


def percentiles_by_group(
    df: pd.DataFrame,
    metrics: List[str],
    group_cols: Optional[List[str]] = None,
    suffix: str = "_pct",
) -> pd.DataFrame:
    """Add percentile columns (0..100) for each metric, optionally within groups."""
    out = df.copy()
    if group_cols:
        g = out.groupby(group_cols, dropna=False)
        for m in metrics:
            colname = f"{m}{suffix}"
            if m in out.columns:
                out[colname] = g[m].transform(to_percentile)
            else:
                out[colname] = np.nan
    else:
        out = _apply_percentiles_frame(out, metrics, suffix)
    return out


# ---------------------------------------------------------------------------
# Similarity
# ---------------------------------------------------------------------------

def _row_to_vec(row: pd.Series, cols: list[str]) -> np.ndarray:
    v = pd.to_numeric(row.reindex(cols), errors="coerce").to_numpy(dtype=float)
    return v.ravel()


def find_similar_players(
    df: pd.DataFrame,
    target_row: pd.Series | pd.DataFrame,
    top_k: int = 10,
    filters: dict | None = None,
) -> pd.DataFrame:
    if filters is None:
        filters = {}

    if isinstance(target_row, pd.DataFrame):
        if len(target_row) == 0:
            return pd.DataFrame()
        target_row = target_row.iloc[0]

    position = map_position_to_role(target_row["Position"])
    if "Position" in df.columns and position is not None:
        role_mask = df["Position"].astype(str).apply(map_position_to_role) == position
        df_f = df[role_mask].copy()
    else:
        df_f = df.copy()

    if filters.get("height", 0) > 0:
        df_f = df_f[pd.to_numeric(df_f["Height"], errors="coerce") >= float(filters["height"])]
    if filters.get("market_value"):
        df_f = df_f[pd.to_numeric(df_f["Market value"], errors="coerce") <= float(filters["market_value"])]
    if filters.get("age"):
        df_f = df_f[pd.to_numeric(df_f["Age"], errors="coerce") < float(filters["age"])]
    if filters.get("minutes_played"):
        df_f = df_f[pd.to_numeric(df_f["Minutes played"], errors="coerce") > float(filters["minutes_played"])]

    # Exclude self by name and Wyscout id
    df_f = df_f[df_f["Player"] != target_row["Player"]]
    if "Wyscout id" in df_f.columns and "Wyscout id" in target_row:
        df_f = df_f[df_f["Wyscout id"] != target_row["Wyscout id"]]

    if df_f.empty:
        return df_f

    mat = (
        df_f.loc[:, AREA_INDEX_COLS]
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0.0)
        .to_numpy(dtype=float)
    )
    tv = np.nan_to_num(_row_to_vec(target_row, AREA_INDEX_COLS), nan=0.0, posinf=0.0, neginf=0.0)

    dist = np.sqrt(((mat - tv) ** 2).sum(axis=1))

    out = df_f.copy()
    out["_sim_distance"] = dist
    return out.sort_values("_sim_distance", ascending=True).head(25)


# ---------------------------------------------------------------------------
# Highlight helpers (shared across scatter/ternary plots)
# ---------------------------------------------------------------------------

def top_n_mask(rank_series: pd.Series, n: int) -> pd.Series:
    """Boolean mask for the top-n entries (lowest rank values)."""
    if n <= 0:
        return pd.Series(False, index=rank_series.index)
    unique_sorted = np.sort(rank_series.unique())
    cutoff = unique_sorted[min(n - 1, len(unique_sorted) - 1)]
    return rank_series <= cutoff


def bottom_n_mask(rank_series: pd.Series, n: int) -> pd.Series:
    """Boolean mask for the bottom-n entries (highest rank values)."""
    if n <= 0:
        return pd.Series(False, index=rank_series.index)
    unique_sorted_desc = np.sort(rank_series.unique())[::-1]
    cutoff = unique_sorted_desc[min(n - 1, len(unique_sorted_desc) - 1)]
    return rank_series >= cutoff
