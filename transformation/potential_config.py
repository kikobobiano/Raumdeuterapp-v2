"""Constants for the historical potential-score pipeline (offline train / app load)."""

from __future__ import annotations

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
    raise RuntimeError(
        "Cannot resolve monorepo root (missing utils/repo_root.py in any parent)."
    )

from utils.repo_root import repo_root

# --- Paths (repo root relative) ---
PROJECT_ROOT = repo_root(_sf)
DATA_PLAYERS_ALL = PROJECT_ROOT / "data" / "players" / "all"
POTENTIAL_DATA_DIR = PROJECT_ROOT / "data" / "potential"
MODEL_PATH = POTENTIAL_DATA_DIR / "potential_model.joblib"
SCORES_PATH = POTENTIAL_DATA_DIR / "potential_scores.parquet"
SCORES_CSV_PATH = POTENTIAL_DATA_DIR / "potential_scores.csv"

# --- Column names ---
PLAYER_ID_COL = "Wyscout id"
PLAYER_NAME_COL = "Player"
MINUTES_COL = "Minutes played"
LEAGUE_COL = "league"
SEASON_YEAR_COL = "season_year"

# --- Cohort: who gets a score / who enters training as "current" row ---
MAX_AGE_COHORT = 25
MIN_MINUTES_CURRENT_SEASON = 400

# --- Target: look-ahead window and future minutes gate ---
FUTURE_HORIZON_SEASONS = 3
MIN_MINUTES_FUTURE_SEASON = 450

# --- Binary label within horizon: strong competition *and* high performance_index ---
# Top-five leagues in LEAGUE_POWER_BASE start ~85.5+; 85 is a practical cut.
BIG_LEAGUE_POWER_THRESHOLD = 85.0
# Same scale as ``performance_index`` / app "Performance index" (0–100 style).
PERFORMANCE_INDEX_TARGET_THRESHOLD = 73.0

# --- Model / validation ---
RANDOM_STATE = 42
TRAIN_LAST_SEASON_EXCLUSIVE = 2023  # train on season_year < this; val/test forward
