"""SQL fragment builder for player filters.

Maps a `PlayerFilters` model into a parametrised WHERE clause for DuckDB
queries against the `players_<season>` views.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.core.config import ROLE_TO_TOKENS
from app.core.player_age import player_age_sql

# Base ROLE_TO_TOKENS codes that appear inside Wyscout side/formation labels
# (RCB→CB, LCMF3→CMF, LB5→LB). Short codes like LW/RW are NOT expanded — that
# would re-break the LWB/RWB boundary fix in role_position_regex.
_SIDE_FORMATION_VARIANTS: dict[str, tuple[str, ...]] = {
    "CB": ("LCB", "RCB", "CB3", "LCB3", "RCB3"),
    "CMF": ("LCMF", "RCMF", "CMF3", "LCMF3", "RCMF3"),
    "DMF": ("LDMF", "RDMF"),
    "LB": ("LB5",),
    "RB": ("RB5",),
}


def _expand_side_formation_variants(tokens: set[str]) -> set[str]:
    out = set(tokens)
    for base, variants in _SIDE_FORMATION_VARIANTS.items():
        if base in out:
            out.update(variants)
    return out


def role_filter_tokens(role_names: list[str]) -> set[str]:
    """Expand API `roles` entries to Wyscout codes: parent role names or raw tokens.

    Also expands side/formation surface forms (RCB, LCMF, …) for base codes so
    SQL exact-token matching stays aligned with ``position_tokens`` / role labels.
    """
    all_known: set[str] = set()
    for toks in ROLE_TO_TOKENS.values():
        all_known.update(toks)
    out: set[str] = set()
    for r in role_names:
        if r in ROLE_TO_TOKENS:
            out.update(ROLE_TO_TOKENS[r])
        elif r in all_known:
            out.add(r)
    return _expand_side_formation_variants(out)


def role_position_regex(tokens: set[str]) -> str | None:
    """Regex matching slash-separated Wyscout position tokens exactly (not substrings).

    Without token boundaries, ``LW`` matches ``LWB`` and ``RW`` matches ``RWB``.
    Pattern: ``(^|/)(LAMF|…|LW|…)(/|$)`` with longer tokens first.
    """
    if not tokens:
        return None
    ordered = sorted(tokens, key=len, reverse=True)
    inner = "|".join(ordered)
    return f"(^|/)({inner})(/|$)"

# Wyscout positions are slash-separated tokens (e.g. LWF/CF). GK = goalkeeper only.
_GK_POSITION_RE = r"(^|/)GK(/|$)"


def not_goalkeeper_sql() -> tuple[str, list[Any]]:
    """SQL fragment + params: exclude goalkeepers from player queries."""
    return (
        'NOT regexp_matches(coalesce("Primary position", Position, \'\'), ?)',
        [_GK_POSITION_RE],
    )


def goalkeeper_only_sql() -> tuple[str, list[Any]]:
    """SQL fragment + params: keep goalkeepers only (trait cohort for GK role)."""
    return (
        'regexp_matches(coalesce("Primary position", Position, \'\'), ?)',
        [_GK_POSITION_RE],
    )


class PlayerFilters(BaseModel):
    season: int = Field(..., description="Season start year, e.g. 2025 for 25-26")
    leagues: list[str] | None = None
    roles: list[str] | None = None
    teams: list[str] | None = None
    age_min: int | None = None
    age_max: int | None = None
    minutes_min: int | None = None
    minutes_max: int | None = None
    market_value_max: float | None = None
    foot: str | None = None
    contract_expires_year_min: int | None = None
    contract_expires_year_max: int | None = None
    xtv_min_eur: float | None = None
    xtv_max_eur: float | None = None
    height_min: int | None = None
    height_max: int | None = None
    passport_countries: list[str] | None = Field(
        default=None,
        description='Passport country in this list (exact match on Wyscout "Passport country" column when present in the view).',
    )


def age_filter_parts(
    f: PlayerFilters,
    cols: set[str],
    *,
    season: int | None = None,
) -> tuple[list[str], list[Any]]:
    """SQL fragments for age_min/age_max using season-aligned age (1 Jul anchor)."""
    parts: list[str] = []
    params: list[Any] = []
    if f.age_min is None and f.age_max is None:
        return parts, params
    age_expr = f"({player_age_sql(cols, season if season is not None else f.season)})"
    if f.age_min is not None:
        parts.append(f"{age_expr} >= ?")
        params.append(f.age_min)
    if f.age_max is not None:
        parts.append(f"{age_expr} <= ?")
        params.append(f.age_max)
    return parts, params


def build_where(
    f: PlayerFilters,
    *,
    cols: set[str] | None = None,
    season: int | None = None,
    include_age: bool = True,
) -> tuple[str, list[Any]]:
    """Return (where_sql, params) excluding the 'WHERE' keyword. Empty string if no filters."""
    parts: list[str] = []
    params: list[Any] = []

    if f.leagues:
        parts.append(f"league IN ({','.join(['?'] * len(f.leagues))})")
        params.extend(f.leagues)

    if f.teams:
        parts.append(f"club IN ({','.join(['?'] * len(f.teams))})")
        params.extend(f.teams)

    if include_age:
        if cols is not None:
            age_parts, age_params = age_filter_parts(f, cols, season=season)
            parts.extend(age_parts)
            params.extend(age_params)
        else:
            if f.age_min is not None:
                parts.append('"Age" >= ?')
                params.append(f.age_min)
            if f.age_max is not None:
                parts.append('"Age" <= ?')
                params.append(f.age_max)

    if f.minutes_min is not None:
        parts.append('"Minutes played" >= ?')
        params.append(f.minutes_min)

    if f.minutes_max is not None:
        parts.append('"Minutes played" <= ?')
        params.append(f.minutes_max)

    if f.market_value_max is not None:
        parts.append('"Market value" <= ?')
        params.append(f.market_value_max)

    if f.foot:
        parts.append("Foot = ?")
        params.append(f.foot)

    if f.contract_expires_year_min is not None:
        parts.append(
            'try_cast("Contract expires" AS DATE) IS NOT NULL '
            'AND year(try_cast("Contract expires" AS DATE)) >= ?'
        )
        params.append(f.contract_expires_year_min)

    if f.contract_expires_year_max is not None:
        parts.append(
            'try_cast("Contract expires" AS DATE) IS NOT NULL '
            'AND year(try_cast("Contract expires" AS DATE)) <= ?'
        )
        params.append(f.contract_expires_year_max)

    if f.xtv_min_eur is not None:
        parts.append('CAST("x_tv_eur" AS DOUBLE) >= ?')
        params.append(f.xtv_min_eur)

    if f.xtv_max_eur is not None:
        parts.append('CAST("x_tv_eur" AS DOUBLE) <= ?')
        params.append(f.xtv_max_eur)

    if f.height_min is not None:
        parts.append('try_cast("Height" AS INTEGER) >= ?')
        params.append(f.height_min)

    if f.height_max is not None:
        parts.append('try_cast("Height" AS INTEGER) <= ?')
        params.append(f.height_max)

    if f.passport_countries:
        ph = ",".join(["?"] * len(f.passport_countries))
        parts.append(f'"Passport country" IN ({ph})')
        params.extend(f.passport_countries)

    if f.roles:
        tokens = role_filter_tokens(f.roles)
        pattern = role_position_regex(tokens)
        if pattern:
            parts.append('regexp_matches(coalesce("Primary position", Position, \'\'), ?)')
            params.append(pattern)

    gk_sql, gk_params = not_goalkeeper_sql()
    parts.append(gk_sql)
    params.extend(gk_params)

    if not parts:
        return "", params
    return " AND ".join(parts), params


def view_name(season: int) -> str:
    return f"players_{season}"
