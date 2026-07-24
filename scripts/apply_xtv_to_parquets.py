"""Attach ``x_tv_eur`` to the latest season ``{Y}_all_leagues.parquet``.

For the season parquet:

1. Compute TM market value as-of the season reference date via
   :func:`utils.tm_market_value.infer_tm_market_value_eur` (column
   ``tm_market_value_eur``).
2. Build the per-row feature matrix (origin league / club tier filled from the
   parquet `league` + club mapping; destination cols zero-init).
3. Sample N destination (league_power, club_tier) pairs per row from the
   training-time destination prior and average the model's exp(log-fee)
   predictions — that becomes ``x_tv_eur``.
4. Write atomically: temp parquet next to the file → ``Path.replace``.

Defaults overwrite in place per project spec; ``--sidecar`` writes
``{Y}_all_leagues_xtv.parquet`` instead.
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd


_YEAR_PQ = re.compile(r"^(20\d{2})_all_leagues\.parquet$")

CURRENT_SEASON_YEARS: tuple[int, ...] = (2026,2025,2024,2023,2022,2021,2020,2019,2018,2016,2015)


def _mv_for_parquet(
    wyscout_ids: pd.Series,
    season_y: int,
    wy_to_tm: pd.Series,
    valuations: pd.DataFrame,
) -> pd.Series:
    """Backward as-of MV using the project ID mapping (incl. fuzzy fallback)."""

    from utils.tm_market_value import season_reference_date

    wy = pd.to_numeric(wyscout_ids, errors="coerce").astype("Int64")
    tm = wy.map(wy_to_tm).astype("Int64")
    ref = pd.Timestamp(season_reference_date(int(season_y)))
    left = pd.DataFrame(
        {
            "_sort": np.arange(len(wy)),
            "player_id": tm.astype("Int64"),
            "ref_dt": pd.Series([ref] * len(wy), dtype="datetime64[ns]"),
        }
    )
    known = (
        left.dropna(subset=["player_id"])
        .assign(player_id=lambda d: d["player_id"].astype("int64"))
        .sort_values("ref_dt", kind="mergesort")
    )
    v = valuations.rename(columns={"val_dt": "_val_snap"}).sort_values("_val_snap", kind="mergesort")
    merged = pd.merge_asof(
        known,
        v,
        left_on="ref_dt",
        right_on="_val_snap",
        by="player_id",
        direction="backward",
    )
    out = pd.Series(np.nan, index=np.arange(len(wy)), dtype="float64")
    if len(merged):
        out.iloc[np.asarray(merged["_sort"].astype("int64"))] = merged["market_value_in_eur"].astype(
            "float64"
        ).to_numpy()
    return pd.Series(out.to_numpy(dtype=np.float64), index=wyscout_ids.index)


def main() -> int:
    try:
        import joblib
    except ImportError as e:
        print(f"Requires joblib: {e}", file=sys.stderr)
        return 1

    from repo_paths import repo_root

    ROOT = repo_root(Path(__file__))

    from transformation.xtv import (
        TM_MV_COL,
        XTV_COLUMN,
        build_parquet_features,
        build_peer_mv_table,
        impute_mv_from_peers,
        predict_xtv_with_marginal,
    )
    from transformation.xtv.club_ctx import (
        club_tier_table,
        load_clubs,
        load_parquet_club_mapping,
        tier_for_parquet_clubs,
    )
    from transformation.xtv.dest_marginal import (
        DEFAULT_N_SAMPLES,
        load_prior,
        sample_destinations,
    )
    from transformation.xtv.id_mapping import load_mapping
    from utils.tm_market_value import (
        load_tm_valuations_raw,
        season_reference_date,
    )

    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, default=ROOT / "models" / "xtv_v2.joblib")
    parser.add_argument("--players-dir", type=Path, default=ROOT / "data" / "players" / "all")
    parser.add_argument("--tm-dir", type=Path, default=ROOT / "data" / "tm")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--sidecar",
        action="store_true",
        help="Write to ``{Y}_all_leagues_xtv.parquet`` rather than overwrite.",
    )
    parser.add_argument("--n-samples", type=int, default=DEFAULT_N_SAMPLES)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    if not args.model.is_file():
        print(f"Missing model {args.model}", file=sys.stderr)
        return 2

    blob = joblib.load(args.model)
    if isinstance(blob, dict) and "pipeline_ratio" in blob:
        pipe_ratio = blob["pipeline_ratio"]
        pipe_abs = blob["pipeline_abs"]
    else:
        pipe_ratio = blob["pipeline"] if isinstance(blob, dict) and "pipeline" in blob else blob
        pipe_abs = None  # legacy single-head fallback

    prior = load_prior(args.tm_dir)
    clubs = load_clubs(args.tm_dir)
    tier_tbl = club_tier_table(clubs)
    club_map = load_parquet_club_mapping(args.tm_dir)
    id_map = load_mapping(args.tm_dir)
    _source_priority = {"exact_soccerway": 0, "exact_wyscout": 1, "bio_exact": 2, "fuzzy": 3}
    wy_to_tm = (
        id_map.dropna(subset=["wyscout_id", "player_tm_id"])
        .astype({"wyscout_id": "int64", "player_tm_id": "int64"})
        .assign(_pri=lambda d: d["source"].map(_source_priority).fillna(9))
        .sort_values("_pri")
        .drop_duplicates("wyscout_id", keep="first")
        .set_index("wyscout_id")["player_tm_id"]
    )
    valuations = load_tm_valuations_raw(args.tm_dir / "player_valuations.csv")
    valuations = valuations.sort_values(["player_id", "val_dt"], kind="mergesort")

    print("Building peer MV table …")
    peer_tbl = build_peer_mv_table(args.players_dir)
    print(f"  peer buckets: {len(peer_tbl)}")

    files = [
        args.players_dir / f"{year}_all_leagues.parquet" for year in CURRENT_SEASON_YEARS
    ]
    if not any(p.is_file() for p in files):
        print(f"No parquets for {CURRENT_SEASON_YEARS} under {args.players_dir}", file=sys.stderr)
        return 3

    rng = np.random.default_rng(args.seed)

    for pq in files:
        if not pq.is_file():
            print(f"Skipping {pq.name}: not found")
            continue
        m = _YEAR_PQ.match(pq.name)
        if not m:
            continue
        year = int(m.group(1))

        if args.dry_run:
            print(f"[dry-run] would process {pq.name} season={year}")
            continue

        df = pd.read_parquet(pq)
        if "Wyscout id" not in df.columns:
            print(f"skip {pq.name} (no Wyscout id)")
            continue

        mv = _mv_for_parquet(df["Wyscout id"], year, wy_to_tm, valuations)
        tier = tier_for_parquet_clubs(df["club"] if "club" in df.columns else pd.Series([], dtype=str),
                                      club_map, tier_tbl) if "club" in df.columns else pd.Series(
            np.full(len(df), 3, dtype=np.int64), index=df.index
        )
        tier.index = df.index
        mv.index = df.index

        # Fill missing TM MV with peer-group median (position × age × league × PI).
        mv_imputed = impute_mv_from_peers(mv, df, peer_tbl, season_y=year)
        mv_imputed.index = df.index

        base = build_parquet_features(df, season_y=year, mv_eur=mv_imputed, tier_for_clubs=tier)
        dest_power, dest_tier = sample_destinations(
            base["origin_league_power"].to_numpy(), prior, n_samples=args.n_samples, rng=rng
        )

        mv_arr = mv_imputed.to_numpy(dtype=np.float64)
        xtv = predict_xtv_with_marginal(
            pipe_ratio,
            base,
            dest_power=dest_power,
            dest_tier=dest_tier,
            mv_eur=mv_arr,
            pipe_abs=pipe_abs,
        )

        from utils.config import LEAGUES_WITHOUT_XTV

        if "league" in df.columns and LEAGUES_WITHOUT_XTV:
            ineligible = df["league"].astype(str).str.strip().isin(LEAGUES_WITHOUT_XTV)
            xtv = np.where(ineligible.to_numpy(), np.nan, xtv)

        df_out = df.copy()
        df_out[TM_MV_COL] = mv.to_numpy(dtype=np.float64)
        df_out[XTV_COLUMN] = xtv

        out_path = pq.with_name(f"{pq.stem}_xtv.parquet") if args.sidecar else pq

        tmp = Path(tempfile.mkstemp(prefix=f".{pq.stem}_xtv_", suffix=".parquet", dir=pq.parent)[1])
        try:
            df_out.to_parquet(tmp, index=False, compression="snappy")
            tmp.replace(out_path)
        finally:
            if tmp.exists():
                tmp.unlink(missing_ok=True)

        n_ok = int(np.isfinite(df_out[XTV_COLUMN].astype(np.float64)).sum())
        n_mv = int(np.isfinite(df_out[TM_MV_COL].astype(np.float64)).sum())
        print(
            f"  {out_path.name}: xTV {n_ok:,}/{len(df_out):,} non-null, "
            f"TM mv {n_mv:,}/{len(df_out):,} non-null"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
