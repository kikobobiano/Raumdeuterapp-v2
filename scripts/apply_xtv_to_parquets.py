"""Write ``x_tv_eur`` onto each ``{Y}_all_leagues.parquet`` using a trained baseline."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd


_YEAR_PQ = re.compile(r"^(20\d{2})_all_leagues\.parquet$")


def main() -> int:
    try:
        import joblib
    except ImportError as e:
        print(f"Requires joblib: {e}", file=sys.stderr)
        return 1

    from repo_paths import repo_root

    from transformation.xtv.baseline import (
        TM_MV_COL,
        XTV_COLUMN,
        predict_xtv_parquet,
    )
    from utils.tm_market_value import infer_tm_market_value_eur

    ROOT = repo_root(Path(__file__))

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model",
        type=Path,
        default=ROOT / "models" / "xtv_baseline_pipeline.joblib",
    )
    parser.add_argument("--players-dir", type=Path, default=ROOT / "data" / "players" / "all")
    parser.add_argument("--tm-dir", type=Path, default=ROOT / "data" / "tm")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace each ``*_all_leagues.parquet`` in place (default writes ``*_xtv.parquet`` sidecar).",
    )
    args = parser.parse_args()

    if not args.model.is_file():
        print(f"Missing model {args.model}", file=sys.stderr)
        return 2

    blob = joblib.load(args.model)
    pipe = blob["pipeline"] if isinstance(blob, dict) and "pipeline" in blob else blob

    files = sorted(args.players_dir.glob("*_all_leagues.parquet"))
    if not files:
        print(f"No parquets under {args.players_dir}", file=sys.stderr)
        return 3

    for pq in files:
        m = _YEAR_PQ.match(pq.name)
        if not m:
            continue
        year = int(m.group(1))

        if args.dry_run:
            print(f"[dry-run] would process {pq.name} season={year}")
            continue

        df = pd.read_parquet(pq)
        if "Wyscout id" not in df.columns:
            print(f"skip {pq.name} (no Wyscout id column)")
            continue

        mv = infer_tm_market_value_eur(df["Wyscout id"], year, tm_dir=args.tm_dir)
        df_out = df.copy()
        df_out[TM_MV_COL] = mv
        df_out[XTV_COLUMN] = predict_xtv_parquet(pipe, df_out, mv_eur=mv, season_y=year)

        out_path = pq if args.overwrite else pq.with_name(f"{pq.stem}_xtv.parquet")

        # When not overwriting, optionally avoid clobbering accidental _xtv name collision
        df_out.to_parquet(out_path, index=False, compression="snappy")

        n_ok = df_out[XTV_COLUMN].notna().sum()
        print(f"  {out_path.name}: wrote {XTV_COLUMN} non-null count {n_ok:,} / {len(df_out):,}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
