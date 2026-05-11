"""Shared constants and configuration for the Streamlit app."""
from __future__ import annotations

import re
from typing import Dict, List

INPUT_DIR = "data/players/all"

# Shared TTL for ``@st.cache_data`` (seconds). 600 = 10 minutes.
STREAMLIT_CACHE_DATA_TTL_SEC = 600

# Shown on charts, Plotly exports, and HTML title blocks.
APP_STREAMLIT_URL = "https://raumdeuterapp.streamlit.app"
APP_CREDIT_LINE = "via raumdeuterapp.streamlit.app"

# Profile page: hide percentile radar below this many minutes played (same idea as Wyscout export filter).
PROFILE_RADAR_MIN_MINUTES = 200

# Top-tier European leagues (same order as the start of LEAGUES); used by Best XI presets.
BIG_FIVE_LEAGUES: tuple[str, ...] = (
    "Premier League",
    "Serie A",
    "La Liga",
    "Bundesliga",
    "Ligue 1",
)

LEAGUES: List[str] = [
    "Premier League",
    "Serie A",
    "La Liga",
    "Bundesliga",
    "Ligue 1",
    "Championship",
    "Belgian Pro League",
    "Primeira Liga",
    "Brasileirão",
    "Eredivisie",
    "Argentina LPF",
    "MLS",
    "Liga de Expansión MX",
    "1. HNL",
    "J1",
    "Ekstraklasa",
    "Superliga",
    "Serie B",
    "Allsvenskan",
    "Süper Lig",
    "La Liga 2",
    "2. Bundesliga",
    "Russian Premier League",
    "Swiss Super League",
    "Austrian Bundesliga",
    "Eliteserien",
    "Greek Super League",
    "Ukrainian Premier League",
    "Scottish Premiership",
    "Saudi Pro League",
    "Ligue 2",
    "Portuguese Segunda Liga",
    "Chilean Primera Division",
    "Veikkausliiga",
    "Portuguese Liga 3",
    "Campeonato de Portugal",
]

LEAGUE_POWER_BASE: Dict[str, float] = {
    "Premier League": 92.6,
    "Serie A": 87.0,
    "La Liga": 87.0,
    "Bundesliga": 86.3,
    "Ligue 1": 85.5,
    "Championship": 80.9,
    "Belgian Pro League": 80.5,
    "Primeira Liga": 79.8,
    "Brasileirão": 79.4,
    "Eredivisie": 78.8,
    "Argentina LPF": 78.6,
    "MLS": 78.5,
    "Liga de Expansión MX": 78.5,
    "J1": 77.9,
    "1. HNL": 77.8,
    "Ekstraklasa": 77.6,
    "Superliga": 77.6,
    "Serie B": 76.4,
    "Allsvenskan": 76.3,
    "Süper Lig": 76.2,
    "La Liga 2": 76.2,
    "2. Bundesliga": 76.2,
    "Russian Premier League": 76.1,
    "Swiss Super League": 76.1,
    "Austrian Bundesliga": 76.1,
    "Eliteserien": 75.9,
    "Greek Super League": 75.0,
    "Ukrainian Premier League": 75.0,
    "Scottish Premiership": 74.5,
    "Saudi Pro League": 74.0,
    "Ligue 2": 74.0,
    "Portuguese Segunda Liga": 70.5,
    "Chilean Primera Division": 72.0,
    "Veikkausliiga": 68.0,
    "Portuguese Liga 3": 65.0,
    "Campeonato de Portugal": 60.0,
}

LEAGUE_POWER_MIN, LEAGUE_POWER_MAX = 0.80, 1.10
LEAGUE_POWER_MIN_ADJUSTED, LEAGUE_POWER_MAX_ADJUSTED = 0.65, 1.0

GAME_AREAS_COLS: List[str] = [
    "Goals per 90", "xG per 90", "Shots per 90", "Shots on target, %",
    "Assists per 90", "Second assists per 90", "Smart passes per 90", "xA per 90",
    "Passes to penalty area per 90", "Through passes per 90",
    "Dribbles per 90", "Successful dribbles, %", "Offensive duels per 90",
    "Progressive runs per 90", "Accelerations per 90",
    "Passes per 90", "Accurate passes, %", "Vertical passes per 90", "Progressive passes per 90", "Long passes per 90",
    "Successful defensive actions per 90", "Defensive duels per 90", "Defensive duels won, %",
    "PAdj Interceptions", "Shots blocked per 90", "PAdj Sliding tackles",
    "Aerial duels per 90", "Aerial duels won, %",
]

TEAM_PERCENTILES_COLS: List[str] = [f"{c}_tm_pct" for c in GAME_AREAS_COLS]
LEAGUE_PERCENTILES_COLS: List[str] = [f"{c}_lg_pct" for c in GAME_AREAS_COLS]

GAME_AREAS = ["Distribution", "Take Ons", "Assistance", "Finishing", "Aerial Play", "Ground Defense"]
AREA_INDEX_COLS = [
    "distribution_index", "take_ons_index", "assistance_index",
    "finishing_index", "aerial_play_index", "ground_defense_index",
]

PCT_GROUPS = [
    "A", "A", "A", "A",
    "B", "B", "B", "B", "B", "B",
    "C", "C", "C", "C", "C",
    "D", "D", "D", "D", "D",
    "E", "E", "E", "E", "E", "E",
    "F", "F",
]
LEGEND_LABELS = {
    "A": "Finishing", "B": "Assistance", "C": "Take Ons",
    "D": "Distribution", "E": "Ground Defense", "F": "Aerial Play",
}
GROUP_COLORS = {
    "A": "#884444", "B": "#6E7358", "C": "#627F66",
    "D": "#79BAB7", "E": "#D09854", "F": "#B06A2E",
}

ROLE_TO_TOKENS: Dict[str, List[str]] = {
    "Goalkeeper": ["GK"],
    "Forward": ["CF", "ST", "STRIKER", "FW"],
    "Winger": ["WF", "LAMF", "RAMF", "LW", "RW", "RWF", "LWF"],
    "Midfielder": ["CMF", "DMF"],
    "Attacking Midfielder": ["AMF"],
    "Fullback": ["LWB", "RWB", "LB", "RB", "WB"],
    "Defender": ["CB", "DMF", "DF"],
}

ROLE_PRIORITY = [
    "Forward",
    "Winger",
    "Midfielder",
    "Attacking Midfielder",
    "Fullback",
    "Defender",
    "Goalkeeper",
]

# Role groups offered in Streamlit position filters (goalkeepers excluded by product choice).
ROLE_PRIORITY_UI = [r for r in ROLE_PRIORITY if r != "Goalkeeper"]

ROLE_TABLE_METRICS: Dict[str, List[str]] = {
    "Forward": [
        "Minutes played",
        "Goals per 90", "xG per 90", "Shots per 90", "Shots on target, %",
        "Head goals per 90",
        "Assists per 90", "xA per 90",
        "Dribbles per 90", "Successful dribbles, %",
        "Offensive duels per 90",
        "Touches in box per 90",
        "Aerial duels per 90", "Aerial duels won, %",
    ],
    "Winger": [
        "Minutes played",
        "Goals per 90", "xG per 90",
        "Assists per 90", "xA per 90",
        "Crosses per 90", "Accurate crosses, %",
        "Dribbles per 90", "Successful dribbles, %",
        "Progressive runs per 90", "Accelerations per 90",
        "Key passes per 90",
        "Passes to final third per 90",
    ],
    "Midfielder": [
        "Minutes played",
        "Successful defensive actions per 90",
        "Defensive duels per 90", "Defensive duels won, %",
        "Aerial duels per 90", "Aerial duels won, %",
        "PAdj Interceptions", "Shots blocked per 90", "PAdj Sliding tackles",
        "Progressive passes per 90",
        "Passes per 90", "Accurate passes, %",
        "Passes to final third per 90",
    ],
    "Attacking Midfielder": [
        "Minutes played",
        "Goals per 90", "xG per 90", "Assists per 90", "xA per 90",
        "Key passes per 90", "Shot assists per 90", "Smart passes per 90",
        "Passes to penalty area per 90", "Through passes per 90",
        "Progressive passes per 90", "Passes per 90", "Accurate passes, %",
        "Passes to final third per 90",
        "Dribbles per 90", "Successful dribbles, %",
        "Progressive runs per 90", "Accelerations per 90",
        "Touches in box per 90",
        "Successful defensive actions per 90",
        "Defensive duels per 90", "Defensive duels won, %",
    ],
    "Fullback": [
        "Minutes played",
        "Successful defensive actions per 90",
        "Defensive duels per 90", "Defensive duels won, %",
        "Aerial duels per 90", "Aerial duels won, %",
        "Crosses per 90", "Accurate crosses, %",
        "Progressive runs per 90", "Accelerations per 90",
        "Passes per 90", "Accurate passes, %",
        "Passes to final third per 90",
    ],
    "Defender": [
        "Minutes played",
        "Successful defensive actions per 90",
        "Defensive duels per 90", "Defensive duels won, %",
        "Aerial duels per 90", "Aerial duels won, %",
        "PAdj Interceptions", "Shots blocked per 90", "PAdj Sliding tackles",
        "Passes per 90", "Accurate passes, %",
        "Progressive passes per 90",
        "Long passes per 90",
    ],
    "Goalkeeper": [
        "Minutes played",
        "Conceded goals per 90", "Save rate, %",
        "xG against per 90", "Prevented goals per 90",
        "Shots against per 90", "Clean sheets",
        "Exits per 90",
        "Back passes received as GK per 90",
        "Passes per 90", "Accurate passes, %",
        "Long passes per 90", "Accurate long passes, %",
    ],
}

LOWER_IS_BETTER: set = {
    "Conceded goals per 90", "xG against per 90", "Shots against per 90",
    "Yellow cards per 90", "Red cards per 90", "Fouls per 90",
    "Conceded goals", "xG against",
    "Team GK conceded per 90",
}

# Longer tokens (LAMF/RAMF) before AMF so substring search does not treat wide-AMF as central AMF.
BASE_TOKEN_RE = re.compile(
    r"(CF|ST|STRIKER|FW|LWB|RWB|LWF|RWF|LAMF|RAMF|LW|RW|AMF|WF|CMF|DMF|LB|RB|WB|CB|DF|GK)"
)

TOKEN_TO_ROLES: Dict[str, set] = {}
for _role, _toks in ROLE_TO_TOKENS.items():
    for _t in _toks:
        TOKEN_TO_ROLES.setdefault(_t, set()).add(_role)

BG_WHITE = "#d9d9d9"
GREY70 = "#d9d9d9"
GREY_LIGHT = "#bdbdbd"
ORANGE_LIGHT = "#ffbd59"
COLORS = ["#FF5A5F", "#007A87", "#C3770D"]

MIDFIELDER_AREAS = [
    "Minutes played",
    "Goals per 90", "Assists per 90", "xG per 90", "xA per 90",
    "Duels per 90", "Duels won, %", "Aerial duels won, %",
    "Interceptions per 90", "Successful defensive actions per 90",
    "Passes per 90", "Accurate passes, %", "Long passes per 90",
    "Progressive passes per 90", "Progressive runs per 90",
    "Key passes per 90", "Passes to final third per 90",
    "Accelerations per 90", "Dribbles per 90", "Successful dribbles, %",
    "Shots per 90",
]

METRIC_COLS = [
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
    """Exclude z-score columns (``*_z``) from Streamlit metric dropdowns."""
    return not str(name).endswith("_z")


VALID_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg")

# Plot styling constants
PLOT_STYLE_RC = {
    "axes.facecolor": "#d9d9d9",
    "figure.facecolor": "#d9d9d9",
    "axes.grid": False,
    "axes.labelsize": 8,
    "axes.edgecolor": "#d9d9d9",
    "axes.labelcolor": "#000",
    "ytick.labelsize": 8,
    "xtick.labelsize": 8,
    "ytick.labelcolor": "#000",
    "xtick.labelcolor": "#000",
}
PLOT_DPI = 220

# ---------------------------------------------------------------------------
# Metric display-label helpers
# ---------------------------------------------------------------------------

METRIC_DISPLAY_LABELS: Dict[str, str] = {
    "assistance_index": "Assistance Index",
    "finishing_index": "Finishing Index",
    "distribution_index": "Distribution Index",
    "take_ons_index": "Take Ons Index",
    "aerial_play_index": "Aerial Play Index",
    "ground_defense_index": "Ground Defense Index",
    "xG": "xG",
    "xA": "xA",
    "xG per 90": "xG /90",
    "NPxG": "NPxG",
    "NPxG per 90": "NPxG /90",
    "xA per 90": "xA /90",
    "xG against": "xG Against",
    "xG against per 90": "xG Against /90",
    "xG per shot per 90": "xG per Shot /90",
    "PAdj Interceptions": "PAdj Interceptions",
    "PAdj Sliding tackles": "PAdj Sliding Tackles",
    "LinkUp Play Quality": "Link-Up Play Quality",
    "Dribling Quality": "Dribbling Quality",
}

_TEAM_IMPACT_SUFFIX = " - % Team Impact"
_TM_PCT_SUFFIX = "_tm_pct"
_LG_PCT_SUFFIX = "_lg_pct"


def format_metric_label(col: str) -> str:
    """Return a user-friendly display label for a metric column name."""
    if col in METRIC_DISPLAY_LABELS:
        return METRIC_DISPLAY_LABELS[col]

    if col.endswith(_TEAM_IMPACT_SUFFIX):
        base = col[: -len(_TEAM_IMPACT_SUFFIX)]
        return f"{format_metric_label(base)} (Team %)"

    if col.endswith(_TM_PCT_SUFFIX):
        base = col[: -len(_TM_PCT_SUFFIX)]
        return f"{format_metric_label(base)} (Team Pctl)"

    if col.endswith(_LG_PCT_SUFFIX):
        base = col[: -len(_LG_PCT_SUFFIX)]
        return f"{format_metric_label(base)} (League Pctl)"

    if "_" in col and " " not in col:
        return col.replace("_", " ").title()

    return col
