"""Team Metrics — Best XI solver.

Ports pages/11_Best_XI.py: for each slot in the chosen formation, picks the
player with the highest performance_index among eligible candidates, respecting
position constraints, side preferences, and dedup across slots.
"""
from __future__ import annotations

import re
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException

from app.core.club_logos import normalize_club_logo
from app.core.duckdb_pool import duckdb_session, fetch_all_dicts, list_views
from app.core.filters import build_where, view_name
from app.core.metrics_catalog import column_names_in_view
from app.core.club_logos import club_logo_select_sql
from app.core.player_age import player_age_sql
from app.core.player_image import player_image_select_sql
from app.schemas import BestXIPlayer, BestXIRequest, BestXIResponse, BestXITop3Row

router = APIRouter(prefix="/teams", tags=["teams"])

# ---------------------------------------------------------------------------
# Formation definitions: slot → (label, allowed_position_types)
# Mirrors FORMATIONS in 11_Best_XI.py; position_types used only as labels here.
# ---------------------------------------------------------------------------
FORMATIONS: dict[str, list[tuple[str, str]]] = {
    "4-3-3": [
        ("GK", "Goalkeeper"), ("RB", "Complete Fullback"), ("RCB", "Ball Playing Center Back"),
        ("LCB", "Ball Playing Center Back"), ("LB", "Complete Fullback"),
        ("DM", "Playmaker"), ("RCM", "Box-to-Box Midfielder"), ("LCM", "Playmaker"),
        ("RW", "Inside Forward"), ("ST", "Poacher"), ("LW", "Inside Forward"),
    ],
    "4-2-3-1": [
        ("GK", "Goalkeeper"), ("RB", "Complete Fullback"), ("RCB", "Ball Playing Center Back"),
        ("LCB", "Ball Playing Center Back"), ("LB", "Complete Fullback"),
        ("RCM", "Playmaker"), ("LCM", "Defensive Midfielder"),
        ("RW", "Inside Forward"), ("AMC", "Attacking Midfielder"), ("LW", "Inside Forward"),
        ("ST", "Poacher"),
    ],
    "4-4-2": [
        ("GK", "Goalkeeper"), ("RB", "Complete Fullback"), ("RCB", "Ball Playing Center Back"),
        ("LCB", "Ball Playing Center Back"), ("LB", "Complete Fullback"),
        ("RM", "Winger"), ("RCM", "Box-to-Box Midfielder"),
        ("LCM", "Box-to-Box Midfielder"), ("LM", "Winger"),
        ("STL", "Poacher"), ("STR", "Target Man"),
    ],
    "4-1-4-1": [
        ("GK", "Goalkeeper"), ("RB", "Complete Fullback"), ("RCB", "Ball Playing Center Back"),
        ("LCB", "Ball Playing Center Back"), ("LB", "Complete Fullback"),
        ("DM", "Defensive Midfielder"), ("RM", "Winger"), ("RCM", "Playmaker"),
        ("LCM", "Playmaker"), ("LM", "Winger"), ("ST", "Poacher"),
    ],
    "3-4-3": [
        ("GK", "Goalkeeper"), ("RCB", "Stopper Center Back"), ("CB", "Ball Playing Center Back"),
        ("LCB", "Stopper Center Back"), ("RWB", "Attacking Fullback"), ("LWB", "Attacking Fullback"),
        ("CMR", "Playmaker"), ("CML", "Box-to-Box Midfielder"),
        ("RW", "Winger"), ("ST", "Poacher"), ("LW", "Winger"),
    ],
    "3-5-2": [
        ("GK", "Goalkeeper"), ("RCB", "Stopper Center Back"), ("CB", "Ball Playing Center Back"),
        ("LCB", "Stopper Center Back"), ("RWB", "Attacking Fullback"), ("LWB", "Attacking Fullback"),
        ("DM", "Defensive Midfielder"), ("CMR", "Box-to-Box Midfielder"), ("CML", "Box-to-Box Midfielder"),
        ("STL", "Poacher"), ("STR", "Target Man"),
    ],
    "3-4-2-1": [
        ("GK", "Goalkeeper"), ("RCB", "Stopper Center Back"), ("CB", "Ball Playing Center Back"),
        ("LCB", "Stopper Center Back"), ("RWB", "Attacking Fullback"), ("LWB", "Attacking Fullback"),
        ("CMR", "Box-to-Box Midfielder"), ("CML", "Box-to-Box Midfielder"),
        ("RF", "Inside Forward"), ("LF", "Inside Forward"), ("ST", "Poacher"),
    ],
    "5-3-2": [
        ("GK", "Goalkeeper"), ("RWB", "Attacking Fullback"), ("RCB", "Stopper Center Back"),
        ("CB", "Ball Playing Center Back"), ("LCB", "Stopper Center Back"), ("LWB", "Attacking Fullback"),
        ("DM", "Defensive Midfielder"), ("CMR", "Playmaker"), ("CML", "Playmaker"),
        ("STL", "Poacher"), ("STR", "Target Man"),
    ],
    "5-4-1": [
        ("GK", "Goalkeeper"), ("RWB", "Attacking Fullback"), ("RCB", "Stopper Center Back"),
        ("CB", "Ball Playing Center Back"), ("LCB", "Stopper Center Back"), ("LWB", "Attacking Fullback"),
        ("RM", "Winger"), ("RCM", "Box-to-Box Midfielder"), ("LCM", "Box-to-Box Midfielder"),
        ("LM", "Winger"), ("ST", "Complete Forward"),
    ],
}

FORMATION_COORDS: dict[str, dict[str, tuple[float, float]]] = {
    "4-3-3": {
        "GK": (50, 5), "RB": (84, 19), "RCB": (60, 17), "LCB": (40, 17), "LB": (16, 19),
        "DM": (50, 40), "LCM": (28, 49), "RCM": (72, 49),
        "RW": (84, 70), "ST": (50, 88), "LW": (16, 70),
    },
    "4-2-3-1": {
        "GK": (50, 5), "RB": (84, 19), "RCB": (60, 17), "LCB": (40, 17), "LB": (16, 19),
        "RCM": (66, 38), "LCM": (34, 38),
        "RW": (82, 58), "AMC": (50, 61), "LW": (18, 58), "ST": (50, 88),
    },
    "4-4-2": {
        "GK": (50, 5), "RB": (84, 19), "RCB": (60, 17), "LCB": (40, 17), "LB": (16, 19),
        "RM": (85, 46), "RCM": (65, 44), "LCM": (35, 44), "LM": (15, 46),
        "STL": (37, 88), "STR": (63, 88),
    },
    "4-1-4-1": {
        "GK": (50, 5), "RB": (84, 19), "RCB": (60, 17), "LCB": (40, 17), "LB": (16, 19),
        "DM": (50, 38), "RM": (85, 52), "RCM": (65, 50), "LCM": (35, 50), "LM": (15, 52),
        "ST": (50, 88),
    },
    "3-4-3": {
        "GK": (50, 5), "RCB": (74, 17), "CB": (50, 15), "LCB": (26, 17),
        "RWB": (86, 36), "LWB": (14, 36), "CMR": (64, 50), "CML": (36, 50),
        "RW": (84, 70), "ST": (50, 88), "LW": (16, 70),
    },
    "3-5-2": {
        "GK": (50, 5), "RCB": (74, 17), "CB": (50, 15), "LCB": (26, 17),
        "RWB": (86, 36), "LWB": (14, 36), "DM": (50, 41),
        "CMR": (65, 53), "CML": (35, 53), "STL": (37, 88), "STR": (63, 88),
    },
    "3-4-2-1": {
        "GK": (50, 5), "RCB": (74, 17), "CB": (50, 15), "LCB": (26, 17),
        "RWB": (86, 36), "LWB": (14, 36), "CMR": (65, 48), "CML": (35, 48),
        "RF": (72, 66), "LF": (28, 66), "ST": (50, 88),
    },
    "5-3-2": {
        "GK": (50, 5), "RWB": (90, 21), "RCB": (70, 17), "CB": (50, 15), "LCB": (30, 17), "LWB": (10, 21),
        "DM": (50, 41), "CMR": (65, 51), "CML": (35, 51), "STL": (37, 76), "STR": (63, 88),
    },
    "5-4-1": {
        "GK": (50, 5), "RWB": (90, 21), "RCB": (70, 17), "CB": (50, 15), "LCB": (30, 17), "LWB": (10, 21),
        "RM": (86, 48), "RCM": (65, 46), "LCM": (35, 46), "LM": (14, 48), "ST": (50, 88),
    },
}

# Position column codes allowed per slot (subset of Wyscout codes).
SLOT_POSITION_ALLOWED: dict[str, list[str]] = {
    "GK": ["GK"],
    "RB": ["RB"], "LB": ["LB"],
    "RWB": ["RWB", "RB"], "LWB": ["LWB", "LB"],
    "RCB": ["RCB"], "LCB": ["LCB"], "CB": ["CB", "RCB", "LCB"],
    "DM": ["DMF", "DM", "CDM", "CM", "CMR", "CML"],
    "CM": ["CM", "CMR", "CML"],
    "RCM": ["CMR", "RCMF", "DM", "RDM", "DMF"],
    "LCM": ["CML", "LCMF", "DM", "LDM", "DMF"],
    "AMC": ["AMC", "AM"],
    "RM": ["RM", "RW", "AMR", "AMC", "RAMF"],
    "LM": ["LM", "LW", "AML", "AMC", "LAMF"],
    "RW": ["AMR", "AML", "RW", "RM", "AMC", "RAMF"],
    "LW": ["AML", "AMR", "LW", "LM", "AMC", "LAMF"],
    "AMR": ["AMR", "RW", "RM", "AMC", "RAMF"],
    "AML": ["AML", "LW", "LM", "AMC", "LAMF"],
    "RF": ["RF", "RW", "AMR", "ST", "RAMF"],
    "LF": ["LF", "LW", "AML", "ST", "LAMF"],
    "CMR": ["CMR", "RCMF", "DM", "RDM", "DMF"],
    "CML": ["CML", "LCMF", "DM", "LDM", "DMF"],
    "ST": ["ST", "CF"], "STL": ["ST", "CF"], "STR": ["ST", "CF"],
}

# Role-broad tokens: Wyscout position codes that belong to each broad role.
# Used to filter to eligible role before slot-specific position check.
_ROLE_TOKENS: dict[str, list[str]] = {
    "GK": ["GK"],
    "CB": ["CB", "RCB", "LCB"],
    "FB": ["RB", "LB", "RWB", "LWB", "WB"],
    "MF": ["CMF", "DMF", "CMR", "CML", "DM", "CDM"],
    "AM": ["AMF", "AMC", "AM"],
    "W": ["RAMF", "LAMF", "RW", "LW", "RWF", "LWF", "WF"],
    "FW": ["CF", "ST", "FW"],
}

# Map slot label → broad role key(s) used for pre-filtering
_SLOT_ROLE: dict[str, list[str]] = {
    "GK": ["GK"],
    "RB": ["FB"], "LB": ["FB"], "RWB": ["FB"], "LWB": ["FB"],
    "RCB": ["CB"], "LCB": ["CB"], "CB": ["CB"],
    "DM": ["MF"], "CM": ["MF"], "RCM": ["MF"], "LCM": ["MF"],
    "CMR": ["MF"], "CML": ["MF"],
    "AMC": ["AM", "MF"],
    "RM": ["W", "MF"], "LM": ["W", "MF"],
    "RW": ["W"], "LW": ["W"],
    "AMR": ["W"], "AML": ["W"],
    "RF": ["W", "FW"], "LF": ["W", "FW"],
    "ST": ["FW"], "STL": ["FW"], "STR": ["FW"],
}

_CM_GROUP_SLOTS = {"CM", "RCM", "LCM", "CMR", "CML", "DM", "DMR", "DML"}


def _position_fits_slot(position_str: str, slot: str) -> bool:
    if not isinstance(position_str, str):
        return False
    allowed = SLOT_POSITION_ALLOWED.get(slot)
    if allowed is None:
        return True
    allowed_upper = [p.upper() for p in allowed]
    tokens = [t.strip().upper() for t in position_str.split(",") if t.strip()]
    matches = [tok for tok in tokens if any(pos in tok for pos in allowed_upper)]
    if not matches:
        return False
    if slot in _CM_GROUP_SLOTS:
        if all(tok.endswith("3") for tok in matches):
            return False
    return True


def _matches_side(slot: str, position_str: str) -> bool:
    if not isinstance(position_str, str):
        return True
    pos = position_str.upper()
    if slot in ("RB", "RWB"):
        return "RB" in pos or "RWB" in pos
    if slot in ("LB", "LWB"):
        return "LB" in pos or "LWB" in pos
    right_tokens = ("RW", "RWF", "RAMF")
    left_tokens = ("LW", "LWF", "LAMF")
    if slot in ("RW", "RF", "RM", "AMR"):
        if any(t in pos for t in right_tokens):
            return True
        if any(t in pos for t in left_tokens):
            return False
    if slot in ("LW", "LF", "LM", "AML"):
        if any(t in pos for t in left_tokens):
            return True
        if any(t in pos for t in right_tokens):
            return False
    if slot == "RCB":
        if "RCB" in pos:
            return True
        if "LCB" in pos:
            return False
        if "CB" in pos and "L" not in pos:
            return True
    if slot == "LCB":
        if "LCB" in pos:
            return True
        if "RCB" in pos:
            return False
        if "CB" in pos and "R" not in pos:
            return True
    return True


def _role_pattern_for_slot(slot: str) -> str | None:
    role_keys = _SLOT_ROLE.get(slot)
    if not role_keys:
        return None
    tokens: list[str] = []
    for rk in role_keys:
        tokens.extend(_ROLE_TOKENS.get(rk, []))
    if not tokens:
        return None
    return "|".join(sorted(set(tokens), key=len, reverse=True))


def _filter_candidates(df: pd.DataFrame, slot: str, used_ids: set[int]) -> pd.DataFrame:
    work = df.copy()

    # Role pre-filter
    pattern = _role_pattern_for_slot(slot)
    if pattern:
        pos_col = "position" if "position" in work.columns else None
        if pos_col:
            mask = work[pos_col].str.upper().str.contains(pattern, na=False, regex=True)
            work = work[mask]
    if work.empty:
        return work

    # Exact position-code filter
    pos_col = "position" if "position" in work.columns else None
    if pos_col:
        work = work[work[pos_col].apply(lambda s: _position_fits_slot(s, slot))]
    if work.empty:
        return work

    # Side filter
    if pos_col and slot != "GK":
        work = work[work[pos_col].apply(lambda s: _matches_side(slot, s))]
    if work.empty:
        return work

    # Dedup
    if used_ids:
        work = work[~work["wyscout_id"].isin(used_ids)]

    return work


def _pick_best(df: pd.DataFrame, slot: str, used_ids: set[int]) -> dict[str, Any] | None:
    candidates = _filter_candidates(df, slot, used_ids)
    if candidates.empty:
        return None
    best = candidates.loc[candidates["performance_index"].idxmax()]
    return best.to_dict()


def _top_n(df: pd.DataFrame, slot: str, used_ids: set[int], n: int = 3) -> list[dict[str, Any]]:
    candidates = _filter_candidates(df, slot, used_ids)
    if candidates.empty:
        return []
    top = candidates.nlargest(n, "performance_index")
    return [row.to_dict() for _, row in top.iterrows()]


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post("/best-xi", response_model=BestXIResponse)
def best_xi(req: BestXIRequest) -> BestXIResponse:
    if req.formation not in FORMATIONS:
        raise HTTPException(400, f"Unknown formation: {req.formation}. Choose from {list(FORMATIONS)}")

    view = view_name(req.filters.season)
    if view not in list_views():
        raise HTTPException(404, f"Season {req.filters.season} not loaded")

    with duckdb_session() as conn:
        cols_in_view = column_names_in_view(conn, view)
        if "performance_index" not in cols_in_view:
            raise HTTPException(422, "performance_index not available for this season")

        logo_sql = club_logo_select_sql(conn, view, req.filters.season)
        img_sql = player_image_select_sql(conn, view)

        # Build filters — skip role filter (we apply per-slot), skip GK exclusion
        where_parts: list[str] = []
        params: list[Any] = []
        f = req.filters

        if f.leagues:
            where_parts.append(f"league IN ({','.join(['?'] * len(f.leagues))})")
            params.extend(f.leagues)
        age_sel = player_age_sql(cols_in_view, req.filters.season)
        if f.age_min is not None:
            where_parts.append(f"({age_sel}) >= ?")
            params.append(f.age_min)
        if f.age_max is not None:
            where_parts.append(f"({age_sel}) <= ?")
            params.append(f.age_max)
        if f.minutes_min is not None:
            where_parts.append('"Minutes played" >= ?')
            params.append(f.minutes_min)
        if f.minutes_max is not None:
            where_parts.append('"Minutes played" <= ?')
            params.append(f.minutes_max)

        if req.mode == "by_club":
            if not req.club:
                raise HTTPException(400, "club required for by_club mode")
            where_parts.append("club = ?")
            params.append(req.club)
        elif req.mode == "two_teams":
            if not req.club:
                raise HTTPException(400, "club required for two_teams mode")
            clubs = [req.club] + ([req.team2] if req.team2 else [])
            where_parts.append(f"club IN ({','.join(['?'] * len(clubs))})")
            params.extend(clubs)

        where_parts.append("performance_index IS NOT NULL")
        where = "WHERE " + " AND ".join(where_parts)

        select_cols = ", ".join(
            [
                '"Wyscout id" AS wyscout_id',
                '"Player" AS player',
                '"Full name" AS full_name',
                "club",
                "league",
                '"Position" AS position',
                f"({age_sel}) AS age",
                '"Minutes played" AS minutes',
                '"Goals" AS goals',
                '"Assists" AS assists',
                "performance_index",
            ]
        )
        sql = f"SELECT {logo_sql}, {img_sql}, {select_cols} FROM {view} {where}"
        rows_raw = fetch_all_dicts(conn, sql, params)

    if not rows_raw:
        raise HTTPException(404, "No players found for the given filters")

    df = pd.DataFrame(rows_raw)
    df["performance_index"] = pd.to_numeric(df["performance_index"], errors="coerce")
    df["wyscout_id"] = pd.to_numeric(df["wyscout_id"], errors="coerce")
    df = df.dropna(subset=["performance_index"])

    # Composite ID = (wyscout_id, club, season). Keep all rows so a transferred
    # player can be considered for both clubs when mode="by_league" or "two_teams".
    # Slot dedup below still uses wyscout_id only (one player can't be in 2 slots).
    df = df.reset_index(drop=True)

    # Context label
    if req.mode == "by_club":
        context = req.club or ""
    elif req.mode == "two_teams":
        clubs = [req.club or "", req.team2 or ""]
        context = " + ".join(c for c in clubs if c)
    else:
        leagues = req.filters.leagues
        context = ", ".join(leagues) if leagues else "All leagues"

    # Solver
    slots_def = FORMATIONS[req.formation]
    used_ids: set[int] = set()
    xi_slots: list[BestXIPlayer] = []

    for slot_label, position_type in slots_def:
        rec = _pick_best(df, slot_label, used_ids)
        if rec is None:
            xi_slots.append(BestXIPlayer(
                slot=slot_label,
                player="—",
                position_type=position_type,
            ))
            continue
        wid = rec.get("wyscout_id")
        if wid is not None and not (isinstance(wid, float) and wid != wid):
            used_ids.add(int(wid))
        xi_slots.append(BestXIPlayer(
            slot=slot_label,
            player=str(rec.get("player") or ""),
            wyscout_id=int(wid) if wid is not None and wid == wid else None,
            club=_nullable_str(rec.get("club")),
            club_logo=normalize_club_logo(rec.get("club_logo")),
            league=_nullable_str(rec.get("league")),
            position=_nullable_str(rec.get("position")),
            age=_safe_int(rec.get("age")),
            minutes=_safe_int(rec.get("minutes")),
            goals=_safe_int(rec.get("goals")),
            assists=_safe_int(rec.get("assists")),
            performance_index=_safe_float(rec.get("performance_index")),
            position_type=position_type,
            player_image_url=_nullable_str(rec.get("player_image_url")),
        ))

    # Top 3 per slot
    slot_groups: dict[str, str] = {
        "RCB": "CB_GROUP", "LCB": "CB_GROUP", "CB": "CB_GROUP",
        "RCM": "CM_GROUP", "LCM": "CM_GROUP", "CMR": "CM_GROUP",
        "CML": "CM_GROUP", "DM": "CM_GROUP",
    }
    group_used: dict[str, set[int]] = {}
    top3_rows: list[BestXITop3Row] = []

    for slot_label, position_type in slots_def:
        group_key = slot_groups.get(slot_label, slot_label)
        group_used.setdefault(group_key, set())
        top = _top_n(df, slot_label, group_used[group_key], n=3)
        for rank, rec in enumerate(top, start=1):
            wid = rec.get("wyscout_id")
            wid_int = int(wid) if wid is not None and wid == wid else None
            if wid_int is not None:
                group_used[group_key].add(wid_int)
            top3_rows.append(BestXITop3Row(
                slot=slot_label,
                rank=rank,
                player=str(rec.get("player") or ""),
                wyscout_id=wid_int,
                club=_nullable_str(rec.get("club")),
                club_logo=normalize_club_logo(rec.get("club_logo")),
                age=_safe_int(rec.get("age")),
                minutes=_safe_int(rec.get("minutes")),
                performance_index=_safe_float(rec.get("performance_index")),
                position_type=position_type,
                player_image_url=_nullable_str(rec.get("player_image_url")),
            ))

    coords_raw = FORMATION_COORDS.get(req.formation, {})
    coords = {k: list(v) for k, v in coords_raw.items()}

    return BestXIResponse(
        formation=req.formation,
        context=context,
        slots=xi_slots,
        top3=top3_rows,
        coords=coords,
    )


def _nullable_str(v: Any) -> str | None:
    """Pandas uses float NaN for missing strings; ``... or None`` keeps NaN (truthy)."""
    if v is None:
        return None
    if isinstance(v, float) and v != v:
        return None
    s = str(v).strip()
    return s if s else None


def _safe_int(v: Any) -> int | None:
    try:
        if v is None or (isinstance(v, float) and v != v):
            return None
        return int(v)
    except (TypeError, ValueError):
        return None


def _safe_float(v: Any) -> float | None:
    try:
        if v is None or (isinstance(v, float) and v != v):
            return None
        f = float(v)
        return round(f, 3)
    except (TypeError, ValueError):
        return None
