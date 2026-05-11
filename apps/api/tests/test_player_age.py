"""Season-aligned age from Birthday + anchor (see core/player_age.py)."""

from __future__ import annotations

from app.core.player_age import player_age_for_season


def test_player_age_for_season_prefers_birthday_over_stale_age_column() -> None:
    rec = {"Birthday": "1995-01-09", "Age": 99}
    assert player_age_for_season(rec, 2025) == 30


def test_player_age_for_season_decrements_when_birthday_after_july_anchor() -> None:
    rec = {"Birthday": "1995-08-15", "Age": 99}
    assert player_age_for_season(rec, 2025) == 29


def test_player_age_for_season_falls_back_when_no_birthday() -> None:
    rec = {"Age": 27}
    assert player_age_for_season(rec, 2025) == 27
