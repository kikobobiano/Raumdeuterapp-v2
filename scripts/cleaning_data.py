"""
Clean Wyscout player CSVs produced by scripts/download_data.py.

- Rewrites cells that look like Python list literals, e.g. "['LWF', 'LW']" -> "LWF, LW"
  (empty list [] becomes an empty string).

Reads and writes UTF-8 CSVs under <repo>/data/players/wyscout/.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pandas as pd

from repo_paths import repo_root

OUT_DIR = repo_root(Path(__file__)) / "data" / "players" / "wyscout"


def flatten_list_like_cell(val: object) -> object:
    if pd.isna(val):
        return val
    if not isinstance(val, str):
        return val
    s = val.strip()
    if not s.startswith("["):
        return val
    try:
        parsed = ast.literal_eval(s)
    except (ValueError, SyntaxError):
        return val
    if not isinstance(parsed, list):
        return val
    return ", ".join(str(x).strip() for x in parsed)


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in df.columns:
        df[col] = df[col].map(flatten_list_like_cell)
    return df


def clean_csv_file(path: Path) -> int:
    df = pd.read_csv(path, encoding="utf-8", low_memory=False)
    df = clean_dataframe(df)
    df.to_csv(path, index=False, encoding="utf-8")
    return len(df)


def main() -> None:
    if not OUT_DIR.is_dir():
        print(f"Directory not found: {OUT_DIR}", file=sys.stderr)
        raise SystemExit(1)

    csv_paths = sorted(OUT_DIR.glob("*.csv"))
    if not csv_paths:
        print(f"No CSV files in {OUT_DIR}")
        return

    for path in csv_paths:
        n = clean_csv_file(path)
        print(f"{path.name}: {n} rows")


if __name__ == "__main__":
    main()
