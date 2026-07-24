"""Unit tests for scouting cohort + archetype helpers (no DuckDB required)."""
from __future__ import annotations

import numpy as np

from app.core.league_tiers import expand_leagues_by_tier, tier_for
from app.core.scouting_archetype import kmeans, pca, silhouette
from app.core.scouting_cohort import shrunk_zscore


def test_league_tier_mapping() -> None:
    assert tier_for("Premier League") == "T1"
    assert tier_for("La Liga 2") in {"T2", "T3"}
    assert tier_for("Veikkausliiga") == "T4"
    assert tier_for(None) == "T4"
    expanded = expand_leagues_by_tier(["Premier League"])
    assert "Bundesliga" in expanded
    assert "Veikkausliiga" not in expanded


def test_shrunk_zscore_basic() -> None:
    assert shrunk_zscore(1.0, mean=0.0, sd=1.0, player_minutes=10000) is not None
    z_full = shrunk_zscore(1.0, mean=0.0, sd=1.0, player_minutes=10000)
    z_low = shrunk_zscore(1.0, mean=0.0, sd=1.0, player_minutes=100)
    assert z_full is not None and z_low is not None
    assert abs(z_low) < abs(z_full)  # low minutes → shrunk toward 0
    assert shrunk_zscore(None, mean=0.0, sd=1.0, player_minutes=1000) is None
    assert shrunk_zscore(1.0, mean=0.0, sd=0.0, player_minutes=1000) is None


def test_shrunk_zscore_clamped() -> None:
    z = shrunk_zscore(100.0, mean=0.0, sd=1.0, player_minutes=10000)
    assert z is not None
    assert z <= 6.0


def test_pca_explained_variance_sums_to_one_on_full_rank() -> None:
    rng = np.random.default_rng(0)
    data = rng.standard_normal((100, 5))
    out = pca(data, k=5)
    total = sum(out["explained"])
    assert 0.99 <= total <= 1.0001
    # First component should not exceed total.
    assert out["explained"][0] <= 1.0


def test_pca_handles_nans() -> None:
    rng = np.random.default_rng(1)
    data = rng.standard_normal((50, 4))
    data[0, 0] = np.nan
    out = pca(data, k=3)
    assert out["scores"].shape == (50, 3)
    assert not np.isnan(out["scores"]).any()


def test_kmeans_deterministic_with_fixed_seed() -> None:
    rng = np.random.default_rng(0)
    a = rng.normal(loc=-3, size=(30, 2))
    b = rng.normal(loc=3, size=(30, 2))
    x = np.vstack([a, b])
    out1 = kmeans(x, k=2, seed=42)
    out2 = kmeans(x, k=2, seed=42)
    # Labels may be permuted; compare via cluster sizes instead.
    sizes1 = sorted([int((out1["labels"] == i).sum()) for i in range(2)])
    sizes2 = sorted([int((out2["labels"] == i).sum()) for i in range(2)])
    assert sizes1 == sizes2
    # Two well-separated blobs → silhouette should be high.
    s = silhouette(x, out1["labels"])
    assert s > 0.4
