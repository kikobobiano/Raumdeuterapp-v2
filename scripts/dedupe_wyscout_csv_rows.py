#!/usr/bin/env python3
"""Remove duplicate rows in Wyscout league CSVs by (Wyscout id, player name, team).

Resolves columns the same way as check_wyscout_duplicate_players.py, plus a player
name column (default: Player, else Full name).

Usage:
  python scripts/dedupe_wyscout_csv_rows.py
  python scripts/dedupe_wyscout_csv_rows.py --csv-dir /path/to/wyscout --dry-run
  python scripts/dedupe_wyscout_csv_rows.py --keep first
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from repo_paths import repo_root

WYSCOUT_ID_CANDIDATES = ("Wyscout id", "Wyscout ID", "wyscout id", "WyscoutId")
PLAYER_CANDIDATES = ("Player", "player", "Full name", "full_name")
TEAM_CANDIDATES = ("Team", "team", "club", "Club")


def _resolve_key_columns(df: pd.DataFrame) -> tuple[str, str, str] | None:
    id_col = next((c for c in WYSCOUT_ID_CANDIDATES if c in df.columns), None)
    player_col = next((c for c in PLAYER_CANDIDATES if c in df.columns), None)
    team_col = next((c for c in TEAM_CANDIDATES if c in df.columns), None)
    if id_col is None or player_col is None or team_col is None:
        return None
    return id_col, player_col, team_col


def _normalize_id_team(s: pd.Series) -> pd.Series:
    return s.map(lambda x: x if pd.isna(x) else str(x).strip())


def dedupe_dataframe(df: pd.DataFrame, *, keep: str) -> tuple[pd.DataFrame, int]:
    cols = _resolve_key_columns(df)
    if cols is None:
        return df, 0
    id_col, player_col, team_col = cols
    work = df.copy()
    work["_dedupe_id"] = _normalize_id_team(work[id_col])
    work["_dedupe_player"] = _normalize_id_team(work[player_col])
    work["_dedupe_team"] = _normalize_id_team(work[team_col])
    n_before = len(work)
    work = work.drop_duplicates(
        subset=["_dedupe_id", "_dedupe_player", "_dedupe_team"],
        keep=keep,
    )
    work = work.drop(columns=["_dedupe_id", "_dedupe_player", "_dedupe_team"])
    removed = n_before - len(work)
    return work, removed


def process_file(path: Path, *, keep: str, dry_run: bool) -> dict[str, int | str | None]:
    try:
        df = pd.read_csv(path, low_memory=False)
    except Exception as e:
        return {"file": path.name, "error": str(e), "before": None, "after": None, "removed": None}

    if _resolve_key_columns(df) is None:
        return {
            "file": path.name,
            "error": "missing Wyscout id, Player/Full name, and/or Team column",
            "before": len(df),
            "after": None,
            "removed": None,
        }

    before = len(df)
    df_out, removed = dedupe_dataframe(df, keep=keep)
    after = len(df_out)

    if not dry_run and removed:
        df_out.to_csv(path, index=False, encoding="utf-8")

    return {"file": path.name, "error": None, "before": before, "after": after, "removed": removed}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deduplicate Wyscout CSV rows by (Wyscout id, player name, team name)."
    )
    parser.add_argument(
        "--csv-dir",
        type=Path,
        default=None,
        help="Directory with Wyscout CSVs (default: <repo>/data/players/wyscout)",
    )
    parser.add_argument(
        "--keep",
        choices=("first", "last"),
        default="last",
        help="Which duplicate row to keep (default: last).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report only; do not write files.",
    )
    args = parser.parse_args()

    root = repo_root(Path(__file__))
    csv_dir = args.csv_dir or (root / "data" / "players" / "wyscout")
    if not csv_dir.is_dir():
        print(f"Not a directory: {csv_dir}", file=sys.stderr)
        return 1

    paths = sorted(csv_dir.glob("*.csv"))
    if not paths:
        print(f"No CSV files under {csv_dir}", file=sys.stderr)
        return 1

    total_removed = 0
    total_written = 0
    for path in paths:
        r = process_file(path, keep=args.keep, dry_run=args.dry_run)
        if r["error"]:
            print(f"{r['file']}: ERROR — {r['error']}")
            continue
        removed = int(r["removed"] or 0)
        if removed:
            total_removed += removed
            total_written += 1
            flag = " (dry-run)" if args.dry_run else ""
            print(
                f"{r['file']}: {r['before']} -> {r['after']} rows "
                f"(removed {removed}){flag}"
            )

    suffix = " (dry-run, no files changed)" if args.dry_run else ""
    print(
        f"\nFiles with duplicates fixed: {total_written}  "
        f"Total rows removed: {total_removed}{suffix}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
