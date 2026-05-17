"""Small utility routes for health checks and simple search/resolve helpers."""

from datetime import datetime
from difflib import SequenceMatcher

from flask import Blueprint, jsonify, request

from config import CURRENT_SEASON
from db.connection import get_db_connection, release_db_connection
from services.api import call_football_api

utils_bp = Blueprint("utils", __name__)


def _score(name, query):
    source = (name or "").lower()
    target = (query or "").lower()
    if source == target:
        return 1.0
    if source.startswith(target):
        return 0.9
    if target in source:
        return 0.75
    return SequenceMatcher(None, source, target).ratio() * 0.5


def _rate_limit_response(data):
    if data and data.get("_error") == "rate_limit":
        return jsonify({"error": "Rate limited by API-Football. Please retry shortly."}), 429
    return None


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
    query = (request.args.get("q") or "").strip()
    search_type = request.args.get("type", "all")
    league_filter = request.args.get("league")

    if len(query) < 3:
        return jsonify({"error": "Query must be at least 3 characters"}), 400

    results = {"teams": [], "competitions": []}

    if search_type in ("all", "teams"):
        # API-Football does not allow 'league' alongside 'search' for teams
        team_data = call_football_api("teams", {"search": query})
        rate_limit = _rate_limit_response(team_data)
        if rate_limit:
            return rate_limit

        for item in (team_data or {}).get("response", [])[:10]:
            team = item.get("team", {})
            results["teams"].append(
                {
                    "id": team.get("id"),
                    "name": team.get("name"),
                    "crest": team.get("logo"),
                }
            )

    if search_type in ("all", "competitions"):
        league_data = call_football_api("leagues", {"search": query})
        rate_limit = _rate_limit_response(league_data)
        if rate_limit:
            return rate_limit

        for item in (league_data or {}).get("response", [])[:10]:
            league = item.get("league", {})
            results["competitions"].append(
                {
                    "id": league.get("id"),
                    "name": league.get("name"),
                    "code": league.get("type"),
                }
            )

    return jsonify(results), 200


@utils_bp.route("/resolve/team", methods=["GET"])
def resolve_team():
    query = (request.args.get("q") or "").strip()
    league_filter = request.args.get("league")

    if len(query) < 3:
        return jsonify({"error": "Query must be at least 3 characters"}), 400

    params = {"search": query}
    if league_filter:
        params["league"] = league_filter

    data = call_football_api("teams", params)
    rate_limit = _rate_limit_response(data)
    if rate_limit:
        return rate_limit

    best_match = None
    best_score = 0
    for item in (data or {}).get("response", []):
        team = item.get("team", {})
        score = _score(team.get("name"), query)
        if score > best_score:
            best_match = team
            best_score = score

    if not best_match:
        return jsonify({"error": "Team not found"}), 404

    return jsonify(
        {
            "id": best_match.get("id"),
            "name": best_match.get("name"),
            "crest": best_match.get("logo"),
        }
    ), 200


@utils_bp.route("/resolve/league", methods=["GET"])
def resolve_league():
    query = (request.args.get("q") or "").strip()

    if len(query) < 3:
        return jsonify({"error": "Query must be at least 3 characters"}), 400

    data = call_football_api("leagues", {"search": query})
    rate_limit = _rate_limit_response(data)
    if rate_limit:
        return rate_limit

    best_match = None
    best_score = 0
    for item in (data or {}).get("response", []):
        league = item.get("league", {})
        score = _score(league.get("name"), query)
        if score > best_score:
            best_match = league
            best_score = score

    if not best_match:
        return jsonify({"error": "League not found"}), 404

    return jsonify({"id": best_match.get("id"), "name": best_match.get("name")}), 200


@utils_bp.route("/teams/<int:team_id>/players", methods=["GET"])
def get_team_players(team_id):
    data = None
    for season in (CURRENT_SEASON, CURRENT_SEASON - 1, CURRENT_SEASON - 2):
        data = call_football_api("players", {"team": team_id, "season": season})
        if data and data.get("response"):
            break

    rate_limit = _rate_limit_response(data)
    if rate_limit:
        return rate_limit

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
    team_id = (request.args.get("id") or "").strip()
    if not team_id:
        return jsonify({"error": "id required"}), 400

    data = call_football_api("teams", {"id": team_id})
    rate_limit = _rate_limit_response(data)
    if rate_limit:
        return rate_limit

    if not data or not data.get("response"):
        return jsonify({"error": "Team not found"}), 404

    team = data["response"][0].get("team", {})
    return jsonify({"id": team.get("id"), "name": team.get("name"), "crest": team.get("logo")}), 200


@utils_bp.route("/resolve/player-by-id", methods=["GET"])
def resolve_player_by_id():
    player_id = (request.args.get("id") or "").strip()
    if not player_id:
        return jsonify({"error": "id required"}), 400

    data = None
    for season in (CURRENT_SEASON, CURRENT_SEASON - 1, CURRENT_SEASON - 2):
        data = call_football_api("players", {"id": player_id, "season": season})
        if data and data.get("response"):
            break

    rate_limit = _rate_limit_response(data)
    if rate_limit:
        return rate_limit

    if not data or not data.get("response"):
        return jsonify({"error": "Player not found"}), 404

    player = data["response"][0].get("player", {})
    return jsonify({"id": player.get("id"), "name": player.get("name")}), 200


@utils_bp.route("/resolve/league-by-id", methods=["GET"])
def resolve_league_by_id():
    league_id = (request.args.get("id") or "").strip()
    if not league_id:
        return jsonify({"error": "id required"}), 400

    data = call_football_api("leagues", {"id": league_id})
    rate_limit = _rate_limit_response(data)
    if rate_limit:
        return rate_limit

    if not data or not data.get("response"):
        return jsonify({"error": "League not found"}), 404

    league = data["response"][0].get("league", {})
    return jsonify({"id": league.get("id"), "name": league.get("name")}), 200
