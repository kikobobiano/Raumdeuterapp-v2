"""Tests for ``utils.tm_market_value`` (TM ``player_valuations.csv`` as-of join)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.tm_market_value import (  # noqa: E402
    infer_tm_market_value_eur,
    season_reference_date,
    x_tv_hat_eur,
)


def test_season_reference_date_default() -> None:
    assert season_reference_date(2024) == __import__("datetime").date(2025, 6, 30)


def test_infer_tm_market_value_eur_asof(tmp_path: Path) -> None:
    tm_dir = tmp_path
    pd.DataFrame(
        {
            "key_wyscout": [np.nan, 999001],
            "key_soccerway": [1001, np.nan],
            "key_transfermarkt": [5001, 5002],
        }
    ).to_csv(tm_dir / "people.csv", index=False)

    pd.DataFrame(
        {
            "player_id": [5001] * 3 + [5002] * 2,
            "date": [
                "2023-06-01",
                "2024-12-15",
                "2025-08-01",
                "2022-01-01",
                "2025-01-01",
            ],
            "market_value_in_eur": [
                100,
                200,
                300,
                10,
                20,
            ],
        }
    ).to_csv(tm_dir / "player_valuations.csv", index=False)

    # Season 2024–25 ⇒ ref ~ 2025-06-30: last valuation ≤ date is 200 (2024-12-15)
    out_s = infer_tm_market_value_eur(
        pd.Series([1001]),
        np.int64(2024),
        tm_dir=tm_dir,
        valuations_csv=tm_dir / "player_valuations.csv",
        ref_month=6,
        ref_day=30,
    )
    assert len(out_s) == 1
    assert pytest.approx(out_s.iloc[0]) == 200.0

    out_broadcast = infer_tm_market_value_eur(
        np.asarray([999001, np.nan]),
        2025,
        tm_dir=tm_dir,
    )
    # Ref 2026-06-30 for Wyscout-export 999001 → TM 5002: last valuation 20 (2025-01)
    assert pytest.approx(out_broadcast.iloc[0]) == 20.0
    assert np.isnan(out_broadcast.iloc[1])


def test_x_tv_hat_formula() -> None:
    mv = pd.Series([1_000_000.0])
    got = x_tv_hat_eur(np.log(1.1), mv)
    assert pytest.approx(got.iloc[0]) == 1.1 * 1_000_000.0
