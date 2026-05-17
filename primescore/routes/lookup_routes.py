"""Utility routes plus shared name-to-ID resolvers for teams, players, and leagues."""

from copy import deepcopy
from datetime import datetime
from difflib import SequenceMatcher
import time
import unicodedata

from flask import Blueprint, jsonify, request

from config import CURRENT_SEASON
from db.connection import get_db_connection, release_db_connection
from services.football_api_client import call_football_api

utils_bp = Blueprint("utils", __name__)

LEAGUE_CODE_TO_ID = {
    "PL": 39,
    "CL": 2,
    "BL1": 78,
    "SA": 135,
    "PD": 140,
    "FL1": 61,
}

LEAGUE_CODE_TO_NAME = {
    "PL": "Premier League",
    "CL": "Champions League",
    "BL1": "Bundesliga",
    "SA": "Serie A",
    "PD": "La Liga",
    "FL1": "Ligue 1",
}

LEAGUE_ID_TO_CODE = {str(league_id): code for code, league_id in LEAGUE_CODE_TO_ID.items()}
REFERENCE_CACHE = {
    "leagues": {},
    "teams": {},
    "players": {},
}
REFERENCE_CACHE_TTL_SECONDS = 300


def score_result(candidate, query):
    source = normalise_match_text(candidate)
    target = normalise_match_text(query)
    if not source or not target:
        return 0.0
    if source == target:
        return 1.0
    if source.startswith(target):
        return 0.9
    if target in source:
        return 0.75
    return SequenceMatcher(None, source, target).ratio() * 0.5


def is_rate_limited_payload(data):
    return bool(data and data.get("_error") == "rate_limit")


def reset_lookup_caches():
    for cache_store in REFERENCE_CACHE.values():
        cache_store.clear()


def _reference_cache_get(kind, cache_key):
    cached_entry = REFERENCE_CACHE[kind].get(cache_key)
    if not cached_entry:
        return None

    if cached_entry["expires_at"] <= time.time():
        REFERENCE_CACHE[kind].pop(cache_key, None)
        return None

    return deepcopy(cached_entry["payload"])


def _reference_cache_set(kind, cache_key, payload):
    if not payload or is_rate_limited_payload(payload):
        return

    REFERENCE_CACHE[kind][cache_key] = {
        "payload": deepcopy(payload),
        "expires_at": time.time() + REFERENCE_CACHE_TTL_SECONDS,
    }


def rate_limit_response(data):
    if is_rate_limited_payload(data):
        return jsonify({"error": "Rate limited by API-Football. Please retry shortly."}), 429
    return None


def normalise_query_value(value):
    return str(value or "").strip()


def normalise_match_text(value):
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(character for character in text if not unicodedata.combining(character))
    return " ".join(text.lower().split())


def _normalise_compact_text(value):
    return normalise_match_text(value).replace(" ", "")


def build_search_terms(value):
    raw_value = normalise_query_value(value)
    normalised_value = normalise_match_text(raw_value)
    tokens = [token for token in normalised_value.split(" ") if token]

    terms = []
    for candidate in (
        raw_value,
        normalised_value,
        " ".join(tokens[-2:]) if len(tokens) >= 2 else "",
        tokens[-1] if tokens else "",
        tokens[0] if tokens else "",
    ):
        cleaned_candidate = normalise_query_value(candidate)
        if cleaned_candidate and len(cleaned_candidate) >= 3 and cleaned_candidate not in terms:
            terms.append(cleaned_candidate)

    return terms


def resolve_league_reference(reference):
    raw_value = normalise_query_value(reference)
    if not raw_value:
        return None

    cache_key = normalise_match_text(raw_value)
    cached_league = _reference_cache_get("leagues", cache_key)
    if cached_league is not None:
        return cached_league

    upper_value = raw_value.upper()
    if upper_value in LEAGUE_CODE_TO_ID:
        payload = {
            "id": LEAGUE_CODE_TO_ID[upper_value],
            "code": upper_value,
            "name": LEAGUE_CODE_TO_NAME.get(upper_value, upper_value),
        }
        _reference_cache_set("leagues", cache_key, payload)
        return payload

    if raw_value.isdigit():
        code = LEAGUE_ID_TO_CODE.get(raw_value)
        payload = {
            "id": int(raw_value),
            "code": code or raw_value,
            "name": LEAGUE_CODE_TO_NAME.get(code, raw_value),
        }
        _reference_cache_set("leagues", cache_key, payload)
        return payload

    compact_query = _normalise_compact_text(raw_value)
    local_match = None
    local_score = 0.0

    for code, name in LEAGUE_CODE_TO_NAME.items():
        compact_name = _normalise_compact_text(name)
        current_score = max(
            score_result(name, raw_value),
            score_result(code, raw_value),
            0.95 if compact_query and compact_name.startswith(compact_query) else 0.0,
            0.8 if compact_query and compact_query in compact_name else 0.0,
        )
        if current_score > local_score:
            local_score = current_score
            local_match = {
                "id": LEAGUE_CODE_TO_ID[code],
                "code": code,
                "name": name,
            }

    if local_match and local_score >= 0.6:
        _reference_cache_set("leagues", cache_key, local_match)
        return local_match

    data = call_football_api("leagues", {"search": raw_value})
    if is_rate_limited_payload(data):
        return data

    best_match = None
    best_score = 0.0
    for item in (data or {}).get("response", []):
        league = item.get("league", {})
        current_score = score_result(league.get("name"), raw_value)
        if current_score > best_score:
            best_score = current_score
            best_match = league

    if not best_match:
        return None

    league_id = best_match.get("id")
    league_code = LEAGUE_ID_TO_CODE.get(str(league_id), str(league_id))
    payload = {
        "id": league_id,
        "code": league_code,
        "name": best_match.get("name", raw_value),
    }
    _reference_cache_set("leagues", cache_key, payload)
    return payload


def resolve_team_reference(reference, league_filter=None):
    raw_value = normalise_query_value(reference)
    if not raw_value:
        return None

    cache_key = f"{normalise_match_text(raw_value)}|league:{normalise_match_text(league_filter or '')}"
    cached_team = _reference_cache_get("teams", cache_key)
    if cached_team is not None:
        return cached_team

    if raw_value.isdigit():
        data = call_football_api("teams", {"id": int(raw_value)})
        if is_rate_limited_payload(data):
            return data
        if not data or not data.get("response"):
            return None

        team = data["response"][0].get("team", {})
        payload = {
            "id": team.get("id"),
            "name": team.get("name", raw_value),
            "crest": team.get("logo", ""),
        }
        _reference_cache_set("teams", cache_key, payload)
        return payload

    league_id = None
    if league_filter:
        league = resolve_league_reference(league_filter)
        if is_rate_limited_payload(league):
            return league
        if league and league.get("id"):
            league_id = league["id"]

    best_match = None
    best_score = 0.0
    seen_team_ids = set()

    for search_term in build_search_terms(raw_value):
        params = {"search": search_term}
        if league_id:
            params["league"] = league_id

        data = call_football_api("teams", params)
        if is_rate_limited_payload(data):
            return data

        for item in (data or {}).get("response", []):
            team = item.get("team", {})
            team_id = team.get("id")
            if team_id in seen_team_ids:
                continue
            seen_team_ids.add(team_id)

            current_score = max(
                score_result(team.get("name"), raw_value),
                score_result(team.get("code"), raw_value),
                score_result(team.get("name"), search_term),
            )
            if current_score > best_score:
                best_score = current_score
                best_match = team

    if not best_match:
        return None

    payload = {
        "id": best_match.get("id"),
        "name": best_match.get("name", raw_value),
        "crest": best_match.get("logo", ""),
    }
    _reference_cache_set("teams", cache_key, payload)
    return payload


def _best_player_match(player_candidates, query, team_name=""):
    best_match = None
    best_score = 0.0
    seen_player_ids = set()

    for candidate in player_candidates:
        player_id = candidate.get("id")
        if player_id in seen_player_ids:
            continue
        seen_player_ids.add(player_id)

        current_score = max(
            score_result(candidate.get("name"), query),
            score_result(candidate.get("firstname"), query),
            score_result(candidate.get("lastname"), query),
            score_result(team_name, query) * 0.1,
        )
        if current_score > best_score:
            best_score = current_score
            best_match = candidate

    return best_match


def _extract_player_candidate(item, default_team=""):
    player = item.get("player", item)
    statistics = (item.get("statistics") or [{}])[0]

    return {
        "id": player.get("id"),
        "name": player.get("name"),
        "firstname": player.get("firstname", ""),
        "lastname": player.get("lastname", ""),
        "photo": player.get("photo", ""),
        "team": (statistics.get("team") or {}).get("name", default_team),
    }


def resolve_player_reference(reference, team_reference=None):
    raw_value = normalise_query_value(reference)
    if not raw_value:
        return None

    cache_key = f"{normalise_match_text(raw_value)}|team:{normalise_match_text(team_reference or '')}"
    cached_player = _reference_cache_get("players", cache_key)
    if cached_player is not None:
        return cached_player

    if raw_value.isdigit():
        data = call_football_api("players", {"id": int(raw_value), "season": CURRENT_SEASON})
        if is_rate_limited_payload(data):
            return data
        if not data or not data.get("response"):
            return None

        player_data = data["response"][0]
        player = player_data.get("player", {})
        statistics = (player_data.get("statistics") or [{}])[0]
        payload = {
            "id": player.get("id", int(raw_value)),
            "name": player.get("name", raw_value),
            "photo": player.get("photo", ""),
            "team": (statistics.get("team") or {}).get("name", ""),
        }
        _reference_cache_set("players", cache_key, payload)
        return payload

    if not team_reference:
        return None

    resolved_team = resolve_team_reference(team_reference)
    if is_rate_limited_payload(resolved_team):
        return resolved_team
    if not resolved_team:
        return None

    squad_data = call_football_api("player_squads", {"team": resolved_team["id"]})
    if is_rate_limited_payload(squad_data):
        return squad_data

    squad_candidates = []
    for squad in (squad_data or {}).get("response", []):
        for player in squad.get("players", []):
            squad_candidates.append(
                {
                    "id": player.get("id"),
                    "name": player.get("name", raw_value),
                    "firstname": player.get("firstname", ""),
                    "lastname": player.get("lastname", ""),
                    "photo": player.get("photo", ""),
                    "team": resolved_team["name"],
                }
            )

    best_match = _best_player_match(squad_candidates, raw_value, resolved_team["name"])
    if best_match:
        payload = {
            "id": best_match.get("id"),
            "name": best_match.get("name", raw_value),
            "photo": best_match.get("photo", ""),
            "team": resolved_team["name"],
        }
        _reference_cache_set("players", cache_key, payload)
        return payload

    players_data = call_football_api("players", {"team": resolved_team["id"], "season": CURRENT_SEASON})
    if is_rate_limited_payload(players_data):
        return players_data

    player_candidates = []
    for item in (players_data or {}).get("response", []):
        player = item.get("player", {})
        statistics = (item.get("statistics") or [{}])[0]
        player_candidates.append(
            {
                "id": player.get("id"),
                "name": player.get("name", raw_value),
                "firstname": player.get("firstname", ""),
                "lastname": player.get("lastname", ""),
                "photo": player.get("photo", ""),
                "team": (statistics.get("team") or {}).get("name", resolved_team["name"]),
            }
        )

    best_match = _best_player_match(player_candidates, raw_value, resolved_team["name"])
    if not best_match:
        return None

    payload = {
        "id": best_match.get("id"),
        "name": best_match.get("name", raw_value),
        "photo": best_match.get("photo", ""),
        "team": best_match.get("team", resolved_team["name"]),
    }
    _reference_cache_set("players", cache_key, payload)
    return payload


@utils_bp.route("/health", methods=["GET"])
def health_check():
    connection = get_db_connection()
    database_ok = connection is not None
    if connection:
        release_db_connection(connection)

    return jsonify(
        {
            "status": "healthy" if database_ok else "degraded",
            "database": "connected" if database_ok else "unreachable",
            "timestamp": datetime.now().isoformat(),
        }
    ), 200 if database_ok else 503


@utils_bp.route("/search", methods=["GET"])
def search():
    query = normalise_query_value(request.args.get("q"))
    search_type = request.args.get("type", "all")
    league_filter = request.args.get("league")
    team_filter = request.args.get("team")

    if len(query) < 3:
        return jsonify({"error": "Query must be at least 3 characters"}), 400

    results = {"teams": [], "players": [], "competitions": []}

    if search_type in ("all", "teams"):
        params = {"search": query}
        if league_filter:
            league = resolve_league_reference(league_filter)
            if is_rate_limited_payload(league):
                return rate_limit_response(league)
            if league and league.get("id"):
                params["league"] = league["id"]

        team_data = call_football_api("teams", params)
        rate_limited = rate_limit_response(team_data)
        if rate_limited:
            return rate_limited

        for item in (team_data or {}).get("response", [])[:10]:
            team = item.get("team", {})
            results["teams"].append(
                {
                    "id": team.get("id"),
                    "name": team.get("name"),
                    "crest": team.get("logo"),
                }
            )

    if search_type in ("all", "players"):
        player_candidates = []
        seen_player_ids = set()

        def add_candidates(player_items, default_team=""):
            for item in player_items:
                candidate = _extract_player_candidate(item, default_team=default_team)
                player_id = candidate.get("id")
                if not player_id or player_id in seen_player_ids:
                    continue
                seen_player_ids.add(player_id)
                player_candidates.append(candidate)

        resolved_team = None
        if team_filter:
            resolved_team = resolve_team_reference(team_filter, league_filter=league_filter)
            rate_limited = rate_limit_response(resolved_team)
            if rate_limited:
                return rate_limited

            if resolved_team:
                squad_data = call_football_api("player_squads", {"team": resolved_team["id"]})
                rate_limited = rate_limit_response(squad_data)
                if rate_limited:
                    return rate_limited

                for squad in (squad_data or {}).get("response", []):
                    add_candidates(squad.get("players", []), default_team=resolved_team["name"])

                if len(query) >= 4:
                    player_data = call_football_api(
                        "players",
                        {"search": query, "team": resolved_team["id"], "season": CURRENT_SEASON},
                    )
                    rate_limited = rate_limit_response(player_data)
                    if rate_limited:
                        return rate_limited
                    add_candidates((player_data or {}).get("response", []), default_team=resolved_team["name"])

        elif league_filter and len(query) >= 4:
            resolved_league = resolve_league_reference(league_filter)
            rate_limited = rate_limit_response(resolved_league)
            if rate_limited:
                return rate_limited

            if resolved_league and resolved_league.get("id"):
                player_data = call_football_api(
                    "players",
                    {"search": query, "league": resolved_league["id"], "season": CURRENT_SEASON},
                )
                rate_limited = rate_limit_response(player_data)
                if rate_limited:
                    return rate_limited
                add_candidates((player_data or {}).get("response", []))

        if not player_candidates:
            for search_term in build_search_terms(query):
                profile_data = call_football_api("player_profiles", {"search": search_term})
                rate_limited = rate_limit_response(profile_data)
                if rate_limited:
                    return rate_limited
                add_candidates((profile_data or {}).get("response", []))

        player_candidates.sort(
            key=lambda candidate: score_result(candidate.get("name"), query),
            reverse=True,
        )

        for candidate in player_candidates[:10]:
            results["players"].append(
                {
                    "id": candidate.get("id"),
                    "name": candidate.get("name"),
                    "photo": candidate.get("photo"),
                    "team": candidate.get("team"),
                }
            )

    if search_type in ("all", "competitions"):
        league_data = call_football_api("leagues", {"search": query})
        rate_limited = rate_limit_response(league_data)
        if rate_limited:
            return rate_limited

        for item in (league_data or {}).get("response", [])[:10]:
            league = item.get("league", {})
            league_id = league.get("id")
            results["competitions"].append(
                {
                    "id": league_id,
                    "name": league.get("name"),
                    "code": LEAGUE_ID_TO_CODE.get(str(league_id), str(league_id or "")),
                }
            )

    return jsonify(results), 200


@utils_bp.route("/resolve/team", methods=["GET"])
def resolve_team():
    query = normalise_query_value(request.args.get("q"))
    league_filter = request.args.get("league")

    if not query:
        return jsonify({"error": "Query is required"}), 400
    if not query.isdigit() and len(query) < 3:
        return jsonify({"error": "Query must be at least 3 characters"}), 400

    team = resolve_team_reference(query, league_filter=league_filter)
    rate_limited = rate_limit_response(team)
    if rate_limited:
        return rate_limited
    if not team:
        return jsonify({"error": "Team not found"}), 404

    return jsonify(team), 200


@utils_bp.route("/resolve/player", methods=["GET"])
def resolve_player():
    query = normalise_query_value(request.args.get("q"))
    team_reference = normalise_query_value(request.args.get("team"))

    if not query:
        return jsonify({"error": "Query is required"}), 400
    if not query.isdigit() and len(query) < 3:
        return jsonify({"error": "Query must be at least 3 characters"}), 400
    if not query.isdigit() and not team_reference:
        return jsonify({"error": "Team is required when searching by player name"}), 400

    player = resolve_player_reference(query, team_reference=team_reference)
    rate_limited = rate_limit_response(player)
    if rate_limited:
        return rate_limited
    if not player:
        return jsonify({"error": "Player not found"}), 404

    return jsonify(player), 200


@utils_bp.route("/resolve/league", methods=["GET"])
def resolve_league():
    query = normalise_query_value(request.args.get("q"))

    if not query:
        return jsonify({"error": "Query is required"}), 400
    if not query.isdigit() and len(query) < 2:
        return jsonify({"error": "Query must be at least 2 characters"}), 400

    league = resolve_league_reference(query)
    rate_limited = rate_limit_response(league)
    if rate_limited:
        return rate_limited
    if not league:
        return jsonify({"error": "League not found"}), 404

    return jsonify(league), 200


@utils_bp.route("/teams/<int:team_id>/players", methods=["GET"])
def get_team_players(team_id):
    # player_squads is purpose-built for roster lookups: no season required,
    # lower API quota cost, and returns position data directly.
    squad_data = call_football_api("player_squads", {"team": team_id})
    rate_limited = rate_limit_response(squad_data)
    if rate_limited:
        return rate_limited

    if squad_data and squad_data.get("response"):
        players = []
        for squad in squad_data["response"]:
            for player in squad.get("players", []):
                players.append({
                    "id": player.get("id"),
                    "name": player.get("name"),
                    "position": player.get("position"),
                })
        if players:
            return jsonify({"players": players}), 200

    # Fallback: season-based players endpoint
    data = None
    for season in (CURRENT_SEASON, CURRENT_SEASON - 1, CURRENT_SEASON - 2):
        data = call_football_api("players", {"team": team_id, "season": season})
        if data and data.get("response"):
            break

    rate_limited = rate_limit_response(data)
    if rate_limited:
        return rate_limited

    players = []
    for item in (data or {}).get("response", []):
        player = item.get("player", {})
        stats = (item.get("statistics") or [{}])[0]
        players.append({
            "id": player.get("id"),
            "name": player.get("name"),
            "position": (stats.get("games") or {}).get("position"),
        })
    return jsonify({"players": players}), 200


@utils_bp.route("/resolve/team-by-id", methods=["GET"])
def resolve_team_by_id():
    team_id = normalise_query_value(request.args.get("id"))
    if not team_id:
        return jsonify({"error": "id required"}), 400

    team = resolve_team_reference(team_id)
    rate_limited = rate_limit_response(team)
    if rate_limited:
        return rate_limited
    if not team:
        return jsonify({"error": "Team not found"}), 404

    return jsonify({"id": team.get("id"), "name": team.get("name"), "crest": team.get("crest")}), 200


@utils_bp.route("/resolve/player-by-id", methods=["GET"])
def resolve_player_by_id():
    player_id = normalise_query_value(request.args.get("id"))
    if not player_id:
        return jsonify({"error": "id required"}), 400

    data = None
    for season in (CURRENT_SEASON, CURRENT_SEASON - 1, CURRENT_SEASON - 2):
        data = call_football_api("players", {"id": player_id, "season": season})
        if data and data.get("response"):
            break

    rate_limited = rate_limit_response(data)
    if rate_limited:
        return rate_limited
    if not data or not data.get("response"):
        return jsonify({"error": "Player not found"}), 404

    player = data["response"][0].get("player", {})
    return jsonify({"id": player.get("id"), "name": player.get("name")}), 200


@utils_bp.route("/resolve/league-by-id", methods=["GET"])
def resolve_league_by_id():
    league_id = normalise_query_value(request.args.get("id"))
    if not league_id:
        return jsonify({"error": "id required"}), 400

    league = resolve_league_reference(league_id)
    rate_limited = rate_limit_response(league)
    if rate_limited:
        return rate_limited
    if not league:
        return jsonify({"error": "League not found"}), 404

    return jsonify({"id": league.get("id"), "name": league.get("name")}), 200
