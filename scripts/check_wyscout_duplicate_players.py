#!/usr/bin/env python3
"""Scan data/players/wyscout/*.csv for duplicate (Wyscout id, Team) rows per file.

Usage:
  python scripts/check_wyscout_duplicate_players.py
  python scripts/check_wyscout_duplicate_players.py --csv-dir /path/to/wyscout
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from repo_paths import repo_root

WYSCOUT_ID_CANDIDATES = ("Wyscout id", "Wyscout ID", "wyscout id", "WyscoutId")
TEAM_CANDIDATES = ("Team", "team", "club", "Club")


def _resolve_columns(df: pd.DataFrame) -> tuple[str, str] | None:
    id_col = next((c for c in WYSCOUT_ID_CANDIDATES if c in df.columns), None)
    team_col = next((c for c in TEAM_CANDIDATES if c in df.columns), None)
    if id_col is None or team_col is None:
        return None
    return id_col, team_col


def analyze_file(path: Path) -> dict[str, int | str | None]:
    """Return summary for one CSV; duplicate_key_count = keys with >1 row."""
    try:
        df = pd.read_csv(path, low_memory=False)
    except Exception as e:
        return {
            "file": path.name,
            "error": str(e),
            "rows": None,
            "duplicate_key_count": None,
            "excess_rows": None,
        }

    cols = _resolve_columns(df)
    if cols is None:
        return {
            "file": path.name,
            "error": "missing Wyscout id and/or Team column",
            "rows": len(df),
            "duplicate_key_count": None,
            "excess_rows": None,
        }

    id_col, team_col = cols
    key = df[[id_col, team_col]].copy()
    key[id_col] = key[id_col].apply(lambda x: x if pd.isna(x) else str(x).strip())
    key[team_col] = key[team_col].apply(
        lambda x: x if pd.isna(x) else str(x).strip()
    )

    counts = key.groupby([id_col, team_col], dropna=False).size()
    dup_mask = counts > 1
    duplicate_key_count = int(dup_mask.sum())
    excess_rows = int((counts[dup_mask] - 1).sum()) if duplicate_key_count else 0

    return {
        "file": path.name,
        "error": None,
        "rows": len(df),
        "duplicate_key_count": duplicate_key_count,
        "excess_rows": excess_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Count (Wyscout id, Team) keys that appear more than once per league CSV."
    )
    parser.add_argument(
        "--csv-dir",
        type=Path,
        default=None,
        help="Directory with Wyscout CSVs (default: <repo>/data/players/wyscout)",
    )
    parser.add_argument(
        "--only-with-dups",
        action="store_true",
        help="Print only files that have at least one duplicated key",
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

    rows_out: list[dict[str, int | str | None]] = []
    for path in paths:
        rows_out.append(analyze_file(path))

    # Console report
    header = f"{'file':<55} {'rows':>8} {'dup_keys':>10} {'excess_rows':>12}  notes"
    print(header)
    print("-" * len(header))
    total_dup_files = 0
    total_dup_keys = 0
    for r in rows_out:
        if r.get("error"):
            note = r["error"]
            if args.only_with_dups:
                continue
            print(
                f"{str(r['file']):<55} {str(r['rows']):>8} {'—':>10} {'—':>12}  { note}"
            )
            continue
        dk = r["duplicate_key_count"] or 0
        if dk:
            total_dup_files += 1
            total_dup_keys += dk
        if args.only_with_dups and dk == 0:
            continue
        er = r["excess_rows"] if r["excess_rows"] is not None else 0
        print(
            f"{str(r['file']):<55} {int(r['rows']):>8} {dk:>10} {int(er):>12}  "
        )

    print("-" * len(header))
    print(
        f"Files scanned: {len(paths)}  "
        f"With duplicate keys: {total_dup_files}  "
        f"Sum of duplicate_key counts: {total_dup_keys}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
