"""Fetch Wyscout `playerHeatmap` for every (wyscout_id, competition_id) in the
latest season parquet and write a parquet under
``data/players/heatmaps/heatmaps_{year}.parquet``.

Re-runs skip already-cached pairs (read existing parquet → diff → fetch only
missing → append). Designed to be idempotent.

Env vars (same as ``scripts/download_data.py``):
  WYSCOUT_SEARCH_TOKEN
  WYSCOUT_GROUP_ID
  WYSCOUT_SUBGROUP_ID
"""

from __future__ import annotations

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parent))
from download_data import ALLOWED_LEAGUE_WYSCOUT_IDS  # noqa: E402
from repo_paths import repo_root  # noqa: E402
from wyscout_heatmap_lib import (  # noqa: E402
    HeatmapFetchResult,
    build_graphql_url,
    fetch_one,
    iter_todo,
)

CURRENT_SEASON_YEARS: tuple[int, ...] = (2026,)

MAX_WORKERS = 5
FLUSH_EVERY = 500
REQUEST_TIMEOUT_SEC = 30
MAX_RETRIES = 3
RETRY_BACKOFF_SEC = 6.0


PARQUET_SCHEMA = pa.schema(
    [
        pa.field("wyscout_id", pa.int64()),
        pa.field("competition_id", pa.int32()),
        pa.field("competition", pa.string()),
        pa.field("season_year", pa.int32()),
        pa.field(
            "points",
            pa.list_(
                pa.struct(
                    [
                        pa.field("x", pa.float32()),
                        pa.field("y", pa.float32()),
                        pa.field("count", pa.int32()),
                    ]
                )
            ),
        ),
        pa.field("n_points", pa.int32()),
        pa.field("fetched_at", pa.timestamp("us", tz="UTC")),
    ]
)


def _build_competition_lookup() -> dict[str, int]:
    """Map league display ``name`` → ``competition_id``.

    Source is :data:`ALLOWED_LEAGUE_WYSCOUT_IDS` in ``download_data.py``.
    The ``name`` field there matches the ``Competition`` column in the
    consolidated parquets.
    """
    return {
        entry["name"]: int(entry["competition_id"])
        for entry in ALLOWED_LEAGUE_WYSCOUT_IDS
    }


def _read_source_pairs(parquet_path: Path) -> pd.DataFrame:
    """Read (wyscout_id, competition_id, competition) from a season parquet.

    Drops rows where Wyscout id or Competition is missing. De-dupes on the
    (wyscout_id, competition_id) pair.
    """
    df = pd.read_parquet(parquet_path, columns=["Wyscout id", "Competition"])
    df = df.dropna(subset=["Wyscout id", "Competition"])
    df = df.rename(columns={"Wyscout id": "wyscout_id", "Competition": "competition"})
    df["wyscout_id"] = df["wyscout_id"].astype("int64")
    lookup = _build_competition_lookup()
    df["competition_id"] = df["competition"].map(lookup).astype("Int32")
    unknown = df[df["competition_id"].isna()]
    if not unknown.empty:
        names = sorted(unknown["competition"].unique().tolist())
        print(
            f"  WARN: {len(unknown)} rows with unknown Competition (no competition_id) — "
            f"skipping. Names: {names}"
        )
    df = df.dropna(subset=["competition_id"])
    df["competition_id"] = df["competition_id"].astype("int32")
    return df.drop_duplicates(subset=["wyscout_id", "competition_id"]).reset_index(drop=True)


def _read_existing_pairs(out_path: Path) -> set[tuple[int, int]]:
    if not out_path.exists():
        return set()
    df = pd.read_parquet(out_path, columns=["wyscout_id", "competition_id"])
    return {
        (int(r.wyscout_id), int(r.competition_id))
        for r in df.itertuples(index=False)
    }


def _results_to_table(
    results: list[HeatmapFetchResult],
    competition_by_id: dict[int, str],
    season_year: int,
) -> pa.Table:
    now = datetime.now(timezone.utc)
    rows = []
    for r in results:
        rows.append(
            {
                "wyscout_id": int(r.wyscout_id),
                "competition_id": int(r.competition_id),
                "competition": competition_by_id.get(int(r.competition_id), ""),
                "season_year": int(season_year),
                "points": [
                    {"x": float(p.x), "y": float(p.y), "count": int(p.count)}
                    for p in r.points
                ],
                "n_points": int(len(r.points)),
                "fetched_at": now,
            }
        )
    return pa.Table.from_pylist(rows, schema=PARQUET_SCHEMA)


def _atomic_write(table: pa.Table, out_path: Path) -> None:
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    pq.write_table(table, tmp, compression="zstd")
    tmp.replace(out_path)


def _flush(
    *,
    new_results: list[HeatmapFetchResult],
    out_path: Path,
    competition_by_id: dict[int, str],
    season_year: int,
) -> None:
    if not new_results:
        return
    new_table = _results_to_table(new_results, competition_by_id, season_year)
    if out_path.exists():
        existing = pq.read_table(out_path)
        combined = pa.concat_tables([existing, new_table], promote_options="default")
    else:
        combined = new_table
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(combined, out_path)


def _process_season(
    *,
    season_year: int,
    source_parquet: Path,
    out_parquet: Path,
    graphql_url: str,
    competition_by_id: dict[int, str],
) -> None:
    print(f"\n=== season {season_year} ===")
    print(f"  source: {source_parquet}")
    print(f"  output: {out_parquet}")
    pairs_df = _read_source_pairs(source_parquet)
    pairs: list[tuple[int, int]] = [
        (int(r.wyscout_id), int(r.competition_id))
        for r in pairs_df.itertuples(index=False)
    ]
    already = _read_existing_pairs(out_parquet)
    todo = iter_todo(pairs, already)
    print(
        f"  pairs: total={len(pairs)} cached={len(already)} todo={len(todo)}"
    )
    if not todo:
        return

    new_results: list[HeatmapFetchResult] = []
    lock = Lock()
    fail_count = 0
    started = time.time()

    def _task(pair: tuple[int, int]) -> HeatmapFetchResult:
        wid, cid = pair
        return fetch_one(
            url=graphql_url,
            wyscout_id=wid,
            competition_id=cid,
            timeout_sec=REQUEST_TIMEOUT_SEC,
            max_retries=MAX_RETRIES,
            retry_backoff_sec=RETRY_BACKOFF_SEC,
        )

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {ex.submit(_task, p): p for p in todo}
        for i, fut in enumerate(as_completed(futures), start=1):
            pair = futures[fut]
            try:
                result = fut.result()
            except Exception as e:
                fail_count += 1
                print(
                    f"  FAIL ({pair[0]}, {pair[1]}): {type(e).__name__}: {e}",
                    file=sys.stderr,
                )
                continue
            with lock:
                new_results.append(result)
                if len(new_results) >= FLUSH_EVERY:
                    _flush(
                        new_results=new_results,
                        out_path=out_parquet,
                        competition_by_id=competition_by_id,
                        season_year=season_year,
                    )
                    new_results.clear()
            if i % 100 == 0:
                elapsed = time.time() - started
                rate = i / elapsed if elapsed else 0
                print(
                    f"  progress: {i}/{len(todo)} ({rate:.1f}/s) fails={fail_count}"
                )

    with lock:
        _flush(
            new_results=new_results,
            out_path=out_parquet,
            competition_by_id=competition_by_id,
            season_year=season_year,
        )
        new_results.clear()

    elapsed = time.time() - started
    ok = len(todo) - fail_count
    print(f"  done: ok={ok} fails={fail_count} in {elapsed:.1f}s")


def main() -> None:
    token = os.environ.get("WYSCOUT_SEARCH_TOKEN")
    group_id = os.environ.get("WYSCOUT_GROUP_ID")
    subgroup_id = os.environ.get("WYSCOUT_SUBGROUP_ID")
    if not token or not group_id or not subgroup_id:
        raise SystemExit(
            "Set WYSCOUT_SEARCH_TOKEN, WYSCOUT_GROUP_ID, and WYSCOUT_SUBGROUP_ID."
        )
    url = build_graphql_url(token=token, group_id=group_id, subgroup_id=subgroup_id)

    root = repo_root(Path(__file__))
    competition_by_id = {
        int(e["competition_id"]): e["name"] for e in ALLOWED_LEAGUE_WYSCOUT_IDS
    }

    for year in CURRENT_SEASON_YEARS:
        source = root / "data" / "players" / "all" / f"{year}_all_leagues.parquet"
        if not source.exists():
            print(f"Skipping {year}: {source} not found")
            continue
        out_path = root / "data" / "players" / "heatmaps" / f"heatmaps_{year}.parquet"
        _process_season(
            season_year=year,
            source_parquet=source,
            out_parquet=out_path,
            graphql_url=url,
            competition_by_id=competition_by_id,
        )

    print("\nDone.")


if __name__ == "__main__":
    main()
