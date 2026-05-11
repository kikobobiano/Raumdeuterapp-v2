"""Build player–season panel from merged `*_all_leagues` files."""

from __future__ import annotations

import glob
import os
import re
from typing import Optional

import numpy as np
import pandas as pd

from transformation.potential_config import (
    DATA_PLAYERS_ALL,
    LEAGUE_COL,
    MINUTES_COL,
    PLAYER_ID_COL,
    PLAYER_NAME_COL,
    SEASON_YEAR_COL,
)

_YEAR_RE = re.compile(r"(20\d{2})_all_leagues\.(csv|parquet)$")


def _read_season_file(path: str) -> tuple[pd.DataFrame, int]:
    year = int(_YEAR_RE.search(os.path.basename(path)).group(1))
    if path.endswith(".parquet"):
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)
    return df, year


def load_merged_panel(
    input_dir: Optional[os.PathLike[str]] = None,
    *,
    one_row_per_player_season: bool = True,
) -> pd.DataFrame:
    """
    Concatenate all `YYYY_all_leagues.{csv,parquet}` under *input_dir*.

    Adds ``season_year`` from filename (start year). Renames club column if needed.
    Drops rows without valid ``Wyscout id``.
    """
    base = os.fspath(input_dir or DATA_PLAYERS_ALL)
    pq = sorted(glob.glob(os.path.join(base, "*_all_leagues.parquet")))
    csv = sorted(glob.glob(os.path.join(base, "*_all_leagues.csv")))
    files = pq + [f for f in csv if f.replace(".csv", ".parquet") not in pq]

    if not files:
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []
    for fp in files:
        m = _YEAR_RE.search(os.path.basename(fp))
        if not m:
            continue
        try:
            df, year = _read_season_file(fp)
        except Exception:
            continue
        df = df.copy()
        df[SEASON_YEAR_COL] = year
        if "club" not in df.columns:
            if "Team within selected timeframe" in df.columns:
                df = df.rename(columns={"Team within selected timeframe": "club"})
            elif "Team" in df.columns:
                df = df.rename(columns={"Team": "club"})
        frames.append(df)

    if not frames:
        return pd.DataFrame()

    out = pd.concat(frames, ignore_index=True)

    if PLAYER_ID_COL not in out.columns:
        return pd.DataFrame()

    out[PLAYER_ID_COL] = pd.to_numeric(out[PLAYER_ID_COL], errors="coerce")
    out = out[out[PLAYER_ID_COL].notna()].copy()
    out[PLAYER_ID_COL] = out[PLAYER_ID_COL].astype(np.int64)

    if MINUTES_COL in out.columns:
        out[MINUTES_COL] = pd.to_numeric(out[MINUTES_COL], errors="coerce").fillna(0)
    if "Age" in out.columns:
        out["Age"] = pd.to_numeric(out["Age"], errors="coerce")

    if one_row_per_player_season and MINUTES_COL in out.columns:
        out = out.sort_values(MINUTES_COL, ascending=False)
        out = out.drop_duplicates(subset=[PLAYER_ID_COL, SEASON_YEAR_COL], keep="first")

    return out.reset_index(drop=True)


def attach_league_power(df: pd.DataFrame, league_to_power: dict[str, float]) -> pd.DataFrame:
    """Add ``league_power`` from league name; unknown leagues -> NaN."""
    work = df.copy()
    if LEAGUE_COL not in work.columns:
        work["league_power"] = np.nan
        return work
    work["league_power"] = work[LEAGUE_COL].map(lambda x: league_to_power.get(str(x), np.nan))
    return work
