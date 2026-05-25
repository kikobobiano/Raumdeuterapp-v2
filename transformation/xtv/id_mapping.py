"""Wyscout ↔ Transfermarkt player id mapping for xTV."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

MAPPING_PARQUET = "xtv_id_mapping.parquet"


def _norm_name(name: str) -> str:
    s = unicodedata.normalize("NFKD", str(name or ""))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
    return s


def load_mapping(tm_dir: Path) -> pd.DataFrame:
    path = tm_dir / MAPPING_PARQUET
    if not path.is_file():
        return pd.DataFrame(
            columns=["player_tm_id", "wyscout_id", "name", "source", "score"],
        )
    return pd.read_parquet(path)


def save_mapping(mapping: pd.DataFrame, tm_dir: Path) -> Path:
    path = tm_dir / MAPPING_PARQUET
    path.parent.mkdir(parents=True, exist_ok=True)
    mapping.to_parquet(path, index=False)
    return path


def mapping_coverage(mapping: pd.DataFrame, transfers_csv: Path) -> dict[str, Any]:
    tr = pd.read_csv(
        transfers_csv,
        usecols=["player_id"],
        engine="python",
        on_bad_lines="skip",
    )
    tr["player_id"] = pd.to_numeric(tr["player_id"], errors="coerce")
    tr = tr.dropna(subset=["player_id"])
    tr_ids = tr["player_id"].astype("int64")
    unique_players = int(tr_ids.nunique())
    transfer_rows = len(tr_ids)

    mapped_tm = set(mapping["player_tm_id"].dropna().astype("int64").tolist())
    matched_rows = int(tr_ids.isin(mapped_tm).sum())
    matched_unique = int(tr_ids[tr_ids.isin(mapped_tm)].nunique())
    fuzzy_rows = int((mapping["source"] == "fuzzy").sum()) if "source" in mapping.columns else 0

    return {
        "transfer_rows": transfer_rows,
        "transfer_rows_matched": matched_rows,
        "coverage_rows": matched_rows / transfer_rows if transfer_rows else 0.0,
        "unique_players": unique_players,
        "unique_players_matched": matched_unique,
        "coverage_unique": matched_unique / unique_players if unique_players else 0.0,
        "fuzzy_rows": fuzzy_rows,
    }


def build_tm_to_wyscout_mapping(
    tm_dir: Path,
    players_all: Path,
    *,
    fuzzy_threshold: int = 92,
) -> pd.DataFrame:
    """Build mapping table; reuses existing parquet when present unless forced refresh."""

    people = pd.read_csv(
        tm_dir / "people.csv",
        usecols=["key_wyscout", "key_transfermarkt", "key_soccerway", "name", "date_of_birth"],
        engine="python",
        on_bad_lines="skip",
    )
    for col in ("key_wyscout", "key_transfermarkt", "key_soccerway"):
        people[col] = pd.to_numeric(people[col], errors="coerce")
    people = people.dropna(subset=["key_transfermarkt"]).copy()
    people["player_tm_id"] = people["key_transfermarkt"].astype("int64")

    rows: list[dict[str, Any]] = []

    sw = people.dropna(subset=["key_soccerway"]).copy()
    for _, r in sw.iterrows():
        rows.append(
            {
                "player_tm_id": int(r["player_tm_id"]),
                "wyscout_id": int(r["key_soccerway"]),
                "name": r.get("name"),
                "source": "exact_soccerway",
                "score": 100.0,
            }
        )

    wy = people.dropna(subset=["key_wyscout"]).copy()
    seen = {(x["player_tm_id"], x["wyscout_id"]) for x in rows}
    for _, r in wy.iterrows():
        key = (int(r["player_tm_id"]), int(r["key_wyscout"]))
        if key in seen:
            continue
        rows.append(
            {
                "player_tm_id": key[0],
                "wyscout_id": key[1],
                "name": r.get("name"),
                "source": "exact_wyscout",
                "score": 100.0,
            }
        )
        seen.add(key)

    # Wyscout ids seen in season parquets
    wyscout_ids: set[int] = set()
    for pq in sorted(Path(players_all).glob("*_all_leagues.parquet")):
        try:
            s = pd.read_parquet(pq, columns=["Wyscout id"])["Wyscout id"]
        except Exception:
            s = pd.read_parquet(pq)["Wyscout id"]
        wyscout_ids.update(int(x) for x in pd.to_numeric(s, errors="coerce").dropna().astype("int64"))

    mapped_wy = {int(r["wyscout_id"]) for r in rows}
    missing_wy = wyscout_ids - mapped_wy

    # Bio exact: TM player name + DOB ↔ parquet Player + Birthday
    if missing_wy:
        bio_index: dict[tuple[str, str], int] = {}
        for _, r in people.iterrows():
            nm = _norm_name(str(r.get("name") or ""))
            dob = str(r.get("date_of_birth") or "")[:10]
            if nm and dob:
                bio_index.setdefault((nm, dob), int(r["player_tm_id"]))

        for pq in sorted(Path(players_all).glob("*_all_leagues.parquet")):
            try:
                df = pd.read_parquet(pq, columns=["Wyscout id", "Player", "Birthday"])
            except Exception:
                continue
            df["Wyscout id"] = pd.to_numeric(df["Wyscout id"], errors="coerce")
            df = df.dropna(subset=["Wyscout id"])
            for _, r in df.iterrows():
                wid = int(r["Wyscout id"])
                if wid not in missing_wy:
                    continue
                nm = _norm_name(str(r.get("Player") or ""))
                bd = str(r.get("Birthday") or "")[:10]
                tm_id = bio_index.get((nm, bd))
                if tm_id is None:
                    continue
                rows.append(
                    {
                        "player_tm_id": tm_id,
                        "wyscout_id": wid,
                        "name": r.get("Player"),
                        "source": "bio_exact",
                        "score": 100.0,
                    }
                )
                missing_wy.discard(wid)

    # Fuzzy name match for remaining ids
    if missing_wy:
        try:
            from rapidfuzz import fuzz, process
        except ImportError:
            fuzz = process = None  # type: ignore[assignment]

        if fuzz is not None and process is not None:
            tm_names = people.assign(
                norm=people["name"].map(_norm_name),
                player_tm_id=people["player_tm_id"].astype("int64"),
            )
            tm_names = tm_names.loc[tm_names["norm"].str.len() > 2]
            choices = tm_names["norm"].tolist()
            choice_ids = tm_names["player_tm_id"].tolist()

            wy_names: dict[int, str] = {}
            for pq in sorted(Path(players_all).glob("*_all_leagues.parquet")):
                try:
                    df = pd.read_parquet(pq, columns=["Wyscout id", "Player"])
                except Exception:
                    continue
                for _, r in df.iterrows():
                    wid = pd.to_numeric(r["Wyscout id"], errors="coerce")
                    if pd.isna(wid):
                        continue
                    wid = int(wid)
                    if wid in missing_wy and wid not in wy_names:
                        wy_names[wid] = _norm_name(str(r.get("Player") or ""))

            for wid, nm in wy_names.items():
                if len(nm) < 3:
                    continue
                match = process.extractOne(nm, choices, scorer=fuzz.token_sort_ratio)
                if not match or match[1] < fuzzy_threshold:
                    continue
                pos = choices.index(match[0])
                rows.append(
                    {
                        "player_tm_id": int(choice_ids[pos]),
                        "wyscout_id": wid,
                        "name": nm,
                        "source": "fuzzy",
                        "score": float(match[1]),
                    }
                )

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    priority = {"exact_soccerway": 0, "exact_wyscout": 1, "bio_exact": 2, "fuzzy": 3}
    out["_pri"] = out["source"].map(priority).fillna(9)
    out = out.sort_values(["wyscout_id", "_pri", "score"], ascending=[True, True, False])
    out = out.drop_duplicates("wyscout_id", keep="first").drop(columns=["_pri"])
    return out.reset_index(drop=True)
