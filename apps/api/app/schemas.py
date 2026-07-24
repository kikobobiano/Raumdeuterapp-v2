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
    x_composite: list[CompositeComponent] = Field(default_factory=list, max_length=8)
    y_composite: list[CompositeComponent] = Field(default_factory=list, max_length=8)
    x_label: str | None = None
    y_label: str | None = None
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


CompositeBasisLiteral = Literal["value", "team_median"]


class CompositeComponent(BaseModel):
    metric: str
    mode: MetricModeLiteral = "as_is"
    basis: CompositeBasisLiteral = "value"
    weight: float = 1.0


class CompositeScoreCriterion(BaseModel):
    """Filter on the computed composite score (not a parquet column)."""

    operator: str = Field(..., pattern=r"^(>=|<=|>|<|=|!=)$")
    value: float


class ScreenerRequest(BaseModel):
    filters: PlayerFilters
    seasons: list[int] = Field(
        default_factory=list,
        max_length=8,
        description="Optional multi-season set. Empty → filters.season only.",
    )
    criteria: list[ScreenerCriterion] = Field(default_factory=list)
    composite: list[CompositeComponent] = Field(default_factory=list, max_length=8)
    composite_criteria: CompositeScoreCriterion | None = None
    sort_by_composite: bool = False
    sort_by: str | None = None
    sort_mode: MetricModeLiteral = "as_is"
    sort_desc: bool = True
    limit: int = Field(20, ge=1, le=2000)
    offset: int = Field(0, ge=0, le=500_000)


class ScreenerRow(BaseModel):
    season: int
    wyscout_id: int | None
    club_logo: str | None = None
    player: str
    club: str | None
    league: str | None
    position: str | None
    age: int | None
    minutes: int | None
    metrics: dict[str, float | None]
    composite: float | None = None


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
    performance_index_role_rank: int | None = Field(
        default=None,
        description="Rank (1-based) of this player among same-role peers in the percentile cohort.",
    )
    performance_index_role_cohort_size: int | None = Field(
        default=None,
        description="Total players in the same-role percentile cohort (denominator for the rank).",
    )
    games: int | None = None
    goals: float | None = None
    assists: float | None = None
    x_tv_eur: float | None = Field(
        default=None,
        description="Expected transfer value (EUR) from the xTV v2 model for the player's season row.",
    )
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
    x_tv_history: list[XtvHistoryPoint] | None = Field(
        default=None,
        description="Filled when GET /players/{wyscout_id}/profile sets x_tv_history_limit (mini xTV trajectory).",
    )


class PerformanceIndexHistoryPoint(BaseModel):
    """Single season snapshot for scout profile PI progression (club = dominant minutes row)."""

    season: int
    performance_index: float
    club: str | None = None
    club_logo: str | None = None
    minutes_played: int | None = Field(
        default=None,
        description="Season minutes for this row; UI hides PI headline under typical radar threshold.",
    )


class PerformanceIndexHistoryResponse(BaseModel):
    """Chronological (oldest → newest), at most ``limit`` seasons with non-null PI."""

    points: list[PerformanceIndexHistoryPoint]


class XtvHistoryPoint(BaseModel):
    """Single season snapshot for scout profile xTV progression (club = dominant minutes row)."""

    season: int
    x_tv_eur: float
    club: str | None = None
    club_logo: str | None = None


class XtvHistoryResponse(BaseModel):
    """Chronological (oldest → newest), at most ``limit`` seasons with non-null xTV."""

    points: list[XtvHistoryPoint]


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
    composites: list[list[CompositeComponent]] = Field(
        default_factory=list,
        description=(
            "Optional parallel to metrics: non-empty list at index i means that slot "
            "is a composite score (metrics[i] is only a response key / label id)."
        ),
    )
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
        if self.composites and len(self.composites) != len(self.metrics):
            raise ValueError("composites length must match metrics length when provided")
        for slot in self.composites:
            if len(slot) > 8:
                raise ValueError("each composite slot supports at most 8 components")
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


AgeBand = Literal["youth", "peak", "experienced", "veteran"]


class ZoneShares(BaseModel):
    """Share of total team minutes per age band, rounded to 1dp (percent)."""

    youth: float = 0.0
    peak: float = 0.0
    experienced: float = 0.0
    veteran: float = 0.0


class MinutesDistributionPlayer(BaseModel):
    wyscout_id: int | None = None
    player: str
    player_image_url: str | None = None
    position: str | None = None
    age: int | None = None
    minutes: int
    matches: int | None = None
    league_minutes_pct: float
    age_zone: AgeBand


class MinutesDistributionResponse(BaseModel):
    """Squad minutes distribution for a single club in a single season.

    `max_league_minutes = max_league_games * 90` from the static
    `LEAGUE_MAX_GAMES` table in `core/config.py`. Multi-stage / playoff leagues
    use the regular-season game count; downstream callers clamp the per-player
    pct to 100 in case a player accrues playoff minutes on top.

    Age bands are fixed: youth (<23), peak (<29), experienced (<34),
    veteran (>=34). `zone_shares` are % of the squad's total minutes played.
    """

    club: str
    club_logo: str | None = None
    league: str | None = None
    season: int
    max_league_games: int
    max_league_minutes: int
    zone_shares: ZoneShares
    domestic_only: bool = False
    domestic_country: str | None = Field(
        default=None,
        description="Primary domestic passport label for this league (e.g. England).",
    )
    players: list[MinutesDistributionPlayer]


class LeagueClubBand(BaseModel):
    club: str
    club_logo: str | None = None
    total_minutes: int
    zone_shares: ZoneShares


class LeagueMinutesOverviewResponse(BaseModel):
    """League-wide minutes overview: one row per club, with each club's squad
    minutes broken down by age band (% of that club's total minutes). Sorted by
    youth share descending, tie-broken alphabetically by club."""

    league: str
    season: int
    max_league_games: int
    max_league_minutes: int
    domestic_only: bool = False
    domestic_country: str | None = None
    clubs: list[LeagueClubBand]


class LeagueMedianBand(BaseModel):
    """Median squad age-band shares across clubs in one league."""

    league: str
    n_clubs: int
    median_zone_shares: ZoneShares


class LeaguesMinutesOverviewResponse(BaseModel):
    """Cross-league overview: one row per league with median zone shares across
    its clubs. Sorted by ``sort_by`` band descending, tie-broken alphabetically."""

    season: int
    sort_by: AgeBand
    domestic_only: bool = False
    leagues: list[LeagueMedianBand]


# ── Scouting: Discover ────────────────────────────────────────────────────────


CohortTierLiteral = Literal["position_tier", "position_league", "position_global"]
NormalizationLiteral = Literal["zscore", "percentile"]
ArchetypeLiteral = Literal["pca_kmeans", "none"]


class ScoutingMetricSpec(BaseModel):
    metric: str
    mode: MetricModeLiteral = "as_is"
    weight: float = 1.0
    threshold_z: float | None = None


class DiscoverRequest(BaseModel):
    filters: PlayerFilters
    metrics: list[ScoutingMetricSpec] = Field(..., min_length=1, max_length=20)
    normalization: NormalizationLiteral = "zscore"
    cohort_tier: CohortTierLiteral = "position_tier"
    archetype: ArchetypeLiteral = "pca_kmeans"
    k_clusters: int = Field(4, ge=2, le=8)
    club_fit_team: str | None = None
    club_fit_weight: float = Field(0.3, ge=0.0, le=1.0)
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0, le=10_000)


class DiscoverMetricValue(BaseModel):
    metric: str
    value: float | None
    z: float | None
    percentile: float | None = None


class DiscoverRow(BaseModel):
    wyscout_id: int | None
    player: str
    club: str | None
    club_logo: str | None = None
    league: str | None
    position: str | None
    age: int | None
    minutes: int | None
    height: int | None = None
    foot: str | None = None
    passport_country: str | None = None
    contract_expires: str | None = None
    x_tv_eur: float | None = None
    player_image_url: str | None = None
    composite_score: float
    style_fit: float | None = None
    cluster_id: int | None = None
    pca_x: float | None = None
    pca_y: float | None = None
    pca_z: float | None = None
    metric_values: list[DiscoverMetricValue]


class DiscoverClusterSummary(BaseModel):
    cluster_id: int
    label: str
    n_members: int


class DiscoverCohortInfo(BaseModel):
    n: int
    tier_used: CohortTierLiteral
    min_minutes: int
    fallback_applied: bool = False


class DiscoverPCAInfo(BaseModel):
    explained_variance: list[float]
    loadings: list[list[float]]


class DiscoverResponse(BaseModel):
    rows: list[DiscoverRow]
    total: int
    cohort: DiscoverCohortInfo
    pca: DiscoverPCAInfo | None = None
    clusters: list[DiscoverClusterSummary] = Field(default_factory=list)
    silhouette: float | None = None
    metric_labels: dict[str, str] = Field(default_factory=dict)


# ── Scouting: Standouts ────────────────────────────────────────────────────────


StandoutSignalLiteral = Literal["overall", "metrics"]


class StandoutRequest(BaseModel):
    filters: PlayerFilters
    signal: StandoutSignalLiteral = "overall"
    metrics: list[ScoutingMetricSpec] = Field(default_factory=list, max_length=20)
    min_standout_z: float = Field(
        1.0,
        ge=0.0,
        le=4.0,
        description="Keep players at least this many σ above the league average.",
    )
    limit: int = Field(50, ge=1, le=200)

    @model_validator(mode="after")
    def _metrics_present(self) -> "StandoutRequest":
        if self.signal == "metrics" and not self.metrics:
            raise ValueError("signal='metrics' requires at least one metric.")
        return self


class StandoutDimension(BaseModel):
    key: str
    label: str
    value: float | None
    z: float | None
    percentile: float | None = None


class StandoutRow(BaseModel):
    wyscout_id: int | None
    player: str
    club: str | None
    club_logo: str | None = None
    league: str | None
    position: str | None
    age: int | None
    minutes: int | None
    player_image_url: str | None = None
    performance_index: float | None = None
    standout_score: float
    dimensions: list[StandoutDimension] = Field(default_factory=list)


class StandoutResponse(BaseModel):
    rows: list[StandoutRow]
    total: int
    league: str | None = None
    cohort_n: int
    min_minutes: int
    signal: StandoutSignalLiteral
    distribution: list[float] = Field(default_factory=list)
    league_mean: float | None = None
    league_sd: float | None = None
    metric_labels: dict[str, str] = Field(default_factory=dict)


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


# ── Squad value (team economic/demographic aggregates) ─────────────────────────


class SquadValueTeamRow(BaseModel):
    """Squad-level aggregates for one club in one season."""

    club: str
    club_logo: str | None = None
    league: str | None = None
    n_players: int
    avg_age: float | None = None
    total_xtv_eur: float | None = None
    avg_xtv_eur: float | None = None
    total_market_value_eur: float | None = None
    avg_market_value_eur: float | None = None
    foreign_share: float | None = Field(
        default=None,
        description="Share (0-1) of players whose Passport country differs from the modal squad passport.",
    )
    n_players_500: int = Field(
        default=0,
        description="Players with at least 500 minutes (quality cohort for PI / xTV z-score).",
    )
    avg_performance_index: float | None = Field(
        default=None,
        description="Mean performance_index among players with >= 500 minutes.",
    )
    squad_xtv_zscore: float | None = Field(
        default=None,
        description="Z-score of total squad xTV (500+ min cohort) vs league mean.",
    )


class SquadValueLeagueResponse(BaseModel):
    season: int
    league: str
    xtv_supported: bool = Field(
        default=True,
        description="False when xTV is not offered for this league (e.g. Campeonato de Portugal).",
    )
    teams: list[SquadValueTeamRow]


class SquadValueHistoryRow(SquadValueTeamRow):
    season: int


class SquadValueHistoryResponse(BaseModel):
    club: str
    xtv_supported: bool = Field(
        default=True,
        description="False when the club has no xTV-eligible seasons in the response.",
    )
    rows: list[SquadValueHistoryRow]
