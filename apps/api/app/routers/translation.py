"""Performance translation between leagues — port of pages/13_Performance_Translation.

For each target league (source league first when applicable), returns:
  - per-league peer pool: same role, min minutes, with age + perf_index + z_score + peer color
  - per-league mu / sigma stats
  - projected_perf_index for the target player using legacy strength_adj formula
  - projected_z_score = (projected - mu) / sigma

Frontend renders a subplot grid (age × z-score per league) with the target player
highlighted by a `Z X.XX` label.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.config import LEAGUE_POWER_BASE, role_for_position
from app.core.duckdb_pool import duckdb_session, fetch_all_dicts, list_views
from app.core.league_style_fit import translation_style_fit_rows
from app.core.metrics_catalog import column_names_in_view
from app.core.player_age import player_age_sql, season_start_year_from_view
from app.core.player_image import player_image_select_sql
from app.core.team_strength import (
    compute_strength_adjustment,
    default_target_leagues_by_power,
    donut_color,
    translate_performance_index,
)
from app.schemas import (
    LeagueStyleFitRow,
    StrengthAdjustment,
    TranslationLeaguePool,
    TranslationPeer,
    TranslationRequest,
    TranslationResponse,
)

router = APIRouter(prefix="/translation", tags=["translation"])

_MIN_PEERS_PER_LEAGUE = 5
_MIN_MINUTES_DEFAULT = 500


def _league_peers(
    conn,
    target_view: str,
    league: str,
    role: str,
    min_minutes: int,
) -> tuple[list[dict], float, float] | None:
    """Return (peers_with_role_and_pi, mu, sigma) for *league* in *target_view*.

    `peers` only includes players whose `role_for_position(Position)` matches `role`.
    """
    img_sel = player_image_select_sql(conn, target_view)
    tgt_season = season_start_year_from_view(target_view)
    vcols = column_names_in_view(conn, target_view)
    age_sel = player_age_sql(vcols, tgt_season)
    rows = fetch_all_dicts(
        conn,
        f"""SELECT
              "Wyscout id" AS wyscout_id,
              "Player" AS player,
              club,
              "Primary position" AS primary_position,
              Position AS position,
              ({age_sel}) AS age,
              "Minutes played" AS minutes,
              performance_index,
              {img_sel}
            FROM {target_view}
            WHERE league = ?
              AND "Minutes played" >= ?
              AND performance_index IS NOT NULL""",
        [league, min_minutes],
    )
    if not rows:
        return None

    matched: list[dict] = []
    for r in rows:
        pos = r.get("primary_position") or r.get("position")
        if role_for_position(pos) != role:
            continue
        pi = r.get("performance_index")
        if pi is None or pi != pi:
            continue
        matched.append(r)

    if len(matched) < _MIN_PEERS_PER_LEAGUE:
        return None

    pis = [float(r["performance_index"]) for r in matched]
    n = len(pis)
    mu = sum(pis) / n
    var = sum((v - mu) ** 2 for v in pis) / n  # population std (ddof=0), match legacy
    sigma = var ** 0.5
    if sigma < 1e-6:
        return None

    return matched, mu, sigma


@router.post("", response_model=TranslationResponse)
def translation(req: TranslationRequest) -> TranslationResponse:
    src_view = f"players_{req.season}"
    if src_view not in list_views():
        raise HTTPException(404, f"season {req.season} not loaded")

    target_season = req.target_season or req.season
    tgt_view = f"players_{target_season}"
    if tgt_view not in list_views():
        raise HTTPException(404, f"target_season {target_season} not loaded")

    min_minutes = req.min_minutes if req.min_minutes is not None else _MIN_MINUTES_DEFAULT

    with duckdb_session() as conn:
        vcols = column_names_in_view(conn, src_view)
        age_sel = player_age_sql(vcols, req.season)
        rows = fetch_all_dicts(
            conn,
            f"""SELECT "Player" AS player, club, league,
                       "Primary position" AS primary_position, Position AS position,
                       ({age_sel}) AS age, "Minutes played" AS minutes,
                       performance_index
                FROM {src_view}
                WHERE "Wyscout id" = ?
                LIMIT 1""",
            [req.player_id],
        )
        if not rows:
            raise HTTPException(404, "player not found in season")

        rec = rows[0]
        pi = rec.get("performance_index")
        src_lg = rec.get("league")
        src_team = rec.get("club")
        if pi is None or pi != pi or not src_lg:
            raise HTTPException(400, "player has no performance index or league")
        if src_lg not in LEAGUE_POWER_BASE:
            raise HTTPException(
                400,
                f"Source league '{src_lg}' has no power score in LEAGUE_POWER_BASE",
            )
        pi = float(pi)
        pos = rec.get("primary_position") or rec.get("position")
        role = role_for_position(pos)
        if not role:
            raise HTTPException(400, "Could not derive role from player position")

        # Source-team strength adjustment (uses team_profiles parquet view)
        adj_src, adj_src_meta = compute_strength_adjustment(
            conn, src_team, src_lg, req.season
        )

        # Resolve target leagues
        all_target_leagues = [
            r[0]
            for r in conn.execute(
                f"SELECT DISTINCT league FROM {tgt_view} WHERE league IS NOT NULL ORDER BY league"
            ).fetchall()
        ]

        if req.target_leagues:
            target_leagues = [lg for lg in req.target_leagues if lg in all_target_leagues]
        else:
            target_leagues = default_target_leagues_by_power(
                source_league=src_lg,
                leagues_in_target_season=all_target_leagues,
                max_leagues=6,
            )

        # Source league first so the grid/table shows current PI vs same-league peers
        if src_lg in all_target_leagues:
            target_leagues = [src_lg] + [lg for lg in target_leagues if lg != src_lg]

        pools: list[TranslationLeaguePool] = []
        for tg_lg in target_leagues:
            res = _league_peers(conn, tgt_view, tg_lg, role, min_minutes)
            if res is None:
                pools.append(
                    TranslationLeaguePool(
                        league=tg_lg,
                        n=0,
                        mu=None,
                        sigma=None,
                        peers=[],
                        projected_perf_index=None,
                        projected_z_score=None,
                        power=LEAGUE_POWER_BASE.get(tg_lg),
                        insufficient_data=True,
                    )
                )
                continue

            peer_rows, mu, sigma = res

            # Same league: peers use raw performance_index — use actual PI and its z vs pool
            if tg_lg == src_lg:
                projected = pi
            else:
                projected = translate_performance_index(
                    pi,
                    src_lg,
                    tg_lg,
                    strength_adj_source=adj_src,
                    strength_adj_target=1.0,
                )
            proj_z = (projected - mu) / sigma if projected is not None else None

            peers: list[TranslationPeer] = []
            for r in peer_rows:
                p_pi = float(r["performance_index"])
                age = r.get("age")
                age_int = int(age) if (age is not None and age == age) else None
                z_val = (p_pi - mu) / sigma
                peers.append(
                    TranslationPeer(
                        wyscout_id=int(r["wyscout_id"]) if r.get("wyscout_id") is not None else None,
                        player=str(r.get("player") or ""),
                        club=r.get("club"),
                        age=age_int,
                        perf_index=p_pi,
                        z_score=z_val,
                        color=donut_color(p_pi),
                        player_image_url=r.get("player_image_url") or None,
                    )
                )

            pools.append(
                TranslationLeaguePool(
                    league=tg_lg,
                    n=len(peers),
                    mu=mu,
                    sigma=sigma,
                    peers=peers,
                    projected_perf_index=projected,
                    projected_z_score=proj_z,
                    projected_color=donut_color(projected) if projected is not None else None,
                    power=LEAGUE_POWER_BASE.get(tg_lg),
                    insufficient_data=False,
                )
            )

        raw_fit = translation_style_fit_rows(
            conn,
            player_base=rec,
            player_id=req.player_id,
            src_view=src_view,
            target_leagues=target_leagues,
            target_season=target_season,
        )
        league_style_fit = [
            LeagueStyleFitRow(
                league=str(r["league"]),
                n_teams=int(r["n_teams"]),
                style_fit=round(float(r["style_fit"]), 3),
            )
            for r in raw_fit
        ]

    src_age = rec.get("age")
    src_age_int = int(src_age) if (src_age is not None and src_age == src_age) else None

    return TranslationResponse(
        player=str(rec.get("player") or ""),
        club=src_team,
        source_league=src_lg,
        source_power=LEAGUE_POWER_BASE.get(src_lg),
        source_perf_index=pi,
        source_strength_adj=StrengthAdjustment(**adj_src_meta, value=float(adj_src)),
        role=role,
        player_age=src_age_int,
        season=req.season,
        target_season=target_season,
        min_minutes=min_minutes,
        pools=pools,
        target_leagues=target_leagues,
        league_style_fit=league_style_fit,
    )
