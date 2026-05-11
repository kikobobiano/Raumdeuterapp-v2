"""Target construction, feature matrix, train/infer for potential score."""

from __future__ import annotations

import warnings
from typing import Any, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from utils.config import AREA_INDEX_COLS, LEAGUE_POWER_BASE
from utils.transforms import classify_position_type, performance_index_max_series

from transformation.potential_config import (
    BIG_LEAGUE_POWER_THRESHOLD,
    FUTURE_HORIZON_SEASONS,
    MAX_AGE_COHORT,
    MIN_MINUTES_CURRENT_SEASON,
    MIN_MINUTES_FUTURE_SEASON,
    MINUTES_COL,
    PERFORMANCE_INDEX_TARGET_THRESHOLD,
    PLAYER_ID_COL,
    PLAYER_NAME_COL,
    RANDOM_STATE,
    SEASON_YEAR_COL,
)


def enrich_panel(df: pd.DataFrame) -> pd.DataFrame:
    """Add league_power, position_type, performance_index."""
    work = df.copy()
    work["league_power"] = work["league"].map(
        lambda x: LEAGUE_POWER_BASE.get(str(x), np.nan) if pd.notna(x) else np.nan
    )
    work["position_type"] = work.apply(classify_position_type, axis=1)
    if "performance_index" in work.columns:
        pass
    else:
        work["performance_index"] = performance_index_max_series(work)
    return work


def compute_future_max_league_power(panel: pd.DataFrame) -> pd.Series:
    """
    For each row index, max ``league_power`` in the next ``FUTURE_HORIZON_SEASONS``
    seasons for the same player, counting only seasons with
    ``Minutes played >= MIN_MINUTES_FUTURE_SEASON``.
    """
    need = [PLAYER_ID_COL, SEASON_YEAR_COL, "league_power", MINUTES_COL]
    for c in need:
        if c not in panel.columns:
            raise ValueError(f"panel missing column {c}")

    p = panel[need].copy()
    y_list: list[float] = []
    idx_order = panel.index.tolist()

    # group once
    grouped = {pid: g for pid, g in p.groupby(PLAYER_ID_COL, sort=False)}

    for i in panel.index:
        row = panel.loc[i]
        pid = row[PLAYER_ID_COL]
        sy = int(row[SEASON_YEAR_COL])
        g = grouped.get(pid)
        if g is None or g.empty:
            y_list.append(np.nan)
            continue
        future = g[
            (g[SEASON_YEAR_COL] > sy)
            & (g[SEASON_YEAR_COL] <= sy + FUTURE_HORIZON_SEASONS)
            & (g[MINUTES_COL] >= MIN_MINUTES_FUTURE_SEASON)
        ]
        if future.empty:
            y_list.append(np.nan)
        else:
            y_list.append(float(future["league_power"].max()))

    return pd.Series(y_list, index=idx_order)


def compute_future_tier_binary(y_max_power: pd.Series) -> pd.Series:
    """1 if future max league power >= threshold; NaN where *y_max_power* is NaN."""
    out = pd.Series(np.nan, index=y_max_power.index, dtype=float)
    m = y_max_power.notna()
    out.loc[m] = (y_max_power.loc[m] >= BIG_LEAGUE_POWER_THRESHOLD).astype(float)
    return out


def compute_future_strong_league_high_pi(panel: pd.DataFrame) -> pd.Series:
    """
    Training target aligned to each player-season row.

    **1** if, within the next ``FUTURE_HORIZON_SEASONS`` seasons, the same player has at
    least one row with ``Minutes played >= MIN_MINUTES_FUTURE_SEASON``,
    ``league_power >= BIG_LEAGUE_POWER_THRESHOLD``, and
    ``performance_index > PERFORMANCE_INDEX_TARGET_THRESHOLD``.

    **0** if such follow-up seasons exist (minutes gate) but none satisfy the joint condition.

    **NaN** if there is no future season in the window that passes the minutes gate
    (outcome not observed).
    """
    need = [
        PLAYER_ID_COL,
        SEASON_YEAR_COL,
        "league_power",
        MINUTES_COL,
        "performance_index",
    ]
    for c in need:
        if c not in panel.columns:
            raise ValueError(f"panel missing column {c}")

    p = panel[need].copy()
    y_list: list[float] = []
    idx_order = panel.index.tolist()
    grouped = {pid: g for pid, g in p.groupby(PLAYER_ID_COL, sort=False)}

    for i in panel.index:
        row = panel.loc[i]
        pid = row[PLAYER_ID_COL]
        sy = int(row[SEASON_YEAR_COL])
        g = grouped.get(pid)
        if g is None or g.empty:
            y_list.append(np.nan)
            continue
        future = g[
            (g[SEASON_YEAR_COL] > sy)
            & (g[SEASON_YEAR_COL] <= sy + FUTURE_HORIZON_SEASONS)
            & (g[MINUTES_COL] >= MIN_MINUTES_FUTURE_SEASON)
        ]
        if future.empty:
            y_list.append(np.nan)
            continue
        lp = pd.to_numeric(future["league_power"], errors="coerce")
        pi = pd.to_numeric(future["performance_index"], errors="coerce")
        hit = (
            (lp >= BIG_LEAGUE_POWER_THRESHOLD)
            & (pi > PERFORMANCE_INDEX_TARGET_THRESHOLD)
        ).any()
        y_list.append(1.0 if hit else 0.0)

    return pd.Series(y_list, index=idx_order)


def add_lag_features(panel: pd.DataFrame) -> pd.DataFrame:
    """Previous-season performance_index and league_power per player (optional features)."""
    work = panel.sort_values([PLAYER_ID_COL, SEASON_YEAR_COL]).copy()
    g = work.groupby(PLAYER_ID_COL, sort=False)
    work["performance_index_lag1"] = g["performance_index"].shift(1)
    work["league_power_lag1"] = g["league_power"].shift(1)
    return work


def cohort_mask(panel: pd.DataFrame) -> pd.Series:
    """Young players with enough minutes in the current row."""
    age_ok = panel["Age"] <= MAX_AGE_COHORT
    mins_ok = panel[MINUTES_COL] >= MIN_MINUTES_CURRENT_SEASON
    pos_ok = panel["position_type"].notna()
    return age_ok & mins_ok & pos_ok


FEATURE_NUMERIC = [
    "Age",
    MINUTES_COL,
    "league_power",
    "performance_index",
    "performance_index_lag1",
    "league_power_lag1",
] + list(AREA_INDEX_COLS)


def build_feature_matrix(panel: pd.DataFrame) -> tuple[pd.DataFrame, list[str], list[str]]:
    """Return X frame (numeric + categorical column), numeric names, categorical names."""
    num_cols = [c for c in FEATURE_NUMERIC if c in panel.columns]
    cat_cols = ["position_type"] if "position_type" in panel.columns else []
    use_cols = num_cols + cat_cols
    X = panel[use_cols].copy()
    for c in num_cols:
        X[c] = pd.to_numeric(X[c], errors="coerce")
    if "position_type" in X.columns:
        X["position_type"] = X["position_type"].astype(str).replace("nan", "unknown")
    return X, num_cols, cat_cols


def make_pipeline(num_cols: list[str], cat_cols: list[str]) -> Pipeline:
    transformers = []
    if num_cols:
        transformers.append(
            (
                "num",
                SimpleImputer(strategy="median"),
                num_cols,
            )
        )
    if cat_cols:
        transformers.append(
            (
                "cat",
                Pipeline(
                    steps=[
                        ("impute", SimpleImputer(strategy="most_frequent")),
                        (
                            "oh",
                            OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                        ),
                    ]
                ),
                cat_cols,
            )
        )
    pre = ColumnTransformer(transformers=transformers, remainder="drop")
    clf = HistGradientBoostingClassifier(
        max_depth=6,
        max_iter=200,
        learning_rate=0.06,
        random_state=RANDOM_STATE,
        class_weight="balanced",
    )
    return Pipeline([("prep", pre), ("clf", clf)])


def train_and_eval_temporal(
    panel: pd.DataFrame,
    y: pd.Series,
    *,
    train_end_exclusive: int,
) -> tuple[Pipeline, dict[str, float]]:
    """
    Train on season_year < train_end_exclusive with non-null y;
    evaluate on [train_end_exclusive, train_end_exclusive+2] if rows exist.
    """
    m = cohort_mask(panel) & y.notna()
    df = panel.loc[m].copy()
    y_clean = y.loc[m].astype(int)

    train_mask = df[SEASON_YEAR_COL] < train_end_exclusive
    test_mask = df[SEASON_YEAR_COL] >= train_end_exclusive

    X, num_cols, cat_cols = build_feature_matrix(df)
    X_train, y_train = X.loc[train_mask], y_clean.loc[train_mask]
    X_test, y_test = X.loc[test_mask], y_clean.loc[test_mask]

    if len(X_train) < 50 or y_train.nunique() < 2:
        warnings.warn("Insufficient training data for potential model.", stacklevel=2)
        pipe = make_pipeline(num_cols, cat_cols)
        pipe.fit(X_train, y_train)
        return pipe, {"roc_auc": float("nan"), "brier": float("nan"), "n_train": float(len(X_train))}

    pipe = make_pipeline(num_cols, cat_cols)
    pipe.fit(X_train, y_train)

    metrics: dict[str, float] = {
        "n_train": float(len(X_train)),
        "n_test": float(len(X_test)),
    }
    if len(X_test) > 0 and y_test.nunique() > 1:
        proba = pipe.predict_proba(X_test)[:, 1]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            metrics["roc_auc"] = float(roc_auc_score(y_test, proba))
        metrics["brier"] = float(brier_score_loss(y_test, proba))
    else:
        metrics["roc_auc"] = float("nan")
        metrics["brier"] = float("nan")

    return pipe, metrics


def fit_full_pipeline(panel: pd.DataFrame, y: pd.Series) -> Pipeline:
    """Fit on all rows with non-null y and cohort mask (for final export model)."""
    m = cohort_mask(panel) & y.notna()
    X, num_cols, cat_cols = build_feature_matrix(panel.loc[m])
    y_clean = y.loc[m].astype(int)
    pipe = make_pipeline(num_cols, cat_cols)
    pipe.fit(X, y_clean)
    return pipe


def predict_proba(
    pipe: Pipeline,
    panel: pd.DataFrame,
    *,
    mask: Optional[pd.Series] = None,
) -> pd.Series:
    """Return P(strong league & performance_index above target within horizon) for *mask* rows."""
    m = cohort_mask(panel) if mask is None else mask
    X, _, _ = build_feature_matrix(panel.loc[m])
    if X.empty:
        return pd.Series(dtype=float)
    p = pipe.predict_proba(X)[:, 1]
    return pd.Series(p, index=X.index)


def scores_table(
    panel: pd.DataFrame,
    proba: pd.Series,
    *,
    season_year: Optional[int] = None,
) -> pd.DataFrame:
    """Build a tidy table for Parquet / Streamlit."""
    idx = proba.index
    sub = panel.loc[idx].copy()
    sub["potential_proba"] = proba.values
    sub["potential_score"] = (sub["potential_proba"] * 100.0).round(1)
    sub["potential_elite_label"] = (sub["potential_proba"] >= 0.5).astype(int)
    cols = [
        SEASON_YEAR_COL,
        PLAYER_ID_COL,
        PLAYER_NAME_COL,
        "league",
        "Age",
        "position_type",
        "performance_index",
        "league_power",
        MINUTES_COL,
        "potential_score",
        "potential_proba",
        "potential_elite_label",
    ]
    cols = [c for c in cols if c in sub.columns]
    out = sub[cols].copy()
    if season_year is not None:
        out = out[out[SEASON_YEAR_COL] == season_year]
    return out.sort_values("potential_proba", ascending=False).reset_index(drop=True)
