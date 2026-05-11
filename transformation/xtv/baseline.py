"""Baseline xTV §4.1: Wyscout snapshot + TM log(mv); label ``log(fee) - log(mv)``.

No transfer ``from_/to_`` seller/buyer context (full model deferred).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from transformation.xtv.age import player_age_parquet_row
from transformation.xtv.season import transfer_season_to_start_year
from utils.tm_market_value import load_wyscout_to_tm_players
from utils.tm_market_value import tm_mv_eur_asof_dates_for_tm_players


AREA_INDEX_FEATURES: list[str] = [
    "distribution_index",
    "take_ons_index",
    "assistance_index",
    "finishing_index",
    "aerial_play_index",
    "ground_defense_index",
]

XTV_COLUMN = "x_tv_eur"
TM_MV_COL = "tm_market_value_eur"

WYSCOUT_ID = "Wyscout id"
PARQUET_READ_COLS = list(
    dict.fromkeys(
        AREA_INDEX_FEATURES
        + [
            "league",
            "club",
            "Minutes played",
            WYSCOUT_ID,
            "Birthday",
            "Age",
        ]
    )
)

BASELINE_FEATURE_ORDER: list[str] = AREA_INDEX_FEATURES + ["age", "log_minutes", "log_mv", "lc_key"]


def _tm_to_primary_wyscout(tm_dir: Path) -> pd.DataFrame:
    w = load_wyscout_to_tm_players(tm_dir)
    return w.sort_values(["player_tm_id", "wyscout_id"]).drop_duplicates("player_tm_id", keep="first")


def _best_row_index_for_season(players_all_dir: Path, start_year: int) -> pd.DataFrame:
    """Wyscout-export id × one row — largest ``Minutes played`` in that parquet."""

    pq = players_all_dir / f"{start_year}_all_leagues.parquet"
    if pq.is_file():
        avail: set[str] | None = None
        try:
            import pyarrow.parquet as pq_mod

            avail = set(pq_mod.ParquetFile(pq).schema.names)
        except Exception:
            avail = None
        need = set(PARQUET_READ_COLS + ["Minutes played"])
        usecols = sorted(need) if avail is None else sorted(c for c in need if c in avail)
        try:
            df = pd.read_parquet(pq, columns=usecols if usecols else None)
        except Exception:
            df = pd.read_parquet(pq)
        return df

    csvp = players_all_dir / f"{start_year}_all_leagues.csv"
    if csvp.is_file():
        return pd.read_csv(csvp, usecols=lambda c: c in set(PARQUET_READ_COLS + ["Minutes played"]))

    return pd.DataFrame()


def _index_max_minutes(df: pd.DataFrame) -> pd.DataFrame:
    """``Wyscout id`` uniquely indexed."""

    for c in PARQUET_READ_COLS:
        if c not in df.columns:
            df[c] = np.nan

    mins = pd.to_numeric(df["Minutes played"], errors="coerce").fillna(0.0)
    df = df.assign(_minutes_sort=mins)
    idx = df.groupby(WYSCOUT_ID, sort=False, dropna=True)["_minutes_sort"].idxmax()
    out = df.loc[idx.dropna()]
    del out["_minutes_sort"]
    return out.drop_duplicates(subset=[WYSCOUT_ID], keep="first").set_index(WYSCOUT_ID, verify_integrity=False)


def _feat_row(rec: pd.Series | dict[str, Any], season_y: int, mv_eur: float) -> dict[str, float | str]:
    r = dict(rec) if hasattr(rec, "keys") else rec
    feats: dict[str, float | str] = {}
    for idx_name in AREA_INDEX_FEATURES:
        v = pd.to_numeric(r.get(idx_name), errors="coerce")
        feats[idx_name] = float(v) if pd.notna(v) else np.nan

    mins = pd.to_numeric(r.get("Minutes played"), errors="coerce")
    mraw = float(mins) if pd.notna(mins) else 0.0

    age = player_age_parquet_row(r, int(season_y))
    feats["age"] = float(age) if age is not None else np.nan

    league = str(r.get("league") or "") or "__na__"
    club = str(r.get("club") or "") or "__na__"
    feats["log_minutes"] = float(np.log1p(max(0.0, mraw)))
    feats["lc_key"] = f"{league}::{club}"

    me = float(mv_eur)
    feats["log_mv"] = float(np.log(me)) if me > 0 else np.nan
    return feats


def parquet_feature_matrix(
    panel: pd.DataFrame,
    *,
    mv_eur_series: pd.Series,
    season_start_year: int,
) -> pd.DataFrame:
    """Feature frame for parquet rows (same columns as training ``X``)."""

    if len(panel) != len(mv_eur_series):
        raise ValueError("mv_eur_series must align with panel row count.")
    if not mv_eur_series.index.equals(panel.index):
        mv_eur_series = mv_eur_series.reindex(panel.index)

    rows: list[dict[str, float | str]] = []
    for i, (_, srow) in enumerate(panel.iterrows()):
        mv = float(mv_eur_series.iloc[i]) if pd.notna(mv_eur_series.iloc[i]) else np.nan
        rows.append(_feat_row(srow, season_start_year, mv))
    out = pd.DataFrame(rows, index=panel.index)
    return out[BASELINE_FEATURE_ORDER]


def build_xy_training(
    repo_root: Path,
    *,
    players_rel: Path | None = None,
    max_rows: int | None = None,
    valuation_fallback_from_transfer_row: bool = True,
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    """Joined transfer × Wyscout season × valuations → ``y = log fee - log mv``."""

    tm_dir = repo_root / "data" / "tm"
    players_all = repo_root / (players_rel if players_rel else Path("data/players/all"))
    xfer = tm_dir / "transfers.csv"
    val_csv = tm_dir / "player_valuations.csv"

    if not xfer.is_file():
        raise FileNotFoundError(xfer)
    if not val_csv.is_file():
        raise FileNotFoundError(val_csv)

    tr = pd.read_csv(
        xfer,
        dtype={"player_name": "string"},
        engine="python",
        on_bad_lines="skip",
    )
    need_cols = {"player_id", "transfer_date", "transfer_season", "transfer_fee"}
    miss = need_cols.difference(set(tr.columns))
    if miss:
        raise ValueError(f"transfers.csv missing columns: {sorted(miss)}")

    fe = pd.to_numeric(tr["transfer_fee"], errors="coerce")
    tr = tr.assign(_fee=fe, _dts=pd.to_datetime(tr["transfer_date"], errors="coerce"))
    mask = tr["_fee"].notna() & (tr["_fee"] > 0) & tr["_dts"].notna()
    tr = tr.loc[mask].copy()
    tr["season_y"] = tr["transfer_season"].apply(transfer_season_to_start_year)
    tr = tr.loc[tr["season_y"].notna()].copy()
    tr["season_y"] = tr["season_y"].astype(np.int64)
    tr["_dts"] = tr["_dts"].dt.normalize()
    tr = tr.loc[tr["_dts"].dt.year <= 2060].copy()

    inv = _tm_to_primary_wyscout(tm_dir)
    tr_pid = pd.to_numeric(tr["player_id"], errors="coerce").astype("Int64")
    tr = tr.assign(player_id_tm=tr_pid).dropna(subset=["player_id_tm"])
    tr["player_id_tm"] = tr["player_id_tm"].astype("int64")
    merged = tr.merge(inv, left_on="player_id_tm", right_on="player_tm_id", how="inner")

    mv_asof = tm_mv_eur_asof_dates_for_tm_players(
        merged["player_id_tm"],
        merged["_dts"],
        valuations_csv=val_csv,
    ).to_numpy(dtype=np.float64, copy=False)
    if valuation_fallback_from_transfer_row and "market_value_in_eur" in merged.columns:
        fb = pd.to_numeric(merged["market_value_in_eur"], errors="coerce").to_numpy(dtype=np.float64)
        fb = np.where(np.isnan(fb) | fb <= 0, np.nan, fb)
        mv_asof = np.where(np.isfinite(mv_asof) & mv_asof > 0, mv_asof, fb)

    merged = merged.assign(_mv_use=mv_asof)
    ok_mv = merged["_mv_use"].notna() & (merged["_mv_use"].astype(np.float64) > 0)
    merged = merged.loc[ok_mv].copy()

    if max_rows is not None:
        merged = merged.iloc[: max_rows]

    cache: dict[int, pd.DataFrame] = {}
    feats: list[dict[str, float | str]] = []
    audit_chunks: list[dict[str, Any]] = []
    y_vals: list[float] = []

    for _, row in merged.iterrows():
        wy = int(row["wyscout_id"])
        yr = int(row["season_y"])
        if yr not in cache:
            bulk = _best_row_index_for_season(Path(players_all), yr)
            cache[yr] = pd.DataFrame() if bulk.empty else _index_max_minutes(bulk)

        ply = cache[yr]
        if ply.empty or wy not in ply.index:
            continue

        srow = ply.loc[wy]
        mv = float(row["_mv_use"])
        fdict = _feat_row(srow, yr, mv)
        targ = float(np.log(row["_fee"]) - np.log(mv))

        feats.append(fdict)
        y_vals.append(targ)

        audit_chunks.append(
            {
                "player_id_tm": int(row["player_id_tm"]),
                "wyscout_id": wy,
                "season_start_year": yr,
                "transfer_date": row["_dts"],
                "fee_eur": float(row["_fee"]),
                "mv_eur_aligned": mv,
            }
        )

    if not feats:
        return pd.DataFrame(), pd.Series(dtype=np.float64), pd.DataFrame()

    X_df = pd.DataFrame(feats)[BASELINE_FEATURE_ORDER]
    audit_df = pd.DataFrame(audit_chunks)
    Y = pd.Series(y_vals, dtype=np.float64, index=X_df.index)
    return X_df, Y, audit_df


def sklearn_baseline_pipeline(*, enable_early_stopping: bool = True) -> Any:
    """HistGradientBoosting + median impute + categorical ``lc_key``."""

    try:
        from sklearn.compose import ColumnTransformer
        from sklearn.impute import SimpleImputer
        from sklearn.ensemble import HistGradientBoostingRegressor
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import OrdinalEncoder
    except ImportError as e:
        raise RuntimeError("Training requires sklearn in the active environment.") from e

    num_feats = AREA_INDEX_FEATURES + ["age", "log_minutes", "log_mv"]
    cat_feats = ["lc_key"]

    cat_encoder = OrdinalEncoder(
        handle_unknown="use_encoded_value",
        unknown_value=-1,
        dtype=np.int64,
    )

    pre = ColumnTransformer(
        [
            ("num", SimpleImputer(strategy="median"), num_feats),
            ("cat", Pipeline([("ord", cat_encoder)]), cat_feats),
        ],
        remainder="drop",
        sparse_threshold=0.0,
    )

    n_num = len(num_feats)
    n_cat = len(cat_feats)
    cat_idx = list(range(n_num, n_num + n_cat))

    gb_params: dict[str, Any] = dict(
        categorical_features=cat_idx,
        max_depth=12,
        max_iter=380,
        learning_rate=0.05,
        l2_regularization=1e-3,
        min_samples_leaf=20,
        random_state=42,
    )
    if enable_early_stopping:
        gb_params |= dict(
            early_stopping=True,
            validation_fraction=0.1,
            n_iter_no_change=18,
        )
    else:
        gb_params["early_stopping"] = False

    gb = HistGradientBoostingRegressor(**gb_params)

    return Pipeline([("prep", pre), ("model", gb)])


def fit_baseline(pipe: Any, X: pd.DataFrame, Y: pd.Series) -> Any:
    if X.empty:
        raise ValueError("No training rows after joins.")
    if len(Y) < 800:
        import warnings

        warnings.warn(f"Thin training rows ({len(X)}); baseline may be unreliable.", stacklevel=1)
    X = X[BASELINE_FEATURE_ORDER].copy()
    for c in AREA_INDEX_FEATURES + ["age", "log_minutes", "log_mv"]:
        X[c] = pd.to_numeric(X[c], errors="coerce")
    X["lc_key"] = X["lc_key"].astype(str).fillna("__na__")
    pipe.fit(X, Y)
    return pipe


def temporal_train_val_masks(
    audit_df: pd.DataFrame,
    cutoff: pd.Timestamp,
) -> tuple[np.ndarray, np.ndarray]:
    ts = pd.to_datetime(audit_df["transfer_date"], errors="coerce")
    train_mask = ts < cutoff
    val_mask = ~train_mask & ts.notna()
    return train_mask.to_numpy(dtype=bool), val_mask.to_numpy(dtype=bool)


def predict_xtv_parquet(pipe: Any, panel: pd.DataFrame, mv_eur: pd.Series, season_y: int) -> pd.Series:
    """``exp(pipe.predict(X)) * mv_eur`` (aligned ``panel.index``)."""

    Xmat = parquet_feature_matrix(panel, mv_eur_series=mv_eur, season_start_year=season_y)
    Xmat = Xmat.astype({c: np.float64 for c in AREA_INDEX_FEATURES + ["age", "log_minutes", "log_mv"]}, errors="ignore")
    Xmat.loc[:, "lc_key"] = Xmat["lc_key"].astype(str).fillna("__na__")

    xp = pipe.predict(Xmat).astype(np.float64)
    mv_arr = mv_eur.reindex(panel.index).astype(np.float64).to_numpy()
    xv = np.full(len(mv_arr), np.nan, dtype=np.float64)
    ok = np.isfinite(mv_arr) & (mv_arr > 0) & np.isfinite(xp)
    xv[ok] = np.exp(np.clip(xp[ok], -8.0, 8.0)) * mv_arr[ok]
    np.clip(xv, 0.0, 1e11, out=xv)

    return pd.Series(xv, index=panel.index)
