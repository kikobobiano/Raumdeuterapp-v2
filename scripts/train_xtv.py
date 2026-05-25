"""Train the xTV v2 regressor on TM transfers × Wyscout season parquets."""

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

    ROOT = repo_root(Path(__file__))

    from transformation.xtv import (
        FEATURE_ORDER,
        build_xy_training,
        fit,
        recency_sample_weight,
        sklearn_pipeline,
        temporal_train_val_masks,
    )
    from transformation.xtv.model import LOG_FEE_MAX, LOG_FEE_MIN
    from transformation.xtv.dest_marginal import build_dest_prior, save_prior
    from transformation.xtv.id_mapping import mapping_coverage

    parser = argparse.ArgumentParser()
    parser.add_argument("--cutoff", default="2023-07-01")
    parser.add_argument("--out-model", type=Path, default=ROOT / "models" / "xtv_v2.joblib")
    parser.add_argument("--fuzzy-threshold", type=int, default=92)
    parser.add_argument("--max-rows", type=int, default=None)
    parser.add_argument("--no-refresh-mappings", dest="refresh", action="store_false")
    parser.set_defaults(refresh=True)
    args = parser.parse_args()

    cutoff = pd.Timestamp(args.cutoff)

    print("Building xTV training set …")
    X, y_fee, y_ratio, audit = build_xy_training(
        ROOT,
        fuzzy_threshold=args.fuzzy_threshold,
        max_rows=args.max_rows,
        refresh_mappings=args.refresh,
    )
    print(f"  rows: {len(X):,}  (with TM mv: {int(y_ratio.notna().sum()):,})")
    if X.empty:
        print("Abort: 0 training rows.", file=sys.stderr)
        return 2

    cov = mapping_coverage(
        pd.read_parquet(ROOT / "data" / "tm" / "xtv_id_mapping.parquet"),
        ROOT / "data" / "tm" / "transfers.csv",
    )
    print(
        "  id mapping coverage: rows {coverage_rows:.1%} "
        "({transfer_rows_matched}/{transfer_rows}), unique {coverage_unique:.1%} "
        "({unique_players_matched}/{unique_players}), fuzzy {fuzzy_rows}".format(**cov)
    )

    print("Building destination prior …")
    prior = build_dest_prior(X)
    save_prior(prior, ROOT / "data" / "tm")
    print(f"  prior buckets: {prior['origin_bucket'].nunique()} (incl. global)")

    train_m, val_m = temporal_train_val_masks(audit, cutoff)
    has_mv = y_ratio.notna().to_numpy()

    # --- Head 1: ratio model (log(fee/mv) on rows with TM mv) ---
    train_r = train_m & has_mv
    val_r = val_m & has_mv
    early_r = int(train_r.sum()) > 4000
    pipe_ratio = sklearn_pipeline(enable_early_stopping=early_r)
    Xt_r = X.loc[train_r].reset_index(drop=True)
    yt_r = y_ratio.loc[train_r].reset_index(drop=True)
    wt_r = recency_sample_weight(Xt_r["transfer_year"].to_numpy())
    fit(pipe_ratio, Xt_r, yt_r, sample_weight=wt_r)

    # --- Head 2: absolute fee model (log(fee) on all rows) ---
    early_a = int(train_m.sum()) > 6000
    pipe_abs = sklearn_pipeline(enable_early_stopping=early_a)
    Xt_a = X.loc[train_m].reset_index(drop=True)
    yt_a = y_fee.loc[train_m].reset_index(drop=True)
    wt_a = recency_sample_weight(Xt_a["transfer_year"].to_numpy())
    fit(pipe_abs, Xt_a, yt_a, sample_weight=wt_a)

    metrics: dict[str, float | int | None] = {
        "train_rows_ratio": int(train_r.sum()),
        "train_rows_abs": int(train_m.sum()),
    }

    if int(val_m.sum()) > 100:
        Xv = X.loc[val_m].reset_index(drop=True)
        yv_fee = y_fee.loc[val_m].reset_index(drop=True)
        has_mv_v = y_ratio.loc[val_m].notna().to_numpy()
        mv_v = np.exp(yv_fee.to_numpy(dtype=np.float64) - y_ratio.loc[val_m].fillna(0.0).to_numpy())
        # fee/exp(log(fee/mv)) = mv when has_mv else NaN/garbage — guard
        mv_v = np.where(has_mv_v, mv_v, np.nan)

        yhat_r = pipe_ratio.predict(Xv)
        yhat_a = pipe_abs.predict(Xv)
        fee_hat = np.where(
            has_mv_v,
            mv_v * np.exp(np.clip(yhat_r, np.log(0.1), np.log(4.0))),
            np.exp(np.clip(yhat_a, LOG_FEE_MIN, LOG_FEE_MAX)),
        )
        fee_actual = np.exp(yv_fee.to_numpy(dtype=np.float64))
        metrics["val_rows"] = int(val_m.sum())
        metrics["val_mae_log"] = float(
            mean_absolute_error(np.log(fee_actual), np.log(np.maximum(fee_hat, 1.0)))
        )
        sp, _ = spearmanr(fee_hat, fee_actual, nan_policy="omit")
        metrics["val_spearman_xtv_vs_fee"] = float(sp) if np.isfinite(sp) else None
        ratio = fee_hat / fee_actual
        metrics["val_within_50pct"] = float(((ratio >= 0.5) & (ratio <= 2.0)).mean())
        metrics["val_within_100pct"] = float(((ratio >= 0.25) & (ratio <= 4.0)).mean())

    print("Metrics:", json.dumps(metrics, indent=2, default=str))

    print("Refitting on full dataset …")
    pipe_ratio_full = clone(pipe_ratio)
    Xf_r = X.loc[has_mv].reset_index(drop=True)
    yf_r = y_ratio.loc[has_mv].reset_index(drop=True)
    fit(pipe_ratio_full, Xf_r, yf_r, sample_weight=recency_sample_weight(Xf_r["transfer_year"].to_numpy()))

    pipe_abs_full = clone(pipe_abs)
    fit(pipe_abs_full, X, y_fee, sample_weight=recency_sample_weight(X["transfer_year"].to_numpy()))

    args.out_model.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "pipeline_ratio": pipe_ratio_full,
            "pipeline_abs": pipe_abs_full,
            "feature_order": FEATURE_ORDER,
            "cutoff_used": str(cutoff.date()),
            "metrics_pre_refit": metrics,
        },
        args.out_model,
    )
    print(f"Wrote {args.out_model}")
    meta = args.out_model.with_suffix(".json")
    meta.write_text(json.dumps({**metrics, "cutoff": str(cutoff.date())}, indent=2), encoding="utf-8")
    print(f"Wrote {meta}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
