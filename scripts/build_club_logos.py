"""Build a club_logos parquet from Wyscout player CSVs under data/players/wyscout/.

Output (default ``data/teams/club_logos.parquet``) columns:

  - ``team`` — club name (Wyscout ``Team``)
  - ``logo_url`` — crest URL (Wyscout ``Team logo``)
  - ``competition`` — domestic competition name (Wyscout ``Competition``), same
    string family as the ``league`` column in season parquets, so e.g. Barcelona
    in La Liga does not share a row with Barcelona in another country.
  - ``n_seasons`` — number of distinct source files the triple appeared in
  - ``latest_file`` — lexicographically latest source filename (for ordering)

Dedup key: ``(team, logo_url, competition)``.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from repo_paths import repo_root

REPO_ROOT = repo_root(Path(__file__))
WYSCOUT_DIR = REPO_ROOT / "data" / "players" / "wyscout"
OUT_DIR = REPO_ROOT / "data" / "teams"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        default=str(OUT_DIR / "club_logos.parquet"),
        help="Output parquet path",
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="Also write a CSV alongside the parquet (debugging)",
    )
    args = parser.parse_args()

    if not WYSCOUT_DIR.exists():
        print(f"Missing {WYSCOUT_DIR}", file=sys.stderr)
        return 1

    files = sorted(WYSCOUT_DIR.glob("*.csv"))
    if not files:
        print(f"No CSVs in {WYSCOUT_DIR}", file=sys.stderr)
        return 2

    rows: list[dict] = []
    for f in files:
        try:
            df = pd.read_csv(f, usecols=["Team", "Team logo", "Competition"])
        except (ValueError, KeyError):
            try:
                df = pd.read_csv(f, usecols=["Team", "Team logo"])
            except (ValueError, KeyError):
                continue
            df["Competition"] = ""
        df = df.dropna(subset=["Team"])
        df["Team"] = df["Team"].astype(str).str.strip()
        df["Team logo"] = df["Team logo"].astype(str).str.strip()
        df["Competition"] = df["Competition"].fillna("").astype(str).str.strip()
        df = df[(df["Team"] != "") & (df["Team logo"] != "") & (df["Team logo"] != "nan")]
        df = df.drop_duplicates(subset=["Team", "Team logo", "Competition"])
        df["latest_file"] = f.name
        rows.append(df)

    if not rows:
        print("No rows extracted.", file=sys.stderr)
        return 3

    full = pd.concat(rows, ignore_index=True)
    full = full.rename(
        columns={
            "Team": "team",
            "Team logo": "logo_url",
            "Competition": "competition",
        }
    )

    grouped = (
        full.groupby(["team", "logo_url", "competition"], as_index=False)
        .agg(n_seasons=("latest_file", "nunique"), latest_file=("latest_file", "max"))
        .sort_values(["team", "competition", "n_seasons"], ascending=[True, True, False])
        .reset_index(drop=True)
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    grouped.to_parquet(out_path, index=False, compression="snappy")
    n_teams = grouped["team"].nunique()
    print(f"Wrote {out_path} ({len(grouped):,} rows; {n_teams:,} distinct team names)")

    if args.csv:
        csv_path = out_path.with_suffix(".csv")
        grouped.to_csv(csv_path, index=False)
        print(f"Wrote {csv_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
