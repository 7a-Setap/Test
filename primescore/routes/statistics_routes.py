"""Statistics routes used by standings and compare pages."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import time

from flask import Blueprint, jsonify, request

from config import CURRENT_SEASON
from services.football_api_client import call_football_api, compute_team_stats, format_standings

stats_bp = Blueprint("stats", __name__)

LEAGUE_MAP = {
    "PL": 39,
    "CL": 2,
    "BL1": 78,
    "SA": 135,
    "PD": 140,
    "FL1": 61,
}

TEAM_ADVANCED_STAT_LABELS = {
    "average_possession": "Ball Possession",
    "average_shots": "Total Shots",
    "average_shots_on_target": "Shots on Goal",
    "average_fouls_committed": "Fouls",
    "average_corners": "Corner Kicks",
}
TEAM_STATS_CACHE = {}
PLAYER_STATS_CACHE = {}
STATISTICS_CACHE_TTL_SECONDS = 180


def _league_id(value):
    return LEAGUE_MAP.get(value, value)


def reset_statistics_route_caches():
    TEAM_STATS_CACHE.clear()
    PLAYER_STATS_CACHE.clear()


def _cache_entry(cache_store, cache_key):
    cached_entry = cache_store.get(cache_key)
    if not cached_entry:
        return None

    if cached_entry["expires_at"] <= time.time():
        cache_store.pop(cache_key, None)
        return None

    return deepcopy(cached_entry["payload"])


def _store_cache_entry(cache_store, cache_key, payload):
    cache_store[cache_key] = {
        "payload": deepcopy(payload),
        "expires_at": time.time() + STATISTICS_CACHE_TTL_SECONDS,
    }


def _today_string():
    return datetime.now(timezone.utc).date().isoformat()


def _date_offset_string(days):
    return (datetime.now(timezone.utc).date() + timedelta(days=days)).isoformat()


def _safe_total(node, *path):
    current = node
    for key in path:
        if not isinstance(current, dict):
            return 0
        current = current.get(key)
    return current or 0


def _extract_league_id_from_standings(data):
    response_items = (data or {}).get("response") or []
    if not response_items:
        return None
    return (response_items[0].get("league") or {}).get("id")


def _extract_league_id_from_leagues(data):
    response_items = (data or {}).get("response") or []
    if not response_items:
        return None

    preferred_item = next(
        (
            item
            for item in response_items
            if str((item.get("league") or {}).get("type", "")).lower() == "league"
        ),
        response_items[0],
    )
    return (preferred_item.get("league") or {}).get("id")


def _empty_team_advanced_stats():
    return {
        "advanced_stats_matches": 0,
        "average_possession": 0.0,
        "average_shots": 0.0,
        "average_shots_on_target": 0.0,
        "average_fouls_committed": 0.0,
        "average_corners": 0.0,
    }


def _coerce_stat_number(raw_value):
    if raw_value in (None, ""):
        return 0.0
    if isinstance(raw_value, (int, float)):
        return float(raw_value)

    cleaned_value = str(raw_value).replace("%", "").strip()
    try:
        return float(cleaned_value)
    except ValueError:
        return 0.0


def _extract_fixture_stat(statistics_items, stat_label):
    for item in statistics_items or []:
        if str(item.get("type") or "").strip().lower() == stat_label.lower():
            return _coerce_stat_number(item.get("value"))
    return 0.0


def _recent_finished_matches(matches_data, limit=10):
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
    return finished_matches[:limit]


def _collect_recent_team_advanced_stats(team_id, matches_data, limit=5):
    totals = {key: 0.0 for key in TEAM_ADVANCED_STAT_LABELS}
    sample_count = 0

    for match in _recent_finished_matches(matches_data, limit=limit):
        fixture_id = (match.get("fixture") or {}).get("id")
        if not fixture_id:
            continue

        fixture_stats = call_football_api("fixture_statistics", {"fixture": fixture_id})
        if not fixture_stats or fixture_stats.get("_error"):
            continue

        team_stats = next(
            (
                item
                for item in (fixture_stats.get("response") or [])
                if str((item.get("team") or {}).get("id")) == str(team_id)
            ),
            None,
        )
        if not team_stats:
            continue

        statistics_items = team_stats.get("statistics") or []
        sample_count += 1
        for key, label in TEAM_ADVANCED_STAT_LABELS.items():
            totals[key] += _extract_fixture_stat(statistics_items, label)

    if sample_count == 0:
        return _empty_team_advanced_stats()

    averaged_stats = {
        key: round(total / sample_count, 1)
        for key, total in totals.items()
    }
    return {
        "advanced_stats_matches": sample_count,
        **averaged_stats,
    }


def _merge_team_stats(base_stats, advanced_stats=None):
    merged_stats = {**(base_stats or {})}
    merged_stats.update(_empty_team_advanced_stats())
    if advanced_stats:
        merged_stats.update(advanced_stats)
    return merged_stats


def _resolve_team_league_id(team_id, requested_league=None):
    if requested_league:
        return _league_id(requested_league)

    standings_data = call_football_api("standings", {"team": team_id, "season": CURRENT_SEASON})
    league_id = _extract_league_id_from_standings(standings_data)
    if league_id:
        return league_id

    leagues_data = call_football_api("leagues", {"team": team_id, "season": CURRENT_SEASON})
    return _extract_league_id_from_leagues(leagues_data)


def _format_official_team_statistics(team_id, stats_data):
    response_payload = (stats_data or {}).get("response") or {}
    if not response_payload:
        return None

    team = response_payload.get("team") or {}
    fixtures = response_payload.get("fixtures") or {}
    goals = response_payload.get("goals") or {}
    clean_sheet = response_payload.get("clean_sheet") or {}

    return {
        "team_id": team.get("id", team_id),
        "team_name": team.get("name", f"Team {team_id}"),
        "team_crest": team.get("logo"),
        "matches_played": _safe_total(fixtures, "played", "total"),
        "wins": _safe_total(fixtures, "wins", "total"),
        "draws": _safe_total(fixtures, "draws", "total"),
        "losses": _safe_total(fixtures, "loses", "total"),
        "goals_scored": _safe_total(goals, "for", "total", "total"),
        "goals_conceded": _safe_total(goals, "against", "total", "total"),
        "clean_sheets": clean_sheet.get("total", 0) or 0,
    }


def _sum_player_stats(statistics_list):
    """Aggregate statistics across multiple team/competition entries for a player."""
    totals = {
        "goals": 0, "assists": 0, "appearances": 0, "minutes": 0,
        "shots": 0, "shots_on_target": 0, "fouls_committed": 0,
        "yellow_cards": 0, "red_cards": 0,
    }
    ratings = []
    position = None
    current_team = None

    for stat in statistics_list:
        games = stat.get("games") or {}
        goals_data = stat.get("goals") or {}
        cards_data = stat.get("cards") or {}
        shots_data = stat.get("shots") or {}
        fouls_data = stat.get("fouls") or {}

        # API-Football uses the misspelled key "appearences" (not "appearances")
        totals["appearances"] += games.get("appearences") or 0
        totals["minutes"] += games.get("minutes") or 0
        totals["goals"] += goals_data.get("total") or 0
        totals["assists"] += goals_data.get("assists") or 0
        totals["shots"] += shots_data.get("total") or 0
        totals["shots_on_target"] += shots_data.get("on") or 0
        totals["fouls_committed"] += fouls_data.get("committed") or 0
        totals["yellow_cards"] += cards_data.get("yellow") or 0
        totals["red_cards"] += cards_data.get("red") or 0

        rating = games.get("rating")
        if rating:
            try:
                ratings.append(float(rating))
            except (ValueError, TypeError):
                pass

        if not position and games.get("position"):
            position = games["position"]
        if not current_team:
            team_name = (stat.get("team") or {}).get("name")
            if team_name:
                current_team = team_name

    totals["rating"] = f"{sum(ratings) / len(ratings):.2f}" if ratings else ""
    return totals, position, current_team


def _format_player_statistics_payload(player_id, player_data):
    player = player_data.get("player", {})
    statistics = (player_data.get("statistics") or [{}])[0]

    return {
        "player_id": player_id,
        "player_name": player.get("name", "Unknown"),
        "current_team": (statistics.get("team") or {}).get("name"),
        "position": (statistics.get("games") or {}).get("position"),
        "statistics": {
            "goals": (statistics.get("goals") or {}).get("total", 0) or 0,
            "assists": (statistics.get("goals") or {}).get("assists", 0) or 0,
            "appearances": (statistics.get("games") or {}).get("appearences", 0) or 0,
            "minutes": (statistics.get("games") or {}).get("minutes", 0) or 0,
            "rating": (statistics.get("games") or {}).get("rating", "") or "",
            "shots": (statistics.get("shots") or {}).get("total", 0) or 0,
            "shots_on_target": (statistics.get("shots") or {}).get("on", 0) or 0,
            "fouls_committed": (statistics.get("fouls") or {}).get("committed", 0) or 0,
            "yellow_cards": (statistics.get("cards") or {}).get("yellow", 0) or 0,
            "red_cards": (statistics.get("cards") or {}).get("red", 0) or 0,
        },
    }


@stats_bp.route("/leagues/<league_id>/standings", methods=["GET"])
def get_league_standings(league_id):
    data = call_football_api("standings", {"league": _league_id(league_id), "season": CURRENT_SEASON})
    return jsonify(format_standings(data)), 200


@stats_bp.route("/standings/lookup", methods=["GET"])
def standings_lookup():
    league_id = request.args.get("league", "PL")
    data = call_football_api("standings", {"league": _league_id(league_id), "season": CURRENT_SEASON})
    formatted = format_standings(data)

    return jsonify(
        {
            "competition": formatted.get("competition", str(league_id)),
            "season": formatted.get("season", str(CURRENT_SEASON)),
            "standings": formatted.get("standings", []),
        }
    ), 200


@stats_bp.route("/teams/<int:team_id>/statistics", methods=["GET"])
def get_team_statistics(team_id):
    team_name = (request.args.get("name") or "").strip()
    requested_league = (request.args.get("league") or "").strip()
    cache_key = (int(team_id), str(requested_league or "").upper(), int(CURRENT_SEASON))
    cached_payload = _cache_entry(TEAM_STATS_CACHE, cache_key)
    if cached_payload is not None:
        return jsonify(cached_payload), 200

    team_data = call_football_api("teams", {"id": team_id})
    team = None
    if team_data and team_data.get("response"):
        team = team_data["response"][0].get("team", {})

    if not team and team_name:
        resolved_team = call_football_api("teams", {"search": team_name})
        if resolved_team and resolved_team.get("response"):
            team = resolved_team["response"][0].get("team", {})
            team_id = team.get("id", team_id)

    team = team or {"id": team_id, "name": team_name or f"Team {team_id}"}

    recent_match_params = {
        "team": team_id,
        "season": CURRENT_SEASON,
        "status": "FT-AET-PEN",
    }
    if requested_league:
        recent_match_params["league"] = _league_id(requested_league)

    matches_data = call_football_api("matches", recent_match_params)
    recent_stats = compute_team_stats(team_id, team, matches_data)

    # FR7: aggregate per-match advanced metrics (possession, shots, shots on
    # target, fouls, corners) from the most recent finished fixtures. This
    # costs ~3 extra API calls per request — bounded so we don't blow the
    # rate limit, and the whole response is cached for 3 minutes anyway.
    advanced_stats = _collect_recent_team_advanced_stats(
        team_id, matches_data, limit=3,
    )

    if recent_stats["matches_played"] > 0:
        response_payload = _merge_team_stats(recent_stats, advanced_stats)
        _store_cache_entry(TEAM_STATS_CACHE, cache_key, response_payload)
        return jsonify(response_payload), 200

    league_id = _resolve_team_league_id(team_id, requested_league=requested_league)
    if league_id:
        official_stats = call_football_api(
            "team_statistics",
            {
                "team": team_id,
                "league": league_id,
                "season": CURRENT_SEASON,
            },
        )
        formatted_official_stats = _format_official_team_statistics(team_id, official_stats)
        if formatted_official_stats:
            response_payload = _merge_team_stats(formatted_official_stats, advanced_stats)
            _store_cache_entry(TEAM_STATS_CACHE, cache_key, response_payload)
            return jsonify(response_payload), 200

    response_payload = _merge_team_stats(recent_stats, advanced_stats)
    _store_cache_entry(TEAM_STATS_CACHE, cache_key, response_payload)
    return jsonify(response_payload), 200


@stats_bp.route("/players/<int:player_id>/statistics", methods=["GET"])
def get_player_statistics(player_id):
    cache_key = (int(player_id), int(CURRENT_SEASON))
    cached_payload = _cache_entry(PLAYER_STATS_CACHE, cache_key)
    if cached_payload is not None:
        return jsonify(cached_payload), 200

    best_data = None
    best_appearances = -1

    for season in (CURRENT_SEASON, CURRENT_SEASON - 1, CURRENT_SEASON - 2):
        candidate = call_football_api("players", {"id": player_id, "season": season})
        if not candidate or not candidate.get("response"):
            continue

        player_entry = candidate["response"][0]
        stats_list = player_entry.get("statistics") or [{}]

        totals, _, _ = _sum_player_stats(stats_list)
        appearances = totals["appearances"]
        if best_data is None or appearances > best_appearances:
            best_data = player_entry
            best_appearances = appearances
        if appearances > 0:
            break

    if not best_data:
        return jsonify({"error": "Player not found"}), 404

    player = best_data.get("player") or {}
    statistics_list = best_data.get("statistics") or [{}]

    totals, position, current_team = _sum_player_stats(statistics_list)
    # stats_available: True whenever the player was found.
    # We only hide stats (N/A) when the player cannot be found at all.
    # The API may return empty statistics under free-plan restrictions even
    # when the player has real career data — in that case we show 0s, not N/A.
    stats_available = best_appearances > 0

    response_payload = {
        "player_id": player_id,
        "player_name": player.get("name", "Unknown"),
        "current_team": current_team,
        "position": position,
        "statistics": totals,
    }
    if stats_available:
        response_payload["stats_available"] = True
    # When stats_available is False we omit the field entirely so the JS
    # treats it as undefined (≠ false) and still renders 0s instead of N/A.
    _store_cache_entry(PLAYER_STATS_CACHE, cache_key, response_payload)
    return jsonify(response_payload), 200
