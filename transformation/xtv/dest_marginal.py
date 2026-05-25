"""Destination (league power, club tier) marginal prior for xTV inference."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_N_SAMPLES = 6
PRIOR_PARQUET = "xtv_dest_prior.parquet"


def origin_bucket(league_power: float) -> int:
    if not np.isfinite(league_power):
        return -1
    return int(round(float(league_power)))


def build_dest_prior(X: pd.DataFrame) -> pd.DataFrame:
    """Empirical P(dest | origin bucket) from training feature rows."""

    need = {"origin_league_power", "dest_league_power", "dest_club_tier"}
    if not need.issubset(X.columns):
        raise ValueError(f"build_dest_prior needs columns {sorted(need)}")

    work = X[list(need)].copy()
    work["origin_bucket"] = work["origin_league_power"].map(origin_bucket)
    work = work.dropna(subset=["dest_league_power", "dest_club_tier"])
    work["dest_club_tier"] = pd.to_numeric(work["dest_club_tier"], errors="coerce").fillna(3).astype(int)

    chunks: list[pd.DataFrame] = []
    for bucket, grp in work.groupby("origin_bucket", sort=True):
        counts = (
            grp.groupby(["dest_league_power", "dest_club_tier"], sort=False)
            .size()
            .reset_index(name="count")
        )
        total = float(counts["count"].sum())
        counts["origin_bucket"] = int(bucket)
        counts["prob"] = counts["count"] / total
        counts["scope"] = "origin"
        chunks.append(counts)

    gcounts = (
        work.groupby(["dest_league_power", "dest_club_tier"], sort=False)
        .size()
        .reset_index(name="count")
    )
    gtotal = float(gcounts["count"].sum())
    gcounts["origin_bucket"] = -1
    gcounts["prob"] = gcounts["count"] / gtotal
    gcounts["scope"] = "global"
    chunks.append(gcounts)

    out = pd.concat(chunks, ignore_index=True)
    return out[
        ["origin_bucket", "dest_league_power", "dest_club_tier", "count", "prob", "scope"]
    ]


def save_prior(prior: pd.DataFrame, tm_dir: Path) -> Path:
    path = tm_dir / PRIOR_PARQUET
    path.parent.mkdir(parents=True, exist_ok=True)
    prior.to_parquet(path, index=False)
    return path


def load_prior(tm_dir: Path) -> pd.DataFrame:
    path = tm_dir / PRIOR_PARQUET
    if not path.is_file():
        raise FileNotFoundError(path)
    return pd.read_parquet(path)


def sample_destinations(
    origin_power: np.ndarray,
    prior: pd.DataFrame,
    *,
    n_samples: int = DEFAULT_N_SAMPLES,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """Sample destination contexts per row; shape ``(n_rows, n_samples)``."""

    n = len(origin_power)
    dp = np.full((n, n_samples), np.nan, dtype=np.float64)
    dt = np.full((n, n_samples), 3, dtype=np.int64)

    global_prior = prior.loc[prior["scope"] == "global"]
    if global_prior.empty:
        global_prior = prior

    for i, op in enumerate(origin_power):
        bucket = origin_bucket(float(op) if np.isfinite(op) else np.nan)
        sub = prior.loc[(prior["scope"] == "origin") & (prior["origin_bucket"] == bucket)]
        if sub.empty:
            sub = global_prior
        probs = sub["prob"].to_numpy(dtype=np.float64)
        probs = probs / probs.sum()
        idx = rng.choice(len(sub), size=n_samples, replace=True, p=probs)
        picked = sub.iloc[idx]
        dp[i, :] = picked["dest_league_power"].to_numpy(dtype=np.float64)
        dt[i, :] = picked["dest_club_tier"].to_numpy(dtype=np.int64)

    return dp, dt
