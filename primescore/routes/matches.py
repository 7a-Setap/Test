"""Match routes used by the current PrimeScore interface."""

import datetime as dt

from flask import Blueprint, jsonify, request, session

from config import CURRENT_SEASON
from services.api import call_football_api

matches_bp = Blueprint("matches", __name__)

LEAGUE_MAP = {
    "PL": 39,
    "CL": 2,
    "BL1": 78,
    "SA": 135,
    "PD": 140,
    "FL1": 61,
}


def _require_login():
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    return None


def _map_match(match, include_scores=False):
    fixture = match.get("fixture", {})
    teams = match.get("teams", {})
    goals = match.get("goals", {})
    league = match.get("league", {})
    status = fixture.get("status", {})

    payload = {
        "match_id": fixture.get("id"),
        "home_team": (teams.get("home") or {}).get("name", "Unknown"),
        "away_team": (teams.get("away") or {}).get("name", "Unknown"),
        "competition": league.get("name", "Unknown"),
        "date": fixture.get("date"),
        "match_date": fixture.get("date"),
        "status": status.get("long", "Unknown"),
    }

    if include_scores:
        payload.update({
            "home_score": goals.get("home"),
            "away_score": goals.get("away"),
        })
    return payload


def _resolve_league_id(raw_league_id):
    if not raw_league_id:
        return 39
    return LEAGUE_MAP.get(raw_league_id, raw_league_id)


@matches_bp.route("/matches/live", methods=["GET"])
def get_live_matches():
    auth_error = _require_login()
    if auth_error:
        return auth_error

    data = call_football_api("fixtures", {"live": "all"})
    if not data or not data.get("response"):
        return jsonify({"matches": []}), 200

    matches = []
    for match in data["response"]:
        mapped_match = _map_match(match, include_scores=True)
        mapped_match["minute"] = ((match.get("fixture") or {}).get("status") or {}).get("elapsed")
        matches.append(mapped_match)

    return jsonify({"matches": matches}), 200


@matches_bp.route("/fixtures", methods=["GET"])
def get_fixtures():
    auth_error = _require_login()
    if auth_error:
        return auth_error

    tomorrow = (dt.datetime.now() + dt.timedelta(days=1)).strftime("%Y-%m-%d")
    params = {"date": tomorrow}

    team_id = request.args.get("team_id")
    if team_id:
        params["team"] = team_id

    data = call_football_api("fixtures", params)
    matches = [_map_match(match) for match in (data or {}).get("response", [])]
    matches.sort(key=lambda match: match.get("date") or "")

    return jsonify({"fixtures": matches[:10]}), 200


@matches_bp.route("/results", methods=["GET"])
def get_results():
    auth_error = _require_login()
    if auth_error:
        return auth_error

    params = {
        "season": CURRENT_SEASON,
        "status": "FT",
        "league": _resolve_league_id(request.args.get("league_id")),
    }

    team_id = request.args.get("team_id")
    if team_id:
        params.pop("league", None)
        params["team"] = team_id

    data = call_football_api("fixtures", params)
    matches = [_map_match(match, include_scores=True) for match in (data or {}).get("response", [])]
    matches.sort(key=lambda match: match.get("date") or "", reverse=True)

    return jsonify({"results": matches[:5]}), 200
