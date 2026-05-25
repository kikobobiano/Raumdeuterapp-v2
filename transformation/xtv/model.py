"""xTV v2 feature engineering, training matrix, and inference helpers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from transformation.xtv.age import player_age_parquet_row
from transformation.xtv.club_ctx import (
    build_parquet_club_mapping,
    club_tier_table,
    league_power_for_club_id,
    load_clubs,
    load_parquet_club_mapping,
    save_parquet_club_mapping,
    tier_for_club_id,
)
from transformation.xtv.id_mapping import build_tm_to_wyscout_mapping, load_mapping, save_mapping
from transformation.xtv.season import transfer_season_to_start_year
from utils.config import LEAGUE_POWER_BASE
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

FEATURE_ORDER: list[str] = AREA_INDEX_FEATURES + [
    "age",
    "log_minutes",
    "log_mv",
    "has_mv",
    "origin_league_power",
    "dest_league_power",
    "origin_club_tier",
    "dest_club_tier",
    "transfer_year",
    "position_group",
]

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
            "Primary position",
            "performance_index",
            TM_MV_COL,
        ]
    )
)

FEE_MIN_EUR = 500_000.0
FEE_MAX_EUR = 200_000_000.0
LOG_FEE_MIN = float(np.log(FEE_MIN_EUR))
LOG_FEE_MAX = float(np.log(FEE_MAX_EUR))

_POSITION_GROUPS: dict[str, int] = {
    "GK": 0,
    "CB": 1,
    "DF": 1,
    "LB": 2,
    "RB": 2,
    "LWB": 2,
    "RWB": 2,
    "WB": 2,
    "DMF": 3,
    "CMF": 4,
    "CM": 4,
    "AMF": 5,
    "AM": 5,
    "LW": 6,
    "RW": 6,
    "LWF": 6,
    "RWF": 6,
    "WF": 6,
    "CF": 7,
    "ST": 7,
    "FW": 7,
    "STR": 7,
}


def position_group_from_str(pos: str | None) -> int:
    if not pos:
        return 4
    token = str(pos).split("/")[0].strip().upper()
    return _POSITION_GROUPS.get(token, 4)


def encode_position_group(group: int) -> int:
    return int(group)


def _league_power(name: str | None) -> float:
    if not name:
        return float("nan")
    return float(LEAGUE_POWER_BASE.get(str(name).strip(), np.nan))


def _best_row_index_for_season(players_all_dir: Path, start_year: int) -> pd.DataFrame:
    pq = players_all_dir / f"{start_year}_all_leagues.parquet"
    if not pq.is_file():
        return pd.DataFrame()
    try:
        import pyarrow.parquet as pq_mod

        avail = set(pq_mod.ParquetFile(pq).schema.names)
        usecols = [c for c in PARQUET_READ_COLS if c in avail]
        df = pd.read_parquet(pq, columns=usecols or None)
    except Exception:
        df = pd.read_parquet(pq)
    return df


def _index_max_minutes(df: pd.DataFrame) -> pd.DataFrame:
    for c in PARQUET_READ_COLS:
        if c not in df.columns:
            df[c] = np.nan
    mins = pd.to_numeric(df["Minutes played"], errors="coerce").fillna(0.0)
    df = df.assign(_minutes_sort=mins)
    idx = df.groupby(WYSCOUT_ID, sort=False, dropna=True)["_minutes_sort"].idxmax()
    out = df.loc[idx.dropna()]
    del out["_minutes_sort"]
    return out.drop_duplicates(subset=[WYSCOUT_ID], keep="first").set_index(WYSCOUT_ID, verify_integrity=False)


def _feat_row(
    rec: pd.Series | dict[str, Any],
    *,
    season_y: int,
    mv_eur: float,
    origin_power: float,
    dest_power: float,
    origin_tier: int,
    dest_tier: int,
    transfer_year: int,
) -> dict[str, float | int]:
    r = dict(rec) if hasattr(rec, "keys") else rec
    feats: dict[str, float | int] = {}
    for idx_name in AREA_INDEX_FEATURES:
        v = pd.to_numeric(r.get(idx_name), errors="coerce")
        feats[idx_name] = float(v) if pd.notna(v) else np.nan

    mins = pd.to_numeric(r.get("Minutes played"), errors="coerce")
    mraw = float(mins) if pd.notna(mins) else 0.0
    age = player_age_parquet_row(r, int(season_y))
    feats["age"] = float(age) if age is not None else np.nan
    feats["log_minutes"] = float(np.log1p(max(0.0, mraw)))

    me = float(mv_eur) if np.isfinite(mv_eur) and mv_eur > 0 else np.nan
    feats["has_mv"] = 1.0 if np.isfinite(me) and me > 0 else 0.0
    feats["log_mv"] = float(np.log(me)) if np.isfinite(me) and me > 0 else 0.0

    feats["origin_league_power"] = float(origin_power) if np.isfinite(origin_power) else np.nan
    feats["dest_league_power"] = float(dest_power) if np.isfinite(dest_power) else np.nan
    feats["origin_club_tier"] = int(origin_tier)
    feats["dest_club_tier"] = int(dest_tier)
    feats["transfer_year"] = int(transfer_year)
    feats["position_group"] = int(position_group_from_str(r.get("Primary position")))
    return feats


def _rows_to_frame(rows: list[dict[str, float | int]]) -> pd.DataFrame:
    return pd.DataFrame(rows)[FEATURE_ORDER]


def build_parquet_features(
    panel: pd.DataFrame,
    *,
    season_y: int,
    mv_eur: pd.Series,
    tier_for_clubs: pd.Series,
) -> pd.DataFrame:
    if len(panel) != len(mv_eur):
        raise ValueError("mv_eur must align with panel row count.")
    if not mv_eur.index.equals(panel.index):
        mv_eur = mv_eur.reindex(panel.index)

    rows: list[dict[str, float | int]] = []
    for i, (_, srow) in enumerate(panel.iterrows()):
        mv = float(mv_eur.iloc[i]) if pd.notna(mv_eur.iloc[i]) else np.nan
        league = str(srow.get("league") or "")
        origin_power = _league_power(league)
        tier = int(tier_for_clubs.iloc[i]) if pd.notna(tier_for_clubs.iloc[i]) else 3
        rows.append(
            _feat_row(
                srow,
                season_y=season_y,
                mv_eur=mv,
                origin_power=origin_power,
                dest_power=origin_power,
                origin_tier=tier,
                dest_tier=3,
                transfer_year=int(season_y),
            )
        )
    return _rows_to_frame(rows)


def build_xy_training(
    repo_root: Path,
    *,
    fuzzy_threshold: int = 92,
    max_rows: int | None = None,
    refresh_mappings: bool = True,
) -> tuple[pd.DataFrame, pd.Series, pd.Series, pd.DataFrame]:
    tm_dir = repo_root / "data" / "tm"
    players_all = repo_root / "data" / "players" / "all"
    xfer = tm_dir / "transfers.csv"
    val_csv = tm_dir / "player_valuations.csv"

    if refresh_mappings or not (tm_dir / "xtv_id_mapping.parquet").is_file():
        mapping = build_tm_to_wyscout_mapping(tm_dir, players_all, fuzzy_threshold=fuzzy_threshold)
        save_mapping(mapping, tm_dir)
        club_map = build_parquet_club_mapping(players_all, tm_dir)
        save_parquet_club_mapping(club_map, tm_dir)
    else:
        mapping = load_mapping(tm_dir)

    clubs = load_clubs(tm_dir)
    tier_tbl = club_tier_table(clubs)
    tm_to_wy = (
        mapping.dropna(subset=["player_tm_id", "wyscout_id"])
        .astype({"player_tm_id": "int64", "wyscout_id": "int64"})
        .drop_duplicates("player_tm_id", keep="first")
        .set_index("player_tm_id")["wyscout_id"]
    )

    tr = pd.read_csv(
        xfer,
        dtype={"player_name": "string"},
        engine="python",
        on_bad_lines="skip",
    )
    need_cols = {
        "player_id",
        "transfer_date",
        "transfer_season",
        "transfer_fee",
        "from_club_id",
        "to_club_id",
    }
    miss = need_cols.difference(set(tr.columns))
    if miss:
        raise ValueError(f"transfers.csv missing columns: {sorted(miss)}")

    tr = tr.assign(
        _fee=pd.to_numeric(tr["transfer_fee"], errors="coerce"),
        _dts=pd.to_datetime(tr["transfer_date"], errors="coerce"),
        from_club_id=pd.to_numeric(tr["from_club_id"], errors="coerce"),
        to_club_id=pd.to_numeric(tr["to_club_id"], errors="coerce"),
    )
    mask = tr["_fee"].notna() & (tr["_fee"] > 0) & tr["_dts"].notna()
    tr = tr.loc[mask].copy()
    tr["season_y"] = tr["transfer_season"].apply(transfer_season_to_start_year)
    tr = tr.loc[tr["season_y"].notna()].copy()
    tr["season_y"] = tr["season_y"].astype(np.int64)
    tr["_dts"] = tr["_dts"].dt.normalize()
    tr["player_id_tm"] = pd.to_numeric(tr["player_id"], errors="coerce")
    tr = tr.dropna(subset=["player_id_tm"]).copy()
    tr["player_id_tm"] = tr["player_id_tm"].astype("int64")
    tr["wyscout_id"] = tr["player_id_tm"].map(tm_to_wy)
    tr = tr.dropna(subset=["wyscout_id"]).copy()
    tr["wyscout_id"] = tr["wyscout_id"].astype("int64")

    if max_rows is not None:
        tr = tr.iloc[: max_rows]

    mv_asof = tm_mv_eur_asof_dates_for_tm_players(
        tr["player_id_tm"],
        tr["_dts"],
        valuations_csv=val_csv,
    ).to_numpy(dtype=np.float64, copy=False)
    if "market_value_in_eur" in tr.columns:
        fb = pd.to_numeric(tr["market_value_in_eur"], errors="coerce").astype("float64").to_numpy()
        bad = ~np.isfinite(fb) | (fb <= 0)
        fb = np.where(bad, np.nan, fb)
        mv_asof = np.where(np.isfinite(mv_asof) & (mv_asof > 0), mv_asof, fb)
    tr = tr.assign(_mv_use=mv_asof)

    cache: dict[int, pd.DataFrame] = {}
    rows: list[dict[str, float | int]] = []
    audit_chunks: list[dict[str, Any]] = []
    y_fee: list[float] = []
    y_ratio: list[float] = []

    for _, row in tr.iterrows():
        wy = int(row["wyscout_id"])
        yr = int(row["season_y"])
        if yr not in cache:
            bulk = _best_row_index_for_season(players_all, yr)
            cache[yr] = pd.DataFrame() if bulk.empty else _index_max_minutes(bulk)
        ply = cache[yr]
        if ply.empty or wy not in ply.index:
            continue

        srow = ply.loc[wy]
        fee = float(row["_fee"])
        mv = float(row["_mv_use"]) if np.isfinite(row["_mv_use"]) and row["_mv_use"] > 0 else np.nan
        from_id = int(row["from_club_id"]) if pd.notna(row["from_club_id"]) else None
        to_id = int(row["to_club_id"]) if pd.notna(row["to_club_id"]) else None
        transfer_year = int(pd.Timestamp(row["_dts"]).year)

        rows.append(
            _feat_row(
                srow,
                season_y=yr,
                mv_eur=mv if np.isfinite(mv) else np.nan,
                origin_power=league_power_for_club_id(from_id, clubs),
                dest_power=league_power_for_club_id(to_id, clubs),
                origin_tier=tier_for_club_id(from_id, tier_tbl),
                dest_tier=tier_for_club_id(to_id, tier_tbl),
                transfer_year=transfer_year,
            )
        )
        y_fee.append(float(np.log(fee)))
        y_ratio.append(float(np.log(fee) - np.log(mv)) if np.isfinite(mv) and mv > 0 else np.nan)
        audit_chunks.append(
            {
                "player_id_tm": int(row["player_id_tm"]),
                "wyscout_id": wy,
                "season_start_year": yr,
                "transfer_date": row["_dts"],
                "transfer_year": transfer_year,
                "fee_eur": fee,
                "mv_eur_aligned": mv,
            }
        )

    if not rows:
        empty_y = pd.Series(dtype=np.float64)
        return pd.DataFrame(columns=FEATURE_ORDER), empty_y, empty_y, pd.DataFrame()

    X_df = _rows_to_frame(rows)
    audit_df = pd.DataFrame(audit_chunks)
    return (
        X_df,
        pd.Series(y_fee, dtype=np.float64, index=X_df.index),
        pd.Series(y_ratio, dtype=np.float64, index=X_df.index),
        audit_df,
    )


def sklearn_pipeline(*, enable_early_stopping: bool = True) -> Any:
    try:
        from sklearn.compose import ColumnTransformer
        from sklearn.impute import SimpleImputer
        from sklearn.ensemble import HistGradientBoostingRegressor
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import FunctionTransformer
    except ImportError as e:
        raise RuntimeError("Training requires sklearn in the active environment.") from e

    num_feats = [c for c in FEATURE_ORDER if c != "position_group"]
    cat_feats = ["position_group"]

    pre = ColumnTransformer(
        [
            ("num", SimpleImputer(strategy="median"), num_feats),
            (
                "cat_pass",
                FunctionTransformer(lambda x: x, validate=False),
                cat_feats,
            ),
        ],
        remainder="drop",
        sparse_threshold=0.0,
    )

    n_num = len(num_feats)
    cat_idx = [n_num]

    gb_params: dict[str, Any] = dict(
        categorical_features=cat_idx,
        max_depth=12,
        max_iter=900,
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


def fit(pipe: Any, X: pd.DataFrame, y: pd.Series, *, sample_weight: np.ndarray | None = None) -> Any:
    if X.empty:
        raise ValueError("No training rows.")
    Xp = _prepare_matrix(X)
    if sample_weight is not None:
        pipe.fit(Xp, y, sample_weight=sample_weight)
    else:
        pipe.fit(Xp, y)
    return pipe


def _prepare_matrix(X: pd.DataFrame) -> pd.DataFrame:
    Xp = X[FEATURE_ORDER].copy()
    for c in AREA_INDEX_FEATURES + ["age", "log_minutes", "log_mv", "has_mv", "origin_league_power", "dest_league_power"]:
        Xp[c] = pd.to_numeric(Xp[c], errors="coerce")
    for c in ("origin_club_tier", "dest_club_tier", "transfer_year", "position_group"):
        Xp[c] = pd.to_numeric(Xp[c], errors="coerce").fillna(3 if "tier" in c else 0).astype(np.int64)
    return Xp


def temporal_train_val_masks(audit_df: pd.DataFrame, cutoff: pd.Timestamp) -> tuple[np.ndarray, np.ndarray]:
    ts = pd.to_datetime(audit_df["transfer_date"], errors="coerce")
    train_mask = ts < cutoff
    val_mask = ~train_mask & ts.notna()
    return train_mask.to_numpy(dtype=bool), val_mask.to_numpy(dtype=bool)


def recency_sample_weight(transfer_years: np.ndarray) -> np.ndarray:
    yrs = np.asarray(transfer_years, dtype=np.float64)
    if len(yrs) == 0:
        return yrs
    base = float(np.nanmin(yrs))
    return np.exp(0.08 * (yrs - base))


def _predict_row_fee(
    pipe_ratio: Any,
    row: pd.DataFrame,
    *,
    mv_eur: float | None,
    pipe_abs: Any | None,
) -> float:
    has_mv = float(row["has_mv"].iloc[0]) > 0.5 and mv_eur is not None and np.isfinite(mv_eur) and mv_eur > 0
    if has_mv and pipe_ratio is not None:
        lr = float(pipe_ratio.predict(_prepare_matrix(row))[0])
        return float(mv_eur * np.exp(np.clip(lr, np.log(0.1), np.log(4.0))))
    if pipe_abs is not None:
        la = float(pipe_abs.predict(_prepare_matrix(row))[0])
        return float(np.exp(np.clip(la, LOG_FEE_MIN, LOG_FEE_MAX)))
    if pipe_ratio is not None:
        la = float(pipe_ratio.predict(_prepare_matrix(row))[0])
        return float(np.exp(np.clip(la, LOG_FEE_MIN, LOG_FEE_MAX)))
    return float("nan")


def predict_xtv_with_marginal(
    pipe_ratio: Any,
    base: pd.DataFrame,
    *,
    dest_power: np.ndarray,
    dest_tier: np.ndarray,
    mv_eur: np.ndarray | None = None,
    pipe_abs: Any | None = None,
) -> np.ndarray:
    n = len(base)
    ns = dest_power.shape[1]
    out = np.full(n, np.nan, dtype=np.float64)
    for i in range(n):
        preds: list[float] = []
        mv = None if mv_eur is None else float(mv_eur[i])
        for j in range(ns):
            row = base.iloc[[i]].copy()
            row["dest_league_power"] = float(dest_power[i, j])
            row["dest_club_tier"] = int(dest_tier[i, j])
            fee = _predict_row_fee(pipe_ratio, row, mv_eur=mv, pipe_abs=pipe_abs)
            if np.isfinite(fee):
                preds.append(fee)
        if preds:
            out[i] = float(np.mean(preds))
    return np.clip(out, FEE_MIN_EUR, FEE_MAX_EUR)


def _age_bucket(age: float) -> str:
    if not np.isfinite(age):
        return "unk"
    a = int(age)
    if a <= 20:
        return "u20"
    if a <= 23:
        return "21-23"
    if a <= 26:
        return "24-26"
    if a <= 29:
        return "27-29"
    return "30+"


def _pi_bucket(pi: float) -> str:
    if not np.isfinite(pi):
        return "unk"
    return str(int(min(9, max(0, round(float(pi) / 10.0)))))


def build_peer_mv_table(players_dir: Path) -> pd.DataFrame:
    """Median TM MV by position × age × league × PI bucket across loaded seasons."""

    pool: list[pd.DataFrame] = []
    for pq in sorted(Path(players_dir).glob("*_all_leagues.parquet")):
        try:
            df = pd.read_parquet(
                pq,
                columns=["Primary position", "Age", "Birthday", "league", "performance_index", TM_MV_COL],
            )
        except Exception:
            continue
        if TM_MV_COL not in df.columns:
            continue
        df = df.dropna(subset=[TM_MV_COL, "performance_index"])
        df = df[df[TM_MV_COL] > 0]
        if df.empty:
            continue
        m = re.match(r"^(20\d{2})_", pq.name)
        season_y = int(m.group(1)) if m else 2020
        df = df.assign(
            position_group=df["Primary position"].map(lambda p: position_group_from_str(p)),
            age=df.apply(lambda r: player_age_parquet_row(r, season_y), axis=1),
        )
        df["age_bucket"] = df["age"].map(_age_bucket)
        df["pi_bucket"] = pd.to_numeric(df["performance_index"], errors="coerce").map(_pi_bucket)
        pool.append(df[["position_group", "age_bucket", "league", "pi_bucket", TM_MV_COL]])

    if not pool:
        return pd.DataFrame(columns=["position_group", "age_bucket", "league", "pi_bucket", "peer_mv_eur"])

    all_df = pd.concat(pool, ignore_index=True)
    return (
        all_df.groupby(["position_group", "age_bucket", "league", "pi_bucket"], dropna=False)[TM_MV_COL]
        .median()
        .reset_index()
        .rename(columns={TM_MV_COL: "peer_mv_eur"})
    )


def impute_mv_from_peers(
    mv: pd.Series,
    df: pd.DataFrame,
    peer_tbl: pd.DataFrame,
    *,
    season_y: int,
) -> pd.Series:
    if peer_tbl.empty:
        return mv

    out = mv.astype("float64").copy()
    pos = df.get("Primary position", pd.Series([None] * len(df), index=df.index)).map(
        lambda p: position_group_from_str(p)
    )
    ages = df.apply(lambda r: player_age_parquet_row(r, season_y), axis=1)
    age_b = ages.map(_age_bucket)
    leagues = df.get("league", pd.Series([None] * len(df), index=df.index))
    pi_b = pd.to_numeric(df.get("performance_index"), errors="coerce").map(_pi_bucket)

    peer_idx = peer_tbl.set_index(["position_group", "age_bucket", "league", "pi_bucket"])["peer_mv_eur"]

    for i in out.index[out.isna()].tolist():
        key = (int(pos.iloc[i]), str(age_b.iloc[i]), str(leagues.iloc[i]), str(pi_b.iloc[i]))
        try:
            val = peer_idx.loc[key]
        except KeyError:
            val = np.nan
        if np.isfinite(val) and val > 0:
            out.iloc[i] = float(val)
    return out
