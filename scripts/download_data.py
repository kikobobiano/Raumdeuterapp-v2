"""
Download Wyscout player search results for each league in ALLOWED_LEAGUE_WYSCOUT_IDS.

Requires environment variables:
  WYSCOUT_SEARCH_TOKEN   — API token (query param `token`)
  WYSCOUT_GROUP_ID       — e.g. 1432001
  WYSCOUT_SUBGROUP_ID    — e.g. 479792

Outputs CSV files under <repo>/data/players/wyscout/, one per league/season.
Waits ~2 seconds after every HTTP request to limit rate.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

from repo_paths import repo_root

BASE_URL = "https://searchapi.wyscout.com/api/v1/search/results.json"
PAGE_SIZE = 500
REQUEST_DELAY_SEC = 0.1

# Wyscout search: only players with at least this many minutes in the selected timeframe.
MINUTES_ON_FIELD_MIN = 0

# Decoded `columns` from the reference curl (same field list).
COLUMNS = (
    "name,id,image,current_team_logo,current_team_color,birth_country_name,"
    "passport_country_names,current_team_name,market_value,total_matches,"
    "minutes_on_field,last_club_name,positions,age,contract_expires,goals,"
    "xg_shot,assists,xg_assist,duels_avg,duels_won,foot,height,weight,on_loan,"
    "successful_defensive_actions_avg,defensive_duels_avg,defensive_duels_won,"
    "aerial_duels_avg,aerial_duels_won,tackle_avg,possession_adjusted_tackle,"
    "shot_block_avg,interceptions_avg,possession_adjusted_interceptions,"
    "fouls_avg,yellow_cards,yellow_cards_avg,red_cards,red_cards_avg,"
    "successful_attacking_actions_avg,goals_avg,non_penalty_goal,"
    "non_penalty_goal_avg,xg_shot_avg,head_goals,head_goals_avg,shots,shots_avg,"
    "shots_on_target_percent,goal_conversion_percent,assists_avg,crosses_avg,"
    "accurate_crosses_percent,cross_from_left_avg,"
    "successful_cross_from_left_percent,cross_from_right_avg,"
    "successful_cross_from_right_percent,cross_to_goalie_box_avg,dribbles_avg,"
    "successful_dribbles_percent,offensive_duels_avg,offensive_duels_won,"
    "touch_in_box_avg,progressive_run_avg,accelerations_avg,received_pass_avg,"
    "received_long_pass_avg,foul_suffered_avg,passes_avg,accurate_passes_percent,"
    "forward_passes_avg,successful_forward_passes_percent,back_passes_avg,"
    "successful_back_passes_percent,vertical_passes_avg,"
    "successful_vertical_passes_percent,short_medium_pass_avg,"
    "accurate_short_medium_pass_percent,long_passes_avg,"
    "successful_long_passes_percent,average_pass_length,average_long_pass_length,"
    "xg_assist_avg,shot_assists_avg,pre_assist_avg,pre_pre_assist_avg,"
    "smart_passes_avg,accurate_smart_passes_percent,key_passes_avg,"
    "passes_to_final_third_avg,accurate_passes_to_final_third_percent,"
    "pass_to_penalty_area_avg,accurate_pass_to_penalty_area_percent,"
    "through_passes_avg,successful_through_passes_percent,"
    "deep_completed_pass_avg,deep_completed_cross_avg,progressive_pass_avg,"
    "successful_progressive_pass_percent,conceded_goals,conceded_goals_avg,"
    "shots_against,shots_against_avg,clean_sheets,save_percent,xg_save,"
    "xg_save_avg,prevented_goals,prevented_goals_avg,back_pass_to_gk_avg,"
    "goalkeeper_exits_avg,gk_aerial_duels_avg,free_kicks_taken_avg,"
    "direct_free_kicks_taken_avg,direct_free_kicks_on_target_percent,"
    "corners_taken_avg,penalties_taken,penalties_conversion_percent"
)

REQUEST_HEADERS = {
    "accept": "*/*",
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "origin": "https://wyscout-apps.hudl.com",
    "referer": "https://wyscout-apps.hudl.com/",
    "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "cross-site",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
    ),
}

# Wyscout season `name` for each season_id, covering all historical seasons of the
# competitions listed in ALLOWED_LEAGUE_WYSCOUT_IDS (extracted from the Wyscout
# competitions export). Add new entries here when new seasons are unlocked.
SEASON_WYSCOUT_NAME: dict[int, str] = {
    # Eredivisie (competition_id=1)
    -7017: "2025/2026", -5352: "2024/2025", -4349: "2023/2024", -3466: "2022/2023",
    -2843: "2021/2022", -1589: "2020/2021", -1194: "2019/2020", -952: "2018/2019",
    # La Liga (7)
    -7000: "2025/2026", -5315: "2024/2025", -4353: "2023/2024", -3465: "2022/2023",
    -2867: "2021/2022", -1608: "2020/2021", -1169: "2019/2020", -982: "2018/2019",
    # Premier League (8)
    -6963: "2025/2026", -5249: "2024/2025", -4330: "2023/2024", -3436: "2022/2023",
    -2816: "2021/2022", -2151: "2020/2021", -1068: "2019/2020", -959: "2018/2019",
    # Bundesliga (9)
    -7002: "2025/2026", -5311: "2024/2025", -4315: "2023/2024", -3423: "2022/2023",
    -2852: "2021/2022", -1606: "2020/2021", -1162: "2019/2020", -983: "2018/2019",
    # 2. Bundesliga (11)
    -6992: "2025/2026", -5317: "2024/2025", -4313: "2023/2024", -3417: "2022/2023",
    -2853: "2021/2022", -1607: "2020/2021", -1122: "2019/2020", -909: "2018/2019",
    # Segunda División / La Liga 2 (12)
    -7001: "2025/2026", -5351: "2024/2025", -4354: "2023/2024", -3467: "2022/2023",
    -2868: "2021/2022", -1609: "2020/2021", -1170: "2019/2020", -979: "2018/2019",
    # Serie A (13)
    -6964: "2025/2026", -5314: "2024/2025", -4335: "2023/2024", -3501: "2022/2023",
    -2869: "2021/2022", -1694: "2020/2021", -1185: "2019/2020", -723: "2018/2019",
    # Serie B (14)
    -7112: "2025/2026", -5425: "2024/2025", -4387: "2023/2024", -3541: "2022/2023",
    -2916: "2021/2022", -1727: "2020/2021", -1186: "2019/2020", -999: "2018/2019",
    # Ligue 1 (16)
    -7024: "2025/2026", -5313: "2024/2025", -5312: "2023/2024", -3463: "2022/2023",
    -2715: "2021/2022", -1584: "2020/2021", -1075: "2019/2020", -928: "2018/2019",
    # Ligue 2 (17)
    -7100: "2025/2026", -5348: "2024/2025", -4428: "2023/2024", -3439: "2022/2023",
    -2800: "2021/2022", -1576: "2020/2021", -1074: "2019/2020", -907: "2018/2019",
    # Süper Lig (19)
    -7046: "2025/2026", -5440: "2024/2025", -4401: "2023/2024", -3510: "2022/2023",
    -2871: "2021/2022", -1734: "2020/2021", -1176: "2019/2020", -958: "2018/2019",
    # Veikkausliiga (22)
    -7782: "2026", -6805: "2025", -4977: "2024", -4073: "2023",
    -2484: "2022", -3185: "2021", -2663: "2020",
    # Belgian Pro League (24)
    -6958: "2025/2026", -5291: "2024/2025", -4323: "2023/2024", -3390: "2022/2023",
    -2730: "2021/2022", -1591: "2020/2021", -1094: "2019/2020", -910: "2018/2019",
    # Brasileirão / Serie A Brazil (26)
    -7592: "2026", -6772: "2025", -5085: "2024", -4097: "2023",
    -3306: "2022", -2509: "2021", -2008: "2020", -818: "2019", -817: "2018",
    # Swiss Super League (27)
    -6962: "2025/2026", -6049: "2024/2025", -4298: "2023/2024", -3426: "2022/2023",
    -2896: "2021/2022", -1573: "2020/2021", -1084: "2019/2020", -901: "2018/2019",
    # Allsvenskan (28)
    -7780: "2026", -6674: "2025", -4832: "2024", -4077: "2023",
    -3150: "2022", -2483: "2021", -2034: "2020", -701: "2019", 15014: "2018",
    # Eliteserien (29)
    -7743: "2026", -6658: "2025", -4831: "2024", -4074: "2023",
    -3145: "2022", -2482: "2021", -2061: "2020", -704: "2019", -703: "2018",
    # Superliga Denmark (30)
    -6952: "2025/2026", -5259: "2024/2025", -4286: "2023/2024", -3380: "2022/2023",
    -2824: "2021/2022", -1553: "2020/2021", -1063: "2019/2020", -880: "2018/2019",
    # MLS (33)
    -7702: "2026", -5919: "2025", -4859: "2024", -3994: "2023",
    -3276: "2022", -2405: "2021", -1985: "2020", -728: "2019", -727: "2018",
    # Scottish Premiership (43)
    -6974: "2025/2026", -5343: "2024/2025", -4341: "2023/2024", -3446: "2022/2023",
    -2717: "2021/2022", -1693: "2020/2021", -1111: "2019/2020", -842: "2018/2019",
    # Austrian Bundesliga (49)
    -7007: "2025/2026", -5321: "2024/2025", -4321: "2023/2024", -3403: "2022/2023",
    -2864: "2021/2022", -1578: "2020/2021", -1093: "2019/2020", -896: "2018/2019",
    # 1. HNL / Superleague Croatia (61)
    -6986: "2025/2026", -5279: "2024/2025", -4296: "2023/2024", -3398: "2022/2023",
    -2766: "2021/2022", -1571: "2020/2021", -1082: "2019/2020", -882: "2018/2019",
    # Primeira Liga (63)
    -7135: "2025/2026", -5377: "2024/2025", -4393: "2023/2024", -3487: "2022/2023",
    -2875: "2021/2022", -1711: "2020/2021", -1175: "2019/2020", -939: "2018/2019",
    # Championship (70)
    -6985: "2025/2026", -5292: "2024/2025", -4328: "2023/2024", -3437: "2022/2023",
    -2823: "2021/2022", -1674: "2020/2021", -1069: "2019/2020", -929: "2018/2019",
    # Liga Profesional Argentina (87)
    -7618: "2026", -6718: "2025", -4829: "2024", -4001: "2023",
    -3167: "2022", -2982: "2021", -1657: "2020/2021", -1205: "2019/2020", -993: "2018/2019",
    # Primera División Chile (90)
    -7659: "2026", -5970: "2025", -4870: "2024", -3982: "2023",
    -3263: "2022", -2373: "2021", -1901: "2020", -650: "2019", -649: "2018",
    # Portuguese Segunda Liga (100)
    -7051: "2025/2026", -6095: "2024/2025", -4394: "2023/2024", -3488: "2022/2023",
    -2873: "2021/2022", -1619: "2020/2021", -1179: "2019/2020",
    # Campeonato de Portugal (101)
    -7120: "2025/2026",
    # Greek Super League (107)
    -7201: "2025/2026", -5446: "2024/2025", -4457: "2023/2024", -3603: "2022/2023",
    -2874: "2021/2022", -1632: "2020/2021", -1251: "2019/2020", -997: "2018/2019",
    # J1 League (109)
    -5916: "2025", -4919: "2024", -3996: "2023", -3142: "2022",
    -2442: "2021", -2234: "2020", -686: "2019", -685: "2018",
    # Ekstraklasa (119)
    -6168: "2025/2026", -5258: "2024/2025", -4306: "2023/2024", -3429: "2022/2023",
    -1556: "2021/2022", -2794: "2020/2021", -1066: "2019/2020", -879: "2018/2019",
    # Premier League Russia (121)
    -6959: "2025/2026", -5333: "2024/2025", -4311: "2023/2024", -3396: "2022/2023",
    -2750: "2021/2022", -1554: "2020/2021", -1096: "2019/2020", -885: "2018/2019",
    # VBET League / Ukrainian Premier League (125)
    -7012: "2025/2026", -5338: "2024/2025", -4566: "2023/2024", -3448: "2022/2023",
    -2795: "2021/2022", -1585: "2020/2021", -1072: "2019/2020", -888: "2018/2019",
    # Liga de Expansión MX (156)
    -7040: "2025/2026", -5364: "2024/2025", -4273: "2023/2024", -3492: "2022/2023",
    -2787: "2021/2022", -1592: "2020/2021", -1086: "2019/2020", -895: "2018/2019",
    # Saudi Pro League (216)
    -7235: "2025/2026", -5406: "2024/2025", -4534: "2023/2024", -3557: "2022/2023",
    -2965: "2021/2022", -1781: "2020/2021", -1780: "2019/2020", -750: "2018/2019",
    # Portuguese Liga 3 (-599)
    -7123: "2025/2026", -5431: "2024/2025", -4488: "2023/2024", -3563: "2022/2023",
    -3562: "2021/2022",
}

# IDs from `arr` for leagues in transformation/new_performance_index.py ALLOWED_LEAGUES.
# Each entry lists every season_id we want to scrape for that competition. Sorted
# newest → oldest; main() iterates league × season_id.
ALLOWED_LEAGUE_WYSCOUT_IDS = [
    {"name": "Premier League", "competition_id": 8, "season_ids": [-6963]},  # older: -5249, -4330, -3436, -2816, -2151, -1068, -959
    {"name": "Serie A", "competition_id": 13, "season_ids": [-6964]},  # older: -5314, -4335, -3501, -2869, -1694, -1185, -723
    {"name": "La Liga", "competition_id": 7, "season_ids": [-7000]},  # older: -5315, -4353, -3465, -2867, -1608, -1169, -982
    {"name": "Bundesliga", "competition_id": 9, "season_ids": [-7002]},  # older: -5311, -4315, -3423, -2852, -1606, -1162, -983
    {"name": "Ligue 1", "competition_id": 16, "season_ids": [-7024]},  # older: -5313, -5312, -3463, -2715, -1584, -1075, -928
    {"name": "Championship", "competition_id": 70, "season_ids": [-6985]},  # older: -5292, -4328, -3437, -2823, -1674, -1069, -929
    {"name": "Belgian Pro League", "competition_id": 24, "season_ids": [-6958]},  # older: -5291, -4323, -3390, -2730, -1591, -1094, -910
    {"name": "Primeira Liga", "competition_id": 63, "season_ids": [-7135]},  # older: -5377, -4393, -3487, -2875, -1711, -1175, -939
    {"name": "Brasileirão", "competition_id": 26, "season_ids": [-7592]},  # older: -6772, -5085, -4097, -3306, -2509, -2008, -818, -817
    {"name": "Eredivisie", "competition_id": 1, "season_ids": [-7017]},  # older: -5352, -4349, -3466, -2843, -1589, -1194, -952
    {"name": "Argentina LPF", "competition_id": 87, "season_ids": [-7618]},  # older: -6718, -4829, -4001, -3167, -2982, -1657, -1205, -993
    {"name": "MLS", "competition_id": 33, "season_ids": [-7702]},  # older: -5919, -4859, -3994, -3276, -2405, -1985, -728, -727
    {"name": "Liga de Expansión MX", "competition_id": 156, "season_ids": [-7040]},  # older: -5364, -4273, -3492, -2787, -1592, -1086, -895
    {"name": "1. HNL", "competition_id": 61, "season_ids": [-6986]},  # older: -5279, -4296, -3398, -2766, -1571, -1082, -882
    {"name": "J1", "competition_id": 109, "season_ids": [-5916]},  # older: -4919, -3996, -3142, -2442, -2234, -686, -685
    {"name": "Ekstraklasa", "competition_id": 119, "season_ids": [-6168]},  # older: -5258, -4306, -3429, -1556, -2794, -1066, -879
    {"name": "Superliga", "competition_id": 30, "season_ids": [-6952]},  # older: -5259, -4286, -3380, -2824, -1553, -1063, -880
    {"name": "Serie B", "competition_id": 14, "season_ids": [-7112]},  # older: -5425, -4387, -3541, -2916, -1727, -1186, -999
    {"name": "Allsvenskan", "competition_id": 28, "season_ids": [-7780]},  # older: -6674, -4832, -4077, -3150, -2483, -2034, -701, 15014
    {"name": "Süper Lig", "competition_id": 19, "season_ids": [-7046]},  # older: -5440, -4401, -3510, -2871, -1734, -1176, -958
    {"name": "La Liga 2", "competition_id": 12, "season_ids": [-7001]},  # older: -5351, -4354, -3467, -2868, -1609, -1170, -979
    {"name": "2. Bundesliga", "competition_id": 11, "season_ids": [-6992]},  # older: -5317, -4313, -3417, -2853, -1607, -1122, -909
    {"name": "Russian Premier League", "competition_id": 121, "season_ids": [-6959]},  # older: -5333, -4311, -3396, -2750, -1554, -1096, -885
    {"name": "Swiss Super League", "competition_id": 27, "season_ids": [-6962]},  # older: -6049, -4298, -3426, -2896, -1573, -1084, -901
    {"name": "Austrian Bundled esliga", "competition_id": 49, "season_ids": [-7007]},  # older: -5321, -4321, -3403, -2864, -1578, -1093, -896
    {"name": "Eliteserien", "competition_id": 29, "season_ids": [-7743]},  # older: -6658, -4831, -4074, -3145, -2482, -2061, -704, -703
    {"name": "Greek Super League", "competition_id": 107, "season_ids": [-7201]},  # older: -5446, -4457, -3603, -2874, -1632, -1251, -997
    {"name": "Ukrainian Premier League", "competition_id": 125, "season_ids": [-7012]},  # older: -5338, -4566, -3448, -2795, -1585, -1072, -888
    {"name": "Scottish Premiership", "competition_id": 43, "season_ids": [-6974]},  # older: -5343, -4341, -3446, -2717, -1693, -1111, -842
    {"name": "Saudi Pro League", "competition_id": 216, "season_ids": [-7235]},  # older: -5406, -4534, -3557, -2965, -1781, -1780, -750
    {"name": "Ligue 2", "competition_id": 17, "season_ids": [-7100]},  # older: -5348, -4428, -3439, -2800, -1576, -1074, -907
    {"name": "Portuguese Segunda Liga", "competition_id": 100, "season_ids": [-7051]},  # older: -6095, -4394, -3488, -2873, -1619, -1179
    {"name": "Chilean Primera Division", "competition_id": 90, "season_ids": [-7659]},  # older: -5970, -4870, -3982, -3263, -2373, -1901, -650, -649
    {"name": "Veikkausliiga", "competition_id": 22, "season_ids": [-7782]},  # older: -6805, -4977, -4073, -2484, -3185, -2663
    {"name": "Portuguese Liga 3", "competition_id": -599, "season_ids": [-7123]},  # older: -5431, -4488, -3563, -3562
    {"name": "Campeonato de Portugal", "competition_id": 101, "season_ids": [-7120]},
]

# Wyscout API field -> human-readable column (order matches export convention).
# The API list repeats "Aerial duels per 90" for outfield vs GK; GK uses a distinct header.
WYSCOUT_API_TO_DISPLAY: tuple[tuple[str, str], ...] = (
    ("name", "Player"),
    ("full_name", "Full name"),
    ("id", "Wyscout id"),
    ("image", "Image"),
    ("current_team_name", "Team"),
    ("last_club_name", "Team within selected timeframe"),
    ("current_team_logo", "Team logo"),
    ("domestic_competition_name", "Competition"),
    ("positions", "Position"),
    ("primary_position", "Primary position"),
    ("primary_position_percent", "Primary position, %"),
    ("secondary_position", "Secondary position"),
    ("secondary_position_percent", "Secondary position, %"),
    ("third_position", "Third position"),
    ("third_position_percent", "Third position, %"),
    ("age", "Age"),
    ("birth_date", "Birthday"),
    ("market_value", "Market value"),
    ("contract_expires", "Contract expires"),
    ("total_matches", "Matches played"),
    ("minutes_on_field", "Minutes played"),
    ("goals", "Goals"),
    ("xg_shot", "xG"),
    ("assists", "Assists"),
    ("xg_assist", "xA"),
    ("duels_avg", "Duels per 90"),
    ("duels_won", "Duels won, %"),
    ("birth_country_name", "Birth country"),
    ("passport_country_names", "Passport country"),
    ("foot", "Foot"),
    ("height", "Height"),
    ("weight", "Weight"),
    ("on_loan", "On loan"),
    ("successful_defensive_actions_avg", "Successful defensive actions per 90"),
    ("defensive_duels_avg", "Defensive duels per 90"),
    ("defensive_duels_won", "Defensive duels won, %"),
    ("aerial_duels_avg", "Aerial duels per 90"),
    ("aerial_duels_won", "Aerial duels won, %"),
    ("tackle_avg", "Sliding tackles per 90"),
    ("possession_adjusted_tackle", "PAdj Sliding tackles"),
    ("shot_block_avg", "Shots blocked per 90"),
    ("interceptions_avg", "Interceptions per 90"),
    ("possession_adjusted_interceptions", "PAdj Interceptions"),
    ("fouls_avg", "Fouls per 90"),
    ("yellow_cards", "Yellow cards"),
    ("yellow_cards_avg", "Yellow cards per 90"),
    ("red_cards", "Red cards"),
    ("red_cards_avg", "Red cards per 90"),
    ("successful_attacking_actions_avg", "Successful attacking actions per 90"),
    ("goals_avg", "Goals per 90"),
    ("non_penalty_goal", "Non-penalty goals"),
    ("non_penalty_goal_avg", "Non-penalty goals per 90"),
    ("xg_shot_avg", "xG per 90"),
    ("head_goals", "Head goals"),
    ("head_goals_avg", "Head goals per 90"),
    ("shots", "Shots"),
    ("shots_avg", "Shots per 90"),
    ("shots_on_target_percent", "Shots on target, %"),
    ("goal_conversion_percent", "Goal conversion, %"),
    ("assists_avg", "Assists per 90"),
    ("crosses_avg", "Crosses per 90"),
    ("accurate_crosses_percent", "Accurate crosses, %"),
    ("cross_from_left_avg", "Crosses from left flank per 90"),
    ("successful_cross_from_left_percent", "Accurate crosses from left flank, %"),
    ("cross_from_right_avg", "Crosses from right flank per 90"),
    ("successful_cross_from_right_percent", "Accurate crosses from right flank, %"),
    ("cross_to_goalie_box_avg", "Crosses to goalie box per 90"),
    ("dribbles_avg", "Dribbles per 90"),
    ("successful_dribbles_percent", "Successful dribbles, %"),
    ("offensive_duels_avg", "Offensive duels per 90"),
    ("offensive_duels_won", "Offensive duels won, %"),
    ("touch_in_box_avg", "Touches in box per 90"),
    ("progressive_run_avg", "Progressive runs per 90"),
    ("accelerations_avg", "Accelerations per 90"),
    ("received_pass_avg", "Received passes per 90"),
    ("received_long_pass_avg", "Received long passes per 90"),
    ("foul_suffered_avg", "Fouls suffered per 90"),
    ("passes_avg", "Passes per 90"),
    ("accurate_passes_percent", "Accurate passes, %"),
    ("forward_passes_avg", "Forward passes per 90"),
    ("successful_forward_passes_percent", "Accurate forward passes, %"),
    ("back_passes_avg", "Back passes per 90"),
    ("successful_back_passes_percent", "Accurate back passes, %"),
    ("short_medium_pass_avg", "Short / medium passes per 90"),
    ("accurate_short_medium_pass_percent", "Accurate short / medium passes, %"),
    ("long_passes_avg", "Long passes per 90"),
    ("successful_long_passes_percent", "Accurate long passes, %"),
    ("average_pass_length", "Average pass length, m"),
    ("average_long_pass_length", "Average long pass length, m"),
    ("xg_assist_avg", "xA per 90"),
    ("shot_assists_avg", "Shot assists per 90"),
    ("pre_assist_avg", "Second assists per 90"),
    ("pre_pre_assist_avg", "Third assists per 90"),
    ("smart_passes_avg", "Smart passes per 90"),
    ("accurate_smart_passes_percent", "Accurate smart passes, %"),
    ("key_passes_avg", "Key passes per 90"),
    ("passes_to_final_third_avg", "Passes to final third per 90"),
    ("accurate_passes_to_final_third_percent", "Accurate passes to final third, %"),
    ("pass_to_penalty_area_avg", "Passes to penalty area per 90"),
    ("accurate_pass_to_penalty_area_percent", "Accurate passes to penalty area, %"),
    ("through_passes_avg", "Through passes per 90"),
    ("successful_through_passes_percent", "Accurate through passes, %"),
    ("deep_completed_pass_avg", "Deep completions per 90"),
    ("deep_completed_cross_avg", "Deep completed crosses per 90"),
    ("progressive_pass_avg", "Progressive passes per 90"),
    ("successful_progressive_pass_percent", "Accurate progressive passes, %"),
    ("successful_vertical_passes_percent", "Accurate vertical passes, %"),
    ("vertical_passes_avg", "Vertical passes per 90"),
    ("conceded_goals", "Conceded goals"),
    ("conceded_goals_avg", "Conceded goals per 90"),
    ("shots_against", "Shots against"),
    ("shots_against_avg", "Shots against per 90"),
    ("clean_sheets", "Clean sheets"),
    ("save_percent", "Save rate, %"),
    ("xg_save", "xG against"),
    ("xg_save_avg", "xG against per 90"),
    ("prevented_goals", "Prevented goals"),
    ("prevented_goals_avg", "Prevented goals per 90"),
    ("back_pass_to_gk_avg", "Back passes received as GK per 90"),
    ("goalkeeper_exits_avg", "Exits per 90"),
    ("gk_aerial_duels_avg", "Aerial duels per 90 (GK)"),
    ("free_kicks_taken_avg", "Free kicks per 90"),
    ("direct_free_kicks_taken_avg", "Direct free kicks per 90"),
    ("direct_free_kicks_on_target_percent", "Direct free kicks on target, %"),
    ("corners_taken_avg", "Corners per 90"),
    ("penalties_taken", "Penalties taken"),
    ("penalties_conversion_percent", "Penalty conversion, %"),
)


def wyscout_dataframe_to_display(df: pd.DataFrame) -> pd.DataFrame:
    """Rename and reorder columns; drops API-only fields not in the mapping."""
    pairs = [(src, disp) for src, disp in WYSCOUT_API_TO_DISPLAY if src in df.columns]
    if not pairs:
        return df
    out = df[[src for src, _ in pairs]].copy()
    out.columns = [disp for _, disp in pairs]
    return out


def display_column_headers() -> list[str]:
    return [disp for _, disp in WYSCOUT_API_TO_DISPLAY]


def season_slug(wyscout_season_name: str) -> str:
    """e.g. 2025/2026 -> 25-26; 2026 -> 2026."""
    m = re.match(r"^(\d{4})/(\d{4})$", wyscout_season_name.strip())
    if m:
        y1, y2 = int(m.group(1)), int(m.group(2))
        return f"{y1 % 100:02d}-{y2 % 100:02d}"
    return wyscout_season_name.strip()


def safe_filename_stem(league_name: str, season_part: str) -> str:
    raw = f"{league_name} {season_part}".strip()
    for ch in '\\/:*?"<>|':
        raw = raw.replace(ch, "-")
    raw = raw.replace("\n", " ").strip()
    if not raw:
        raw = "export"
    return raw


def extract_result_rows(payload: object) -> list[dict]:
    """Best-effort parse of Wyscout search JSON into a list of player dicts."""
    if isinstance(payload, list):
        if payload and isinstance(payload[0], dict):
            return payload
        return []

    if not isinstance(payload, dict):
        return []

    paths = (
        ("results",),
        ("data", "results"),
        ("search", "results"),
        ("data", "records"),
        ("records",),
        ("hits",),
    )
    for path in paths:
        cur: object = payload
        ok = True
        for key in path:
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:
                ok = False
                break
        if ok and isinstance(cur, list) and (not cur or isinstance(cur[0], dict)):
            return cur

    for v in payload.values():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            sample = v[0]
            if "id" in sample and (
                "name" in sample or "market_value" in sample or "current_team_name" in sample
            ):
                return v
    return []


def build_initial_search_url(
    *,
    competition_id: int,
    season_id: int,
    token: str,
    group_id: str,
    subgroup_id: str,
) -> str:
    """First-page URL. Subsequent pages use ``meta.next`` from the response."""
    params = {
        "search[women_mode]": "false",
        "search[time_frame]": str(season_id),
        "search[competition]": str(competition_id),
        "search[minutes_on_field][min]": str(MINUTES_ON_FIELD_MIN),
        "search[minutes_on_field][max]": 7578,
        "search[youth_stats]": "false",
        "count": str(PAGE_SIZE),
        "sort": "market_value desc",
        "language": "pt",
        "columns": COLUMNS,
        "token": token,
        "groupId": group_id,
        "subgroupId": subgroup_id,
    }
    return f"{BASE_URL}?{urllib.parse.urlencode(params)}"


def http_get_json(url: str) -> object:
    req = urllib.request.Request(url, headers=REQUEST_HEADERS, method="GET")
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = resp.read().decode("utf-8")
    return json.loads(body)


def _meta_next_url(payload: object) -> str | None:
    """Return ``meta.next`` URL when more pages remain, else ``None``.

    Wyscout always emits a ``next`` link (it loops back to page 0), so guard
    with ``page_current + 1 < page_count`` to detect the real end.
    """
    if not isinstance(payload, dict):
        return None
    meta = payload.get("meta")
    if not isinstance(meta, dict):
        return None
    nxt = meta.get("next")
    if not isinstance(nxt, str) or not nxt:
        return None
    page_current = meta.get("page_current")
    page_count = meta.get("page_count")
    if isinstance(page_current, int) and isinstance(page_count, int):
        if page_current + 1 >= page_count:
            return None
    return nxt


_MAX_PAGE_RETRIES = 5
_RETRY_DELAY_SEC = 6


def fetch_all_players(
    *,
    competition_id: int,
    season_id: int,
    token: str,
    group_id: str,
    subgroup_id: str,
) -> list[dict]:
    """Walk Wyscout pagination via ``meta.next``. Page size fixed at PAGE_SIZE.

    Retries pages with duplicate (id, current_team_name) keys — the API can
    return stale cached results from a backend. cache-control: no-cache headers
    plus a delay between retries force a fresh backend response.
    If dups persist after _MAX_PAGE_RETRIES, skips them and moves on.
    """
    rows: list[dict] = []
    seen_keys: set = set()
    url: str | None = build_initial_search_url(
        competition_id=competition_id,
        season_id=season_id,
        token=token,
        group_id=group_id,
        subgroup_id=subgroup_id,
    )
    page_idx = 0
    while url:
        for attempt in range(_MAX_PAGE_RETRIES):
            try:
                payload = http_get_json(url)
            except urllib.error.HTTPError as e:
                raise RuntimeError(
                    f"HTTP {e.code} for competition={competition_id} season={season_id} page={page_idx}"
                ) from e

            batch = extract_result_rows(payload)
            if not batch and page_idx == 0 and payload is not None:
                hint = ""
                if isinstance(payload, dict):
                    hint = f" top-level keys: {list(payload.keys())[:25]}"
                print(f"  warning: could not find player rows in JSON; adjust extract_result_rows if needed.{hint}")

            dups = [(r.get("id"), r.get("current_team_name")) for r in batch if (r.get("id"), r.get("current_team_name")) in seen_keys]
            if not dups:
                break
            if attempt < _MAX_PAGE_RETRIES - 1:
                print(f"  page {page_idx} attempt {attempt + 1}: {len(dups)} dup(s) — retrying in {_RETRY_DELAY_SEC}s...")
                time.sleep(_RETRY_DELAY_SEC)
        else:
            print(f"  page {page_idx}: {len(dups)} dup(s) after {_MAX_PAGE_RETRIES} retries — skipping dups.")

        new_rows = [r for r in batch if (r.get("id"), r.get("current_team_name")) not in seen_keys]
        skipped = len(batch) - len(new_rows)
        for r in new_rows:
            seen_keys.add((r.get("id"), r.get("current_team_name")))

        if isinstance(payload, dict):
            meta = payload.get("meta", {})
            if isinstance(meta, dict):
                print(
                    f"  page {page_idx}: got {len(new_rows)} new rows (+{skipped} dups) "
                    f"(total so far: {len(seen_keys)}) | "
                    f"page_current={meta.get('page_current')} "
                    f"page_count={meta.get('page_count')} "
                    f"next={'yes' if meta.get('next') else 'no'}"
                )

        rows.extend(new_rows)

        if not batch:
            break

        url = _meta_next_url(payload)
        page_idx += 1
        if url:
            time.sleep(REQUEST_DELAY_SEC)

    return rows


def write_league_csv(out_path: Path, rows: list[dict]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        pd.DataFrame(columns=display_column_headers()).to_csv(
            out_path, index=False, encoding="utf-8"
        )
        return
    df = pd.json_normalize(rows)
    if "birth_date" not in df.columns and "birth_day" in df.columns:
        df = df.rename(columns={"birth_day": "birth_date"})
    df = wyscout_dataframe_to_display(df)
    df.to_csv(out_path, index=False, encoding="utf-8")


def main() -> None:
    token = os.environ.get("WYSCOUT_SEARCH_TOKEN")
    group_id = os.environ.get("WYSCOUT_GROUP_ID")
    subgroup_id = os.environ.get("WYSCOUT_SUBGROUP_ID")
    if not token or not group_id or not subgroup_id:
        raise SystemExit(
            "Set WYSCOUT_SEARCH_TOKEN, WYSCOUT_GROUP_ID, and WYSCOUT_SUBGROUP_ID in the environment."
        )

    root = repo_root(Path(__file__))
    out_dir = root / "data" / "players" / "wyscout"

    for entry in ALLOWED_LEAGUE_WYSCOUT_IDS:
        league_name = entry["name"]
        cid = entry["competition_id"]
        season_ids = entry.get("season_ids")
        if not season_ids:
            # Back-compat: allow single ``season_id`` entries to keep working.
            single = entry.get("season_id")
            season_ids = [single] if single is not None else []
        if not season_ids:
            print(f"Skipping {league_name}: no season_ids configured")
            continue

        for sid in season_ids:
            wy_name = SEASON_WYSCOUT_NAME.get(sid)
            if not wy_name:
                raise KeyError(
                    f"No SEASON_WYSCOUT_NAME entry for season_id={sid} ({league_name})"
                )
            season_part = season_slug(wy_name)
            stem = safe_filename_stem(league_name, season_part)
            out_path = out_dir / f"{stem}.csv"

            print(
                f"Fetching {league_name} (competition={cid}, season={sid} / {wy_name}) "
                f"-> {out_path.name}"
            )
            rows = fetch_all_players(
                competition_id=cid,
                season_id=sid,
                token=token,
                group_id=group_id,
                subgroup_id=subgroup_id,
            )
            write_league_csv(out_path, rows)
            print(f"  wrote {len(rows)} rows")
            time.sleep(1)

    print("Done.")


if __name__ == "__main__":
    main()
