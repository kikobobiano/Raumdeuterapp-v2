"""Shared Pydantic schemas for API responses + requests."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.core.filters import PlayerFilters

MetricModeLiteral = Literal["raw", "p90", "as_is"]


class SeasonsResponse(BaseModel):
    seasons: list[int]


class PlayerListItem(BaseModel):
    wyscout_id: int | None = None
    player: str
    full_name: str | None = None
    club: str | None = None
    league: str | None = None
    position: str | None = None
    age: int | None = None
    minutes: int | None = None
    market_value: float | None = None


class TopPerformancePlayer(BaseModel):
    wyscout_id: int | None = None
    player: str
    club: str | None = None
    league: str | None = None
    position: str | None = None
    age: int | None = None
    minutes: int | None = None
    performance_index: float | None = None
    club_logo: str | None = None
    player_image_url: str | None = None
    distribution_index: float | None = None
    take_ons_index: float | None = None
    assistance_index: float | None = None
    finishing_index: float | None = None
    aerial_play_index: float | None = None
    ground_defense_index: float | None = None


class TopPerformancePage(BaseModel):
    """Paged slice of leaderboard + total eligible players (distinct Wyscout IDs)."""

    items: list[TopPerformancePlayer]
    total: int


class PlayerSearchResponse(BaseModel):
    items: list[PlayerListItem]
    total: int


class MetricOption(BaseModel):
    name: str
    label: str
    supports_mode: bool = False
    default_mode: MetricModeLiteral = "as_is"


class ScatterRequest(BaseModel):
    filters: PlayerFilters
    x_metric: str
    y_metric: str
    x_mode: MetricModeLiteral = "as_is"
    y_mode: MetricModeLiteral = "as_is"
    size_metric: str | None = None
    label_metric: str | None = None
    highlight_player_ids: list[int] = Field(default_factory=list)


class ScatterPoint(BaseModel):
    wyscout_id: int | None
    player: str
    club: str | None
    league: str | None
    position: str | None
    age: int | None
    minutes: int | None
    x: float | None
    y: float | None
    size: float | None = None
    player_image_url: str | None = None


class ScatterResponse(BaseModel):
    points: list[ScatterPoint]
    x_metric: str
    y_metric: str
    x_label: str
    y_label: str
    size_metric: str | None
    n: int


class ScreenerCriterion(BaseModel):
    metric: str
    mode: MetricModeLiteral = "as_is"
    operator: str = Field(..., pattern=r"^(>=|<=|>|<|=|!=)$")
    value: float


class ScreenerRequest(BaseModel):
    filters: PlayerFilters
    criteria: list[ScreenerCriterion] = Field(default_factory=list)
    sort_by: str | None = None
    sort_mode: MetricModeLiteral = "as_is"
    sort_desc: bool = True
    limit: int = Field(20, ge=1, le=2000)
    offset: int = Field(0, ge=0, le=500_000)


class ScreenerRow(BaseModel):
    wyscout_id: int | None
    club_logo: str | None = None
    player: str
    club: str | None
    league: str | None
    position: str | None
    age: int | None
    minutes: int | None
    metrics: dict[str, float | None]


class ScreenerResponse(BaseModel):
    rows: list[ScreenerRow]
    total: int


class ProfileMetric(BaseModel):
    metric: str
    label: str
    value: float | None
    percentile: float | None


class GameAreaProfileBlock(BaseModel):
    area: str
    index: ProfileMetric
    metrics: list[ProfileMetric]


class PlayerTrait(BaseModel):
    positive: bool
    label: str
    game_area: str


class ProfileClubStint(BaseModel):
    club: str
    minutes: int | None = None
    club_logo: str | None = None


class PlayerProfile(BaseModel):
    wyscout_id: int | None
    player: str
    full_name: str | None
    club: str | None
    league: str | None
    club_logo: str | None = None
    position: str | None
    age: int | None
    minutes: int | None
    market_value: float | None
    foot: str | None
    height: int | None
    role: str | None
    radar: list[ProfileMetric]
    table: list[ProfileMetric]
    performance_index: float | None
    performance_index_percentile: float | None = None
    games: int | None = None
    goals: float | None = None
    assists: float | None = None
    player_image_url: str | None = Field(
        default=None,
        description="HTTPS headshot URL (Transfermarkt CDN or Wyscout image when enriched in parquet)",
    )
    position_tokens: list[str] = Field(default_factory=list)
    position_tokens_primary: list[str] = Field(default_factory=list)
    position_tokens_secondary: list[str] = Field(default_factory=list)
    game_areas: list[GameAreaProfileBlock] = Field(default_factory=list)
    traits: list[PlayerTrait] = Field(default_factory=list)
    clubs_in_season: list[ProfileClubStint] = Field(
        default_factory=list,
        description="All (club, minutes) rows for this wyscout_id in the season — surface a switcher when length > 1.",
    )
    performance_index_history: list[PerformanceIndexHistoryPoint] | None = Field(
        default=None,
        description="Filled when GET /players/{wyscout_id}/profile sets performance_index_history_limit (mini PI trajectory).",
    )


class PerformanceIndexHistoryPoint(BaseModel):
    """Single season snapshot for scout profile PI progression (club = dominant minutes row)."""

    season: int
    performance_index: float
    club: str | None = None
    club_logo: str | None = None


class PerformanceIndexHistoryResponse(BaseModel):
    """Chronological (oldest → newest), at most ``limit`` seasons with non-null PI."""

    points: list[PerformanceIndexHistoryPoint]


# ── F4: Progression ────────────────────────────────────────────────────────────


class ProgressionPoint(BaseModel):
    season: int
    value: float | None
    club: str | None = None
    league: str | None = None
    minutes: int | None = None
    club_logo: str | None = None


class ProgressionMetricSeries(BaseModel):
    metric: str
    label: str
    points: list[ProgressionPoint]


class ProgressionRequest(BaseModel):
    metrics: list[str] = Field(..., min_length=1, max_length=10)
    target_season: int
    seasons_count: int = Field(5, ge=2, le=10)
    mode: MetricModeLiteral = "as_is"


class ProgressionResponse(BaseModel):
    player: str | None
    metrics: list[ProgressionMetricSeries]
    seasons: list[int]


# ── F4: Replacement ────────────────────────────────────────────────────────────


ReplacementProfile = Literal["indices", "per90", "combined"]
ReplacementMethod = Literal["cosine", "euclidean"]

REPLACEMENT_PROFILE_DEFAULT: ReplacementProfile = "combined"
REPLACEMENT_METHOD_DEFAULT: ReplacementMethod = "cosine"


class ReplacementRequest(BaseModel):
    target_player_id: int
    target_season: int
    candidate_seasons: list[int] = Field(..., min_length=1, max_length=8)
    candidate_filters: PlayerFilters
    limit: int = Field(20, ge=1, le=100)


class ReplacementCandidate(BaseModel):
    wyscout_id: int | None
    player: str
    club: str | None
    league: str | None
    position: str | None
    age: int | None
    minutes: int | None
    similarity: float
    candidate_season: int | None = None
    club_logo: str | None = None
    player_image_url: str | None = None


class ReplacementResponse(BaseModel):
    target: ReplacementCandidate | None
    candidates: list[ReplacementCandidate]
    n: int
    profile: ReplacementProfile
    method: ReplacementMethod


# ── F4: Rankings ───────────────────────────────────────────────────────────────


class RankingsRequest(BaseModel):
    filters: PlayerFilters
    metric: str
    mode: MetricModeLiteral = "as_is"
    desc: bool = True
    limit: int = Field(50, ge=1, le=500)


class RankingsRow(BaseModel):
    rank: int
    wyscout_id: int | None
    player: str
    club: str | None
    league: str | None
    position: str | None
    age: int | None
    minutes: int | None
    club_logo: str | None = None
    value: float | None


class RankingsResponse(BaseModel):
    rows: list[RankingsRow]
    metric: str
    label: str
    n: int


# ── F4: Bar chart ──────────────────────────────────────────────────────────────


class BarRequest(BaseModel):
    season: int
    player_ids: list[int] = Field(..., min_length=1, max_length=12)
    metrics: list[str] = Field(..., min_length=1, max_length=12)
    mode: MetricModeLiteral = "as_is"


class BarPlayerSeries(BaseModel):
    wyscout_id: int | None
    player: str
    club: str | None
    league: str | None
    position: str | None
    minutes: int | None
    values: dict[str, float | None]


class BarResponse(BaseModel):
    metrics: list[str]
    labels: dict[str, str]
    players: list[BarPlayerSeries]


# ── F4: Translation ────────────────────────────────────────────────────────────


class TranslationRequest(BaseModel):
    player_id: int
    season: int
    target_season: int | None = None
    target_leagues: list[str] | None = None
    min_minutes: int | None = None


class StrengthAdjustment(BaseModel):
    value: float
    xg_factor: float
    tier_factor: float
    league_factor: float
    raw_team_xg_p90: float | None = None
    raw_league_avg_xg_p90: float | None = None
    dominance_z: float = 0.0
    available: bool = False
    clamped: bool = False


class TranslationPeer(BaseModel):
    wyscout_id: int | None
    player: str
    club: str | None
    age: int | None
    perf_index: float
    z_score: float
    color: str
    player_image_url: str | None = None


class TranslationLeaguePool(BaseModel):
    league: str
    n: int
    mu: float | None
    sigma: float | None
    peers: list[TranslationPeer]
    projected_perf_index: float | None
    projected_z_score: float | None
    projected_color: str | None = None
    power: float | None
    insufficient_data: bool = False


class LeagueStyleFitRow(BaseModel):
    """Cosine similarity of player style vs minutes-weighted league centroid (see legacy League Style Fit)."""

    league: str
    n_teams: int
    style_fit: float = Field(..., description="Cosine similarity in z-scored style space (higher = closer fit).")


class TranslationResponse(BaseModel):
    player: str
    club: str | None
    source_league: str
    source_power: float | None
    source_perf_index: float
    source_strength_adj: StrengthAdjustment
    role: str
    player_age: int | None
    season: int
    target_season: int
    min_minutes: int
    pools: list[TranslationLeaguePool]
    target_leagues: list[str]
    league_style_fit: list[LeagueStyleFitRow] = Field(default_factory=list)


# ── F4: Bar ranking ────────────────────────────────────────────────────────────


class BarRankingRequest(BaseModel):
    filters: PlayerFilters
    metrics: list[str] = Field(..., min_length=1, max_length=3)
    modes: list[MetricModeLiteral] = Field(default_factory=list)
    sort_combined: bool = Field(
        True,
        description=(
            "When true, order by sum of |m_i|/max_i over selected metrics in the filtered set "
            "(same scale as stacked bars). When false, use sort_by + sort_mode."
        ),
    )
    sort_by: str = Field(default="", description="Ignored when sort_combined is true.")
    sort_mode: MetricModeLiteral = "as_is"
    sort_desc: bool = True
    limit: int = Field(20, ge=1, le=50)

    @model_validator(mode="after")
    def _bar_sort_by_when_single(self) -> BarRankingRequest:
        if not self.sort_combined and not (self.sort_by or "").strip():
            raise ValueError("sort_by is required when sort_combined is false")
        return self


class BarRankingRow(BaseModel):
    rank: int
    wyscout_id: int | None
    player: str
    club: str | None
    league: str | None
    position: str | None
    age: int | None
    minutes: int | None
    club_logo: str | None = None
    player_image_url: str | None = None
    values: dict[str, float | None]


class BarRankingResponse(BaseModel):
    rows: list[BarRankingRow]
    metrics: list[str]
    labels: dict[str, str]
    sort_combined: bool
    sort_by: str
    sort_mode: MetricModeLiteral
    n: int
    metric_max_abs: dict[str, float] | None = Field(
        default=None,
        description=(
            "When combined sort ran: ABS max per metric over the filtered cohort — "
            "stacked-bar segment widths use this so they match ranking logic."
        ),
    )


# ── F5: Best XI ────────────────────────────────────────────────────────────────


class BestXIRequest(BaseModel):
    filters: PlayerFilters
    formation: str = "4-3-3"
    mode: Literal["by_league", "by_club", "two_teams"] = "by_league"
    club: str | None = None
    team2: str | None = None


class BestXIPlayer(BaseModel):
    slot: str
    player: str
    wyscout_id: int | None = None
    club: str | None = None
    club_logo: str | None = None
    league: str | None = None
    position: str | None = None
    age: int | None = None
    minutes: int | None = None
    goals: int | None = None
    assists: int | None = None
    performance_index: float | None = None
    position_type: str
    player_image_url: str | None = None


class BestXITop3Row(BaseModel):
    slot: str
    rank: int
    player: str
    wyscout_id: int | None = None
    club: str | None = None
    club_logo: str | None = None
    age: int | None = None
    minutes: int | None = None
    performance_index: float | None = None
    position_type: str
    player_image_url: str | None = None


class BestXIResponse(BaseModel):
    formation: str
    context: str
    slots: list[BestXIPlayer]
    top3: list[BestXITop3Row]
    coords: dict[str, list[float]]


# ── F4: Potential ──────────────────────────────────────────────────────────────


class PotentialRequest(BaseModel):
    filters: PlayerFilters


class PotentialPlayer(BaseModel):
    wyscout_id: int | None
    player: str
    club: str | None = None
    club_logo: str | None = None
    league: str | None = None
    position: str | None = None
    age: int | None = None
    minutes: int | None = None
    current_pi: float | None = None
    potential_score: float
    player_image_url: str | None = None


class PotentialResponse(BaseModel):
    players: list[PotentialPlayer]
    n: int


class PotentialCohortRequest(BaseModel):
    """Single age-cohort slice for the Potential big-board (paginated)."""

    filters: PlayerFilters
    age: int = Field(..., ge=14, le=40)
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0, le=10_000)


class PotentialCohortResponse(BaseModel):
    age: int
    players: list[PotentialPlayer]
    total: int


class MinutesDistributionPlayer(BaseModel):
    wyscout_id: int | None = None
    player: str
    player_image_url: str | None = None
    position: str | None = None
    age: int | None = None
    minutes: int
    matches: int | None = None
    league_minutes_pct: float
    age_zone: Literal["young", "prime", "veteran"]


class MinutesDistributionResponse(BaseModel):
    """Squad minutes distribution for a single club in a single season.

    `max_league_minutes = max_league_games * 90` from the static
    `LEAGUE_MAX_GAMES` table in `core/config.py`. Multi-stage / playoff leagues
    use the regular-season game count; downstream callers clamp the per-player
    pct to 100 in case a player accrues playoff minutes on top.
    """

    club: str
    club_logo: str | None = None
    league: str | None = None
    season: int
    max_league_games: int
    max_league_minutes: int
    young_max_age: int
    prime_max_age: int
    players: list[MinutesDistributionPlayer]


# ── F8: Heatmap ────────────────────────────────────────────────────────────────


class HeatmapPoint(BaseModel):
    x: float
    y: float
    count: int


class HeatmapResponse(BaseModel):
    wyscout_id: int
    competition_id: int
    competition: str
    season: int
    points: list[HeatmapPoint]
    n_points: int
    max_count: int
