"""Build centralized Wyscout player photo lookup.

Walks ``data/players/all/*_all_leagues.parquet`` newest → oldest and keeps the
first non-null Wyscout image URL seen per ``Wyscout id``. Output:

  data/players/player_photos.parquet
  columns: wyscout_id (int64), Image (str)

Skips Transfermarkt URLs and the Wyscout ``photo-not-found.png`` placeholder.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from repo_paths import repo_root

PHOTO_NOT_FOUND_URL = "https://cdn5.wyscout.com/reports-img/photo-not-found.png"
WYSCOUT_HOST = "cdn5.wyscout.com"


def _season_from_filename(name: str) -> int | None:
    m = re.match(r"(20\d{2})_all_leagues\.parquet$", name)
    return int(m.group(1)) if m else None


def _is_wyscout_url(url: object) -> bool:
    if not isinstance(url, str):
        return False
    s = url.strip()
    if not s.startswith("http"):
        return False
    if s == PHOTO_NOT_FOUND_URL:
        return False
    return WYSCOUT_HOST in s


def main() -> None:
    root = repo_root(Path(__file__))
    src_dir = root / "data" / "players" / "all"
    out_path = root / "data" / "players" / "player_photos.parquet"

    files = sorted(
        (f for f in src_dir.glob("*_all_leagues.parquet") if _season_from_filename(f.name)),
        key=lambda f: _season_from_filename(f.name) or 0,
        reverse=True,
    )
    if not files:
        raise SystemExit(f"No parquets found in {src_dir}")

    photos: dict[int, str] = {}  # wyscout_id -> Wyscout image URL
    for f in files:
        year = _season_from_filename(f.name)
        df = pd.read_parquet(f, columns=["Wyscout id", "image_url"])
        df = df[df["image_url"].apply(_is_wyscout_url)]
        df = df.dropna(subset=["Wyscout id"])
        df["Wyscout id"] = df["Wyscout id"].astype("int64")

        added = 0
        for wid, url in zip(df["Wyscout id"], df["image_url"]):
            if wid not in photos:
                photos[int(wid)] = url
                added += 1
        print(f"  {year}: scanned {len(df)} Wyscout images, added {added} new (total: {len(photos)})")

    out = pd.DataFrame({"wyscout_id": list(photos.keys()), "Image": list(photos.values())})
    out = out.sort_values("wyscout_id").reset_index(drop=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(out_path, index=False)
    print(f"\nwrote {len(out)} rows -> {out_path}")


if __name__ == "__main__":
    main()
