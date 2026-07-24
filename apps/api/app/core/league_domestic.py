"""Map each Wyscout league to passport country/countries treated as domestic.

Wyscout ``Passport country`` can list multiple nationalities comma-separated
(e.g. ``England, Nigeria``). A player counts as domestic when any listed
passport matches the league's domestic set.
"""
from __future__ import annotations

from app.core.config import LEAGUES

# Primary passport country/countries per league (aligned with modal squad passport
# in each competition's player pool).
LEAGUE_DOMESTIC_PASSPORT: dict[str, tuple[str, ...]] = {
    "Premier League": ("England",),
    "Serie A": ("Italy",),
    "La Liga": ("Spain",),
    "Bundesliga": ("Germany",),
    "Ligue 1": ("France",),
    "Championship": ("England",),
    "Belgian Pro League": ("Belgium",),
    "Primeira Liga": ("Portugal",),
    "Brasileirão": ("Brazil",),
    "Eredivisie": ("Netherlands",),
    "Argentina LPF": ("Argentina",),
    "MLS": ("United States",),
    "Liga de Expansión MX": ("Mexico",),
    "1. HNL": ("Croatia",),
    "J1": ("Japan",),
    "Ekstraklasa": ("Poland",),
    "Superliga": ("Denmark",),
    "Serie B": ("Italy",),
    "Allsvenskan": ("Sweden",),
    "Süper Lig": ("Türkiye",),
    "La Liga 2": ("Spain",),
    "2. Bundesliga": ("Germany",),
    "Russian Premier League": ("Russia",),
    "Swiss Super League": ("Switzerland",),
    "Austrian Bundesliga": ("Austria",),
    "Eliteserien": ("Norway",),
    "Greek Super League": ("Greece",),
    "Ukrainian Premier League": ("Ukraine",),
    "Scottish Premiership": ("Scotland",),
    "Saudi Pro League": ("Saudi Arabia",),
    "Ligue 2": ("France",),
    "Portuguese Segunda Liga": ("Portugal",),
    "Chilean Primera Division": ("Chile",),
    "Veikkausliiga": ("Finland",),
    "Portuguese Liga 3": ("Portugal",),
    "Campeonato de Portugal": ("Portugal",),
}

# Ensure every catalogued league has an explicit domestic mapping.
assert set(LEAGUES) <= set(LEAGUE_DOMESTIC_PASSPORT.keys())


def league_domestic_passports(league: str | None) -> tuple[str, ...] | None:
    if not league:
        return None
    return LEAGUE_DOMESTIC_PASSPORT.get(league.strip())


def league_domestic_label(league: str | None) -> str | None:
    """Primary UI label for the league's domestic passport (first entry)."""
    passports = league_domestic_passports(league)
    if not passports:
        return None
    return passports[0]


def passport_tokens(passport: str | None) -> list[str]:
    if not passport:
        return []
    return [part.strip() for part in str(passport).split(",") if part.strip()]


def is_domestic_passport(passport: str | None, league: str | None) -> bool | None:
    """Return True/False when passport is known; None when passport is missing."""
    if not passport or not str(passport).strip():
        return None
    domestic = league_domestic_passports(league)
    if not domestic:
        return None
    tokens = passport_tokens(passport)
    return any(token in domestic for token in tokens)