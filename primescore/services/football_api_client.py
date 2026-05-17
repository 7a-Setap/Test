"""Minimal API-Football client used by the current PrimeScore app."""

from copy import deepcopy
import logging
import re
import time

import requests

from config import FOOTBALL_API_BASE, FOOTBALL_API_KEY, FOOTBALL_API_TIMEOUT

logger = logging.getLogger(__name__)

ENDPOINTS = {
    "fixtures": "fixtures",
    "matches": "fixtures",
    "fixture_statistics": "fixtures/statistics",
    "fixture_events": "fixtures/events",
    "fixture_lineups": "fixtures/lineups",
    "fixture_h2h": "fixtures/headtohead",
    "teams": "teams",
    "players": "players",
    "player_profiles": "players/profiles",
    "player_squads": "players/squads",
    "standings": "standings",
    "leagues": "leagues",
    "team_statistics": "teams/statistics",
}

API_CACHE = {}
RATE_LIMIT_BACKOFF_UNTIL = 0.0
RATE_LIMIT_BACKOFF_SECONDS = 20


def is_rate_limited_response(data):
    return bool(data and data.get("_error") == "rate_limit")


def is_in_backoff():
    """Return True if the rate-limit backoff window is still active."""
    return RATE_LIMIT_BACKOFF_UNTIL > time.time()


def reset_api_client_state():
    """Clear in-memory API cache and rate-limit backoff state."""

    global RATE_LIMIT_BACKOFF_UNTIL
    API_CACHE.clear()
    RATE_LIMIT_BACKOFF_UNTIL = 0.0


def _headers():
    if "api-sports.io" in FOOTBALL_API_BASE:
        return {
            "x-apisports-key": FOOTBALL_API_KEY,
        }

    host = FOOTBALL_API_BASE.replace("https://", "").split("/")[0]
    return {
        "x-rapidapi-key": FOOTBALL_API_KEY,
        "x-rapidapi-host": host,
    }


def _clean_params(params):
    return {
        key: value
        for key, value in (params or {}).items()
        if value not in (None, "", [])
    }


def _cache_key(endpoint, params):
    cleaned_params = _clean_params(params)
    return (
        endpoint,
        tuple(sorted((str(key), str(value)) for key, value in cleaned_params.items())),
    )


def _cache_ttl(endpoint, params):
    cleaned_params = _clean_params(params)

    if endpoint == "standings":
        return 300
    if endpoint == "fixtures":
        if cleaned_params.get("live"):
            return 15
        if cleaned_params.get("next") or cleaned_params.get("last"):
            return 60
        if cleaned_params.get("status") in ("NS", "FT"):
            return 60
        return 30
    if endpoint == "matches":
        if cleaned_params.get("next") or cleaned_params.get("last"):
            return 60
        if cleaned_params.get("status") in ("FT", "NS"):
            return 60
        return 30
    if endpoint == "fixture_statistics":
        return 300
    if endpoint == "fixture_events":
        return 30
    if endpoint == "fixture_lineups":
        # Lineups change rarely once published — 5 minutes is enough churn
        # for substitution-after-the-fact corrections without hammering the
        # API when the user toggles a card open and closed.
        return 300
    if endpoint == "fixture_h2h":
        # Historical head-to-head records — only change when the two teams
        # play again. 30 minutes is generous and saves repeat clicks.
        return 1800
    if endpoint in ("teams", "player_profiles", "player_squads"):
        return 300
    if endpoint == "players":
        return 180
    if endpoint == "leagues":
        return 1800
    if endpoint == "team_statistics":
        return 300
    return 0


def _get_cached_response(endpoint, params):
    key = _cache_key(endpoint, params)
    cached_entry = API_CACHE.get(key)
    if not cached_entry:
        return None

    if cached_entry["expires_at"] <= time.time():
        API_CACHE.pop(key, None)
        return None

    logger.info("API Cache hit %s params=%s", f"{FOOTBALL_API_BASE}/{ENDPOINTS[endpoint]}", _clean_params(params))
    return deepcopy(cached_entry["data"])


def _set_cached_response(endpoint, params, data):
    ttl_seconds = _cache_ttl(endpoint, params)
    if ttl_seconds <= 0:
        return

    API_CACHE[_cache_key(endpoint, params)] = {
        "data": deepcopy(data),
        "expires_at": time.time() + ttl_seconds,
    }


def _activate_rate_limit_backoff(seconds=None):
    global RATE_LIMIT_BACKOFF_UNTIL
    RATE_LIMIT_BACKOFF_UNTIL = time.time() + (seconds if seconds is not None else RATE_LIMIT_BACKOFF_SECONDS)


def _log_quota_headers(response):
    """Surface API-Football's daily quota headers in the server log.

    The response carries x-ratelimit-requests-remaining and -limit on every
    successful call. When the remaining count hits 0 the next call will 429
    and the per-minute backoff won't help — we extend it to an hour so we
    stop hammering the dead endpoint until the daily window resets.
    """
    remaining_raw = response.headers.get("x-ratelimit-requests-remaining")
    limit_raw = response.headers.get("x-ratelimit-requests-limit")
    if remaining_raw is None or limit_raw is None:
        return

    try:
        remaining = int(remaining_raw)
        daily_limit = int(limit_raw)
    except (TypeError, ValueError):
        return

    if remaining <= 0:
        logger.warning(
            "API-Football DAILY QUOTA EXHAUSTED — %s/%s requests used. "
            "All calls will 429 until the daily window resets (midnight UTC). "
            "Extending backoff to 1 hour.",
            daily_limit, daily_limit,
        )
        _activate_rate_limit_backoff(seconds=3600)
    elif remaining <= 10:
        logger.warning(
            "API-Football quota running low: %s of %s requests remaining today.",
            remaining, daily_limit,
        )
    else:
        logger.info("API quota: %s / %s requests remaining today.", remaining, daily_limit)


def _rate_limit_payload():
    retry_after_seconds = max(0, int(RATE_LIMIT_BACKOFF_UNTIL - time.time()))
    return {
        "_error": "rate_limit",
        "status_code": 429,
        "retry_after": retry_after_seconds,
    }


def _request_api_json(api_path, cleaned_params):
    if RATE_LIMIT_BACKOFF_UNTIL > time.time():
        logger.warning("Skipping API request during rate-limit backoff: %s params=%s", api_path, cleaned_params)
        return _rate_limit_payload()

    try:
        response = requests.get(
            f"{FOOTBALL_API_BASE}/{api_path}",
            headers=_headers(),
            params=cleaned_params,
            timeout=FOOTBALL_API_TIMEOUT,
        )
        logger.info("API Request %s params=%s -> %s", f"{FOOTBALL_API_BASE}/{api_path}", cleaned_params, response.status_code)
    except Exception as error:
        logger.error("API request failed: %s - %s", type(error).__name__, error)
        return None

    # Log quota state on every response (200 or 429 — both carry the headers).
    # This will trigger the long backoff automatically when remaining hits 0.
    _log_quota_headers(response)

    if response.status_code == 429:
        # Distinguish daily-quota 429s from per-minute 429s for clearer logs.
        remaining_raw = response.headers.get("x-ratelimit-requests-remaining")
        if remaining_raw == "0":
            logger.error("API request 429 — daily quota exhausted.")
        else:
            logger.error("API request 429 — per-minute rate limit hit.")
            _activate_rate_limit_backoff()
        return _rate_limit_payload()

    if response.status_code != 200:
        logger.error("API request failed with status %s", response.status_code)
        return None

    try:
        data = response.json()
    except ValueError:
        logger.error("API response was not valid JSON")
        return None

    return data


def _extract_plan_supported_season_range(errors):
    if not isinstance(errors, dict):
        return None

    plan_message = str(errors.get("plan") or "")
    if not plan_message or "season" not in plan_message.lower():
        return None

    years = [int(year) for year in re.findall(r"\b(20\d{2})\b", plan_message)]
    if not years:
        return None

    return min(years), max(years)


def _season_retry_params(cleaned_params, errors):
    if "season" not in cleaned_params:
        return []

    supported_range = _extract_plan_supported_season_range(errors)
    if not supported_range:
        return []

    try:
        requested_season = int(cleaned_params["season"])
    except (TypeError, ValueError):
        return []

    minimum_supported, maximum_supported = supported_range
    highest_retry_season = min(maximum_supported, requested_season)
    if highest_retry_season < minimum_supported:
        highest_retry_season = maximum_supported

    return [
        {**cleaned_params, "season": season}
        for season in range(highest_retry_season, minimum_supported - 1, -1)
        if season != requested_season
    ]


def _is_rate_limit_error(errors):
    if isinstance(errors, dict):
        return "rateLimit" in errors
    if isinstance(errors, list):
        return any(str(item) == "rateLimit" for item in errors)
    return False


def call_football_api(endpoint, params=None):
    api_path = ENDPOINTS.get(endpoint)
    if not api_path:
        logger.error("Unsupported endpoint: %s", endpoint)
        return None

    original_params = _clean_params(params)
    attempted_keys = set()
    params_to_try = [original_params]

    while params_to_try:
        cleaned_params = params_to_try.pop(0)
        current_cache_key = _cache_key(endpoint, cleaned_params)
        if current_cache_key in attempted_keys:
            continue
        attempted_keys.add(current_cache_key)

        cached_response = _get_cached_response(endpoint, cleaned_params)
        if cached_response is not None:
            if cleaned_params != original_params:
                _set_cached_response(endpoint, original_params, cached_response)
            return cached_response

        data = _request_api_json(api_path, cleaned_params)
        if is_rate_limited_response(data):
            return data
        if not data:
            return None

        if data.get("errors"):
            if _is_rate_limit_error(data["errors"]):
                _activate_rate_limit_backoff()
                rate_limit_data = _rate_limit_payload()
                rate_limit_data["errors"] = data["errors"]
                return rate_limit_data

            retry_params = _season_retry_params(cleaned_params, data["errors"])
            if retry_params:
                logger.warning(
                    "Retrying %s with supported season fallback %s after API-Football plan error",
                    api_path,
                    [candidate["season"] for candidate in retry_params],
                )
                params_to_try = retry_params + params_to_try
                continue

            logger.error("API-Football errors: %s", data["errors"])
            return None

        _set_cached_response(endpoint, cleaned_params, data)
        if cleaned_params != original_params:
            _set_cached_response(endpoint, original_params, data)
        return data

    return None


def format_standings(data):
    if not data or not data.get("response"):
        return {"competition": "Unknown", "season": "", "standings": []}

    league = data["response"][0].get("league", {})
    standings_groups = league.get("standings", [])
    standings = standings_groups[0] if standings_groups else []

    return {
        "competition": league.get("name", "Unknown"),
        "season": str(league.get("season", "")),
        "standings": [
            {
                "position": team.get("rank"),
                "team": (team.get("team") or {}).get("name", "Unknown"),
                "team_crest": (team.get("team") or {}).get("logo"),
                "played": (team.get("all") or {}).get("played", 0),
                "won": (team.get("all") or {}).get("win", 0),
                "drawn": (team.get("all") or {}).get("draw", 0),
                "lost": (team.get("all") or {}).get("lose", 0),
                "goals_for": ((team.get("all") or {}).get("goals") or {}).get("for", 0),
                "goals_against": ((team.get("all") or {}).get("goals") or {}).get("against", 0),
                "goal_difference": team.get("goalsDiff", 0),
                "points": team.get("points", 0),
            }
            for team in standings
        ],
    }


def compute_team_stats(team_id, team, matches_data):
    stats = {
        "team_id": team_id,
        "team_name": team.get("name", "Unknown"),
        "team_crest": team.get("logo"),
        "matches_played": 0,
        "wins": 0,
        "draws": 0,
        "losses": 0,
        "goals_scored": 0,
        "goals_conceded": 0,
        "clean_sheets": 0,
    }

    finished_matches = []
    for match in (matches_data or {}).get("response", []):
        fixture = match.get("fixture", {})
        status = (fixture.get("status") or {}).get("short")
        if status not in ("FT", "AET", "PEN"):
            continue
        finished_matches.append(match)

    finished_matches.sort(
        key=lambda match: ((match.get("fixture") or {}).get("date") or ""),
        reverse=True,
    )

    for match in finished_matches[:10]:
        fixture = match.get("fixture", {})

        teams = match.get("teams", {})
        goals = match.get("goals", {})
        is_home = ((teams.get("home") or {}).get("id")) == team_id
        goals_for = goals.get("home", 0) if is_home else goals.get("away", 0)
        goals_against = goals.get("away", 0) if is_home else goals.get("home", 0)

        stats["matches_played"] += 1
        stats["goals_scored"] += goals_for or 0
        stats["goals_conceded"] += goals_against or 0

        if goals_against == 0:
            stats["clean_sheets"] += 1
        if goals_for > goals_against:
            stats["wins"] += 1
        elif goals_for < goals_against:
            stats["losses"] += 1
        else:
            stats["draws"] += 1

    return stats
