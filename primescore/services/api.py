"""Minimal API-Football client used by the current PrimeScore app."""

import logging
import time as _time
from typing import Optional
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import FOOTBALL_API_BASE, FOOTBALL_API_KEY, FOOTBALL_API_TIMEOUT

logger = logging.getLogger(__name__)

if not FOOTBALL_API_KEY:
    raise ValueError(
        "FOOTBALL_API_KEY is not set. "
        "Check your config before starting the app."
    )

ENDPOINTS = {
    "fixtures":    "fixtures",
    "matches":     "fixtures",            # alias for "fixtures"
    "headtohead":  "fixtures/headtohead",
    "events":      "fixtures/events",
    "lineups":     "fixtures/lineups",
    "statistics":  "fixtures/statistics",
    "teams":       "teams",
    "players":     "players",
    "standings":   "standings",
    "leagues":     "leagues",
    "injuries":    "injuries",
    "predictions": "predictions",
}


_MAX_MATCHES_DEFAULT = 10

FINISHED_STATUSES = frozenset({"FT", "AET", "PEN"})

_response_cache: dict = {}

_CACHE_TTL_BY_ENDPOINT: dict = {
    "fixtures":    300,      # 5 min  – live scores, upcoming, results
    "matches":     300,      # 5 min  – alias for fixtures
    "standings":   3600,     # 1 hour – league tables
    "teams":       86400,    # 24 h   – team info / search
    "players":     86400,    # 24 h   – player info / squad lists
    "leagues":     86400,    # 24 h   – league search / resolve
    "injuries":    1800,     # 30 min
    "predictions": 1800,     # 30 min
}
_CACHE_TTL_DEFAULT: int = 300


def _cache_ttl_for(endpoint: str) -> int:
    return _CACHE_TTL_BY_ENDPOINT.get(endpoint, _CACHE_TTL_DEFAULT)


def _cache_get(key: tuple) -> Optional[dict]:
    entry = _response_cache.get(key)
    if not entry:
        return None
    endpoint = key[0]
    if (_time.monotonic() - entry["ts"]) < _cache_ttl_for(endpoint):
        return entry["data"]
    return None


def _cache_set(key: tuple, data: dict) -> None:
    _response_cache[key] = {"data": data, "ts": _time.monotonic()}


def _build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist={500, 502, 503, 504},
        allowed_methods={"GET"},
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


_session = _build_session()


def _headers() -> dict:
    if "api-sports.io" in FOOTBALL_API_BASE:
        return {
            "x-apisports-key": FOOTBALL_API_KEY,
            "Accept": "application/json",
        }

    host = urlparse(FOOTBALL_API_BASE).netloc
    return {
        "x-rapidapi-key": FOOTBALL_API_KEY,
        "x-rapidapi-host": host,
        "Accept": "application/json",
    }


def _safe(d: Optional[dict], *keys: str, default: int = 0) -> int:
    """Return the value at the given key path, or *default* if any key is absent or None."""
    for k in keys:
        d = (d or {}).get(k)
    return d if d is not None else default


def _log_rate_limit(response: requests.Response) -> None:
    remaining = response.headers.get("x-ratelimit-requests-remaining")
    limit = response.headers.get("x-ratelimit-requests-limit")
    if remaining is not None and limit is not None:
        logger.debug("API quota: %s / %s requests remaining", remaining, limit)
        if int(remaining) < 10:
            logger.warning(
                "API quota running low: %s of %s requests remaining today.",
                remaining,
                limit,
            )


def call_football_api(
    endpoint: str,
    params: Optional[dict] = None,
) -> Optional[dict]:
    api_path = ENDPOINTS.get(endpoint)
    if not api_path:
        logger.error("Unsupported endpoint: %s", endpoint)
        return None

    cache_key = (endpoint, tuple(sorted((params or {}).items())))
    cached = _cache_get(cache_key)
    if cached is not None:
        logger.debug("Cache hit for %s %s", endpoint, params)
        return cached

    url = f"{FOOTBALL_API_BASE}/{api_path}"

    try:
        response = _session.get(
            url,
            headers=_headers(),
            params=params or {},
            timeout=FOOTBALL_API_TIMEOUT,
        )
        logger.info("API %s status=%s params=%s", url, response.status_code, params or {})
        _log_rate_limit(response)
    except requests.exceptions.RequestException as error:
        logger.error("API request failed: %s - %s", type(error).__name__, error)
        return None

    if response.status_code != 200:
        logger.error("API request failed with status %s", response.status_code)
        return None

    try:
        data = response.json()
    except ValueError:
        logger.error("Non-JSON response from API (status %s)", response.status_code)
        return None

    if data.get("errors"):
        logger.error("API-Football errors: %s", data["errors"])
        if "rateLimit" in data["errors"]:
            return {"_error": "rate_limit", "errors": data["errors"]}
        return None

    _cache_set(cache_key, data)
    return data


def format_standings(
    data: Optional[dict],
    group_index: int = 0,
) -> dict:
    if not data or not data.get("response"):
        return {"competition": "Unknown", "season": "", "standings": []}

    league = data["response"][0].get("league", {})
    standings_groups = league.get("standings", [])

    if standings_groups and not (0 <= group_index < len(standings_groups)):
        raise ValueError(
            f"group_index {group_index} is out of range "
            f"(competition has {len(standings_groups)} group(s))."
        )

    if len(standings_groups) > 1:
        logger.warning(
            "Multiple standings groups found (%d); returning group %d. "
            "Pass group_index to select a different group.",
            len(standings_groups),
            group_index,
        )

    standings = standings_groups[group_index] if standings_groups else []

    return {
        "competition": league.get("name", "Unknown"),
        "season": str(league.get("season", "")),
        "standings": [
            {
                "position":        team.get("rank"),
                "team":            (team.get("team") or {}).get("name", "Unknown"),
                "team_crest":      (team.get("team") or {}).get("logo"),
                "played":          _safe(team, "all", "played"),
                "won":             _safe(team, "all", "win"),
                "drawn":           _safe(team, "all", "draw"),
                "lost":            _safe(team, "all", "lose"),
                "goals_for":       _safe(team, "all", "goals", "for"),
                "goals_against":   _safe(team, "all", "goals", "against"),
                "goal_difference": team.get("goalsDiff", 0),
                "points":          team.get("points", 0),
            }
            for team in standings
        ],
    }


def compute_team_stats(
    team_id: int,
    team: dict,
    matches_data: Optional[dict],
    max_matches: int = _MAX_MATCHES_DEFAULT,
) -> dict:
    stats = {
        "team_id":        team_id,
        "team_name":      team.get("name", "Unknown"),
        "team_crest":     team.get("logo"),
        "matches_played": 0,
        "wins":           0,
        "draws":          0,
        "losses":         0,
        "goals_scored":   0,
        "goals_conceded": 0,
        "clean_sheets":   0,
    }

    for match in (matches_data or {}).get("response", [])[:max_matches]:
        fixture = match.get("fixture", {})
        status = (fixture.get("status") or {}).get("short")
        if status not in FINISHED_STATUSES:
            continue

        teams = match.get("teams", {})
        goals = match.get("goals", {})
        is_home = ((teams.get("home") or {}).get("id")) == team_id

        home_goals = goals.get("home") or 0
        away_goals = goals.get("away") or 0

        goals_for     = home_goals if is_home else away_goals
        goals_against = away_goals if is_home else home_goals

        stats["matches_played"] += 1
        stats["goals_scored"]   += goals_for
        stats["goals_conceded"] += goals_against

        if goals_against == 0:
            stats["clean_sheets"] += 1
        if goals_for > goals_against:
            stats["wins"] += 1
        elif goals_for < goals_against:
            stats["losses"] += 1
        else:
            stats["draws"] += 1

    return stats
