"""Season resolution helpers for the Screener multi-season path."""

from __future__ import annotations

from app.core.filters import view_name


def resolve_screener_seasons(seasons: list[int], fallback: int) -> list[int]:
    """Empty ``seasons`` → single-season fallback (global / filters.season)."""
    return list(seasons) if seasons else [fallback]


def assert_seasons_loaded(seasons: list[int], loaded_views: set[str] | list[str]) -> None:
    """Raise ``ValueError`` with the missing year if a season view is absent."""
    views = set(loaded_views)
    for y in seasons:
        if view_name(y) not in views:
            raise ValueError(str(y))
