"""SQL fragment builder for player filters.

Maps a `PlayerFilters` model into a parametrised WHERE clause for DuckDB
queries against the `players_<season>` views.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.core.config import ROLE_TO_TOKENS


def role_filter_tokens(role_names: list[str]) -> set[str]:
    """Expand API `roles` entries to Wyscout codes: parent role names or raw tokens."""
    all_known: set[str] = set()
    for toks in ROLE_TO_TOKENS.values():
        all_known.update(toks)
    out: set[str] = set()
    for r in role_names:
        if r in ROLE_TO_TOKENS:
            out.update(ROLE_TO_TOKENS[r])
        elif r in all_known:
            out.add(r)
    return out

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


def build_where(f: PlayerFilters) -> tuple[str, list[Any]]:
    """Return (where_sql, params) excluding the 'WHERE' keyword. Empty string if no filters."""
    parts: list[str] = []
    params: list[Any] = []

    if f.leagues:
        parts.append(f"league IN ({','.join(['?'] * len(f.leagues))})")
        params.extend(f.leagues)

    if f.teams:
        parts.append(f"club IN ({','.join(['?'] * len(f.teams))})")
        params.extend(f.teams)

    if f.age_min is not None:
        parts.append("Age >= ?")
        params.append(f.age_min)

    if f.age_max is not None:
        parts.append("Age <= ?")
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

    if f.roles:
        # Role filter: position string matches any Wyscout token (parent role or sub-position).
        tokens = role_filter_tokens(f.roles)
        if tokens:
            pattern = "(" + "|".join(sorted(tokens, key=len, reverse=True)) + ")"
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
