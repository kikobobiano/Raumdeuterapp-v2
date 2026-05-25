"""DuckDB connection + view registration over parquet files in data/."""
from __future__ import annotations

import contextlib
import re
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import duckdb

from app.settings import settings

_rlock = threading.RLock()
_conn: duckdb.DuckDBPyConnection | None = None


def _season_from_filename(name: str) -> int | None:
    m = re.match(r"(20\d{2})_all_leagues\.parquet$", name)
    return int(m.group(1)) if m else None


def _register_views(conn: duckdb.DuckDBPyConnection) -> None:
    players_dir = settings.data_dir / "players" / "all"
    if players_dir.exists():
        files = sorted(players_dir.glob("*_all_leagues.parquet"))
        for f in files:
            year = _season_from_filename(f.name)
            if year is None:
                continue
            conn.execute(
                f"CREATE OR REPLACE VIEW players_{year} AS "
                f"SELECT * FROM read_parquet('{f.as_posix()}')"
            )
        if files:
            paths = ", ".join(f"'{f.as_posix()}'" for f in files)
            conn.execute(
                f"CREATE OR REPLACE VIEW players_all AS "
                f"SELECT * FROM read_parquet([{paths}], union_by_name=true)"
            )

    teams_dir = settings.data_dir / "teams"
    if teams_dir.exists():
        for f in teams_dir.glob("*.parquet"):
            view_name = f"teams_{f.stem}".replace("-", "_")
            conn.execute(
                f"CREATE OR REPLACE VIEW {view_name} AS "
                f"SELECT * FROM read_parquet('{f.as_posix()}')"
            )

    # Team profiles (legacy data/teams/profiles/team_profiles.parquet) — register
    # under the canonical name `team_profiles` for translation strength adj.
    team_profiles_path = settings.data_dir / "teams" / "profiles" / "team_profiles.parquet"
    if team_profiles_path.exists():
        conn.execute(
            f"CREATE OR REPLACE VIEW team_profiles AS "
            f"SELECT * FROM read_parquet('{team_profiles_path.as_posix()}')"
        )

    # Potential scores — model output (potential_score 0-100) keyed by Wyscout id + season_year.
    potential_path = settings.data_dir / "potential" / "potential_scores.parquet"
    if potential_path.exists():
        conn.execute(
            f"CREATE OR REPLACE VIEW potential_scores AS "
            f"SELECT * FROM read_parquet('{potential_path.as_posix()}')"
        )

    # Centralized Wyscout photo lookup (data/players/player_photos.parquet).
    # Built by scripts/build_player_photos.py — keyed by wyscout_id (int64),
    # value is the Wyscout CDN image URL. Used by player_image_select_sql as
    # the primary source so older seasons still resolve to a Wyscout photo
    # when one exists in any newer season's parquet.
    player_photos_path = settings.data_dir / "players" / "player_photos.parquet"
    if player_photos_path.exists():
        conn.execute(
            f"CREATE OR REPLACE VIEW player_photos AS "
            f"SELECT * FROM read_parquet('{player_photos_path.as_posix()}')"
        )

    # Player heatmaps — per-season parquet under data/players/heatmaps/.
    # File pattern: heatmaps_{year}.parquet. Built by scripts/download_heatmaps.py.
    heatmaps_dir = settings.data_dir / "players" / "heatmaps"
    if heatmaps_dir.exists():
        for f in sorted(heatmaps_dir.glob("heatmaps_*.parquet")):
            stem = f.stem
            try:
                year = int(stem.split("_")[1])
            except (IndexError, ValueError):
                continue
            conn.execute(
                f"CREATE OR REPLACE VIEW heatmaps_{year} AS "
                f"SELECT * FROM read_parquet('{f.as_posix()}')"
            )


def _list_views_unlocked(conn: duckdb.DuckDBPyConnection) -> list[str]:
    rows = conn.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_type='VIEW' ORDER BY table_name"
    ).fetchall()
    return [r[0] for r in rows]


def _heatmap_views_missing(conn: duckdb.DuckDBPyConnection) -> bool:
    """True when heatmap parquets exist on disk but DuckDB views were not registered."""
    heatmaps_dir = settings.data_dir / "players" / "heatmaps"
    if not heatmaps_dir.is_dir():
        return False
    registered = set(_list_views_unlocked(conn))
    for f in heatmaps_dir.glob("heatmaps_*.parquet"):
        try:
            year = int(f.stem.split("_")[1])
        except (IndexError, ValueError):
            continue
        if f"heatmaps_{year}" not in registered:
            return True
    return False


def _ensure_conn_unlocked() -> duckdb.DuckDBPyConnection:
    global _conn
    if _conn is None:
        _conn = duckdb.connect(":memory:", read_only=False)
        _conn.execute("PRAGMA threads=4")
        _register_views(_conn)
    elif _heatmap_views_missing(_conn):
        # Parquets added (or view registration restored) after first connect — e.g. post git restore.
        _register_views(_conn)
    return _conn


@contextlib.contextmanager
def duckdb_session() -> Iterator[duckdb.DuckDBPyConnection]:
    """Hold the DuckDB lock for a sequence of operations on the shared connection.

    One global connection is not safe for concurrent use: DuckDB may release the
    GIL during execution, so overlapping requests can corrupt native heap state.
    """
    with _rlock:
        yield _ensure_conn_unlocked()


def fetch_all_dicts(
    conn: duckdb.DuckDBPyConnection, sql: str, params: list[Any] | None = None
) -> list[dict[str, Any]]:
    """Materialize rows as dicts without pandas (avoids fetchdf issues on some platforms)."""
    with _rlock:
        actual = _ensure_conn_unlocked()
        if actual is not conn:
            raise RuntimeError("fetch_all_dicts must use the connection from duckdb_session()")
        result = conn.execute(sql, params or [])
        desc = result.description
        names = [d[0] for d in desc] if desc else []
        return [dict(zip(names, row, strict=True)) for row in result.fetchall()]


def list_views() -> list[str]:
    with _rlock:
        c = _ensure_conn_unlocked()
        return _list_views_unlocked(c)


def list_seasons() -> list[int]:
    players_dir: Path = settings.data_dir / "players" / "all"
    if not players_dir.exists():
        return []
    files = players_dir.glob("*_all_leagues.parquet")
    seasons = sorted(
        {y for y in (_season_from_filename(f.name) for f in files) if y},
        reverse=True,
    )
    return seasons
