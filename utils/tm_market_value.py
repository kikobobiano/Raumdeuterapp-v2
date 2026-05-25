"""TM market value as-of inference for Wyscout panels (§7 xTV design spec).

Reads ``data/tm/player_valuations.csv`` (+ ``people.csv`` for Wyscout id ↔ TM
``player_id``) and attaches the **latest** valuation with ``date`` ≤ reference
date for each (Wyscout row, football season).

Parquet naming in this repo uses **season start year** ``Y`` (e.g.
``players_2024`` = 2024–25). Reference date defaults to **30 June Y+1** (end of
the typical European season); override via :func:`season_reference_date`.

Reconstructing xTV::

    mv = inferred TM valuation (EUR)
    x_tv_hat_eur = exp(y_hat_log_ratio) * mv

where ``y_hat_log_ratio`` comes from the trained baseline predicting
``log(fee) - log(mv)`` on transfers.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Reference calendar (European club season centred on autumn–spring)
# ---------------------------------------------------------------------------


def season_reference_date(season_start_year: int, *, month: int = 6, day: int = 30) -> _dt.date:
    """Last TM snapshot date aligned to Wyscout parquet season ``season_start_year``.

    ``players_{Y}`` covers the football season beginning in calendar ``Y``.
    By default valuations are clipped to ``Y+1-{month}-{day}`` inclusive
    (~summer window after campaigns that end ~May/June north of the Equator).

    Older leagues or MLS-heavy panels may warrant a project-level override of
    ``month`` / ``day``.
    """
    return _dt.date(season_start_year + 1, month, day)


def season_reference_datetime(
    season_start_year: int | pd.Series | np.ndarray,
    *,
    month: int = 6,
    day: int = 30,
) -> pd.Series:
    """Vector of timezone-naive datetimes at 00:00 UTC for merge_asof."""

    def _one(y: int) -> pd.Timestamp:
        d = season_reference_date(int(y), month=month, day=day)
        return pd.Timestamp(d)

    if isinstance(season_start_year, (int, np.integer)):
        return pd.Series([_one(int(season_start_year))])

    arr = pd.Series(np.asarray(season_start_year)).astype("Int64")
    return pd.Series([_one(int(y)) if pd.notna(y) else pd.NaT for y in arr], dtype="datetime64[ns]")


def x_tv_hat_eur(
    y_hat_log_ratio: float | pd.Series | np.ndarray,
    mv_eur: float | pd.Series | np.ndarray,
) -> float | pd.Series | np.ndarray:
    r""":math:`\\widehat{\\text{xTV}} = \\exp(\\hat{y}) \\cdot \\text{mv}` (EUR)."""
    exp_y = np.exp(np.asarray(y_hat_log_ratio, dtype=np.float64))
    mv_arr = np.asarray(mv_eur, dtype=np.float64)
    out = exp_y * mv_arr
    if isinstance(mv_eur, pd.Series):
        return pd.Series(out, index=mv_eur.index, dtype="Float64")
    if isinstance(y_hat_log_ratio, pd.Series) and not isinstance(mv_eur, pd.Series):
        return pd.Series(out, index=y_hat_log_ratio.index, dtype="Float64")
    if np.ndim(out) == 0:
        return float(out)
    return out


# ---------------------------------------------------------------------------
# Lookup construction (same namespaces as enrich_with_tm / build_player_valuations)
# ---------------------------------------------------------------------------


def load_wyscout_to_tm_players(tm_dir: Path) -> pd.DataFrame:
    """One Wyscout-export id ↔ Transfermarkt ``player_id`` per ambiguous column.

    ``Wyscout id`` exports often equal ``key_soccerway`` rather than ``key_wyscout`` in
    people.csv; emitting both keyed rows then ``drop_duplicates`` matches
    :func:`scripts.enrich_with_tm._build_lookup`.

    Columns: ``wyscout_id``, ``player_tm_id`` (same as valuations ``player_id``).
    """
    people = pd.read_csv(
        tm_dir / "people.csv",
        usecols=["key_wyscout", "key_transfermarkt", "key_soccerway"],
        engine="python",
        on_bad_lines="skip",
    )
    for col in ("key_wyscout", "key_transfermarkt", "key_soccerway"):
        people[col] = pd.to_numeric(people[col], errors="coerce")
    people = people.dropna(subset=["key_transfermarkt"]).copy()

    # Soccerway is what the parquet ``Wyscout id`` column carries for the bulk
    # of players — emit it first so it wins the dedupe on wyscout_id collisions
    # (key_wyscout chunk is a noisy fallback covering only a few hundred ids).
    chunks: list[pd.DataFrame] = []
    sw = people.dropna(subset=["key_soccerway"]).assign(
        wyscout_id=lambda d: d["key_soccerway"].astype("int64"),
        player_tm_id=lambda d: d["key_transfermarkt"].astype("int64"),
    )[["wyscout_id", "player_tm_id"]]
    chunks.append(sw)
    w = people.dropna(subset=["key_wyscout"]).assign(
        wyscout_id=lambda d: d["key_wyscout"].astype("int64"),
        player_tm_id=lambda d: d["key_transfermarkt"].astype("int64"),
    )[["wyscout_id", "player_tm_id"]]
    chunks.append(w)
    out = pd.concat(chunks, ignore_index=True).drop_duplicates(subset=["wyscout_id"], keep="first")
    return out


def load_tm_valuations_raw(valuations_csv: Path) -> pd.DataFrame:
    """``player_valuations.csv`` trimmed to modelling columns."""
    df = pd.read_csv(
        valuations_csv,
        usecols=["player_id", "date", "market_value_in_eur"],
        engine="python",
        on_bad_lines="skip",
    )
    df["player_id"] = pd.to_numeric(df["player_id"], errors="coerce").astype("Int64")
    df = df.dropna(subset=["player_id"])
    df["player_id"] = df["player_id"].astype("int64")
    df["val_dt"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize().astype("datetime64[ns]")
    df["market_value_in_eur"] = pd.to_numeric(df["market_value_in_eur"], errors="coerce")
    df = df.dropna(subset=["val_dt", "market_value_in_eur"])
    df.loc[df["market_value_in_eur"] <= 0, "market_value_in_eur"] = np.nan
    df = df.dropna(subset=["market_value_in_eur"]).drop_duplicates(
        subset=["player_id", "val_dt"], keep="last"
    )
    return df[["player_id", "val_dt", "market_value_in_eur"]]


def tm_mv_eur_asof_dates_for_tm_players(
    player_tm_ids: pd.Series | np.ndarray,
    reference_dates: pd.Series | np.ndarray,
    *,
    valuations_csv: Path,
) -> pd.Series:
    """Last ``market_value_in_eur`` with ``date`` ≤ ``reference_dates`` keyed by TM ``player_id``.

    Uses the same cleansing as :func:`load_tm_valuations_raw`. Intended for aligning
    training labels on ``transfers.csv`` (`player_id`, ``transfer_date``) with the
    xTV valuation rule (historical snapshots only, backward as-of).

    Rows with missing ``player_tm_ids`` / ``reference_dates`` or no earlier TM row
    return ``NaN``.

    Aligns indices with ``player_tm_ids`` when passed as a :class:`~pandas.Series`.
    """
    v_raw = load_tm_valuations_raw(valuations_csv)

    if isinstance(player_tm_ids, pd.Series):
        base_index = player_tm_ids.index
        pt = pd.to_numeric(player_tm_ids, errors="coerce").astype("Int64")
    else:
        pt = pd.to_numeric(pd.Series(np.asarray(player_tm_ids)), errors="coerce").astype("Int64")
        base_index = pd.RangeIndex(len(pt))

    ref = pd.to_datetime(pd.Series(reference_dates), errors="coerce").dt.normalize().astype("datetime64[ns]")
    if len(ref) != len(pt):
        raise ValueError("reference_dates length must match player_tm_ids.")

    frame = pd.DataFrame(
        {
            "_sort": np.arange(len(pt)),
            "player_tm_id": pt,
            "ref_dt": ref,
        }
    )
    known = frame.dropna(subset=["player_tm_id", "ref_dt"]).copy()
    known["player_tm_id"] = known["player_tm_id"].astype("int64")
    known = known.sort_values("ref_dt", kind="mergesort")

    vals = (
        v_raw[v_raw["player_id"].isin(known["player_tm_id"].unique())]
        .rename(columns={"val_dt": "_val_snap"})
        .sort_values("_val_snap", kind="mergesort")
    )

    left_m = known.rename(columns={"player_tm_id": "player_id"})
    merged = pd.merge_asof(
        left_m,
        vals,
        left_on="ref_dt",
        right_on="_val_snap",
        by="player_id",
        direction="backward",
    )

    out = pd.Series(np.nan, index=np.arange(len(pt)), dtype="float64")
    if len(merged) > 0:
        out.iloc[np.asarray(merged["_sort"].astype(np.int64), dtype=int)] = merged[
            "market_value_in_eur"
        ].astype("float64").to_numpy()

    return pd.Series(out.to_numpy(dtype=np.float64, copy=False), index=base_index)


def valuations_long_with_wyscout(valuations_norm: pd.DataFrame, wy_tm: pd.DataFrame) -> pd.DataFrame:
    """Join TM valuations to Wyscout-export ids."""
    merged = valuations_norm.merge(wy_tm, left_on="player_id", right_on="player_tm_id", how="inner")
    merged = merged.rename(columns={"player_id": "tm_player_id"})
    return merged[["wyscout_id", "val_dt", "market_value_in_eur"]].drop_duplicates(
        subset=["wyscout_id", "val_dt"], keep="last"
    ).sort_values(
        ["wyscout_id", "val_dt"],
        kind="mergesort",
    )


def infer_tm_market_value_eur(
    wyscout_ids: pd.Series | np.ndarray,
    season_start_year: int | pd.Series | np.ndarray,
    *,
    tm_dir: Path,
    valuations_csv: Path | None = None,
    ref_month: int = 6,
    ref_day: int = 30,
) -> pd.Series:
    """Last ``market_value_in_eur`` with ``date`` ≤ season reference date, per row.

    Parameters mirror :func:`season_reference_date`. Rows without TM mapping or
    without qualifying valuations yield ``NaN``.

    Reads full ``player_valuations.csv`` (filtered exports like
    ``build_player_valuations`` are optional optimizations only).

    If ``wyscout_ids`` is a :class:`~pandas.Series`, the result shares its index.
    """
    if valuations_csv is None:
        valuations_csv = tm_dir / "player_valuations.csv"

    v_raw = load_tm_valuations_raw(valuations_csv)
    wy_tm = load_wyscout_to_tm_players(tm_dir)
    v_long = valuations_long_with_wyscout(v_raw, wy_tm)

    if isinstance(wyscout_ids, pd.Series):
        base_index = wyscout_ids.index
        wy_np = wyscout_ids.to_numpy()
    else:
        base_index = pd.RangeIndex(len(np.asarray(wyscout_ids)))
        wy_np = np.asarray(wyscout_ids)

    wy_num = pd.to_numeric(pd.Series(wy_np), errors="coerce").astype("Int64")

    y_flat = np.asarray(season_start_year).ravel()
    if y_flat.size == 1:
        yrs_int = pd.Series(np.full(len(wy_num), int(y_flat[0])), dtype="Int64")
    else:
        yrs_int = pd.Series(y_flat.astype(np.int64, copy=False)).astype("Int64")

    if len(yrs_int) != len(wy_num):
        raise ValueError(
            "season_start_year length must equal wyscout_ids "
            "(or broadcast a scalar by passing a zero-dim ndarray / length-1 array)."
        )

    refs = pd.Series(
        [
            pd.Timestamp(season_reference_date(int(yrs_int.iloc[i]), month=ref_month, day=ref_day))
            if pd.notna(yrs_int.iloc[i]) and pd.notna(wy_num.iloc[i])
            else pd.NaT
            for i in range(len(wy_num))
        ],
        dtype="datetime64[ns]",
    ).astype("datetime64[ns]")

    left = pd.DataFrame(
        {
            "_sort": np.arange(len(wy_num)),
            "wyscout_id": wy_num,
            "ref_dt": refs,
        }
    )
    left_known = (
        left.dropna(subset=["wyscout_id", "ref_dt"])
        .assign(wyscout_id=lambda d: d["wyscout_id"].astype("int64"))
        .sort_values("ref_dt", kind="mergesort")
    )

    v_sub = v_long[v_long["wyscout_id"].isin(left_known["wyscout_id"].unique())].copy()
    # merge_asof right key must carry a distinct name after rename
    v_sub_side = v_sub.rename(columns={"val_dt": "_val_snap"}).sort_values(
        "_val_snap", kind="mergesort"
    )

    merged = pd.merge_asof(
        left_known,
        v_sub_side,
        left_on="ref_dt",
        right_on="_val_snap",
        by="wyscout_id",
        direction="backward",
    )

    out_full = pd.Series(np.nan, index=np.arange(len(wy_num)), dtype="float64")
    if len(merged) > 0:
        out_full.iloc[np.asarray(merged["_sort"].astype(np.int64), dtype=int)] = merged[
            "market_value_in_eur"
        ].astype("float64").to_numpy()

    wy_tm_map = wy_tm.drop_duplicates("wyscout_id").set_index("wyscout_id")["player_tm_id"]
    mapped = wy_num.map(wy_tm_map)
    missing_tm = wy_num.notna().to_numpy() & mapped.isna().to_numpy()
    if missing_tm.any():
        out_full.iloc[np.flatnonzero(missing_tm)] = np.nan

    return pd.Series(out_full.to_numpy(dtype=np.float64, copy=False), index=base_index)


def attach_tm_mv_eur_to_player_frame(
    df: pd.DataFrame,
    season_start_year: int,
    *,
    tm_dir: Path,
    valuations_csv: Path | None = None,
    wyscout_col: str = "Wyscout id",
    out_col: str = "tm_market_value_eur",
    ref_month: int = 6,
    ref_day: int = 30,
) -> pd.DataFrame:
    """Convenience for a whole ``*_all_leagues`` frame (single parquet season).

    Does **not** write to disk — assign when building parquet in your ETL notebook.
    """
    if wyscout_col not in df.columns:
        raise ValueError(f"Missing column {wyscout_col!r}")
    mv = infer_tm_market_value_eur(
        df[wyscout_col],
        season_start_year,
        tm_dir=tm_dir,
        valuations_csv=valuations_csv,
        ref_month=ref_month,
        ref_day=ref_day,
    )
    out = df.copy()
    out[out_col] = mv
    return out
