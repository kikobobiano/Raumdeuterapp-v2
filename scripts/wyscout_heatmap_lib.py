"""Helpers for fetching Wyscout `playerHeatmap` GraphQL responses.

Used by `scripts/download_heatmaps.py`. Pure functions — no parquet I/O,
no global state. Keeps the main script readable and the logic testable.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Iterable

# Same operation name + query string as the curl example from the user.
HEATMAP_QUERY = (
    "query Player($playerId: ID!, $timeframe: TimeframeEnum, "
    "$timeframeYouthMode: Boolean, $timeframeCompetitionId: ID) {\n"
    "  playerHeatmap(playerId: $playerId, timeframe: $timeframe, "
    "timeframeYouthMode: $timeframeYouthMode, "
    "timeframeCompetitionId: $timeframeCompetitionId) {\n"
    "    points {\n      x\n      y\n      count\n      __typename\n    }\n"
    "    __typename\n  }\n}\n"
)

GRAPHQL_URL = "https://searchapi.wyscout.com/graphql"

REQUEST_HEADERS = {
    "accept": "*/*",
    "content-type": "application/json",
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "origin": "https://wyscout-apps.hudl.com",
    "referer": "https://wyscout-apps.hudl.com/",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
    ),
}


@dataclass(frozen=True)
class HeatmapPoint:
    x: float
    y: float
    count: int


@dataclass(frozen=True)
class HeatmapFetchResult:
    wyscout_id: int
    competition_id: int
    points: tuple[HeatmapPoint, ...]


def build_graphql_url(*, token: str, group_id: str, subgroup_id: str) -> str:
    qs = urllib.parse.urlencode(
        {"token": token, "groupId": group_id, "subgroupId": subgroup_id}
    )
    return f"{GRAPHQL_URL}?{qs}"


def build_body(*, wyscout_id: int, competition_id: int) -> bytes:
    payload = {
        "operationName": "Player",
        "variables": {
            "playerId": wyscout_id,
            "timeframeYouthMode": False,
            "timeframeCompetitionId": competition_id,
        },
        "query": HEATMAP_QUERY,
    }
    return json.dumps(payload).encode("utf-8")


def parse_points(payload: object) -> tuple[HeatmapPoint, ...]:
    """Extract `data.playerHeatmap.points` from a GraphQL response.

    Returns an empty tuple when the player has no heatmap (Wyscout returns
    ``{"data": {"playerHeatmap": null}}`` for players with no minutes).
    Raises ``ValueError`` if the shape is unexpected (so the caller can
    retry / log).
    """
    if not isinstance(payload, dict):
        raise ValueError("response is not a JSON object")
    data = payload.get("data")
    if not isinstance(data, dict):
        raise ValueError("missing `data` key")
    heatmap = data.get("playerHeatmap")
    if heatmap is None:
        return ()
    if not isinstance(heatmap, dict):
        raise ValueError("`playerHeatmap` is not an object")
    points = heatmap.get("points")
    if points is None:
        return ()
    if not isinstance(points, list):
        raise ValueError("`points` is not a list")
    out: list[HeatmapPoint] = []
    for p in points:
        if not isinstance(p, dict):
            continue
        try:
            out.append(
                HeatmapPoint(
                    x=float(p["x"]),
                    y=float(p["y"]),
                    count=int(p["count"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return tuple(out)


def fetch_one(
    *,
    url: str,
    wyscout_id: int,
    competition_id: int,
    timeout_sec: int = 30,
    max_retries: int = 3,
    retry_backoff_sec: float = 6.0,
) -> HeatmapFetchResult:
    """POST GraphQL request with linear backoff on HTTP 429/5xx.

    Raises the last exception on persistent failure so the main loop can
    log it and move on (without writing a partial row).
    """
    body = build_body(wyscout_id=wyscout_id, competition_id=competition_id)
    req = urllib.request.Request(
        url, data=body, headers=REQUEST_HEADERS, method="POST"
    )

    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                raw = resp.read().decode("utf-8")
            payload = json.loads(raw)
            points = parse_points(payload)
            return HeatmapFetchResult(
                wyscout_id=wyscout_id,
                competition_id=competition_id,
                points=points,
            )
        except urllib.error.HTTPError as e:
            last_exc = e
            if e.code not in (429, 500, 502, 503, 504):
                raise
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            last_exc = e

        if attempt < max_retries - 1:
            time.sleep(retry_backoff_sec)

    assert last_exc is not None
    raise last_exc


def iter_todo(
    pairs: Iterable[tuple[int, int]],
    already_done: set[tuple[int, int]],
) -> list[tuple[int, int]]:
    """Filter input (wyscout_id, competition_id) pairs against a cache set."""
    return [p for p in pairs if p not in already_done]
