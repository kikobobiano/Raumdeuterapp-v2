"""Build a filtered player_valuations file for players that appear in Wyscout CSVs.

Output columns: ``wyscout_id``, ``key_transfermarkt``, ``date``, ``market_value_in_eur``.

The Wyscout export column ``Wyscout id`` usually matches **key_soccerway** in Reep
``people.csv`` more often than **key_wyscout**; the filter maps either id to
``key_transfermarkt`` (same idea as ``enrich_with_tm.py``).

Inputs:
  data/tm/people.csv — ``key_transfermarkt`` plus ``key_wyscout`` / ``key_soccerway``
  data/tm/player_valuations.csv
  data/players/wyscout/*.csv

Outputs:
  data/tm/player_valuations_filtered.csv  (always)
  data/tm/player_valuations_filtered.parquet (when --parquet)

Filter: keep ``player_id`` (TM) whose mapped export id appears in the chosen Wyscout
file set (``--mode union`` by default, ``intersection`` across files if needed).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from repo_paths import repo_root

REPO_ROOT = repo_root(Path(__file__))
TM_DIR = REPO_ROOT / "data" / "tm"
WYSCOUT_DIR = REPO_ROOT / "data" / "players" / "wyscout"


def _wyscout_ids_per_file() -> list[set[int]]:
    """Set of Wyscout ids per CSV (one set per file)."""
    out: list[set[int]] = []
    for path in sorted(WYSCOUT_DIR.glob("*.csv")):
        try:
            df = pd.read_csv(path, usecols=["Wyscout id"])
        except (ValueError, KeyError):
            continue
        ids = pd.to_numeric(df["Wyscout id"], errors="coerce").dropna().astype("int64")
        if not ids.empty:
            out.append(set(ids.tolist()))
    return out


def _intersect_wyscout_ids(per_file: list[set[int]]) -> set[int]:
    if not per_file:
        return set()
    common: set[int] = set(per_file[0])
    for s in per_file[1:]:
        common &= s
    return common


def _union_wyscout_ids(per_file: list[set[int]]) -> set[int]:
    out: set[int] = set()
    for s in per_file:
        out |= s
    return out


def _mapping_for_export_ids(wyscout_ids: set[int]) -> pd.DataFrame:
    """Rows ``wyscout_id`` (id as in Wyscout CSV) ↔ ``key_transfermarkt`` for ids in the set."""
    people = pd.read_csv(
        TM_DIR / "people.csv",
        usecols=["key_wyscout", "key_soccerway", "key_transfermarkt"],
        engine="python",
        on_bad_lines="skip",
    )
    people["ksw"] = pd.to_numeric(people["key_wyscout"], errors="coerce")
    people["ksc"] = pd.to_numeric(people["key_soccerway"], errors="coerce")
    people["ktm"] = pd.to_numeric(people["key_transfermarkt"], errors="coerce")
    people = people.dropna(subset=["ktm"])
    ms = people["ksc"].isin(wyscout_ids)
    mw = people["ksw"].isin(wyscout_ids)
    sub = people[ms | mw].copy()
    if sub.empty:
        return pd.DataFrame(columns=["wyscout_id", "key_transfermarkt"])

    # Prefer Soccerway id when it appears in exports (same column name "Wyscout id" in CSV)
    sub["wyscout_id"] = sub["ksc"].where(ms, sub["ksw"]).astype("int64")
    sub["key_transfermarkt"] = sub["ktm"].astype("int64")
    out = sub[["wyscout_id", "key_transfermarkt"]].drop_duplicates(
        subset=["key_transfermarkt"], keep="first"
    )
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=("intersection", "union"),
        default="union",
        help=(
            "union (default; player in any Wyscout CSV) | "
            "intersection (player in every CSV — usually returns 0 since no player "
            "plays every league/season)"
        ),
    )
    parser.add_argument("--parquet", action="store_true", help="Also write .parquet")
    parser.add_argument(
        "--out-stem",
        default="player_valuations_filtered",
        help="Output filename stem (under data/tm/)",
    )
    args = parser.parse_args()

    if not (TM_DIR / "player_valuations.csv").exists():
        print(f"Missing {TM_DIR / 'player_valuations.csv'}", file=sys.stderr)
        return 1
    if not WYSCOUT_DIR.exists():
        print(f"Missing {WYSCOUT_DIR}", file=sys.stderr)
        return 1

    print("Scanning Wyscout files for player ids…")
    per_file = _wyscout_ids_per_file()
    print(f"  {len(per_file)} files scanned")

    wyscout_ids = (
        _intersect_wyscout_ids(per_file)
        if args.mode == "intersection"
        else _union_wyscout_ids(per_file)
    )
    print(f"  {len(wyscout_ids):,} export player ids in {args.mode}")

    mapping = _mapping_for_export_ids(wyscout_ids)
    print(f"  {len(mapping):,} people rows mapped to key_transfermarkt (wyscout + soccerway)")

    if mapping.empty:
        print("No mapped players. Aborting.", file=sys.stderr)
        return 2

    print("Reading player_valuations.csv…")
    # The C engine can hit 'list index out of range' on this file when warnings
    # are emitted; the python engine handles it cleanly.
    valuations = pd.read_csv(
        TM_DIR / "player_valuations.csv",
        usecols=["player_id", "date", "market_value_in_eur"],
        engine="python",
    )
    valuations["player_id"] = pd.to_numeric(valuations["player_id"], errors="coerce").astype("Int64")

    keep_ids = set(mapping["key_transfermarkt"].tolist())
    filtered = valuations[valuations["player_id"].isin(keep_ids)].copy()
    print(f"  {len(filtered):,} valuation rows after player_id filter")

    out = filtered.merge(
        mapping.rename(columns={"key_transfermarkt": "player_id"}),
        on="player_id",
        how="left",
    )
    out = out.rename(columns={"player_id": "key_transfermarkt"})
    out = out[["wyscout_id", "key_transfermarkt", "date", "market_value_in_eur"]]
    out = out.sort_values(["wyscout_id", "date"]).reset_index(drop=True)

    csv_path = TM_DIR / f"{args.out_stem}.csv"
    out.to_csv(csv_path, index=False)
    print(f"Wrote {csv_path} ({len(out):,} rows)")

    if args.parquet:
        parquet_path = TM_DIR / f"{args.out_stem}.parquet"
        out.to_parquet(parquet_path, index=False, compression="snappy")
        print(f"Wrote {parquet_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
