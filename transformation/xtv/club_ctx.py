"""TM club context: domestic league power and squad-value tier."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

from utils.config import LEAGUE_POWER_BASE

CLUB_MAP_PARQUET = "xtv_club_mapping.parquet"

_TM_COMP_TO_LEAGUE: dict[str, str] = {
    "premier-league": "Premier League",
    "serie-a": "Serie A",
    "laliga": "La Liga",
    "bundesliga": "Bundesliga",
    "ligue-1": "Ligue 1",
    "championship": "Championship",
    "jupiler-pro-league": "Belgian Pro League",
    "liga-portugal": "Primeira Liga",
    "campeonato-brasileiro-serie-a": "Brasileirão",
    "eredivisie": "Eredivisie",
    "liga-profesional-argentina": "Argentina LPF",
    "torneo-apertura": "Argentina LPF",
    "torneo-clausura": "Argentina LPF",
    "major-league-soccer": "MLS",
    "j1-league": "J1",
    "1-hnl": "1. HNL",
    "pko-bp-ekstraklasa": "Ekstraklasa",
    "superliga": "Superliga",
    "serie-b": "Serie B",
    "allsvenskan": "Allsvenskan",
    "super-lig": "Süper Lig",
    "laliga2": "La Liga 2",
    "2-bundesliga": "2. Bundesliga",
    "russian-premier-liga": "Russian Premier League",
    "super-league": "Swiss Super League",
    "bundesliga-oesterreich": "Austrian Bundesliga",
    "eliteserien": "Eliteserien",
    "super-league-1": "Greek Super League",
    "premier-liga": "Ukrainian Premier League",
    "scottish-premiership": "Scottish Premiership",
    "saudi-pro-league": "Saudi Pro League",
    "ligue-2": "Ligue 2",
    "liga-portugal-2": "Portuguese Segunda Liga",
    "campeonato-planvital": "Chilean Primera Division",
    "veikkausliiga": "Veikkausliiga",
}


def _norm_club(name: str) -> str:
    s = unicodedata.normalize("NFKD", str(name or ""))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
    return s


def _tm_comp_to_league(comp_name: str | None, comp_id: str | None) -> str | None:
    slug = str(comp_name or comp_id or "").strip().lower()
    if not slug:
        return None
    if slug in _TM_COMP_TO_LEAGUE:
        return _TM_COMP_TO_LEAGUE[slug]
    for key, league in _TM_COMP_TO_LEAGUE.items():
        if key in slug:
            return league
    return None


def load_clubs(tm_dir: Path) -> pd.DataFrame:
    clubs = pd.read_csv(
        tm_dir / "clubs.csv",
        usecols=["club_id", "name", "domestic_competition_id", "total_market_value"],
        engine="python",
        on_bad_lines="skip",
    )
    clubs["club_id"] = pd.to_numeric(clubs["club_id"], errors="coerce")
    clubs = clubs.dropna(subset=["club_id"]).copy()
    clubs["club_id"] = clubs["club_id"].astype("int64")
    clubs["total_market_value"] = pd.to_numeric(clubs["total_market_value"], errors="coerce")

    comp = pd.read_csv(
        tm_dir / "competitions.csv",
        usecols=["competition_id", "name"],
        engine="python",
        on_bad_lines="skip",
    ).rename(columns={"name": "competition_name"})
    # NB: both frames carry a "name" column (club vs competition). Rename the
    # competition one before the merge so the club "name" survives intact —
    # otherwise pandas emits name_x/name_y and downstream `clubs["name"]` breaks
    # and the league mapping silently falls back to the TM code (league_power NaN).
    merged = clubs.merge(comp, left_on="domestic_competition_id", right_on="competition_id", how="left")
    merged["wyscout_league"] = [
        _tm_comp_to_league(row.get("competition_name"), row.get("domestic_competition_id"))
        for _, row in merged.iterrows()
    ]
    merged["league_power"] = merged["wyscout_league"].map(LEAGUE_POWER_BASE)
    return merged


def club_tier_table(clubs: pd.DataFrame) -> pd.DataFrame:
    """Map ``club_id`` → tier 1 (top) … 5 (bottom) within domestic league."""

    work = clubs.dropna(subset=["club_id"]).copy()
    work["club_id"] = work["club_id"].astype("int64")
    mv = work["total_market_value"].fillna(0.0)

    tiers = np.full(len(work), 3, dtype=np.int64)
    for _, grp in work.groupby("domestic_competition_id", dropna=False):
        pos = work.index.get_indexer(grp.index)
        vals = mv.loc[grp.index].to_numpy(dtype=np.float64)
        if len(vals) < 5:
            continue
        ranks = pd.Series(vals).rank(method="first", ascending=False)
        q = pd.qcut(ranks, 5, labels=[1, 2, 3, 4, 5]).astype(int).to_numpy()
        tiers[pos] = q

    return pd.DataFrame({"club_id": work["club_id"].to_numpy(), "club_tier": tiers})


def load_parquet_club_mapping(tm_dir: Path) -> pd.DataFrame:
    path = tm_dir / CLUB_MAP_PARQUET
    if not path.is_file():
        return pd.DataFrame(columns=["parquet_club", "norm_club", "club_id", "source", "score"])
    return pd.read_parquet(path)


def build_parquet_club_mapping(players_all: Path, tm_dir: Path) -> pd.DataFrame:
    """Exact normalized club-name match against TM ``clubs.csv``."""

    clubs = load_clubs(tm_dir)
    tm_by_norm = clubs.assign(norm_name=clubs["name"].map(_norm_club)).drop_duplicates("norm_name")

    names: set[str] = set()
    for pq in sorted(Path(players_all).glob("*_all_leagues.parquet")):
        try:
            df = pd.read_parquet(pq, columns=["club"])
        except Exception:
            df = pd.read_parquet(pq)
        if "club" not in df.columns:
            continue
        names.update(str(x) for x in df["club"].dropna().unique())

    rows: list[dict[str, object]] = []
    for club in sorted(names):
        norm = _norm_club(club)
        hit = tm_by_norm.loc[tm_by_norm["norm_name"] == norm]
        if hit.empty:
            rows.append(
                {"parquet_club": club, "norm_club": norm, "club_id": np.nan, "source": "none", "score": 0.0}
            )
        else:
            row = hit.iloc[0]
            rows.append(
                {
                    "parquet_club": club,
                    "norm_club": norm,
                    "club_id": int(row["club_id"]),
                    "source": "exact",
                    "score": 100.0,
                }
            )
    return pd.DataFrame(rows)


def save_parquet_club_mapping(mapping: pd.DataFrame, tm_dir: Path) -> Path:
    path = tm_dir / CLUB_MAP_PARQUET
    mapping.to_parquet(path, index=False)
    return path


def league_power_for_club_id(club_id: int | None, clubs: pd.DataFrame) -> float:
    if club_id is None or not np.isfinite(club_id):
        return float("nan")
    hit = clubs.loc[clubs["club_id"] == int(club_id), "league_power"]
    if hit.empty:
        return float("nan")
    return float(hit.iloc[0])


def tier_for_club_id(club_id: int | None, tier_tbl: pd.DataFrame) -> int:
    if club_id is None or not np.isfinite(club_id):
        return 3
    hit = tier_tbl.loc[tier_tbl["club_id"] == int(club_id), "club_tier"]
    if hit.empty:
        return 3
    return int(hit.iloc[0])


def tier_for_parquet_clubs(
    club_series: pd.Series,
    club_map: pd.DataFrame,
    tier_tbl: pd.DataFrame,
) -> pd.Series:
    if club_map.empty:
        return pd.Series(np.full(len(club_series), 3, dtype=np.int64), index=club_series.index)

    by_club = club_map.dropna(subset=["club_id"]).drop_duplicates("parquet_club").set_index("parquet_club")[
        "club_id"
    ]
    tier_by_id = tier_tbl.set_index("club_id")["club_tier"]
    club_ids = club_series.map(by_club)
    tiers = club_ids.map(tier_by_id).fillna(3).astype(np.int64)
    return tiers
