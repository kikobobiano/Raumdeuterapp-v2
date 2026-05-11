"""Hundreds of percentile-based style tags; pick the strongest few for the player profile."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import pandas as pd

from app.core.config import (
    GAME_AREAS_COLS,
    LEGEND_LABELS,
    LOWER_IS_BETTER,
    METRIC_COLS,
    PCT_GROUPS,
)

METRIC_TO_GAME_AREA: dict[str, str] = {
    col: LEGEND_LABELS[g] for col, g in zip(GAME_AREAS_COLS, PCT_GROUPS, strict=True)
}


def _infer_game_area(metric: str) -> str:
    s = metric.lower()
    if "touch" in s and "box" in s:
        return "Finishing"
    if "aerial" in s or "head goal" in s:
        return "Aerial Play"
    if "foul" in s and "suffered" in s:
        return "Take Ons"
    if any(
        k in s
        for k in (
            "cross",
            "corner",
            "shot assist",
            "second assist",
            "third assist",
            "deep completion",
            "smart pass",
            "through pass",
            "key pass",
        )
    ):
        return "Assistance"
    if any(
        k in s
        for k in (
            "dribble",
            "offensive duel",
            "acceleration",
            "progressive run",
            "successful attacking",
            "ball progression",
        )
    ):
        return "Take Ons"
    if any(
        k in s
        for k in (
            "goal",
            "shot",
            "xg",
            "penalty",
            "finishing",
            "conversion",
            "expected offensive",
            "offensive output",
        )
    ):
        return "Finishing"
    if any(
        k in s
        for k in (
            "defensive",
            "interception",
            "tackle",
            "shots blocked",
            "successful defensive",
            "foul",
            "card",
            "clean sheet",
            "save rate",
            "conceded",
            "prevented goal",
            "exit",
            "gk",
            "ball winning",
        )
    ):
        return "Ground Defense"
    if "pass" in s or "received" in s:
        return "Distribution"
    return "Distribution"


def game_area_for_trait_rule(rule: TraitRule) -> str:
    for metric, _, _ in rule.bounds:
        return METRIC_TO_GAME_AREA.get(metric, _infer_game_area(metric))
    return "Distribution"

# --- which raw columns feed automated tier rules ---------------------------------

_SKIP_EXACT = frozenset(
    {
        "Goals",
        "xG",
        "Assists",
        "xA",
        "Head goals",
        "Shots",
        "Yellow cards",
        "Red cards",
        "Conceded goals",
        "xG against",
        "Prevented goals",
        "Shots against",
        "Penalties taken",
        "Non-penalty goals",
    }
)


def _trait_metric_columns() -> list[str]:
    out: list[str] = []
    for m in METRIC_COLS:
        if m in _SKIP_EXACT:
            continue
        if "Team Impact" in m or "_index" in m or "Quality" in m:
            continue
        out.append(m)
    return out


TRAIT_METRICS: list[str] = _trait_metric_columns()

# Readable nouns for single-metric tiers (fallback: lowercased metric stem)
_STYLE_NOUN: dict[str, str] = {
    "Goals per 90": "goal threat",
    "Non-penalty goals per 90": "open-play finisher",
    "xG per 90": "chance generator",
    "Shots per 90": "shooting volume",
    "Shots on target, %": "shot precision",
    "Goal conversion, %": "clinical finisher",
    "Head goals per 90": "aerial goal threat",
    "Assists per 90": "assist provider",
    "xA per 90": "expected-assist engine",
    "Second assists per 90": "pre-assist linker",
    "Third assists per 90": "deep creator",
    "Shot assists per 90": "shot-assist hub",
    "Key passes per 90": "key passer",
    "Smart passes per 90": "risk-taking passer",
    "Through passes per 90": "through-ball threat",
    "Passes to penalty area per 90": "penalty-box passer",
    "Passes to final third per 90": "final-third progressor",
    "Accurate passes to final third, %": "final-third passer (accuracy)",
    "Accurate passes to penalty area, %": "box passer (accuracy)",
    "Accurate through passes, %": "through-ball precision",
    "Deep completions per 90": "deep completion threat",
    "Deep completed crosses per 90": "cutback/cross finisher",
    "Crosses per 90": "crossing volume",
    "Accurate crosses, %": "crossing accuracy",
    "Crosses from left flank per 90": "left-flank crosser",
    "Crosses from right flank per 90": "right-flank crosser",
    "Crosses to goalie box per 90": "dangerous crosser",
    "Dribbles per 90": "dribbler",
    "Successful dribbles, %": "1v1 technician",
    "Offensive duels per 90": "duel-seeker (attack)",
    "Offensive duels won, %": "offensive duel winner",
    "Touches in box per 90": "box presence",
    "Progressive runs per 90": "ball carrier",
    "Accelerations per 90": "acceleration threat",
    "Received passes per 90": "involvement hub",
    "Received long passes per 90": "long-ball outlet",
    "Fouls suffered per 90": "foul-drawer",
    "Passes per 90": "passing volume",
    "Accurate passes, %": "passing accuracy",
    "Forward passes per 90": "forward passer",
    "Accurate forward passes, %": "forward-pass precision",
    "Back passes per 90": "recycling passer",
    "Accurate back passes, %": "safe recycler",
    "Short / medium passes per 90": "short-game passer",
    "Accurate short / medium passes, %": "short-pass precision",
    "Long passes per 90": "long passer",
    "Accurate long passes, %": "long-ball precision",
    "Average pass length, m": "long-range passer (length)",
    "Average long pass length, m": "bomb passer",
    "Vertical passes per 90": "vertical passer",
    "Accurate vertical passes, %": "vertical-pass precision",
    "Progressive passes per 90": "progressive passer",
    "Accurate progressive passes, %": "progressive-pass precision",
    "Successful defensive actions per 90": "defensive-actions volume",
    "Defensive duels per 90": "defensive duel volume",
    "Defensive duels won, %": "defensive duel winner",
    "Aerial duels per 90": "aerial contest volume",
    "Aerial duels won, %": "aerial dominance",
    "Sliding tackles per 90": "slider",
    "PAdj Sliding tackles": "ball-winner (slide)",
    "Shots blocked per 90": "shot blocker",
    "Interceptions per 90": "interceptor",
    "PAdj Interceptions": "PAdj interceptor",
    "Duels per 90": "duel volume",
    "Duels won, %": "duel winner",
    "Fouls per 90": "fouling rate",
    "Yellow cards per 90": "card risk",
    "Red cards per 90": "send-off risk",
    "Successful attacking actions per 90": "attacking-actions volume",
    "Conceded goals per 90": "goals conceded rate",
    "Shots against per 90": "busy keeper (shots faced)",
    "Save rate, %": "shot-stopper",
    "xG against per 90": "xGA exposure",
    "Prevented goals per 90": "goals prevented",
    "Back passes received as GK per 90": "build-up GK involvement",
    "Exits per 90": "sweeper-keeper",
    "Free kicks per 90": "free-kick volume",
    "Direct free kicks per 90": "direct-FK shooter",
    "Direct free kicks on target, %": "direct-FK accuracy",
    "Penalty conversion, %": "penalty specialist",
    "Expected Offensive Output per 90": "expected offensive output",
    "Offensive Output per 90": "offensive output",
    "Ball Progression per 90": "ball progression",
    "Ball Winning Actions per 90": "ball-winning actions",
    "Touches in box per shot per 90": "box efficiency (touches/shot)",
    "xG per shot per 90": "shot quality (xG/shot)",
}


def _style_noun(metric: str) -> str:
    if metric in _STYLE_NOUN:
        return _STYLE_NOUN[metric]
    stem = metric.replace(" per 90", "").replace(", %", "").strip()
    if not stem:
        return metric.lower()
    return stem[0].lower() + stem[1:] if len(stem) > 1 else stem.lower()


_TIER_LOS = (92, 87, 81, 75, 68)
_TIER_NAMES = ("Elite", "Outstanding", "Strong", "Impactful", "Solid")


def _tier_label_fixed(lo: int, noun: str) -> str:
    for i, t in enumerate(_TIER_LOS):
        if lo == t:
            return f"{_TIER_NAMES[i]} {noun}"
    return f"Strong {noun}"


# Role buckets for combo gating
_R_FW = frozenset({"Forward"})
_R_W = frozenset({"Winger"})
_R_MF = frozenset({"Midfielder", "Attacking Midfielder"})
_R_FB = frozenset({"Fullback"})
_R_CB = frozenset({"Defender"})
_R_GK = frozenset({"Goalkeeper"})
_R_ATT = frozenset({"Forward", "Winger"})
_R_WFB = frozenset({"Winger", "Fullback"})
_R_OUT = frozenset({"Forward", "Winger", "Midfielder", "Attacking Midfielder", "Fullback"})


@dataclass(frozen=True)
class TraitRule:
    family: str
    label: str
    positive: bool
    priority: int
    bounds: tuple[tuple[str, float, float], ...]
    roles: frozenset[str] | None = None


def _combo(
    family: str,
    label: str,
    positive: bool,
    priority: int,
    specs: Sequence[tuple[str, float]],
    roles: frozenset[str] | None = None,
) -> TraitRule:
    bounds = tuple((m, lo, 100.0) for m, lo in specs)
    return TraitRule(family, label, positive, priority, bounds, roles)


def _neg_combo(
    family: str,
    label: str,
    priority: int,
    specs: Sequence[tuple[str, float]],
    roles: frozenset[str] | None = None,
) -> TraitRule:
    """Tag when *effective* percentile is low (bad discipline, etc.)."""
    bounds = tuple((m, 0.0, hi) for m, hi in specs)
    return TraitRule(family, label, False, priority, bounds, roles)


def _build_combo_rules() -> list[TraitRule]:
    r: list[TraitRule] = []

    # Dribbling & carry
    r += [
        _combo("c:dr_elite", "Elite dribbler", True, 118, (("Dribbles per 90", 88), ("Successful dribbles, %", 84))),
        _combo("c:dr_vol", "Volume dribbler", True, 108, (("Dribbles per 90", 91), ("Successful dribbles, %", 48))),
        _combo("c:dr_eff", "Efficient dribbler", True, 104, (("Dribbles per 90", 72), ("Successful dribbles, %", 88))),
        _combo("c:carry", "Line-breaking carrier", True, 112, (("Progressive runs per 90", 85), ("Accelerations per 90", 82))),
        _combo("c:carry2", "Direct runner", True, 102, (("Progressive runs per 90", 80), ("Touches in box per 90", 78)), _R_ATT | _R_WFB),
        _combo("c:cb1", "Ball-carrier Defender", True, 100, (("Progressive runs per 90", 85), ("Accelerations per 90", 80)), _R_CB),
        _combo("c:cb1", "Ball-carrier Midfielder", True, 100, (("Progressive runs per 90", 80), ("Accelerations per 90", 80)), _R_MF),
    ]

    # Shooting & finishing
    r += [
        _combo("c:fin1", "Ruthless finisher", True, 116, (("Goals per 90", 86), ("xG per 90", 78)), _R_ATT),
        _combo("c:fin2", "Shot monster", True, 106, (("Shots per 90", 88), ("Shots on target, %", 75)), _R_ATT),
        _combo("c:fin3", "Clinical in the box", True, 110, (("Goal conversion, %", 85), ("Touches in box per 90", 80)), _R_ATT),
        _combo("c:fin4", "High xG threat", True, 105, (("xG per 90", 88), ("Shots per 90", 75)), _R_ATT),
        _combo("c:head", "Aerial goal threat", True, 103, (("Head goals per 90", 82), ("Aerial duels won, %", 78)), _R_ATT | _R_CB),
    ]

    # Chance creation
    r += [
        _combo("c:cr1", "Chance creator", True, 115, (("xA per 90", 86), ("Key passes per 90", 82))),
        _combo("c:cr2", "Playmaker", True, 114, (("Smart passes per 90", 84), ("Through passes per 90", 78)),_R_MF),
        _combo("c:cr3", "Final-third creator", True, 108, (("Passes to final third per 90", 85), ("Key passes per 90", 78))),
        _combo("c:cr4", "Box passer", True, 107, (("Passes to penalty area per 90", 85), ("xA per 90", 75))),
        _combo("c:cr5", "Assist merchant", True, 109, (("Assists per 90", 88), ("xA per 90", 72))),
    ]

    # Crossing & wide
    r += [
        _combo("c:wx1", "Wide crosser", True, 111, (("Crosses per 90", 86), ("Accurate crosses, %", 72)), _R_WFB),
        _combo("c:wx2", "Cutback specialist", True, 100, (("Crosses to goalie box per 90", 82), ("Accurate crosses, %", 70)), _R_WFB),
    ]

    # Passing volume & progression
    r += [
        _combo("c:pv1", "Maestro", True, 104, (("Passes per 90", 88), ("Accurate passes, %", 78)),_R_MF | _R_CB | _R_FB),
        _combo("c:pv2", "Progressive distributor", True, 110, (("Progressive passes per 90", 86), ("Vertical passes per 90", 80))),
        _combo("c:pv3", "Vertical launcher", True, 106, (("Vertical passes per 90", 86), ("Long passes per 90", 75))),
        _combo("c:pv4", "Long-switch threat", True, 102, (("Long passes per 90", 85), ("Accurate long passes, %", 78))),
        _combo("c:pv5", "Forward passer", True, 99, (("Forward passes per 90", 85), ("Accurate forward passes, %", 78))),
    ]

    # Defense & duels
    r += [
        _combo("c:def1", "Ball-winner", True, 113, (("Successful defensive actions per 90", 86), ("PAdj Interceptions", 78))),
        _combo("c:def2", "Ground duel monster", True, 108, (("Defensive duels per 90", 85), ("Defensive duels won, %", 80))),
        _combo("c:def3", "Interceptor", True, 105, (("PAdj Interceptions", 88), ("Interceptions per 90", 75))),
        _combo("c:def4", "Shot blocker", True, 100, (("Shots blocked per 90", 86), ("Defensive duels won, %", 75))),
        _combo("c:def5", "Slide tackler", True, 98, (("PAdj Sliding tackles", 86), ("Defensive duels per 90", 72))),
        _combo("c:def6", "Aerial defender", True, 104, (("Aerial duels won, %", 86), ("Aerial duels per 90", 78)), _R_CB | _R_MF | _R_FB),
    ]

    # Offensive output composites
    r += [
        _combo("c:eo1", "Offensive Monster", True, 101, (("Expected Offensive Output per 90", 85), ("Successful attacking actions per 90", 78))),
        _combo("c:eo2", "Ball-progression engine", True, 100, (("Ball Progression per 90", 86), ("Progressive runs per 90", 75))),
        _combo("c:eo3", "Ball-winning midfielder", True, 103, (("Ball Winning Actions per 90", 86), ("Defensive duels per 90", 72)), _R_MF),
    ]

    # Fullback / wing-back
    r += [
        _combo("c:fb1", "Overlapping full-back", True, 107, (("Progressive runs per 90", 82), ("Crosses per 90", 75)), _R_FB),
        _combo("c:fb2", "Defensive full-back", True, 105, (("Defensive duels won, %", 84), ("Successful defensive actions per 90", 80)), _R_FB),
    ]

    # Midfielder blends
    r += [
        _combo("c:mf1", "Box-to-box carrier", True, 106, (("Progressive runs per 90", 80), ("Successful defensive actions per 90", 78)), _R_MF),
        _combo("c:mf2", "Deep-lying creator", True, 108, (("Progressive passes per 90", 82), ("xA per 90", 75)), _R_MF),
        TraitRule(
            "c:mf3",
            "Press-resistant pivot",
            True,
            99,
            (
                ("Passes per 90", 82.0, 100.0),
                ("Fouls suffered per 90", 78.0, 100.0),
                ("Accurate passes, %", 76.0, 100.0),
            ),
            _R_MF,
        ),
    ]

    # Forwards: movement
    r += [
        _combo("c:fw1", "Penalty-box crasher", True, 112, (("Touches in box per 90", 88), ("Offensive duels per 90", 78)), _R_FW)
    ]

    # Goalkeepers
    r += [
        _combo("c:gk1", "Shot-stopping GK", True, 115, (("Save rate, %", 86), ("Prevented goals per 90", 75)), _R_GK),
        _combo("c:gk2", "Sweeper keeper", True, 108, (("Exits per 90", 82), ("Back passes received as GK per 90", 72)), _R_GK),
        _combo("c:gk3", "Ball-playing GK", True, 106, (("Passes per 90", 78), ("Accurate passes, %", 80)), _R_GK),
        _combo("c:gk4", "Busy keeper", True, 95, (("Shots against per 90", 88), ("Save rate, %", 72)), _R_GK),
    ]

    # Set pieces
    r += [
        _combo("c:sp1", "Set-piece shooter", True, 96, (("Direct free kicks per 90", 82), ("Direct free kicks on target, %", 72))),
        _combo("c:sp2", "FK volume", True, 90, (("Free kicks per 90", 88), ("Corners per 90", 70))),
    ]

    # Extended precision / profile combos
    r += [
        _combo(
            "x:late_chain",
            "Late-assist chain",
            True,
            88,
            (("Third assists per 90", 80), ("Second assists per 90", 78)),
            _R_ATT | _R_MF | _R_W,
        ),
        _combo(
            "x:smart_snip",
            "Smart-pass sniper",
            True,
            89,
            (("Smart passes per 90", 82), ("Accurate smart passes, %", 78)),
        ),
        _combo(
            "x:ft3_surg",
            "Final-third surgeon",
            True,
            88,
            (("Passes to final third per 90", 84), ("Accurate passes to final third, %", 76)),
        ),
        _combo(
            "x:box_prec",
            "Precise box-line passer",
            True,
            87,
            (
                ("Passes to penalty area per 90", 82),
                ("Accurate passes to penalty area, %", 76),
            ),
        ),
        _combo(
            "x:thr_clean",
            "Clean through-ball threat",
            True,
            88,
            (("Through passes per 90", 80), ("Accurate through passes, %", 78)),
        ),
        _combo(
            "x:short_ctl",
            "Short-game controller",
            True,
            86,
            (
                ("Short / medium passes per 90", 86),
                ("Accurate short / medium passes, %", 78),
            ),
        ),
        TraitRule(
            "x:recycle",
            "Elite recycler",
            True,
            86,
            (
                ("Back passes per 90", 78.0, 100.0),
                ("Accurate back passes, %", 76.0, 100.0),
                ("Passes per 90", 82.0, 100.0),
                ("Forward passes per 90", 52.0, 100.0),
            ),
            _R_MF,
        ),
        _combo(
            "x:xga_wall",
            "Low-xGA wall",
            True,
            90,
            (("xG against per 90", 82), ("Conceded goals per 90", 80)),
            _R_CB | _R_FB,
        ),
        _combo(
            "x:corner",
            "Corner weapon",
            True,
            85,
            (("Corners per 90", 82), ("xA per 90", 72)),
            _R_W | _R_WFB | _R_MF,
        ),
        _combo(
            "x:pen_spec",
            "Penalty specialist",
            True,
            84,
            (("Penalty conversion, %", 85), ("xG per 90", 62)),
            _R_ATT,
        ),
        _combo(
            "x:eco_box",
            "Economical box finisher",
            True,
            87,
            (("Touches in box per shot per 90", 80), ("Goal conversion, %", 78)),
            _R_ATT,
        ),
        _combo(
            "x:long_tgt",
            "Long-ball target",
            True,
            86,
            (("Received long passes per 90", 80), ("Aerial duels won, %", 74)),
            _R_FW | _R_ATT,
        ),
        _combo(
            "x:duel_dom",
            "Overall duel dominator",
            True,
            88,
            (("Duels per 90", 85), ("Duels won, %", 85)),
        ),
        _combo(
            "x:slide_dis",
            "Sliding disruptor",
            True,
            86,
            (("Sliding tackles per 90", 82), ("Interceptions per 90", 76)),
            _R_MF | _R_FB | _R_CB,
        ),
        _combo(
            "x:cross_L",
            "Left-flank delivery",
            True,
            87,
            (
                ("Crosses from left flank per 90", 82),
                ("Accurate crosses from left flank, %", 80),
            ),
            _R_WFB | _R_W,
        ),
        _combo(
            "x:cross_R",
            "Right-flank delivery",
            True,
            87,
            (
                ("Crosses from right flank per 90", 82),
                ("Accurate crosses from right flank, %", 80),
            ),
            _R_WFB | _R_W,
        ),
        _combo(
            "x:trans_eng",
            "Transition engine",
            True,
            87,
            (
                ("Accelerations per 90", 82),
                ("Successful attacking actions per 90", 78),
            ),
            _R_OUT,
        ),
        _combo(
            "x:wide_2way",
            "Two-way Wide Threat",
            True,
            90,
            (("Goals per 90", 90), ("Assists per 90", 90)),
            _R_W | _R_FW,
        ),
        _combo(
            "x:half_cr",
            "Half-space creator",
            True,
            88,
            (("Deep completions per 90", 85), ("Key passes per 90", 85)),
        ),
        _combo(
            "x:gk_phys",
            "Sweeper-keeper",
            True,
            87,
            (("Exits per 90", 78), ("PAdj Sliding tackles", 72)),
            _R_GK,
        ),
        _combo(
            "x:2nd_cr",
            "Second-line creator",
            True,
            88,
            (("Third assists per 90", 85), ("Key passes per 90", 80)),
            _R_ATT | _R_MF | _R_W,
        ),
        _combo(
            "y:2w_press",
            "Two-way wide presser",
            True,
            87,
            (("Defensive duels won, %", 80), ("Successful dribbles, %", 78)),
            _R_W | _R_FW | _R_WFB,
        ),
        _combo(
            "y:wide_cr",
            "Wide creator",
            True,
            88,
            (("xA per 90", 78), ("Crosses per 90", 80)),
            _R_W | _R_WFB,
        ),
        _combo(
            "y:shot_qual",
            "Shot-quality sniper",
            True,
            87,
            (("xG per shot per 90", 78), ("Shots on target, %", 78)),
            _R_ATT,
        ),
    ]

    # --- Pair grid: many named two-stat profiles (medium priority) ----------------
    _pairs: list[tuple[str, str, str, float, float, int, frozenset[str] | None]] = [
        ("p:xgxa", "xG + xA threat", "xG per 90", 82, "xA per 90", 82, 96, _R_ATT | _R_MF),
        ("p:progvert", "Vertical progressor", "Progressive passes per 90", 84, "Vertical passes per 90", 82, 94, None),
        ("p:xa_key", "Final-ball threat", "xA per 90", 84, "Shot assists per 90", 80, 95, None),
        ("p:deep", "Deep passer", "Deep completions per 90", 82, "Progressive passes per 90", 80, 93, None),
        ("p:duel_att", "Offensive duel bully", "Offensive duels per 90", 85, "Offensive duels won, %", 80, 97, _R_OUT),
        ("p:recv", "Central outlet", "Received passes per 90", 86, "Accurate passes, %", 78, 92, _R_MF),
        ("p:foul", "Foul magnet", "Fouls suffered per 90", 88, "Dribbles per 90", 72, 91, _R_ATT | _R_W),
        ("p:prog_acc", "Direct accelerator", "Progressive runs per 90", 82, "Accelerations per 90", 85, 95, None),
        ("p:cross_deep", "Dangerous wide service", "Crosses per 90", 80, "Deep completed crosses per 90", 78, 90, _R_WFB),
        ("p:tackle_int", "Ground disruptor", "PAdj Sliding tackles", 80, "PAdj Interceptions", 82, 94, _R_MF | _R_FB | _R_CB),
        ("p:aerial_vol", "Aerial battler", "Aerial duels per 90", 86, "Aerial duels won, %", 75, 96, None),
        ("p:pass_progacc", "Pass-and-run threat", "Progressive passes per 90", 82, "Progressive runs per 90", 80, 93, _R_MF | _R_W),
        ("p:smart_key", "Risk-taking creator", "Smart passes per 90", 82, "Key passes per 90", 80, 94, None),
        ("p:thr_pen", "Line-splitting passer", "Through passes per 90", 80, "Passes to penalty area per 90", 80, 93, None),
        ("p:long_acc", "Long-ball distributor", "Long passes per 90", 82, "Accurate long passes, %", 80, 92, _R_CB | _R_MF | _R_GK),
        ("p:gk_long", "Long-passing GK", "Long passes per 90", 75, "Accurate long passes, %", 78, 92, _R_GK),
        ("p:conv_shot", "Efficient shooter", "Goal conversion, %", 82, "xG per shot per 90", 80, 98, _R_ATT),
        ("p:att_sda", "Attacking defender", "Successful attacking actions per 90", 82, "Successful defensive actions per 90", 75, 95, _R_FB | _R_W),
    ]
    for fam, lbl, m1, t1, m2, t2, pr, roles in _pairs:
        r.append(_combo(fam, lbl, True, pr, ((m1, t1), (m2, t2)), roles))

    # --- Negative / warning tags (lower priority so strengths fill first) ----------
    r += [
        TraitRule(
            "n:aerial",
            "Aerially exposed",
            False,
            28,
            (("Aerial duels won, %", 0.0, 26.0), ("Aerial duels per 90", 38.0, 100.0)),
            None,
        ),
        TraitRule(
            "n:pass_safe",
            "Risk-averse passer",
            False,
            26,
            (("Forward passes per 90", 0.0, 5.0), ("Back passes per 90", 80.0, 100.0)),
            _R_MF | _R_ATT,
        ),
        TraitRule(
            "n:shot_wild",
            "Wayward shooter",
            False,
            24,
            (("Shots on target, %", 0.0, 28.0), ("Shots per 90", 65.0, 100.0)),
            _R_ATT,
        ),
        _neg_combo("n:discipline", "Discipline concern", 22, (("Yellow cards per 90", 10.0),)),
        _neg_combo("n:foul_rate", "Foul-prone", 21, (("Fouls per 90", 10.0),)),
        _neg_combo(
            "n:leaky_line",
            "Leaky defensive line",
            19,
            (("xG against per 90", 22.0), ("Conceded goals per 90", 22.0)),
            _R_CB | _R_FB,
        ),
        TraitRule(
            "n:def_pass",
            "Defensive passenger",
            False,
            18,
            (
                ("Successful defensive actions per 90", 0.0, 10.0),
                ("Defensive duels per 90", 0.0, 5.0),
            ),
            _R_CB | _R_FB | _R_MF,
        ),
        TraitRule(
            "n:long_lib",
            "Long-ball liability",
            False,
            17,
            (("Long passes per 90", 65.0, 100.0), ("Accurate long passes, %", 0.0, 32.0)),
            _R_CB | _R_MF | _R_GK,
        ),
        TraitRule(
            "n:cross_spam",
            "Cross spammer",
            False,
            16,
            (("Crosses per 90", 68.0, 100.0), ("Accurate crosses, %", 0.0, 30.0)),
            _R_W | _R_WFB,
        ),
        TraitRule(
            "n:disp_carrier",
            "Dispossession-prone carrier",
            False,
            15,
            (("Dribbles per 90", 68.0, 100.0), ("Successful dribbles, %", 0.0, 32.0)),
            _R_OUT,
        ),
        TraitRule(
            "n:prog_shy",
            "Progression-shy passer",
            False,
            14,
            (("Accurate passes, %", 72.0, 100.0), ("Progressive passes per 90", 0.0, 30.0)),
            _R_MF | _R_FB,
        ),
        TraitRule(
            "n:periph_fw",
            "Peripheral forward",
            False,
            13,
            (("Touches in box per 90", 0.0, 30.0), ("xG per 90", 0.0, 32.0)),
            _R_FW | _R_ATT,
        ),
        TraitRule(
            "n:xg_under",
            "xG underperformer",
            False,
            12,
            (("xG per 90", 70.0, 100.0), ("Goals per 90", 0.0, 10.0)),
            _R_ATT,
        ),
    ]

    return r


def _build_single_metric_rules() -> list[TraitRule]:
    rules: list[TraitRule] = []
    for m in TRAIT_METRICS:
        noun = _style_noun(m)
        for lo in _TIER_LOS:
            rules.append(
                TraitRule(
                    f"s:{m}",
                    _tier_label_fixed(lo, noun),
                    True,
                    40 + lo // 2,
                    ((m, float(lo), 100.0),),
                    None,
                )
            )
    return rules


# ALL_TRAIT_RULES: Tuple[TraitRule, ...] = tuple(_build_combo_rules() + _build_single_metric_rules())
ALL_TRAIT_RULES: tuple[TraitRule, ...] = tuple(_build_combo_rules())


def _player_mask(df: pd.DataFrame, player_row: pd.Series) -> pd.Series:
    pc = "Player" if "Player" in df.columns else "Full name"
    name = player_row.get("Player") or player_row.get(pc)
    m = df[pc].astype(str) == str(name)
    if "club" in df.columns and player_row.get("club") is not None and str(player_row.get("club")) != "nan":
        m &= df["club"].astype(str) == str(player_row.get("club"))
    return m


def _raw_percentile_dict(df: pd.DataFrame, player_row: pd.Series) -> dict[str, float]:
    mask = _player_mask(df, player_row)
    if not mask.any() or len(df) < 12:
        return {}
    cols = [m for m in TRAIT_METRICS if m in df.columns]
    if not cols:
        return {}
    num = df[cols].apply(pd.to_numeric, errors="coerce")
    cols_ok = num.columns[num.notna().sum(axis=0) >= 12].tolist()
    if not cols_ok:
        return {}
    pct_frame = num[cols_ok].rank(pct=True, method="average") * 100.0
    try:
        row_label = mask.idxmax()
        row = pct_frame.loc[row_label]
    except (TypeError, ValueError, KeyError):
        return {}
    out: dict[str, float] = {}
    for m in cols_ok:
        val = row[m]
        if pd.notna(val):
            out[m] = float(val)
    return out


def _effective_percentiles(raw: dict[str, float]) -> dict[str, float]:
    eff: dict[str, float] = {}
    for m, v in raw.items():
        if pd.isna(v):
            continue
        if m in LOWER_IS_BETTER:
            eff[m] = 100.0 - float(v)
        else:
            eff[m] = float(v)
    return eff


def _tier_primary(rule: TraitRule) -> float:
    """Larger = stronger label (single-metric: percentile floor; combos: priority)."""
    if rule.family.startswith("s:"):
        return float(rule.bounds[0][1])
    return float(rule.priority)


def _rule_margin(rule: TraitRule, eff: dict[str, float]) -> float | None:
    margins: list[float] = []
    for m, lo, hi in rule.bounds:
        if m not in eff or pd.isna(eff[m]):
            return None
        v = eff[m]
        if v < lo or v > hi:
            return None
        margins.append(min(v - lo, hi - v))
    if not margins:
        return None
    return float(min(margins))


def select_player_traits(
    player_row: pd.Series,
    df_pos: pd.DataFrame,
    role: str | None,
    *,
    max_traits: int = 9,
    min_margin: float = 0.25,
) -> list[tuple[bool, str, str]]:
    """
    Return up to ``max_traits`` (positive, label, game_area) for matplotlib rendering.
    Percentiles are computed within ``df_pos`` (callers should pass rows for the
    same mapped role; e.g. full season across all leagues).

    Order is best → worst: positive traits first — highest tier (Elite before Solid)
    and stronger combo priority before lower — then margin as tie-breaker. Negative
    traits follow (milder before harsher). If truncated, positives are kept in full
    and the most severe negative matches fill remaining slots.
    """
    raw = _raw_percentile_dict(df_pos, player_row)
    if not raw:
        return []
    eff = _effective_percentiles(raw)

    # Store (margin, rule) per family. For single-metric families ``s:...``, keep the
    # strictest tier that matches (highest ``lo``), not the one with largest margin —
    # otherwise Solid beats Elite at high percentiles.
    best_by_family: dict[str, tuple[float, TraitRule]] = {}
    for rule in ALL_TRAIT_RULES:
        if rule.roles is not None and (role is None or role not in rule.roles):
            continue
        mar = _rule_margin(rule, eff)
        if mar is None or mar < min_margin:
            continue
        prev = best_by_family.get(rule.family)
        if prev is None:
            best_by_family[rule.family] = (mar, rule)
            continue
        prev_mar, prev_rule = prev
        if rule.family.startswith("s:"):
            lo, plo = rule.bounds[0][1], prev_rule.bounds[0][1]
            if lo > plo or (lo == plo and mar > prev_mar):
                best_by_family[rule.family] = (mar, rule)
        else:
            sc = mar + rule.priority * 0.01
            psc = prev_mar + prev_rule.priority * 0.01
            if sc > psc:
                best_by_family[rule.family] = (mar, rule)

    # Best → worst: strongest positives first, then negatives (mild → harsh at the end).
    items = list(best_by_family.values())
    positives = [(m, r) for m, r in items if r.positive]
    negatives = [(m, r) for m, r in items if not r.positive]
    positives.sort(key=lambda mr: (-_tier_primary(mr[1]), -mr[0]))
    negatives.sort(key=lambda mr: -(mr[0] + mr[1].priority * 0.01))

    n_pos, n_neg = len(positives), len(negatives)
    if n_pos + n_neg <= max_traits:
        chosen_rules = [r for _, r in positives] + [r for _, r in negatives]
    elif n_pos >= max_traits:
        chosen_rules = [r for _, r in positives[:max_traits]]
    else:
        k_neg = max_traits - n_pos
        chosen_rules = [r for _, r in positives] + [r for _, r in negatives[-k_neg:]]

    return [
        (rule.positive, rule.label, game_area_for_trait_rule(rule))
        for rule in chosen_rules
    ]


def trait_rule_count() -> int:
    """Useful for tests / sanity checks (hundreds expected)."""
    return len(ALL_TRAIT_RULES)
