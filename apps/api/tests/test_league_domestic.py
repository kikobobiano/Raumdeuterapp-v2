"""Tests for league domestic passport matching."""
from __future__ import annotations

from app.core.league_domestic import (
    is_domestic_passport,
    league_domestic_label,
    passport_tokens,
)


def test_passport_tokens_splits_compound_values() -> None:
    assert passport_tokens("England, Nigeria") == ["England", "Nigeria"]
    assert passport_tokens("France") == ["France"]


def test_is_domestic_passport_single_and_compound() -> None:
    assert is_domestic_passport("England", "Premier League") is True
    assert is_domestic_passport("England, Nigeria", "Premier League") is True
    assert is_domestic_passport("Brazil", "Premier League") is False
    assert is_domestic_passport(None, "Premier League") is None


def test_league_domestic_label() -> None:
    assert league_domestic_label("Serie A") == "Italy"
    assert league_domestic_label("Unknown") is None
