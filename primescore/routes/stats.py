"""Statistics routes used by standings and compare pages."""

from flask import Blueprint, jsonify, request

from config import CURRENT_SEASON
from services.api import call_football_api, compute_team_stats, format_standings

stats_bp = Blueprint("stats", __name__)

LEAGUE_MAP = {
    "PL": 39,
    "CL": 2,
    "BL1": 78,
    "SA": 135,
    "PD": 140,
    "FL1": 61,
}


def _league_id(value):
    return LEAGUE_MAP.get(value, value)


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

    matches_data = call_football_api(
        "matches",
        {
            "team": team_id,
            "season": CURRENT_SEASON,
            "status": "FT",
        },
    ) or call_football_api("matches", {"team": team_id, "season": CURRENT_SEASON})

    return jsonify(compute_team_stats(team_id, team, matches_data)), 200


def _sum_player_stats(statistics_list):
    total_goals = 0
    total_assists = 0
    total_appearances = 0
    total_yellow = 0
    total_red = 0
    position = None
    current_team = None

    for stat in statistics_list:
        games = stat.get("games") or {}
        goals_data = stat.get("goals") or {}
        cards_data = stat.get("cards") or {}

        apps = (
            games.get("appearances")
            or 0
        )
        total_appearances += apps
        total_goals       += goals_data.get("total") or 0
        total_assists     += goals_data.get("assists") or 0
        total_yellow      += cards_data.get("yellow") or 0
        total_red         += cards_data.get("red") or 0

        if not position and games.get("position"):
            position = games["position"]
        if not current_team:
            team_name = (stat.get("team") or {}).get("name")
            if team_name:
                current_team = team_name

    return total_goals, total_assists, total_appearances, total_yellow, total_red, position, current_team


@stats_bp.route("/players/<int:player_id>/statistics", methods=["GET"])
def get_player_statistics(player_id):
    best_data = None
    best_appearances = -1
    for season in (CURRENT_SEASON, CURRENT_SEASON - 1):
        candidate = call_football_api("players", {"id": player_id, "season": season})
        if not candidate or not candidate.get("response"):
            continue
        stats_list = candidate["response"][0].get("statistics") or [{}]
        result = _sum_player_stats(stats_list)
        appearances = result[2]
        if best_data is None:
            best_data = candidate
        if appearances > best_appearances:
            best_data = candidate
            best_appearances = appearances
        if appearances > 0:
            break  

    data = best_data
    if not data or not data.get("response"):
        return jsonify({"error": "Player not found"}), 404

    player_data = data["response"][0]
    player = player_data.get("player", {})
    statistics_list = player_data.get("statistics") or [{}]

    goals, assists, appearances, yellow_cards, red_cards, position, current_team = (
        _sum_player_stats(statistics_list)
    )
    stats_available = appearances > 0

    return jsonify(
        {
            "player_id": player_id,
            "player_name": player.get("name", "Unknown"),
            "current_team": current_team,
            "position": position,
            "stats_available": stats_available,
            "statistics": {
                "goals":        goals,
                "assists":      assists,
                "appearances":  appearances,
                "yellow_cards": yellow_cards,
                "red_cards":    red_cards,
            },
        }
    ), 200
