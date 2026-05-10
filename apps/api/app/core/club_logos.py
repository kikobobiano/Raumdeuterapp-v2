"""Per-row club logo resolution.

Wyscout per-row layout:
  - ``Team``        : current team (most recent on the row's CSV export).
  - ``Team logo``   : logo of ``Team``, NOT necessarily the historical club.
  - ``Team within selected timeframe`` → renamed to ``club`` by the loader:
                      the team the player played for during the season window.

For transferred players ``Team`` and ``club`` differ. The correct crest is the
one belonging to ``club``. We resolve it via the same-season players view by
matching ``Team = <this row's club>`` and grabbing that row's ``Team logo``.

When a pre-built ``data/teams/club_logos.parquet`` is registered as the
``teams_club_logos`` view it is preferred (broader cross-season coverage), but
it is not required.
"""

from __future__ import annotations

import duckdb

from app.core.duckdb_pool import fetch_all_dicts, list_views

TEAMS_CLUB_LOGOS_VIEW = "teams_club_logos"
_TEAM_LOGO_COL = "Team logo"
_TEAM_COL = "Team"
_CLUB_COL = "club"


def season_csv_tag(season: int) -> str:
    """Suffix used in Wyscout export filenames, e.g. 2025 -> ``25-26``."""
    y = season % 100
    y2 = (season + 1) % 100
    return f"{y:02d}-{y2:02d}"


def normalize_club_logo(v: object | None) -> str | None:
    if v is None:
        return None
    if isinstance(v, float) and v != v:
        return None
    s = str(v).strip()
    return s if s else None


def club_logo_from_parquet_row(rec: dict) -> str | None:
    """Logo from a single player row: trust ``club_logo``, else row logos if ``Team`` == ``club``.

    For transferred players (`Team` differs from `club`) per-row Wyscout logos may
    not match the stint club — callers should prefer :func:`resolve_club_logo` first.
    """
    pre_aliased = rec.get("club_logo")
    v = normalize_club_logo(pre_aliased)
    if v:
        return v
    team_val = rec.get("Team")
    club_val = rec.get("club")
    if (
        isinstance(team_val, str)
        and isinstance(club_val, str)
        and team_val.strip() == club_val.strip()
    ):
        for key in (_TEAM_LOGO_COL, "Club logo"):
            if key in rec:
                v = normalize_club_logo(rec.get(key))
                if v:
                    return v
    return None


def _view_has_column(conn: duckdb.DuckDBPyConnection, view: str, column_name: str) -> bool:
    for sql, params in (
        (
            """
            SELECT 1 FROM duckdb_columns()
            WHERE database_name = current_database()
              AND schema_name = 'main'
              AND table_name = ?
              AND column_name = ?
            LIMIT 1
            """,
            [view, column_name],
        ),
        (
            """
            SELECT 1 FROM duckdb_columns()
            WHERE schema_name = 'main'
              AND table_name = ?
              AND column_name = ?
            LIMIT 1
            """,
            [view, column_name],
        ),
        (
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'main'
              AND table_name = ?
              AND column_name = ?
            LIMIT 1
            """,
            [view, column_name],
        ),
    ):
        try:
            if conn.execute(sql, params).fetchone():
                return True
        except Exception:
            continue
    return False


def _self_join_club_logo_sql(view: str, outer: str) -> str:
    """``... AS club_logo`` from the same-season players view, keyed on ``club``.

    ``outer`` is the alias (or table name) used to qualify the outer row's
    columns. The inner subquery always reads from ``view`` aliased as ``v2``.

    Order of preference:
      1. Row's own ``Team logo`` when ``Team == club`` (no transfer).
      2. Any other row's ``Team logo`` where ``Team == this row's club``
         (the transferred player's historical team).
      3. Cross-season fallback via ``teams_club_logos`` when registered.
      4. Row's ``Team logo`` as a last resort (current team — usually wrong for
         transferred players, but better than NULL).
    """
    parts = [
        f'CASE WHEN {outer}."{_TEAM_COL}" = {outer}.{_CLUB_COL} '
        f'THEN CAST({outer}."{_TEAM_LOGO_COL}" AS VARCHAR) END',
        f'(SELECT CAST(v2."{_TEAM_LOGO_COL}" AS VARCHAR) '
        f"FROM {view} AS v2 "
        f'WHERE v2."{_TEAM_COL}" = {outer}.{_CLUB_COL} '
        f'AND v2."{_TEAM_LOGO_COL}" IS NOT NULL '
        f"LIMIT 1)",
    ]
    if TEAMS_CLUB_LOGOS_VIEW in list_views():
        parts.append(
            f"(SELECT CAST(cl.logo_url AS VARCHAR) "
            f"FROM {TEAMS_CLUB_LOGOS_VIEW} cl "
            f"WHERE cl.team = {outer}.{_CLUB_COL} "
            f"ORDER BY cl.latest_file DESC NULLS LAST LIMIT 1)"
        )
    parts.append(f'CAST({outer}."{_TEAM_LOGO_COL}" AS VARCHAR)')
    return f"COALESCE({', '.join(parts)}) AS club_logo"


def club_logo_select_sql(
    conn: duckdb.DuckDBPyConnection,
    view: str,
    season: int,  # noqa: ARG001
    *,
    table_alias: str | None = None,
) -> str:
    """SQL fragment: ``... AS club_logo`` resolved against ``view`` for the
    correct stint.

    ``table_alias`` must match the alias used by the outer ``FROM`` clause when
    one is given (e.g. ``FROM players_2025 p`` → ``table_alias="p"``). When the
    outer query has no alias, the table name itself is used.

    ``season`` is accepted for API stability with previous callers; the
    resolution is per-row and uses the per-season ``view`` directly so a season
    argument is no longer needed.
    """
    outer = table_alias or view
    has_logo = _view_has_column(conn, view, _TEAM_LOGO_COL)
    has_team = _view_has_column(conn, view, _TEAM_COL)
    has_club = _view_has_column(conn, view, _CLUB_COL)
    if not has_logo:
        return "CAST(NULL AS VARCHAR) AS club_logo"
    if not (has_team and has_club):
        # Cannot disambiguate transferred players — return the row's logo.
        return f'CAST({outer}."{_TEAM_LOGO_COL}" AS VARCHAR) AS club_logo'
    return _self_join_club_logo_sql(view, outer)


def resolve_club_logo(
    conn: duckdb.DuckDBPyConnection, club: str | None, season: int
) -> str | None:
    """Logo URL for ``club`` in ``season`` from the same-season players view.

    Falls back to ``teams_club_logos`` (when registered) for cross-season
    coverage of clubs the season parquet doesn't contain.
    """
    club_s = normalize_club_logo(club)
    if not club_s:
        return None

    view = f"players_{season}"
    if view in list_views():
        try:
            row = conn.execute(
                f'SELECT "{_TEAM_LOGO_COL}" FROM {view} '
                f'WHERE "{_TEAM_COL}" = ? AND "{_TEAM_LOGO_COL}" IS NOT NULL '
                "LIMIT 1",
                [club_s],
            ).fetchone()
        except Exception:
            row = None
        if row and row[0]:
            return normalize_club_logo(row[0])

    if TEAMS_CLUB_LOGOS_VIEW not in list_views():
        return None

    tag = season_csv_tag(season)
    pattern = f"%{tag}.csv"
    rows = fetch_all_dicts(
        conn,
        f"""
        SELECT logo_url FROM {TEAMS_CLUB_LOGOS_VIEW}
        WHERE team = ? AND latest_file LIKE ?
        ORDER BY latest_file DESC NULLS LAST LIMIT 1
        """,
        [club_s, pattern],
    )
    if rows:
        return normalize_club_logo(rows[0].get("logo_url"))
    rows = fetch_all_dicts(
        conn,
        f"""
        SELECT logo_url FROM {TEAMS_CLUB_LOGOS_VIEW}
        WHERE team = ?
        ORDER BY latest_file DESC NULLS LAST LIMIT 1
        """,
        [club_s],
    )
    if rows:
        return normalize_club_logo(rows[0].get("logo_url"))
    return None
