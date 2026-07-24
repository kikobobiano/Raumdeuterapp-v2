"""Role position regex must match Wyscout tokens exactly (LW ≠ LWB)."""

from __future__ import annotations

import duckdb

from app.core.filters import role_filter_tokens, role_position_regex


def _matches(pattern: str, position: str) -> bool:
    conn = duckdb.connect()
    return bool(conn.execute("SELECT regexp_matches(?, ?)", [position, pattern]).fetchone()[0])


def test_winger_filter_excludes_fullback_tokens() -> None:
    tokens = role_filter_tokens(["Winger"])
    pattern = role_position_regex(tokens)
    assert pattern is not None
    assert _matches(pattern, "LW")
    assert _matches(pattern, "LWF/CF")
    assert _matches(pattern, "RB/RW")
    assert not _matches(pattern, "LWB")
    assert not _matches(pattern, "RWB")
    assert not _matches(pattern, "WB")
    assert not _matches(pattern, "LWB/RWB")


def test_fullback_filter_still_matches_wing_backs() -> None:
    tokens = role_filter_tokens(["Fullback"])
    pattern = role_position_regex(tokens)
    assert pattern is not None
    assert _matches(pattern, "LWB")
    assert _matches(pattern, "RWB")
    assert _matches(pattern, "WB")
    assert not _matches(pattern, "LW")
    assert not _matches(pattern, "RW")


def test_old_pattern_would_false_match_lwb_as_winger() -> None:
    tokens = role_filter_tokens(["Winger"])
    broken = "(" + "|".join(sorted(tokens, key=len, reverse=True)) + ")"
    assert _matches(broken, "LWB")


def test_defender_filter_matches_side_prefixed_cb() -> None:
    """Wyscout uses RCB/LCB(/3); ROLE_TO_TOKENS only lists base CB."""
    tokens = role_filter_tokens(["Defender"])
    pattern = role_position_regex(tokens)
    assert pattern is not None
    for pos in ("CB", "RCB", "LCB", "RCB3", "LCB3", "CB3", "DMF", "LDMF", "RDMF", "DF"):
        assert _matches(pattern, pos), pos
    assert not _matches(pattern, "LB")
    assert not _matches(pattern, "RB")


def test_midfielder_filter_matches_side_prefixed_cmf_dmf() -> None:
    tokens = role_filter_tokens(["Midfielder"])
    pattern = role_position_regex(tokens)
    assert pattern is not None
    for pos in ("CMF", "LCMF", "RCMF", "LCMF3", "RCMF3", "DMF", "LDMF", "RDMF"):
        assert _matches(pattern, pos), pos
    assert not _matches(pattern, "CB")
    assert not _matches(pattern, "RCB")


def test_fullback_filter_matches_lb5_rb5() -> None:
    tokens = role_filter_tokens(["Fullback"])
    pattern = role_position_regex(tokens)
    assert pattern is not None
    assert _matches(pattern, "LB5")
    assert _matches(pattern, "RB5")
