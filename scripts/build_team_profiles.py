"""Build data/teams/profiles/team_profiles.parquet from player data.

Usage:
    python scripts/build_team_profiles.py                    # all seasons
    python scripts/build_team_profiles.py --seasons 2024 2025
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from repo_paths import repo_root

ROOT = repo_root(Path(__file__))

import pandas as pd

from transformation.team_profiles import RAW_FEATURE_SPEC, build_team_profiles
from utils.config import INPUT_DIR
from utils.data_loading import load_season_df, available_seasons

OUTPUT_DIR = Path("data/teams/profiles")
OUTPUT_PATH = OUTPUT_DIR / "team_profiles.parquet"

# Columns required for aggregation (Team, league, Minutes + everything in spec).
REQUIRED_COLS = ("Team", "Team within selected timeframe", "league", "Minutes played") + tuple(
    RAW_FEATURE_SPEC.values()
)


def _load(season: int) -> pd.DataFrame:
    """Load the season's player frame and restore ``Team`` if the loader renamed it.

    ``utils.data_loading.load_season_df`` unconditionally renames ``Team`` → ``club``
    when ``club`` isn't already in the frame. We need ``Team`` for the aggregation
    groupby.
    """
    df = load_season_df(season, input_dir=INPUT_DIR, columns=REQUIRED_COLS)
    if "Team" not in df.columns and "club" in df.columns:
        df = df.assign(Team=df["club"])
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Build team_profiles.parquet")
    parser.add_argument("--seasons", type=int, nargs="*", default=None)
    parser.add_argument("--min-team-minutes", type=float, default=5000.0)
    parser.add_argument("--output", type=str, default=str(OUTPUT_PATH))
    args = parser.parse_args()

    seasons = args.seasons if args.seasons else available_seasons()
    if not seasons:
        raise SystemExit("No seasons found.")

    print(f"Building team profiles for seasons: {seasons}")
    out = build_team_profiles(
        seasons=seasons,
        loader=_load,
        min_team_minutes=args.min_team_minutes,
    )
    if out.empty:
        raise SystemExit("No team profiles produced — check data availability.")

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(out_path, index=False)
    print(f"Wrote {len(out)} rows to {out_path}")


if __name__ == "__main__":
    main()
