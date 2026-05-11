"""Enrich Wyscout CSVs with image_url and height_in_cm from Transfermarkt data.

Reads ``data/tm/people.csv`` for ``key_transfermarkt`` (+ optional cross-ids),
then joins ``data/tm/players.csv`` for ``image_url`` / ``height_in_cm``.

Wyscout CSVs expose a numeric player id column often named ``Wyscout id``. In practice
that value aligns with **`key_soccerway`** in Reep/people slightly more often than with
``key_wyscout``. The lookup includes **both** ids so merges match either namespace.

Inputs (read):
  data/tm/people.csv — ``key_transfermarkt`` required; ``key_wyscout`` /
    ``key_soccerway`` used as alternate join targets into Wyscout CSV player id column
  data/tm/players.csv  — ``player_id``, ``image_url``, ``height_in_cm``
  data/players/wyscout/*.csv

Output:
  Overwrites each `data/players/wyscout/*.csv` in place. Resolves ``image_url``
  with Wyscout ``Image`` column as primary source, Transfermarkt ``image_url`` as
  fallback. The ``Image`` column is dropped after resolution. Updates ``Height``
  only when height_in_cm is available; otherwise keeps the existing Wyscout value.

Usage:
  python scripts/enrich_with_tm.py [--dry-run]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

from repo_paths import repo_root

REPO_ROOT = repo_root(Path(__file__))
TM_DIR = REPO_ROOT / "data" / "tm"
WYSCOUT_DIR = REPO_ROOT / "data" / "players" / "wyscout"


def _load_people_tm_rows() -> pd.DataFrame:
    """people rows with TM player attributes (image, height) joined from players.csv."""
    people = pd.read_csv(
        TM_DIR / "people.csv",
        usecols=["key_wyscout", "key_transfermarkt", "key_soccerway"],
        dtype={
            "key_wyscout": "string",
            "key_transfermarkt": "string",
            "key_soccerway": "string",
        },
        engine="python",
        on_bad_lines="skip",
    )
    for col in ("key_wyscout", "key_transfermarkt", "key_soccerway"):
        people[col] = pd.to_numeric(people[col], errors="coerce")
    people = people.dropna(subset=["key_transfermarkt"])
    players = _load_players()
    out = people.merge(
        players, left_on="key_transfermarkt", right_on="player_id", how="left"
    )
    return out


def _load_players() -> pd.DataFrame:
    """player_id (= key_transfermarkt) → image_url, height_in_cm."""
    players = pd.read_csv(
        TM_DIR / "players.csv",
        usecols=["player_id", "image_url", "height_in_cm"],
    )
    players["player_id"] = pd.to_numeric(players["player_id"], errors="coerce")
    players = players.dropna(subset=["player_id"])
    players["player_id"] = players["player_id"].astype("int64")
    return players.drop_duplicates(subset=["player_id"], keep="first")


def _build_lookup() -> pd.DataFrame:
    """One row per distinct player id found in Wyscout CSVs (either Wyscout or Soccerway id)."""
    rows = _load_people_tm_rows()
    pieces: list[pd.DataFrame] = []

    # Reep ``key_wyscout`` (true Wyscout internal id when the export uses it)
    w = rows.dropna(subset=["key_wyscout"]).copy()
    w = w.rename(columns={"key_wyscout": "Wyscout id"})
    pieces.append(w[["Wyscout id", "image_url", "height_in_cm"]])

    # ``key_soccerway`` often matches Wyscout CSV column ``Wyscout id`` (misleading name)
    s = rows.dropna(subset=["key_soccerway"]).copy()
    s = s.rename(columns={"key_soccerway": "Wyscout id"})
    pieces.append(s[["Wyscout id", "image_url", "height_in_cm"]])

    out = pd.concat(pieces, ignore_index=True)
    return out.drop_duplicates(subset=["Wyscout id"], keep="first")


def enrich_csv(path: Path, lookup: pd.DataFrame, *, dry_run: bool = False) -> dict:
    df = pd.read_csv(path)
    if "Wyscout id" not in df.columns:
        return {"file": path.name, "skipped": "no Wyscout id column"}

    df["Wyscout id"] = pd.to_numeric(df["Wyscout id"], errors="coerce").astype("Int64")
    before_image = df["image_url"].notna().sum() if "image_url" in df.columns else 0

    merged = df.merge(lookup, on="Wyscout id", how="left", suffixes=("", "__tm"))

    # image_url: Wyscout Image is primary, TM image_url is fallback.
    # Suffix "__tm" only appears when df already had image_url; otherwise lookup's
    # image_url lands unsuffixed (no collision). Extract both before resolving.
    if "image_url__tm" in merged.columns:
        tm_series = merged.pop("image_url__tm")
    elif "Image" in merged.columns and "image_url" in merged.columns:
        # df had no image_url; lookup brought it in without suffix — steal it
        tm_series = merged["image_url"].copy()
        merged = merged.drop(columns=["image_url"])
    else:
        tm_series = None

    wy_series = merged.pop("Image") if "Image" in merged.columns else None

    PHOTO_NOT_FOUND = "https://cdn5.wyscout.com/reports-img/photo-not-found.png"
    if wy_series is not None:
        wy_valid = wy_series.str.startswith("http", na=False) & (wy_series != PHOTO_NOT_FOUND)
        if tm_series is not None:
            merged["image_url"] = wy_series.where(wy_valid, other=tm_series)
        else:
            merged["image_url"] = wy_series
    elif tm_series is not None:
        existing = merged["image_url"] if "image_url" in merged.columns else None
        if existing is not None:
            merged["image_url"] = existing.combine_first(tm_series)
        else:
            merged["image_url"] = tm_series

    # Height: if height_in_cm present, replace
    if "Height" in merged.columns and "height_in_cm" in merged.columns:
        new_h = pd.to_numeric(merged["height_in_cm"], errors="coerce")
        old_h = pd.to_numeric(merged["Height"], errors="coerce")
        merged["Height"] = new_h.combine_first(old_h)
    elif "Height" not in merged.columns and "height_in_cm" in merged.columns:
        merged["Height"] = pd.to_numeric(merged["height_in_cm"], errors="coerce")
    if "height_in_cm" in merged.columns:
        merged = merged.drop(columns=["height_in_cm"])

    after_image = merged["image_url"].notna().sum() if "image_url" in merged.columns else 0
    height_filled = merged["Height"].notna().sum() if "Height" in merged.columns else 0

    if not dry_run:
        merged.to_csv(path, index=False)

    return {
        "file": path.name,
        "rows": len(merged),
        "image_url_added": int(after_image - before_image),
        "image_url_total": int(after_image),
        "height_filled": int(height_filled),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Don't write files")
    args = parser.parse_args()

    if not WYSCOUT_DIR.exists():
        print(f"Wyscout dir not found: {WYSCOUT_DIR}", file=sys.stderr)
        return 1
    if not (TM_DIR / "people.csv").exists():
        print(f"Missing {TM_DIR / 'people.csv'}", file=sys.stderr)
        return 1

    print("Loading TM mapping…")
    lookup = _build_lookup()
    print(f"  {len(lookup):,} distinct player ids (Wyscout-id + Soccerway-id) with TM rows")

    files = sorted(WYSCOUT_DIR.glob("*.csv"))
    print(f"Enriching {len(files)} wyscout CSVs…")
    for f in files:
        info = enrich_csv(f, lookup, dry_run=args.dry_run)
        print(
            f"  {info['file']}: rows={info.get('rows', '—')} "
            f"image_url_total={info.get('image_url_total', '—')} "
            f"height_filled={info.get('height_filled', '—')}"
        )
    if args.dry_run:
        print("\n(dry-run — no files written)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
