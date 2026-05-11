# Player Heatmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-player Wyscout heatmap pipeline (fetcher + parquet + API endpoint + SVG overlay) so the Profile pitch card renders a soft heat-glow base layer under the existing position zones for the current season(s).

**Architecture:** New script `scripts/download_heatmaps.py` writes one parquet per "current" season year (`heatmaps_2025.parquet`, `heatmaps_2026.parquet`). DuckDB pool registers each as a view. A thin FastAPI router `GET /players/{wyscout_id}/heatmap?season=Y&competition_id=N` returns `{points, max_count, …}`. Frontend extends `PlayerPositionPitch` with an optional `heatmap` prop and a TanStack Query in the profile client.

**Tech Stack:** Python 3.12 + `urllib` + `concurrent.futures.ThreadPoolExecutor` + `pyarrow`; FastAPI + Pydantic v2 + DuckDB; Next.js 16 + TanStack Query 5 + SVG + Tailwind 4.

---

## Pre-flight

- Make sure you are in the monorepo root (`/Users/fbobiano/Projects/raumdeuterappv2`).
- Confirm parquets exist: `ls data/players/all/2025_all_leagues.parquet data/players/all/2026_all_leagues.parquet`.
- Env vars must be set before running the script (Task 2): `WYSCOUT_SEARCH_TOKEN`, `WYSCOUT_GROUP_ID`, `WYSCOUT_SUBGROUP_ID`.
- pnpm + uv are installed.

---

## Task 1: Add competition-id helper module

**Files:**
- Create: `scripts/wyscout_heatmap_lib.py`

**Purpose:** Isolate the GraphQL request + retry + JSON parsing so the main script stays small and the logic is unit-testable later. No I/O to parquet here.

- [ ] **Step 1: Create the helper file**

Create `scripts/wyscout_heatmap_lib.py`:

```python
"""Helpers for fetching Wyscout `playerHeatmap` GraphQL responses.

Used by `scripts/download_heatmaps.py`. Pure functions — no parquet I/O,
no global state. Keeps the main script readable and the logic testable.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Iterable

# Same operation name + query string as the curl example from the user.
HEATMAP_QUERY = (
    "query Player($playerId: ID!, $timeframe: TimeframeEnum, "
    "$timeframeYouthMode: Boolean, $timeframeCompetitionId: ID) {\n"
    "  playerHeatmap(playerId: $playerId, timeframe: $timeframe, "
    "timeframeYouthMode: $timeframeYouthMode, "
    "timeframeCompetitionId: $timeframeCompetitionId) {\n"
    "    points {\n      x\n      y\n      count\n      __typename\n    }\n"
    "    __typename\n  }\n}\n"
)

GRAPHQL_URL = "https://searchapi.wyscout.com/graphql"

REQUEST_HEADERS = {
    "accept": "*/*",
    "content-type": "application/json",
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "origin": "https://wyscout-apps.hudl.com",
    "referer": "https://wyscout-apps.hudl.com/",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
    ),
}


@dataclass(frozen=True)
class HeatmapPoint:
    x: float
    y: float
    count: int


@dataclass(frozen=True)
class HeatmapFetchResult:
    wyscout_id: int
    competition_id: int
    points: tuple[HeatmapPoint, ...]


def build_graphql_url(*, token: str, group_id: str, subgroup_id: str) -> str:
    qs = urllib.parse.urlencode(
        {"token": token, "groupId": group_id, "subgroupId": subgroup_id}
    )
    return f"{GRAPHQL_URL}?{qs}"


def build_body(*, wyscout_id: int, competition_id: int) -> bytes:
    payload = {
        "operationName": "Player",
        "variables": {
            "playerId": wyscout_id,
            "timeframeYouthMode": False,
            "timeframeCompetitionId": competition_id,
        },
        "query": HEATMAP_QUERY,
    }
    return json.dumps(payload).encode("utf-8")


def parse_points(payload: object) -> tuple[HeatmapPoint, ...]:
    """Extract `data.playerHeatmap.points` from a GraphQL response.

    Returns an empty tuple when the player has no heatmap (Wyscout returns
    ``{"data": {"playerHeatmap": null}}`` for players with no minutes).
    Raises ``ValueError`` if the shape is unexpected (so the caller can
    retry / log).
    """
    if not isinstance(payload, dict):
        raise ValueError("response is not a JSON object")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("missing `data` key")
    heatmap = data.get("playerHeatmap")
    if heatmap is None:
        return ()
    if not isinstance(heatmap, dict):
        raise ValueError("`playerHeatmap` is not an object")
    points = heatmap.get("points")
    if points is None:
        return ()
    if not isinstance(points, list):
        raise ValueError("`points` is not a list")
    out: list[HeatmapPoint] = []
    for p in points:
        if not isinstance(p, dict):
            continue
        try:
            out.append(
                HeatmapPoint(
                    x=float(p["x"]),
                    y=float(p["y"]),
                    count=int(p["count"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return tuple(out)


def fetch_one(
    *,
    url: str,
    wyscout_id: int,
    competition_id: int,
    timeout_sec: int = 30,
    max_retries: int = 3,
    retry_backoff_sec: float = 6.0,
) -> HeatmapFetchResult:
    """POST GraphQL request with linear backoff on HTTP 429/5xx.

    Raises the last exception on persistent failure so the main loop can
    log it and move on (without writing a partial row).
    """
    body = build_body(wyscout_id=wyscout_id, competition_id=competition_id)
    req = urllib.request.Request(
        url, data=body, headers=REQUEST_HEADERS, method="POST"
    )

    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                raw = resp.read().decode("utf-8")
            payload = json.loads(raw)
            points = parse_points(payload)
            return HeatmapFetchResult(
                wyscout_id=wyscout_id,
                competition_id=competition_id,
                points=points,
            )
        except urllib.error.HTTPError as e:
            last_exc = e
            if e.code not in (429, 500, 502, 503, 504):
                raise
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            last_exc = e

        if attempt < max_retries - 1:
            time.sleep(retry_backoff_sec)

    assert last_exc is not None
    raise last_exc


def iter_todo(
    pairs: Iterable[tuple[int, int]],
    already_done: set[tuple[int, int]],
) -> list[tuple[int, int]]:
    """Filter input (wyscout_id, competition_id) pairs against a cache set."""
    return [p for p in pairs if p not in already_done]
```

- [ ] **Step 2: Quick local sanity (no test framework yet)**

Run:

```bash
cd /Users/fbobiano/Projects/raumdeuterappv2
python -c "from scripts.wyscout_heatmap_lib import parse_points; \
  print(parse_points({'data': {'playerHeatmap': None}})); \
  print(len(parse_points({'data': {'playerHeatmap': {'points': [{'x':1.0,'y':2.0,'count':3}]}}})))"
```

Expected stdout:

```
()
1
```

- [ ] **Step 3: Commit**

```bash
git add scripts/wyscout_heatmap_lib.py
git commit -m "feat(scripts): wyscout playerHeatmap GraphQL helper lib"
```

---

## Task 2: Add `scripts/download_heatmaps.py`

**Files:**
- Create: `scripts/download_heatmaps.py`

**Purpose:** Orchestrator. Reads source parquets, computes work list, runs 5 workers, writes per-season parquet with skip-existing semantics. Operational script (no unit test — manual verification on a single league first).

- [ ] **Step 1: Create the script**

Create `scripts/download_heatmaps.py`:

```python
"""Fetch Wyscout `playerHeatmap` for every (wyscout_id, competition_id) in the
current season parquet(s) and write a parquet per season under
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
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# Importing the existing single source of truth for league → competition_id.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from download_data import ALLOWED_LEAGUE_WYSCOUT_IDS  # noqa: E402
from repo_paths import repo_root  # noqa: E402
from wyscout_heatmap_lib import (  # noqa: E402
    HeatmapFetchResult,
    build_graphql_url,
    fetch_one,
    iter_todo,
)

# Both years are "current" simultaneously because split-year leagues end in
# 2026 (e.g. Premier League 2025/26) and single-year leagues run in 2026
# (e.g. MLS, Allsvenskan). Update on season roll.
CURRENT_SEASON_YEARS: tuple[int, ...] = (2025, 2026)

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
    """Map league display `name` → `competition_id`.

    Source is `ALLOWED_LEAGUE_WYSCOUT_IDS` in `download_data.py`. The `name`
    field there matches the `Competition` column in the consolidated parquets.
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
    now = datetime.now(UTC)
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
                print(f"  FAIL ({pair[0]}, {pair[1]}): {type(e).__name__}: {e}", file=sys.stderr)
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
```

- [ ] **Step 2: Smoke-run on one league only (manual verification)**

Temporarily edit `_process_source_pairs` filter to one league for a fast first run. Easiest patch — at the end of `_read_source_pairs`, add (then revert):

```python
df = df[df["competition"] == "Primeira Liga"]
```

Run:

```bash
cd /Users/fbobiano/Projects/raumdeuterappv2
WYSCOUT_SEARCH_TOKEN=... WYSCOUT_GROUP_ID=... WYSCOUT_SUBGROUP_ID=... \
  python scripts/download_heatmaps.py
```

Expected: progress log, eventually `done: ok=~500 fails=0`, file at `data/players/heatmaps/heatmaps_2025.parquet`.

- [ ] **Step 3: Inspect the parquet via DuckDB**

```bash
cd /Users/fbobiano/Projects/raumdeuterappv2
python -c "
import duckdb
c = duckdb.connect()
r = c.execute(\"SELECT wyscout_id, competition, n_points, len(points) FROM read_parquet('data/players/heatmaps/heatmaps_2025.parquet') LIMIT 5\").fetchall()
for row in r: print(row)
print('total:', c.execute(\"SELECT count(*) FROM read_parquet('data/players/heatmaps/heatmaps_2025.parquet')\").fetchone()[0])
"
```

Expected: 5 rows printed, total ~500 (or whatever the league count is).

- [ ] **Step 4: Revert the one-league filter and commit the script**

Remove the `df = df[df["competition"] == "Primeira Liga"]` line.

```bash
git add scripts/download_heatmaps.py
git commit -m "feat(scripts): download Wyscout player heatmaps to parquet"
```

- [ ] **Step 5: Run the full pipeline (optional — can run later)**

```bash
WYSCOUT_SEARCH_TOKEN=... WYSCOUT_GROUP_ID=... WYSCOUT_SUBGROUP_ID=... \
  python scripts/download_heatmaps.py
```

Expected: two seasons processed, ~5–15 min total, files at:
- `data/players/heatmaps/heatmaps_2025.parquet`
- `data/players/heatmaps/heatmaps_2026.parquet`

No commit — data lives outside git (symlinked).

---

## Task 3: Register heatmap views in the DuckDB pool

**Files:**
- Modify: `apps/api/app/core/duckdb_pool.py`

- [ ] **Step 1: Add registration block at the end of `_register_views`**

Open `apps/api/app/core/duckdb_pool.py`. After the `player_photos` registration block (currently the last block in `_register_views`), append:

```python
    # Player heatmaps — per-season parquet under data/players/heatmaps/.
    # File pattern: heatmaps_{year}.parquet. Built by scripts/download_heatmaps.py.
    heatmaps_dir = settings.data_dir / "players" / "heatmaps"
    if heatmaps_dir.exists():
        for f in sorted(heatmaps_dir.glob("heatmaps_*.parquet")):
            stem = f.stem  # e.g. heatmaps_2025
            try:
                year = int(stem.split("_")[1])
            except (IndexError, ValueError):
                continue
            conn.execute(
                f"CREATE OR REPLACE VIEW heatmaps_{year} AS "
                f"SELECT * FROM read_parquet('{f.as_posix()}')"
            )
```

- [ ] **Step 2: Verify the view registers (manual)**

Run a tiny check (requires the parquet to exist from Task 2 step 2 or step 5):

```bash
cd /Users/fbobiano/Projects/raumdeuterappv2/apps/api
PATH="$HOME/.local/bin:$PATH" uv run python -c "
from app.core.duckdb_pool import duckdb_session, list_views
with duckdb_session():
    views = list_views()
print([v for v in views if v.startswith('heatmaps_')])
"
```

Expected: `['heatmaps_2025']` (and/or `heatmaps_2026` if you ran the full pipeline).

- [ ] **Step 3: Commit**

```bash
git add apps/api/app/core/duckdb_pool.py
git commit -m "feat(api): register heatmaps_{year} DuckDB views"
```

---

## Task 4: Add Pydantic schemas

**Files:**
- Modify: `apps/api/app/schemas.py`

- [ ] **Step 1: Append the new models at the end of `schemas.py`**

Add at the bottom of `apps/api/app/schemas.py`:

```python
# ── F8: Heatmap ────────────────────────────────────────────────────────────────


class HeatmapPoint(BaseModel):
    x: float
    y: float
    count: int


class HeatmapResponse(BaseModel):
    wyscout_id: int
    competition_id: int
    competition: str
    season: int
    points: list[HeatmapPoint]
    n_points: int
    max_count: int
```

- [ ] **Step 2: Verify import still works**

```bash
cd /Users/fbobiano/Projects/raumdeuterappv2/apps/api
PATH="$HOME/.local/bin:$PATH" uv run python -c "from app.schemas import HeatmapResponse, HeatmapPoint; print('ok')"
```

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add apps/api/app/schemas.py
git commit -m "feat(api): HeatmapPoint + HeatmapResponse schemas"
```

---

## Task 5: Core lookup module

**Files:**
- Create: `apps/api/app/core/player_heatmap.py`

- [ ] **Step 1: Create the core module**

Create `apps/api/app/core/player_heatmap.py`:

```python
"""Look up a stored player heatmap from the DuckDB pool.

No FastAPI imports — pure data access. Routers wrap this in HTTP semantics.
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb

from app.core.duckdb_pool import list_views


@dataclass(frozen=True)
class HeatmapData:
    wyscout_id: int
    competition_id: int
    competition: str
    season: int
    points: list[dict]  # [{"x": float, "y": float, "count": int}, ...]
    max_count: int


def fetch_heatmap(
    conn: duckdb.DuckDBPyConnection,
    *,
    wyscout_id: int,
    season: int,
    competition_id: int | None = None,
) -> HeatmapData | None:
    """Return a HeatmapData or None if the view / row is missing."""
    view = f"heatmaps_{season}"
    if view not in list_views():
        return None

    if competition_id is not None:
        sql = (
            f'SELECT wyscout_id, competition_id, competition, points '
            f'FROM "{view}" '
            f'WHERE wyscout_id = ? AND competition_id = ? '
            f'LIMIT 1'
        )
        params = [int(wyscout_id), int(competition_id)]
    else:
        sql = (
            f'SELECT wyscout_id, competition_id, competition, points '
            f'FROM "{view}" '
            f'WHERE wyscout_id = ? '
            f'ORDER BY competition_id ASC '
            f'LIMIT 1'
        )
        params = [int(wyscout_id)]

    row = conn.execute(sql, params).fetchone()
    if row is None:
        return None

    raw_points = row[3] or []
    points: list[dict] = []
    max_count = 0
    for p in raw_points:
        # DuckDB returns list<struct> as list[dict] (named struct fields).
        if isinstance(p, dict):
            x, y, c = p.get("x"), p.get("y"), p.get("count")
        else:
            # Fallback for tuple-shaped struct returns.
            x, y, c = p[0], p[1], p[2]
        if x is None or y is None or c is None:
            continue
        cint = int(c)
        points.append({"x": float(x), "y": float(y), "count": cint})
        if cint > max_count:
            max_count = cint

    return HeatmapData(
        wyscout_id=int(row[0]),
        competition_id=int(row[1]),
        competition=str(row[2]) if row[2] is not None else "",
        season=int(season),
        points=points,
        max_count=int(max_count),
    )
```

- [ ] **Step 2: Verify import**

```bash
cd /Users/fbobiano/Projects/raumdeuterappv2/apps/api
PATH="$HOME/.local/bin:$PATH" uv run python -c "from app.core.player_heatmap import fetch_heatmap, HeatmapData; print('ok')"
```

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add apps/api/app/core/player_heatmap.py
git commit -m "feat(api): core fetch_heatmap from heatmaps_{year} view"
```

---

## Task 6: HTTP router + wire into `main.py`

**Files:**
- Create: `apps/api/app/routers/heatmap.py`
- Modify: `apps/api/app/main.py`

- [ ] **Step 1: Create the router**

Create `apps/api/app/routers/heatmap.py`:

```python
"""Per-player Wyscout heatmap endpoint (current season(s) only)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.core.duckdb_pool import duckdb_session
from app.core.player_heatmap import fetch_heatmap
from app.schemas import HeatmapPoint, HeatmapResponse

router = APIRouter(prefix="/players", tags=["heatmap"])


@router.get("/{wyscout_id}/heatmap", response_model=HeatmapResponse)
def get_heatmap(
    wyscout_id: int,
    season: int = Query(..., ge=2015, le=2099),
    competition_id: int | None = Query(None),
) -> HeatmapResponse:
    with duckdb_session() as conn:
        data = fetch_heatmap(
            conn,
            wyscout_id=wyscout_id,
            season=season,
            competition_id=competition_id,
        )
    if data is None:
        raise HTTPException(404, "No heatmap for this player/season")

    return HeatmapResponse(
        wyscout_id=data.wyscout_id,
        competition_id=data.competition_id,
        competition=data.competition,
        season=data.season,
        points=[HeatmapPoint(**p) for p in data.points],
        n_points=len(data.points),
        max_count=data.max_count,
    )
```

- [ ] **Step 2: Wire into `main.py`**

Open `apps/api/app/main.py`. Add `heatmap` to the import list (alphabetically) and `include_router` call.

Change the import block:

```python
from app.routers import (
    bar,
    bar_ranking,
    heatmap,
    meta,
    players,
    potential,
    profile,
    progression,
    rankings,
    replacement,
    scatter,
    screener,
    team_minutes,
    teams,
    translation,
)
```

Add the include line (group with other `include_router` calls — place after `potential`):

```python
app.include_router(heatmap.router)
```

- [ ] **Step 3: Boot the API and probe the endpoint**

Terminal 1:

```bash
cd /Users/fbobiano/Projects/raumdeuterappv2/apps/api
PATH="$HOME/.local/bin:$PATH" uv run uvicorn app.main:app --port 8000
```

Terminal 2 (find a wyscout id from the source parquet that you fetched in Task 2):

```bash
curl -s 'http://localhost:8000/players/SOME_ID/heatmap?season=2025' | head -c 400
```

Expected: JSON with `wyscout_id`, `points: [...]`, `max_count`. For an unknown id: `{"detail":"No heatmap for this player/season"}` with status 404.

- [ ] **Step 4: Commit**

```bash
git add apps/api/app/routers/heatmap.py apps/api/app/main.py
git commit -m "feat(api): GET /players/{id}/heatmap endpoint"
```

---

## Task 7: Smoke test

**Files:**
- Modify: `apps/api/tests/test_endpoints.py`

- [ ] **Step 1: Add a TestClient smoke test at the end of the file**

Append to `apps/api/tests/test_endpoints.py`:

```python
def test_heatmap_smoke() -> None:
    with TestClient(app) as c:
        seasons = c.get("/meta/seasons").json()
        if not seasons:
            return
        # Use the most recent season (where heatmaps live).
        season = seasons[0]
        rows = c.get(
            f"/players/search?season={season}&q=salah&limit=1"
        ).json()
        if not rows or rows[0].get("wyscout_id") is None:
            return
        wid = rows[0]["wyscout_id"]
        r = c.get(f"/players/{wid}/heatmap", params={"season": season})
        # 404 is acceptable when the heatmaps parquet hasn't been generated
        # yet (CI / fresh checkout). 200 must return valid shape.
        assert r.status_code in (200, 404), r.text
        if r.status_code == 200:
            d = r.json()
            assert d["wyscout_id"] == wid
            assert isinstance(d["points"], list)
            assert "max_count" in d
            assert "n_points" in d
            for p in d["points"][:5]:
                assert set(p.keys()) >= {"x", "y", "count"}
```

- [ ] **Step 2: Run the test**

```bash
cd /Users/fbobiano/Projects/raumdeuterappv2/apps/api
PATH="$HOME/.local/bin:$PATH" uv run pytest tests/test_endpoints.py::test_heatmap_smoke -v
```

Expected: PASS.

- [ ] **Step 3: Run the full test file (no regressions)**

```bash
PATH="$HOME/.local/bin:$PATH" uv run pytest -q
```

Expected: all tests green (or same set passing as before this branch).

- [ ] **Step 4: Commit**

```bash
git add apps/api/tests/test_endpoints.py
git commit -m "test(api): smoke for /players/{id}/heatmap"
```

---

## Task 8: Regenerate OpenAPI + TypeScript types

**Files:**
- Modify: `packages/shared-types/openapi.json` (generated)
- Modify: `packages/shared-types/src/api.d.ts` (generated)

- [ ] **Step 1: Regen the OpenAPI snapshot**

```bash
cd /Users/fbobiano/Projects/raumdeuterappv2/apps/api
PATH="$HOME/.local/bin:$PATH" uv run python -c \
  "import json; from app.main import app; print(json.dumps(app.openapi()))" \
  > ../../packages/shared-types/openapi.json
```

- [ ] **Step 2: Regen the TS types**

```bash
cd /Users/fbobiano/Projects/raumdeuterappv2
pnpm --filter shared-types gen
```

Expected: `packages/shared-types/src/api.d.ts` updated. No errors.

- [ ] **Step 3: Verify the type appears in TS**

```bash
cd /Users/fbobiano/Projects/raumdeuterappv2
grep -c 'players/{wyscout_id}/heatmap' packages/shared-types/src/api.d.ts
```

Expected: `1` (or higher — both the path and component type generate entries).

- [ ] **Step 4: Typecheck the web app**

```bash
cd /Users/fbobiano/Projects/raumdeuterappv2/apps/web
pnpm exec tsc --noEmit
```

Expected: no errors.

- [ ] **Step 5: Commit**

```bash
cd /Users/fbobiano/Projects/raumdeuterappv2
git add packages/shared-types/openapi.json packages/shared-types/src/api.d.ts
git commit -m "chore(types): regen OpenAPI + TS for /heatmap endpoint"
```

---

## Task 9: Extend `PlayerPositionPitch` with optional heatmap layer

**Files:**
- Modify: `apps/web/src/components/domain/player-position-pitch.tsx`

- [ ] **Step 1: Add heatmap rendering inside the same SVG**

Open `apps/web/src/components/domain/player-position-pitch.tsx`.

(a) Extend the `Props` interface (replace the existing block):

```tsx
export interface HeatmapInput {
  points: { x: number; y: number; count: number }[];
  maxCount: number;
}

interface Props {
  primaryTokens: string[];
  secondaryTokens?: string[];
  heatmap?: HeatmapInput | null;
  className?: string;
}
```

(b) Update the function signature:

```tsx
export function PlayerPositionPitch({
  primaryTokens,
  secondaryTokens = [],
  heatmap = null,
  className,
}: Props) {
```

(c) Add helpers above the JSX `return`:

```tsx
const heatmapId = React.useId();
const heatmapPoints = React.useMemo(() => {
  if (!heatmap || !heatmap.points.length || heatmap.maxCount <= 0) return [];
  const R_BASE = 0.5;
  const R_SCALE = 2.3;
  const max = heatmap.maxCount;
  return heatmap.points.map((p) => {
    const ratio = Math.min(1, Math.max(0, p.count / max));
    const r = R_BASE + R_SCALE * Math.sqrt(ratio);
    const opacity = 0.22 + 0.55 * ratio;
    // Wyscout: x = pitch length (0 own → 100 opponent), y = pitch width.
    // SVG: y axis is flipped (attacking up = small y).
    const svgX = p.y;
    const svgY = 100 - p.x;
    return { svgX, svgY, r, opacity };
  });
}, [heatmap]);
```

(d) Insert the heatmap `<g>` between the pitch lines and the zone circles. Inside the `<svg>` block, find:

```tsx
          <rect x="32" y="84" width="36" height="14" fill="none" stroke={LINE} strokeWidth="0.4" />

          {ZONES.map((z, i) => {
            const kind = zoneKind(z, primary, secondary);
            if (kind !== "secondary") return null;
```

Insert this between the last pitch-line `<rect>` and the secondary-zones `.map(...)`:

```tsx
          {heatmapPoints.length > 0 && (
            <>
              <defs>
                <radialGradient id={`hm-${heatmapId}`} cx="50%" cy="50%" r="50%">
                  <stop offset="0%" stopColor="#14d1ff" stopOpacity="0.95" />
                  <stop offset="60%" stopColor="#14d1ff" stopOpacity="0.4" />
                  <stop offset="100%" stopColor="#14d1ff" stopOpacity="0" />
                </radialGradient>
                <filter id={`hmblur-${heatmapId}`} x="-10%" y="-10%" width="120%" height="120%">
                  <feGaussianBlur stdDeviation="0.6" />
                </filter>
              </defs>
              <g
                filter={`url(#hmblur-${heatmapId})`}
                style={{ mixBlendMode: "screen" }}
              >
                {heatmapPoints.map((p, i) => (
                  <circle
                    key={`hm-${i}`}
                    cx={p.svgX}
                    cy={p.svgY}
                    r={p.r}
                    fill={`url(#hm-${heatmapId})`}
                    opacity={p.opacity}
                  />
                ))}
              </g>
            </>
          )}
```

(e) Add a small caption under the positions text block. Find the closing `</div>` of the `mt-3 space-y-1.5` block at the bottom of the JSX. Just before it, add:

```tsx
              {heatmap && heatmap.points.length > 0 && (
                <p className="text-on-surface-variant/80">
                  <span className="font-mono text-[0.65rem] font-semibold tracking-wider text-on-surface-variant/90">
                    Heatmap
                  </span>
                  <span className="mx-2 opacity-50">·</span>
                  <span className="data-mono opacity-85">
                    {heatmap.points.length} zones
                  </span>
                </p>
              )}
```

- [ ] **Step 2: Typecheck**

```bash
cd /Users/fbobiano/Projects/raumdeuterappv2/apps/web
pnpm exec tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/components/domain/player-position-pitch.tsx
git commit -m "feat(web): heatmap base layer on PlayerPositionPitch"
```

---

## Task 10: Fetch the heatmap from the profile client

**Files:**
- Modify: `apps/web/src/app/scout/profile/[wyscoutId]/profile-detail-client.tsx`

- [ ] **Step 1: Add the TanStack Query and pass it into the pitch**

Open `profile-detail-client.tsx`.

(a) After the existing `profileQ` block (around line ~113, right after `const p = profileQ.data;` on line 115), add:

```tsx
  const heatmapQ = useQuery({
    queryKey: ["heatmap", wyscoutId, season, p?.competition_id ?? null],
    queryFn: async () => {
      const { data, error, response } = await api.GET(
        "/players/{wyscout_id}/heatmap",
        {
          params: {
            path: { wyscout_id: wyscoutId },
            query: {
              season,
              competition_id: p?.competition_id ?? undefined,
            },
          },
        },
      );
      if (error) {
        if (response.status === 404) return null;
        throw error;
      }
      return data ?? null;
    },
    enabled: profileQ.isSuccess && Number.isFinite(wyscoutId),
    staleTime: 60 * 60 * 1000,
  });

  const heatmapForPitch = React.useMemo(() => {
    const h = heatmapQ.data;
    if (!h || !h.points.length) return null;
    return { points: h.points, maxCount: h.max_count };
  }, [heatmapQ.data]);
```

> **Note on `p.competition_id`:** the existing `/profile` response may not currently expose `competition_id`. If a typecheck error surfaces in Step 2, that field does NOT exist on the profile payload and you must either (a) add it to `apps/api/app/routers/profile.py` + schema (regen types), or (b) drop `competition_id` from the heatmap query and rely on the endpoint's `ORDER BY competition_id ASC` fallback. **Default behaviour: drop it.** Replace the `competition_id: p?.competition_id ?? undefined,` line with omitting that key entirely if the type doesn't allow it.

(b) Pass the prop into the existing `<PlayerPositionPitch>` (around line 225):

```tsx
              <PlayerPositionPitch
                primaryTokens={p.position_tokens_primary ?? (p.position_tokens ?? [])}
                secondaryTokens={p.position_tokens_secondary ?? []}
                heatmap={heatmapForPitch}
              />
```

- [ ] **Step 2: Typecheck**

```bash
cd /Users/fbobiano/Projects/raumdeuterappv2/apps/web
pnpm exec tsc --noEmit
```

If `p.competition_id` is not present on the profile type, follow the note above (omit the field from the query).

Expected: no errors.

- [ ] **Step 3: Manual visual verification**

Terminal 1 (API):

```bash
cd /Users/fbobiano/Projects/raumdeuterappv2/apps/api
PATH="$HOME/.local/bin:$PATH" uv run uvicorn app.main:app --port 8000
```

Terminal 2 (web — may already be running):

```bash
cd /Users/fbobiano/Projects/raumdeuterappv2/apps/web
pnpm dev
```

Open `http://localhost:3000/scout/profile/<some wyscout id with heatmap data>?season=2025` in a browser.

Verify:
- Heat blobs render under the position zone circles.
- Striker / winger: cluster top half. Defender: cluster bottom half. GK: cluster around y=98 (bottom edge for own goal).
- If orientation looks mirrored (CF appears at bottom), flip the mapping in `player-position-pitch.tsx`: change `const svgY = 100 - p.x;` to `const svgY = p.x;` (and/or swap `svgX = 100 - p.y`). Re-test.
- Switch the URL `?season=` to a non-current year. Heatmap should disappear; zones still render.

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/app/scout/profile/[wyscoutId]/profile-detail-client.tsx
git commit -m "feat(web): fetch and render player heatmap on profile pitch"
```

---

## Task 11: Update AGENTS.md roadmap (optional housekeeping)

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: Bump the roadmap section**

Open `AGENTS.md`. In §8 "Open work / roadmap", add a "Done" line:

```
- F8 — Player heatmap (current season pitch overlay). ✓
```

- [ ] **Step 2: Commit**

```bash
git add AGENTS.md
git commit -m "docs: mark F8 heatmap as done in roadmap"
```

---

## Verification summary

After all tasks:

- `pytest -q` green from `apps/api`.
- `pnpm exec tsc --noEmit` green from `apps/web`.
- Browser visual check: a sample profile renders heatmap blobs under zones for season 2025/2026.
- Re-running `scripts/download_heatmaps.py` after a successful run prints `cached=N todo=0` for each season → confirms idempotency.
- Removing `data/players/heatmaps/heatmaps_2025.parquet` and reloading the profile shows the pitch in zones-only mode (graceful fallback).

---

## Notes / known limitations

- `CURRENT_SEASON_YEARS` is hardcoded. When the season rolls (Aug 2027), bump to `(2026, 2027)` or similar before re-running the script.
- Coordinate mapping (`svgX = p.y, svgY = 100 - p.x`) is the assumed orientation; verify on first render (Task 10 Step 3).
- Heatmap empty payload for players with zero minutes is stored as a row with `points=[]` to prevent re-fetch loops.
- The `profile` payload may not expose `competition_id` today. If so, the endpoint's `ORDER BY competition_id ASC` fallback applies (deterministic but arbitrary if a player exists in two competitions). Adding `competition_id` to `/profile` is out of scope for this plan.
