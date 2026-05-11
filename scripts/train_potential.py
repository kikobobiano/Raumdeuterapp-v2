#!/usr/bin/env python3
"""
Offline pipeline: build player-season panel, train HistGradientBoosting potential model,
export joblib model + Parquet/CSV scores.

Target (per player-season): within the next 3 seasons, at least one row with enough
minutes, league power ≥ BIG_LEAGUE_POWER_THRESHOLD, and performance_index >
PERFORMANCE_INDEX_TARGET_THRESHOLD (see transformation/potential_config.py).

Run from repo root:
  python scripts/train_potential.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from repo_paths import repo_root

ROOT = repo_root(Path(__file__))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import joblib
import pandas as pd

from transformation.potential_config import (
    BIG_LEAGUE_POWER_THRESHOLD,
    MODEL_PATH,
    PERFORMANCE_INDEX_TARGET_THRESHOLD,
    POTENTIAL_DATA_DIR,
    SCORES_CSV_PATH,
    SCORES_PATH,
    TRAIN_LAST_SEASON_EXCLUSIVE,
)
from transformation.potential_model import (
    add_lag_features,
    cohort_mask,
    compute_future_strong_league_high_pi,
    enrich_panel,
    fit_full_pipeline,
    predict_proba,
    scores_table,
    train_and_eval_temporal,
)
from transformation.potential_panel import load_merged_panel


def main() -> None:
    POTENTIAL_DATA_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading merged season files …")
    raw = load_merged_panel()
    if raw.empty:
        print("No data found under data/players/all. Abort.")
        sys.exit(1)

    print(f"Rows: {len(raw):,}, seasons: {sorted(raw['season_year'].unique())}")
    print("Enriching (league power, position type, performance index) …")
    panel = enrich_panel(raw)
    panel = add_lag_features(panel)

    print(
        "Computing target: within 3 seasons, strong league "
        f"(power≥{BIG_LEAGUE_POWER_THRESHOLD:g}) and "
        f"performance_index>{PERFORMANCE_INDEX_TARGET_THRESHOLD:g} …"
    )
    y_bin = compute_future_strong_league_high_pi(panel)
    panel["_y_elite_future"] = y_bin

    labeled = cohort_mask(panel) & y_bin.notna()
    print(
        f"Training-eligible rows (age≤23, minutes≥450, position ok, future known): {labeled.sum():,}"
    )
    print(
        f"Positive rate (strong league + PI>{PERFORMANCE_INDEX_TARGET_THRESHOLD:g}): "
        f"{y_bin[labeled].mean():.3f}"
    )

    print(f"Temporal hold-out: train season_year < {TRAIN_LAST_SEASON_EXCLUSIVE}")
    pipe_eval, metrics = train_and_eval_temporal(
        panel, y_bin, train_end_exclusive=TRAIN_LAST_SEASON_EXCLUSIVE
    )
    print("Validation metrics:", json.dumps(metrics, indent=2))

    print("Fitting final model on all labeled rows …")
    pipe_full = fit_full_pipeline(panel, y_bin)
    joblib.dump(pipe_full, MODEL_PATH)
    print(f"Saved model → {MODEL_PATH}")

    # Score every eligible player-season (all years) so the app can filter by season.
    score_mask = cohort_mask(panel)
    print(f"Scoring full cohort across all seasons (n={score_mask.sum():,}) …")
    proba = predict_proba(pipe_full, panel, mask=score_mask)
    out = scores_table(panel, proba)
    out.to_parquet(SCORES_PATH, index=False)
    out.to_csv(SCORES_CSV_PATH, index=False)
    print(f"Saved scores → {SCORES_PATH} and {SCORES_CSV_PATH}")


if __name__ == "__main__":
    main()
