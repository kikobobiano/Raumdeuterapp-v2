"""Smoke tests for transformation.xtv (PYTHONPATH must include monorepo root)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from transformation.xtv.baseline import (  # noqa: E402
    BASELINE_FEATURE_ORDER,
    fit_baseline,
    predict_xtv_parquet,
    sklearn_baseline_pipeline,
)
from transformation.xtv.season import transfer_season_to_start_year  # noqa: E402


def test_transfer_season_to_start_year() -> None:
    assert transfer_season_to_start_year("25/26") == 2025
    assert transfer_season_to_start_year("24/25") == 2024
    assert transfer_season_to_start_year(None) is None


def test_sklearn_pipeline_fit_predict() -> None:
    pytest.importorskip("sklearn")
    rng = np.random.default_rng(0)
    n = 400
    X = pd.DataFrame(
        {
            "distribution_index": rng.normal(55, 15, n),
            "take_ons_index": rng.normal(52, 14, n),
            "assistance_index": rng.normal(53, 13, n),
            "finishing_index": rng.normal(51, 14, n),
            "aerial_play_index": rng.normal(50, 12, n),
            "ground_defense_index": rng.normal(52, 15, n),
            "age": rng.integers(17, 34, n).astype(float),
            "log_minutes": np.log1p(rng.integers(300, 3400, n).astype(float)),
            "log_mv": np.log(rng.uniform(0.5e6, 35e6, n)),
            "lc_key": np.where(rng.random(n) > 0.3, "Premier League::Arsenal", "__na__::__na__"),
        }
    )
    y = 0.08 * (X["distribution_index"] / 100.0) + 0.03 * X["log_mv"] + rng.normal(0, 0.12, n)

    pipe = sklearn_baseline_pipeline(enable_early_stopping=False)
    fit_baseline(pipe, X[BASELINE_FEATURE_ORDER], pd.Series(y))

    panel = X.copy()
    mv = np.exp(X["log_mv"]) * 1.0
    out = predict_xtv_parquet(pipe, panel, mv_eur=pd.Series(mv), season_y=2024)
    assert out.notna().sum() > n * 0.5
    assert (out.dropna() >= 0).all()
