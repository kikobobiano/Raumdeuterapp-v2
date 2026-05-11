"""Train xTV baseline HistGradientBoosting on TM transfers × Wyscout parquets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def main() -> int:
    try:
        import joblib
        from scipy.stats import spearmanr
        from sklearn.base import clone
        from sklearn.metrics import mean_absolute_error
    except ImportError as e:
        print(f"Requires joblib scipy sklearn: {e}", file=sys.stderr)
        return 1

    from repo_paths import repo_root
    from transformation.xtv.baseline import (
        build_xy_training,
        fit_baseline,
        sklearn_baseline_pipeline,
        temporal_train_val_masks,
    )

    ROOT = repo_root(Path(__file__))
    repo = ROOT

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cutoff",
        default="2021-07-01",
        help="Temporal cutoff on transfer_date — validation slice for metrics!",
    )
    parser.add_argument(
        "--players-subdir",
        default="data/players/all",
        type=Path,
    )
    parser.add_argument(
        "--out-model",
        type=Path,
        default=repo / "models" / "xtv_baseline_pipeline.joblib",
    )
    parser.add_argument("--max-rows", type=int, default=None, dest="max_rows")
    parser.add_argument("--no-fallback-transfer-mv", action="store_false", dest="fb_mv")
    parser.set_defaults(fb_mv=True)

    args = parser.parse_args()
    cutoff = pd.Timestamp(args.cutoff)

    print("Building training table …")
    X, Y, audit = build_xy_training(
        repo,
        players_rel=args.players_subdir,
        max_rows=args.max_rows,
        valuation_fallback_from_transfer_row=args.fb_mv,
    )
    print(f"  usable rows: {len(X):,}")

    if X.empty:
        print("Abort: zero rows (check transfers, people.csv, valuations, player parquets).", file=sys.stderr)
        return 2

    train_m, val_m = temporal_train_val_masks(audit, cutoff)
    early_ok = int(train_m.sum()) > 6000

    pipe = sklearn_baseline_pipeline(enable_early_stopping=early_ok)
    Xt = X.loc[train_m].reset_index(drop=True)
    Yt = Y.loc[train_m].reset_index(drop=True)

    fit_baseline(pipe, Xt, Yt)

    metrics: dict[str, float | str | int | None] = {"train_rows_fit": len(Yt)}
    if int(val_m.sum()) > 150:
        Xv = X.loc[val_m].reset_index(drop=True)
        Yv = Y.loc[val_m].reset_index(drop=True)
        yhat_v = pipe.predict(Xv)
        metrics["val_mae_log"] = float(mean_absolute_error(Yv, yhat_v))
        fee_v = audit.loc[val_m, "fee_eur"].to_numpy(dtype=np.float64)
        mv_v = audit.loc[val_m, "mv_eur_aligned"].to_numpy(dtype=np.float64)
        xtv_v = np.exp(np.clip(yhat_v, -8.0, 8.0)) * mv_v
        sp, _ = spearmanr(xtv_v, fee_v, nan_policy="omit")
        metrics["val_spearman_xtv_vs_fee"] = float(sp) if np.isfinite(sp) else None

    print("Refitting on full dataset…")
    pipe_full = clone(pipe)
    fit_baseline(pipe_full, X, Y)

    args.out_model.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "pipeline": pipe_full,
            "cutoff_used": str(cutoff.date()),
            "metrics_pre_refit": metrics,
        },
        args.out_model,
    )
    print(f"Wrote {args.out_model}")

    meta_path = args.out_model.with_suffix(".json")
    meta_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(f"Wrote {meta_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
