from collections import OrderedDict

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from app.core.config import (
    AREA_INDEX_COLS,
    GAME_AREA_METRIC_GROUPS,
    PROFILE_RADAR_MIN_MINUTES,
    ROLE_TABLE_METRICS,
    format_metric_label,
    position_tokens,
    position_tokens_merged,
    role_for_position,
)
from app.core.duckdb_pool import duckdb_session, fetch_all_dicts, list_views
from app.core.filters import goalkeeper_only_sql, not_goalkeeper_sql
from app.core.club_logos import club_logo_from_parquet_row, normalize_club_logo, resolve_club_logo
from app.core.pi_history import build_pi_history_payload
from app.core.player_age import player_age_for_season
from app.core.player_traits import TRAIT_METRICS, select_player_traits
from app.core.profile_percentiles import percentiles_for_cohort
from app.core.sql_ident import q_ident
from app.schemas import (
    GameAreaProfileBlock,
    PerformanceIndexHistoryPoint,
    PerformanceIndexHistoryResponse,
    PlayerProfile,
    PlayerTrait,
    ProfileClubStint,
    ProfileMetric,
)

router = APIRouter(prefix="/players", tags=["profile"])


def _traits_identity_columns(available: set[str]) -> list[str]:
    order = (
        "Player",
        "Full name",
        "club",
        "Position",
        "Primary position",
        "Wyscout id",
    )
    return [c for c in order if c in available]


def _traits_cohort_dataframe(
    conn,
    view: str,
    cols: set[str],
    role: str | None,
) -> pd.DataFrame:
    """All leagues, same tactical role pool as legacy Profile (``df_traits_pos``)."""
    if not role:
        return pd.DataFrame()
    id_cols = _traits_identity_columns(cols)
    metric_cols = [m for m in TRAIT_METRICS if m in cols]
    select_cols = id_cols + metric_cols
    if not id_cols or not metric_cols:
        return pd.DataFrame()
    if role == "Goalkeeper":
        where_sql, params = goalkeeper_only_sql()
    else:
        where_sql, params = not_goalkeeper_sql()
    sql = f"SELECT {', '.join(q_ident(c) for c in select_cols)} FROM {view} WHERE {where_sql}"
    rows = fetch_all_dicts(conn, sql, params)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def _pick_numeric(rec: dict, keys: tuple[str, ...]) -> float | None:
    for key in keys:
        if key not in rec:
            continue
        val = rec[key]
        if val is None or (isinstance(val, float) and val != val):
            continue
        return float(val)
    return None


def _pick_int(rec: dict, keys: tuple[str, ...]) -> int | None:
    v = _pick_numeric(rec, keys)
    return int(v) if v is not None else None


_PHOTO_NOT_FOUND_URL = "https://cdn5.wyscout.com/reports-img/photo-not-found.png"


def _photo_from_central(conn, wyscout_id: int | None) -> str | None:
    """Look up Wyscout photo from centralized ``player_photos`` view by Wyscout id."""
    if wyscout_id is None:
        return None
    try:
        row = conn.execute(
            'SELECT "Image" FROM player_photos WHERE wyscout_id = ? LIMIT 1',
            [int(wyscout_id)],
        ).fetchone()
    except Exception:
        return None
    if not row or not row[0]:
        return None
    s = str(row[0]).strip()
    if not s.startswith("http") or s == _PHOTO_NOT_FOUND_URL:
        return None
    return s


def _player_image_url(rec: dict, conn=None) -> str | None:
    """Return player image URL.

    Resolution order:
      1. Centralized ``player_photos`` view (when ``conn`` provided + ``Wyscout id``)
      2. Per-row columns: ``Image``, ``Image URL``, ``Player image``, ``image_url``
    Wyscout ``photo-not-found.png`` placeholder is skipped at every level.
    """
    if conn is not None:
        wid = rec.get("Wyscout id")
        if wid is not None:
            try:
                wid = int(wid)
            except (TypeError, ValueError):
                wid = None
        central = _photo_from_central(conn, wid)
        if central:
            return central

    for key in ("Image", "Image URL", "Player image", "image_url"):
        raw = rec.get(key)
        if isinstance(raw, str):
            s = raw.strip()
            if s.startswith("http") and s != _PHOTO_NOT_FOUND_URL:
                return s
    return None


def _secondary_position_parts(rec: dict, cols: set[str]) -> list[str]:
    """Wyscout-style secondary / other position columns (non-empty strings only)."""
    keys = (
        "Secondary position",
        "Secondary positions",
        "Other positions",
        "Other position",
    )
    out: list[str] = []
    for key in keys:
        if key not in cols:
            continue
        raw = rec.get(key)
        if isinstance(raw, str) and raw.strip():
            out.append(raw.strip())
    return out




@router.get("/{wyscout_id}/performance-index-history", response_model=PerformanceIndexHistoryResponse)
def performance_index_history(
    wyscout_id: int,
    season: int = Query(..., description="Anchor season (inclusive) — last N loaded seasons up to this year."),
    limit: int = Query(5, ge=1, le=10),
) -> PerformanceIndexHistoryResponse:
    """Up to ``limit`` consecutive loaded seasons ending at ``season``, non-null PI rows only (chronological).

    One row per season: the club with most minutes (same default as profile).
    """
    with duckdb_session() as conn:
        payload = build_pi_history_payload(conn, wyscout_id, season, limit)
        return PerformanceIndexHistoryResponse(
            points=[PerformanceIndexHistoryPoint(**p) for p in payload],
        )


@router.get("/{wyscout_id}/profile", response_model=PlayerProfile)
def profile(
    wyscout_id: int,
    season: int = Query(...),
    club: str | None = Query(
        None,
        description="Disambiguates when a player has rows for multiple clubs in the same season.",
    ),
    league: str | None = Query(
        None,
        description="Percentile cohort league; omit to use this player's league",
    ),
    min_minutes: int = Query(PROFILE_RADAR_MIN_MINUTES, ge=0),
    performance_index_history_limit: int | None = Query(
        None,
        ge=1,
        le=10,
        description="When set, include up to N PI trajectory seasons inside this response.",
    ),
) -> PlayerProfile:
    view = f"players_{season}"
    if view not in list_views():
        raise HTTPException(404, f"season {season} not loaded")

    with duckdb_session() as conn:
        if club:
            rows = fetch_all_dicts(
                conn,
                f'SELECT * FROM {view} WHERE "Wyscout id" = ? AND club = ? LIMIT 1',
                [wyscout_id, club],
            )
        else:
            # Pick row with most minutes so transferred player defaults to main club.
            rows = fetch_all_dicts(
                conn,
                f'SELECT * FROM {view} WHERE "Wyscout id" = ? '
                'ORDER BY "Minutes played" DESC NULLS LAST LIMIT 1',
                [wyscout_id],
            )
        if not rows:
            raise HTTPException(404, f"player {wyscout_id} not found in {view}")

        # All clubs the player has rows for in this season — UI can offer a switcher.
        stint_rows = fetch_all_dicts(
            conn,
            f'SELECT club, "Minutes played" AS minutes FROM {view} '
            'WHERE "Wyscout id" = ? AND club IS NOT NULL '
            'ORDER BY "Minutes played" DESC NULLS LAST',
            [wyscout_id],
        )

        rec = rows[0]
        cols = set(rec.keys())
        pos = rec.get("Primary position") or rec.get("Position")
        role = role_for_position(pos)
        sec_parts = _secondary_position_parts(rec, cols)
        toks_primary = position_tokens(pos)
        prim_set = set(toks_primary)
        toks_secondary: list[str] = []
        seen_sec: set[str] = set()
        for part in sec_parts:
            for tok in position_tokens(part):
                if tok in prim_set or tok in seen_sec:
                    continue
                seen_sec.add(tok)
                toks_secondary.append(tok)
        toks = position_tokens_merged(pos, *sec_parts)

        # Cohort: min minutes; league = query override, else player's league (league percentiles)
        cohort_where_parts: list[str] = ['"Minutes played" >= ?']
        cohort_params: list = [min_minutes]
        cohort_league = league if league is not None else rec.get("league")
        if cohort_league:
            cohort_where_parts.append("league = ?")
            cohort_params.append(cohort_league)
        gk_sql, gk_params = not_goalkeeper_sql()
        cohort_where_parts.append(gk_sql)
        cohort_params.extend(gk_params)
        cohort_where = " AND ".join(cohort_where_parts)

        def num(key: str) -> float | None:
            v = rec.get(key)
            return float(v) if (v is not None and v == v) else None

        def intg(key: str) -> int | None:
            v = num(key)
            return int(v) if v is not None else None

        metric_list = ROLE_TABLE_METRICS.get(role or "Midfielder", [])
        table_metrics = [m for m in metric_list if m in cols]

        perc_inputs: OrderedDict[str, float] = OrderedDict()

        def offer_pct(metric: str, raw: object | None) -> None:
            v = float(raw) if (raw is not None and raw == raw) else None
            if v is None or v != v:
                return
            perc_inputs.setdefault(metric, v)

        for m in AREA_INDEX_COLS:
            if m in cols:
                offer_pct(m, rec.get(m))

        for m in table_metrics:
            if m == "Minutes played":
                continue
            offer_pct(m, rec.get(m))

        for _, _, area_metric_cols in GAME_AREA_METRIC_GROUPS:
            for m in area_metric_cols:
                if m == "Minutes played":
                    continue
                if m not in cols:
                    continue
                offer_pct(m, rec.get(m))

        pi = num("performance_index")
        if pi is not None and "performance_index" in cols:
            perc_inputs.setdefault("performance_index", float(pi))

        perc_items = list(perc_inputs.items())
        pct_batch = (
            percentiles_for_cohort(conn, view, perc_items, cohort_where, cohort_params)
            if perc_items
            else {}
        )

        radar: list[ProfileMetric] = []
        for m in AREA_INDEX_COLS:
            if m not in cols:
                radar.append(
                    ProfileMetric(
                        metric=m, label=format_metric_label(m), value=None, percentile=None,
                    )
                )
                continue
            val = rec.get(m)
            v = float(val) if (val is not None and val == val) else None
            pct = pct_batch.get(m)
            radar.append(
                ProfileMetric(
                    metric=m, label=format_metric_label(m), value=v, percentile=pct,
                )
            )

        table: list[ProfileMetric] = []
        for m in table_metrics:
            val = rec.get(m)
            v = float(val) if (val is not None and val == val) else None
            if m == "Minutes played":
                table.append(
                    ProfileMetric(
                        metric=m, label=format_metric_label(m), value=v, percentile=None,
                    )
                )
                continue
            pct = pct_batch.get(m)
            table.append(
                ProfileMetric(
                    metric=m, label=format_metric_label(m), value=v, percentile=pct,
                )
            )

        radar_by_metric = {m.metric: m for m in radar}
        game_areas: list[GameAreaProfileBlock] = []
        for area_name, index_col, area_metric_cols in GAME_AREA_METRIC_GROUPS:
            idx_pm = radar_by_metric.get(
                index_col,
                ProfileMetric(
                    metric=index_col,
                    label=format_metric_label(index_col),
                    value=None,
                    percentile=None,
                ),
            )
            block_metrics: list[ProfileMetric] = []
            for m in area_metric_cols:
                if m not in cols:
                    block_metrics.append(
                        ProfileMetric(
                            metric=m, label=format_metric_label(m), value=None, percentile=None,
                        )
                    )
                    continue
                val = rec.get(m)
                v = float(val) if (val is not None and val == val) else None
                if m == "Minutes played":
                    block_metrics.append(
                        ProfileMetric(
                            metric=m,
                            label=format_metric_label(m),
                            value=v,
                            percentile=None,
                        )
                    )
                    continue
                pct = pct_batch.get(m)
                block_metrics.append(
                    ProfileMetric(
                        metric=m,
                        label=format_metric_label(m),
                        value=v,
                        percentile=pct,
                    )
                )
            game_areas.append(
                GameAreaProfileBlock(area=area_name, index=idx_pm, metrics=block_metrics)
            )

        pi_pct = pct_batch.get("performance_index")
        img = _player_image_url(rec, conn)
        games = _pick_int(
            rec,
            ("Matches played", "Appearances", "Games played", "Matches"),
        )
        goals_n = _pick_numeric(rec, ("Goals",))
        assists_n = _pick_numeric(rec, ("Assists",))

        traits_out: list[PlayerTrait] = []
        df_traits_full = _traits_cohort_dataframe(conn, view, cols, role)
        if role and not df_traits_full.empty:
            pos_col = (
                "Primary position"
                if "Primary position" in df_traits_full.columns
                else "Position"
            )
            if pos_col in df_traits_full.columns:

                def _row_role(val: object) -> str | None:
                    if val is None or pd.isna(val):
                        return None
                    return role_for_position(str(val))

                mapped = df_traits_full[pos_col].map(_row_role)
                df_pos = df_traits_full.loc[mapped == role]
                player_row = pd.Series(rec)
                traits_out = [
                    PlayerTrait(positive=positive, label=label, game_area=area)
                    for positive, label, area in select_player_traits(
                        player_row, df_pos, role
                    )
                ]

        pi_embed: list[PerformanceIndexHistoryPoint] | None = None
        if performance_index_history_limit is not None:
            raw_hist = build_pi_history_payload(
                conn, wyscout_id, season, performance_index_history_limit
            )
            pi_embed = [PerformanceIndexHistoryPoint(**p) for p in raw_hist]

        return PlayerProfile(
            wyscout_id=intg("Wyscout id"),
            player=str(rec.get("Player") or ""),
            full_name=rec.get("Full name"),
            club=rec.get("club"),
            league=rec.get("league"),
            club_logo=resolve_club_logo(conn, rec.get("club"), season)
            or club_logo_from_parquet_row(rec),
            position=pos,
            age=player_age_for_season(rec, season),
            minutes=intg("Minutes played"),
            market_value=num("Market value"),
            foot=rec.get("Foot"),
            height=intg("Height"),
            role=role,
            radar=radar,
            table=table,
            performance_index=pi,
            performance_index_percentile=pi_pct,
            games=games,
            goals=goals_n,
            assists=assists_n,
            player_image_url=img,
            position_tokens=toks,
            position_tokens_primary=toks_primary,
            position_tokens_secondary=toks_secondary,
            game_areas=game_areas,
            traits=traits_out,
            clubs_in_season=[
                ProfileClubStint(
                    club=str(r["club"]),
                    minutes=int(r["minutes"]) if r.get("minutes") is not None else None,
                    club_logo=resolve_club_logo(conn, r["club"], season),
                )
                for r in stint_rows
            ],
            performance_index_history=pi_embed,
        )
