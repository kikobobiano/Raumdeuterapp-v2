"""Synthetic smoke test for xTV v2 — feature build + pipeline fit + predict."""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest


def _ensure_repo_on_path() -> None:
    here = Path(__file__).resolve()
    for cand in here.parents:
        if (cand / "transformation" / "xtv" / "model.py").is_file():
            s = str(cand)
            if s not in sys.path:
                sys.path.insert(0, s)
            return
    raise RuntimeError("Could not locate raumdeuterappv2 root.")


_ensure_repo_on_path()


def _fake_player_rows(n: int = 30) -> pd.DataFrame:
    rng = np.random.default_rng(11)
    return pd.DataFrame(
        {
            "Wyscout id": np.arange(n) + 1,
            "Player": [f"Player {i}" for i in range(n)],
            "league": rng.choice(["Premier League", "Eredivisie", "Primeira Liga"], size=n),
            "club": rng.choice(["Man City", "Ajax", "Benfica"], size=n),
            "Birthday": [f"199{(i % 9)}-0{(i % 9) + 1}-15" for i in range(n)],
            "Age": rng.integers(18, 35, size=n).astype(float),
            "Minutes played": rng.integers(200, 3000, size=n).astype(float),
            "Primary position": rng.choice(["CF", "CMF", "CB", "RW"], size=n),
            "distribution_index": rng.uniform(0.2, 0.95, size=n),
            "take_ons_index": rng.uniform(0.2, 0.95, size=n),
            "assistance_index": rng.uniform(0.2, 0.95, size=n),
            "finishing_index": rng.uniform(0.2, 0.95, size=n),
            "aerial_play_index": rng.uniform(0.2, 0.95, size=n),
            "ground_defense_index": rng.uniform(0.2, 0.95, size=n),
        }
    )


def test_feature_build_and_pipeline_fit_predict():
    from transformation.xtv import (
        FEATURE_ORDER,
        FEE_MAX_EUR,
        FEE_MIN_EUR,
        build_parquet_features,
        fit,
        predict_xtv_with_marginal,
        sklearn_pipeline,
    )

    df = _fake_player_rows(40)
    mv = pd.Series(np.random.default_rng(3).uniform(2e5, 5e7, size=len(df)), index=df.index)
    tier = pd.Series(np.full(len(df), 3, dtype=np.int64), index=df.index)
    feats = build_parquet_features(df, season_y=2023, mv_eur=mv, tier_for_clubs=tier)

    assert list(feats.columns) == FEATURE_ORDER
    assert len(feats) == len(df)
    assert feats["age"].notna().all()
    assert (feats["has_mv"] == 1.0).all()

    rng = np.random.default_rng(0)
    y = pd.Series(
        rng.uniform(np.log(5e5), np.log(5e7), size=len(feats)),
        index=feats.index,
        dtype=np.float64,
    )
    pipe = sklearn_pipeline(enable_early_stopping=False)
    fit(pipe, feats, y)

    # Marginalised predict — synthetic destination samples (single-head path)
    dp = rng.uniform(70.0, 92.0, size=(len(feats), 6))
    dt = rng.integers(1, 6, size=(len(feats), 6))
    xtv = predict_xtv_with_marginal(pipe, feats, dest_power=dp, dest_tier=dt)
    assert xtv.shape == (len(feats),)
    assert np.all(np.isfinite(xtv))
    assert np.all(xtv >= FEE_MIN_EUR)
    assert np.all(xtv <= FEE_MAX_EUR)

    # Two-head dispatch (ratio + abs)
    mv = pd.Series([5e6] * len(feats), index=feats.index)
    xtv2 = predict_xtv_with_marginal(
        pipe, feats, dest_power=dp, dest_tier=dt, mv_eur=mv.to_numpy(), pipe_abs=pipe
    )
    assert xtv2.shape == (len(feats),)
    assert np.all(np.isfinite(xtv2))


def test_missing_mv_is_handled():
    from transformation.xtv import build_parquet_features

    df = _fake_player_rows(8)
    mv = pd.Series([np.nan] * len(df), index=df.index, dtype=np.float64)
    tier = pd.Series(np.full(len(df), 3, dtype=np.int64), index=df.index)
    feats = build_parquet_features(df, season_y=2023, mv_eur=mv, tier_for_clubs=tier)
    assert (feats["has_mv"] == 0.0).all()
    assert (feats["log_mv"] == 0.0).all()
    assert feats["origin_league_power"].notna().all()


@pytest.mark.parametrize(
    "pos,group_idx",
    [("CF", 7), ("CMF", 4), ("CB", 1), ("LWB", 2), ("AMF", 5), ("GK", 0)],
)
def test_position_group_encoding(pos: str, group_idx: int):
    from transformation.xtv.model import encode_position_group, position_group_from_str

    grp = position_group_from_str(pos)
    assert encode_position_group(grp) == group_idx
