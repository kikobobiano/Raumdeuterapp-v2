"""Domain constants — port of legacy utils/config.py without streamlit deps."""
from __future__ import annotations

import re

PROFILE_RADAR_MIN_MINUTES = 200

BIG_FIVE_LEAGUES: tuple[str, ...] = (
    "Premier League",
    "Serie A",
    "La Liga",
    "Bundesliga",
    "Ligue 1",
)

LEAGUES: list[str] = [
    "Premier League", "Serie A", "La Liga", "Bundesliga", "Ligue 1",
    "Championship", "Belgian Pro League", "Primeira Liga", "Brasileirão",
    "Eredivisie", "Argentina LPF", "MLS", "Liga de Expansión MX", "1. HNL",
    "J1", "Ekstraklasa", "Superliga", "Serie B", "Allsvenskan", "Süper Lig",
    "La Liga 2", "2. Bundesliga", "Russian Premier League", "Swiss Super League",
    "Austrian Bundesliga", "Eliteserien", "Greek Super League",
    "Ukrainian Premier League", "Scottish Premiership", "Saudi Pro League",
    "Ligue 2", "Portuguese Segunda Liga", "Chilean Primera Division",
    "Veikkausliiga", "Portuguese Liga 3", "Campeonato de Portugal",
]

LEAGUE_POWER_MIN: float = 0.80
LEAGUE_POWER_MAX: float = 1.10
LEAGUE_POWER_MIN_ADJUSTED: float = 0.65
LEAGUE_POWER_MAX_ADJUSTED: float = 1.0

LEAGUE_MAX_GAMES: dict[str, int] = {
    "Premier League": 38, "Serie A": 38, "La Liga": 38,
    "Bundesliga": 34, "Ligue 1": 34, "Championship": 46,
    "Belgian Pro League": 30, "Primeira Liga": 34, "Brasileirão": 38,
    "Eredivisie": 34, "MLS": 34, "1. HNL": 36, "J1": 38,
    "Ekstraklasa": 34, "Superliga": 32, "Serie B": 38,
    "Allsvenskan": 30, "Süper Lig": 38, "La Liga 2": 42,
    "2. Bundesliga": 34, "Russian Premier League": 30,
    "Swiss Super League": 38, "Austrian Bundesliga": 32,
    "Eliteserien": 30, "Greek Super League": 26,
    "Scottish Premiership": 38, "Saudi Pro League": 34,
    "Ligue 2": 34, "Portuguese Segunda Liga": 34,
    "Chilean Primera Division": 30, "Veikkausliiga": 27,
    "Argentina LPF": 27, "Liga de Expansión MX": 17,
    "Ukrainian Premier League": 30,
    "Portuguese Liga 3": 30, "Campeonato de Portugal": 30,
}
LEAGUE_MAX_GAMES_DEFAULT = 38


def league_max_games(league: str | None) -> int:
    return LEAGUE_MAX_GAMES.get(league or "", LEAGUE_MAX_GAMES_DEFAULT)


def league_max_minutes(league: str | None) -> int:
    return league_max_games(league) * 90


LEAGUE_POWER_BASE: dict[str, float] = {
    "Premier League": 92.6, "Serie A": 87.0, "La Liga": 87.0, "Bundesliga": 86.3,
    "Ligue 1": 85.5, "Championship": 80.9, "Belgian Pro League": 80.5,
    "Primeira Liga": 79.8, "Brasileirão": 79.4, "Eredivisie": 78.8,
    "Argentina LPF": 78.6, "MLS": 78.5, "Liga de Expansión MX": 78.5, "J1": 77.9,
    "1. HNL": 77.8, "Ekstraklasa": 77.6, "Superliga": 77.6, "Serie B": 76.4,
    "Allsvenskan": 76.3, "Süper Lig": 76.2, "La Liga 2": 76.2, "2. Bundesliga": 76.2,
    "Russian Premier League": 76.1, "Swiss Super League": 76.1,
    "Austrian Bundesliga": 76.1, "Eliteserien": 75.9, "Greek Super League": 75.0,
    "Ukrainian Premier League": 75.0, "Scottish Premiership": 74.5,
    "Saudi Pro League": 74.0, "Ligue 2": 74.0, "Portuguese Segunda Liga": 70.5,
    "Chilean Primera Division": 72.0, "Veikkausliiga": 68.0,
    "Portuguese Liga 3": 65.0, "Campeonato de Portugal": 60.0,
}

GAME_AREAS_COLS: list[str] = [
    "Goals per 90", "xG per 90", "Shots per 90", "Shots on target, %",
    "Assists per 90", "Second assists per 90", "Smart passes per 90", "xA per 90",
    "Passes to penalty area per 90", "Through passes per 90",
    "Dribbles per 90", "Successful dribbles, %", "Offensive duels per 90",
    "Progressive runs per 90", "Accelerations per 90",
    "Passes per 90", "Accurate passes, %", "Vertical passes per 90",
    "Progressive passes per 90", "Long passes per 90",
    "Successful defensive actions per 90", "Defensive duels per 90",
    "Defensive duels won, %", "PAdj Interceptions", "Shots blocked per 90",
    "PAdj Sliding tackles",     "Aerial duels per 90", "Aerial duels won, %",
]

# Same letter → game-area mapping as legacy (player trait pill colours / radar groups).
PCT_GROUPS: list[str] = [
    "A", "A", "A", "A",
    "B", "B", "B", "B", "B", "B",
    "C", "C", "C", "C", "C",
    "D", "D", "D", "D", "D",
    "E", "E", "E", "E", "E", "E",
    "F", "F",
]
LEGEND_LABELS: dict[str, str] = {
    "A": "Finishing",
    "B": "Assistance",
    "C": "Take Ons",
    "D": "Distribution",
    "E": "Ground Defense",
    "F": "Aerial Play",
}

GAME_AREAS = ["Distribution", "Take Ons", "Assistance", "Finishing", "Aerial Play", "Ground Defense"]
AREA_INDEX_COLS = [
    "distribution_index", "take_ons_index", "assistance_index",
    "finishing_index", "aerial_play_index", "ground_defense_index",
]

# Per-game-area metrics that feed each index (same order as GAME_AREAS / AREA_INDEX_COLS).
# Mirrors the Performance Index metric weights in transformation/new_performance_index.py.
GAME_AREA_METRIC_GROUPS: list[tuple[str, str, list[str]]] = [
    (
        "Distribution",
        "distribution_index",
        [
            "Passes per 90",
            "Received passes per 90",
            "Accurate passes, %",
            "Progressive passes per 90",
            "Long passes per 90",
            "Accurate long passes, %",
            "Average long pass length, m",
            "Passes to final third per 90",
            "Third assists per 90",
            "Second assists per 90",
        ],
    ),
    (
        "Take Ons",
        "take_ons_index",
        [
            "Dribbles per 90",
            "Successful dribbles, %",
            "Progressive runs per 90",
            "Accelerations per 90",
            "Fouls suffered per 90",
        ],
    ),
    (
        "Assistance",
        "assistance_index",
        [
            "xA per 90",
            "Shot assists per 90",
            "Key passes per 90",
            "Passes to penalty area per 90",
            "Through passes per 90",
            "Deep completions per 90",
            "Offensive duels minus dribbles per 90",
            "Back passes per 90",
        ],
    ),
    (
        "Finishing",
        "finishing_index",
        [
            "Shots per 90",
            "Shots on target, %",
            "xG per shot per 90",
            "Non-penalty goals per 90",
            "Goal conversion, %",
            "NPxG per 90",
        ],
    ),
    (
        "Aerial Play",
        "aerial_play_index",
        [
            "Aerial duels per 90",
            "Aerial duels won, %",
        ],
    ),
    (
        "Ground Defense",
        "ground_defense_index",
        [
            "Defensive duels per 90",
            "Defensive duels won, %",
            "PAdj Interceptions",
            "Shots blocked per 90",
            "PAdj Sliding tackles",
            "Team GK conceded per 90",
        ],
    ),
]

ROLE_TO_TOKENS: dict[str, list[str]] = {
    "Goalkeeper": ["GK"],
    "Forward": ["CF", "ST", "STRIKER", "FW"],
    "Winger": ["WF", "LAMF", "RAMF", "LW", "RW", "RWF", "LWF"],
    "Midfielder": ["CMF", "DMF"],
    "Attacking Midfielder": ["AMF"],
    "Fullback": ["LWB", "RWB", "LB", "RB", "WB"],
    "Defender": ["CB", "DMF", "DF"],
}

ROLE_PRIORITY = [
    "Forward", "Winger", "Midfielder", "Attacking Midfielder",
    "Fullback", "Defender", "Goalkeeper",
]

ROLE_PRIORITY_UI = [r for r in ROLE_PRIORITY if r != "Goalkeeper"]

ROLE_TABLE_METRICS: dict[str, list[str]] = {
    "Forward": [
        "Minutes played", "Goals per 90", "xG per 90", "Shots per 90",
        "Shots on target, %", "Head goals per 90", "Assists per 90", "xA per 90",
        "Dribbles per 90", "Successful dribbles, %", "Offensive duels per 90",
        "Touches in box per 90", "Aerial duels per 90", "Aerial duels won, %",
    ],
    "Winger": [
        "Minutes played", "Goals per 90", "xG per 90", "Assists per 90",
        "xA per 90", "Crosses per 90", "Accurate crosses, %", "Dribbles per 90",
        "Successful dribbles, %", "Progressive runs per 90", "Accelerations per 90",
        "Key passes per 90", "Passes to final third per 90",
    ],
    "Midfielder": [
        "Minutes played", "Successful defensive actions per 90",
        "Defensive duels per 90", "Defensive duels won, %",
        "Aerial duels per 90", "Aerial duels won, %",
        "PAdj Interceptions", "Shots blocked per 90", "PAdj Sliding tackles",
        "Progressive passes per 90", "Passes per 90", "Accurate passes, %",
        "Passes to final third per 90",
    ],
    "Attacking Midfielder": [
        "Minutes played", "Goals per 90", "xG per 90", "Assists per 90",
        "xA per 90", "Key passes per 90", "Shot assists per 90",
        "Smart passes per 90", "Passes to penalty area per 90",
        "Through passes per 90", "Progressive passes per 90", "Passes per 90",
        "Accurate passes, %", "Passes to final third per 90", "Dribbles per 90",
        "Successful dribbles, %", "Progressive runs per 90", "Accelerations per 90",
        "Touches in box per 90", "Successful defensive actions per 90",
        "Defensive duels per 90", "Defensive duels won, %",
    ],
    "Fullback": [
        "Minutes played", "Successful defensive actions per 90",
        "Defensive duels per 90", "Defensive duels won, %",
        "Aerial duels per 90", "Aerial duels won, %", "Crosses per 90",
        "Accurate crosses, %", "Progressive runs per 90", "Accelerations per 90",
        "Passes per 90", "Accurate passes, %", "Passes to final third per 90",
    ],
    "Defender": [
        "Minutes played", "Successful defensive actions per 90",
        "Defensive duels per 90", "Defensive duels won, %",
        "Aerial duels per 90", "Aerial duels won, %",
        "PAdj Interceptions", "Shots blocked per 90", "PAdj Sliding tackles",
        "Passes per 90", "Accurate passes, %", "Progressive passes per 90",
        "Long passes per 90",
    ],
    "Goalkeeper": [
        "Minutes played", "Conceded goals per 90", "Save rate, %",
        "xG against per 90", "Prevented goals per 90", "Shots against per 90",
        "Clean sheets", "Exits per 90", "Back passes received as GK per 90",
        "Passes per 90", "Accurate passes, %", "Long passes per 90",
        "Accurate long passes, %",
    ],
}

METRIC_COLS: list[str] = [
    "Goals", "xG", "Assists", "xA",
    "Duels per 90", "Duels won, %",
    "Successful defensive actions per 90", "Defensive duels per 90", "Defensive duels won, %",
    "Aerial duels per 90", "Aerial duels won, %",
    "Sliding tackles per 90", "PAdj Sliding tackles", "Shots blocked per 90",
    "Interceptions per 90", "PAdj Interceptions",
    "Fouls per 90", "Yellow cards", "Yellow cards per 90", "Red cards", "Red cards per 90",
    "Successful attacking actions per 90",
    "Goals per 90", "Non-penalty goals", "Non-penalty goals per 90", "xG per 90",
    "NPxG", "NPxG per 90",
    "Head goals", "Head goals per 90",
    "Shots", "Shots per 90", "Shots on target, %", "Goal conversion, %",
    "Assists per 90",
    "Crosses per 90", "Accurate crosses, %",
    "Crosses from left flank per 90", "Accurate crosses from left flank, %",
    "Crosses from right flank per 90", "Accurate crosses from right flank, %",
    "Crosses to goalie box per 90",
    "Dribbles per 90", "Successful dribbles, %",
    "Offensive duels per 90", "Offensive duels won, %",
    "Touches in box per 90", "Progressive runs per 90", "Accelerations per 90",
    "Received passes per 90", "Received long passes per 90", "Fouls suffered per 90",
    "Passes per 90", "Accurate passes, %",
    "Forward passes per 90", "Accurate forward passes, %",
    "Back passes per 90", "Accurate back passes, %",
    "Short / medium passes per 90", "Accurate short / medium passes, %",
    "Long passes per 90", "Accurate long passes, %",
    "Average pass length, m", "Average long pass length, m",
    "xA per 90", "Shot assists per 90", "Second assists per 90", "Third assists per 90",
    "Smart passes per 90", "Accurate smart passes, %",
    "Key passes per 90",
    "Passes to final third per 90", "Accurate passes to final third, %",
    "Passes to penalty area per 90", "Accurate passes to penalty area, %",
    "Through passes per 90", "Accurate through passes, %",
    "Deep completions per 90", "Deep completed crosses per 90",
    "Progressive passes per 90", "Accurate progressive passes, %",
    "Accurate vertical passes, %", "Vertical passes per 90",
    "Conceded goals", "Conceded goals per 90", "Team GK conceded per 90",
    "Shots against", "Shots against per 90",
    "Clean sheets", "Save rate, %",
    "xG against", "xG against per 90", "Prevented goals", "Prevented goals per 90",
    "Back passes received as GK per 90", "Exits per 90",
    "Free kicks per 90", "Direct free kicks per 90", "Direct free kicks on target, %",
    "Corners per 90", "Penalties taken", "Penalty conversion, %",
    "Expected Offensive Output per 90", "Offensive Output per 90",
    "Ball Progression per 90", "Ball Winning Actions per 90",
    "Touches in box per shot per 90", "xG per shot per 90",
    "aerial_play_index", "ground_defense_index", "distribution_index",
    "take_ons_index", "finishing_index", "assistance_index",
    "LinkUp Play Quality", "Finishing Quality", "Dribling Quality",
    "Distribution Quality", "Aerial Play Quality", "Ground Defense Quality",
    "Creativity Quality",
    "potential_score",
    "Goals per 90 - % Team Impact", "xG per 90 - % Team Impact",
    "NPxG per 90 - % Team Impact",
    "Shots per 90 - % Team Impact", "Shots on target, % - % Team Impact",
    "Assists per 90 - % Team Impact", "Second assists per 90 - % Team Impact",
    "Smart passes per 90 - % Team Impact", "xA per 90 - % Team Impact",
    "Passes to penalty area per 90 - % Team Impact", "Through passes per 90 - % Team Impact",
    "Dribbles per 90 - % Team Impact", "Successful dribbles, % - % Team Impact",
    "Offensive duels per 90 - % Team Impact", "Progressive runs per 90 - % Team Impact",
    "Accelerations per 90 - % Team Impact",
    "Passes per 90 - % Team Impact", "Accurate passes, % - % Team Impact",
    "Vertical passes per 90 - % Team Impact", "Progressive passes per 90 - % Team Impact",
    "Successful defensive actions per 90 - % Team Impact",
    "Defensive duels per 90 - % Team Impact", "Defensive duels won, % - % Team Impact",
    "PAdj Interceptions - % Team Impact", "Shots blocked per 90 - % Team Impact",
    "PAdj Sliding tackles - % Team Impact",
    "Aerial duels per 90 - % Team Impact", "Aerial duels won, % - % Team Impact",
    "Expected Offensive Output per 90 - % Team Impact",
    "Offensive Output per 90 - % Team Impact",
    "Ball Progression per 90 - % Team Impact",
    "Ball Winning Actions per 90 - % Team Impact",
    "Touches in box per shot per 90 - % Team Impact",
    "xG per shot per 90 - % Team Impact",
]


def metric_column_show_in_selectors(name: str) -> bool:
    return not str(name).endswith("_z")


LOWER_IS_BETTER: set = {
    "Conceded goals per 90", "xG against per 90", "Shots against per 90",
    "Yellow cards per 90", "Red cards per 90", "Fouls per 90",
    "Conceded goals", "xG against", "Team GK conceded per 90",
}

BASE_TOKEN_RE = re.compile(
    r"(CF|ST|STRIKER|FW|LWB|RWB|LWF|RWF|LAMF|RAMF|LW|RW|AMF|WF|CMF|DMF|LB|RB|WB|CB|DF|GK)"
)

TOKEN_TO_ROLES: dict[str, set] = {}
for _role, _toks in ROLE_TO_TOKENS.items():
    for _t in _toks:
        TOKEN_TO_ROLES.setdefault(_t, set()).add(_role)


def position_tokens(pos: str | None) -> list[str]:
    """Wyscout position codes in string order, deduped (e.g. 'LWF/CF' → ['LWF','CF'])."""
    if not pos:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for tok in BASE_TOKEN_RE.findall(pos):
        if tok not in seen:
            seen.add(tok)
            out.append(tok)
    return out


def position_tokens_merged(*parts: str | None) -> list[str]:
    """Merge tokens from primary + secondary position strings; order = first field, then next, deduped."""
    seen: set[str] = set()
    out: list[str] = []
    for part in parts:
        if not part:
            continue
        for tok in position_tokens(part):
            if tok not in seen:
                seen.add(tok)
                out.append(tok)
    return out


def role_for_position(pos: str | None) -> str | None:
    """Map a Wyscout position string (e.g. 'LWF/CF') to highest-priority role."""
    if not pos:
        return None
    tokens = position_tokens(pos)
    roles_found: set[str] = set()
    for tok in tokens:
        roles_found.update(TOKEN_TO_ROLES.get(tok, set()))
    for role in ROLE_PRIORITY:
        if role in roles_found:
            return role
    return None


METRIC_DISPLAY_LABELS: dict[str, str] = {
    "assistance_index": "Assistance Index",
    "finishing_index": "Finishing Index",
    "distribution_index": "Distribution Index",
    "take_ons_index": "Take Ons Index",
    "aerial_play_index": "Aerial Play Index",
    "ground_defense_index": "Ground Defense Index",
    "xG": "xG", "xA": "xA",
    "xG per 90": "xG /90", "NPxG": "NPxG", "NPxG per 90": "NPxG /90",
    "xA per 90": "xA /90",
    "xG against": "xG Against", "xG against per 90": "xG Against /90",
    "xG per shot per 90": "xG per Shot /90",
    "PAdj Interceptions": "PAdj Interceptions",
    "PAdj Sliding tackles": "PAdj Sliding Tackles",
    "LinkUp Play Quality": "Link-Up Play Quality",
    "Dribling Quality": "Dribbling Quality",
    "Offensive duels minus dribbles per 90": "Offensive duels per 90",
}


def format_metric_label(col: str) -> str:
    if col in METRIC_DISPLAY_LABELS:
        return METRIC_DISPLAY_LABELS[col]
    if col.endswith(" - % Team Impact"):
        return f"{format_metric_label(col[:-len(' - % Team Impact')])} (Team %)"
    if col.endswith("_tm_pct"):
        return f"{format_metric_label(col[:-len('_tm_pct')])} (Team Pctl)"
    if col.endswith("_lg_pct"):
        return f"{format_metric_label(col[:-len('_lg_pct')])} (League Pctl)"
    if "_" in col and " " not in col:
        return col.replace("_", " ").title()
    return col
