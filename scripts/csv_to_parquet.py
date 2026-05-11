"""Convert Wyscout season CSVs to Parquet (snappy), then remove the CSVs.

Run from project root:
    python scripts/csv_to_parquet.py

Converts every *_all_leagues.csv in data/players/all/ to .parquet alongside it,
then removes that CSV immediately after a successful write. Use this when ingesting
new CSV drops from Wyscout; the app reads Parquet only at runtime.
"""
from __future__ import annotations

import glob
import os
import sys
from pathlib import Path

import pandas as pd

from repo_paths import repo_root

INPUT_DIR = os.fspath(repo_root(Path(__file__)) / "data" / "players" / "all")


def convert_all(input_dir: str = INPUT_DIR) -> None:
    csv_files = sorted(glob.glob(os.path.join(input_dir, "*_all_leagues.csv")))
    if not csv_files:
        print(f"No CSV files found in {input_dir!r}")
        sys.exit(1)

    converted = 0
    for csv_path in csv_files:
        parquet_path = csv_path.replace(".csv", ".parquet")
        print(f"  {os.path.basename(csv_path)} -> {os.path.basename(parquet_path)} ... ", end="")
        df = pd.read_csv(csv_path)
        df.to_parquet(parquet_path, engine="pyarrow", compression="snappy", index=False)
        csv_mb = os.path.getsize(csv_path) / 1_048_576
        os.remove(csv_path)
        pq_mb = os.path.getsize(parquet_path) / 1_048_576
        pct = (pq_mb / csv_mb * 100) if csv_mb else 0
        print(f"{csv_mb:.1f} MB -> {pq_mb:.1f} MB  ({pct:.0f}%), CSV removed")
        converted += 1

    print(f"\nConverted {converted} files.")


if __name__ == "__main__":
    convert_all()
