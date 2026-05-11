"""Player image URL resolution helpers.

Resolution order:
  1. Centralized ``player_photos`` view (Wyscout URL keyed by ``wyscout_id``)
  2. View's own ``Image`` column (raw Wyscout CSV)
  3. View's ``image_url`` column (TM-enriched fallback)

The centralized lookup ensures older seasons still resolve to a Wyscout
photo when one exists in any newer season's parquet (since Wyscout photos
only cover ~2018–2026 by season but the same player may appear earlier).

Pipeline (``scripts/enrich_with_tm.py``) writes the resolved value into
``image_url`` and drops ``Image`` from the CSV; so post-pipeline parquets only
have ``image_url``. Helpers below detect column presence and emit the correct
SQL — never reference ``"Image"`` when the column doesn't exist (DuckDB binder
error otherwise).
"""
from __future__ import annotations

import duckdb

from app.core.metrics_catalog import column_names_in_view

PHOTO_NOT_FOUND_URL = "https://cdn5.wyscout.com/reports-img/photo-not-found.png"


def _has_player_photos_view(conn: duckdb.DuckDBPyConnection) -> bool:
    try:
        row = conn.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name = 'player_photos' AND table_type = 'VIEW' LIMIT 1"
        ).fetchone()
    except Exception:
        return False
    return row is not None


def player_image_select_sql(
    conn: duckdb.DuckDBPyConnection,
    view: str,
    *,
    table_alias: str = "",
    alias: str = "player_image_url",
) -> str:
    """Return ``... AS player_image_url`` SQL fragment scoped to ``view``.

    Resolves via centralized ``player_photos`` first, then view's ``Image``,
    then view's ``image_url``. Placeholder ``photo-not-found.png`` is treated
    as null at every level. Returns ``CAST(NULL AS VARCHAR) AS <alias>`` if
    no source is available.
    """
    cols = column_names_in_view(conn, view)
    prefix = f"{table_alias}." if table_alias else ""
    has_image = "Image" in cols
    has_image_url = "image_url" in cols
    has_wyscout_id = "Wyscout id" in cols
    has_photos_view = _has_player_photos_view(conn)

    parts: list[str] = []
    if has_photos_view and has_wyscout_id:
        parts.append(
            f"(SELECT NULLIF(pp.\"Image\", '{PHOTO_NOT_FOUND_URL}') "
            f"FROM player_photos pp WHERE pp.wyscout_id = {prefix}\"Wyscout id\")"
        )
    if has_image:
        parts.append(f"NULLIF({prefix}\"Image\", '{PHOTO_NOT_FOUND_URL}')")
    if has_image_url:
        parts.append(f"NULLIF({prefix}\"image_url\", '{PHOTO_NOT_FOUND_URL}')")

    if not parts:
        return f"CAST(NULL AS VARCHAR) AS {alias}"
    if len(parts) == 1:
        return f"{parts[0]} AS {alias}"
    return f"COALESCE({', '.join(parts)}) AS {alias}"


def clean_player_image_url(value: str | None) -> str | None:
    """Python-side equivalent: drop placeholder, return ``None`` for empty/non-http."""
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s.startswith("http"):
        return None
    if s == PHOTO_NOT_FOUND_URL:
        return None
    return s
