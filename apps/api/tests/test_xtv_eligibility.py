"""xTV league eligibility helpers."""

from __future__ import annotations

from app.core.xtv_eligibility import league_supports_xtv, xtv_parquet_sql


def test_campeonato_de_portugal_excluded() -> None:
    assert league_supports_xtv("Campeonato de Portugal") is False
    assert league_supports_xtv("Premier League") is True


def test_xtv_parquet_sql_nulls_ineligible_league() -> None:
    sql = xtv_parquet_sql({"x_tv_eur", "league"})
    assert "Campeonato de Portugal" in sql
    assert "CASE WHEN" in sql
