"""Match routes used by the current PrimeScore interface."""

from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request, session

from config import CURRENT_SEASON
from services.football_api_client import call_football_api, is_rate_limited_response

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
    home_team = teams.get("home") or {}
    away_team = teams.get("away") or {}

    payload = {
        "match_id": fixture.get("id"),
        "home_team": home_team.get("name", "Unknown"),
        # Surface team IDs so the frontend can call /h2h without a lookup.
        "home_team_id": home_team.get("id"),
        "away_team": away_team.get("name", "Unknown"),
        "away_team_id": away_team.get("id"),
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


def _today_string():
    return datetime.now(timezone.utc).date().isoformat()


def _date_offset_string(days):
    return (datetime.now(timezone.utc).date() + timedelta(days=days)).isoformat()


def _format_match_event(event):
    """Shape a single fixtures/events entry into a UI-friendly dict.

    The API returns events of type "Goal", "Card", "subst", "Var". We surface
    the three the spec requires (cards, subs) plus goals for completeness so
    the timeline reads naturally.
    """
    time = event.get("time") or {}
    team = event.get("team") or {}
    player = event.get("player") or {}
    assist = event.get("assist") or {}

    event_type = (event.get("type") or "").lower()  # "goal", "card", "subst", "var"
    detail = event.get("detail") or ""

    # Normalise a friendly subtype: "yellow_card", "red_card", "substitution",
    # "goal", "own_goal", "penalty_goal" — the frontend uses this to pick an icon.
    if event_type == "card":
        subtype = "red_card" if "red" in detail.lower() else "yellow_card"
    elif event_type == "subst":
        subtype = "substitution"
    elif event_type == "goal":
        d = detail.lower()
        if "own" in d:
            subtype = "own_goal"
        elif "penalty" in d:
            subtype = "penalty_goal"
        else:
            subtype = "goal"
    else:
        subtype = event_type or "event"

    return {
        "minute": time.get("elapsed"),
        "extra_minute": time.get("extra"),
        "team": team.get("name"),
        "team_id": team.get("id"),
        "player": player.get("name"),
        "assist": assist.get("name"),
        "type": event_type,
        "subtype": subtype,
        "detail": detail,
    }


def _format_lineup_player(entry):
    """Shape one startXI / substitutes entry from /fixtures/lineups."""
    player = entry.get("player") or {}
    return {
        "id": player.get("id"),
        "name": player.get("name") or "",
        "number": player.get("number"),
        "position": player.get("pos") or "",   # "G" / "D" / "M" / "F"
        "grid": player.get("grid"),            # "line:position" or None
    }


def _format_team_lineup(team_lineup):
    """Convert one team entry from the API into a UI-friendly dict.

    The API returns a list with one entry per team. Each entry has team,
    coach, formation, startXI (with grid coordinates we can render on a
    pitch), and substitutes. We pass the data through with shallow renaming
    so the frontend doesn't have to know about the API shape.
    """
    if not team_lineup:
        return None

    team = team_lineup.get("team") or {}
    coach = team_lineup.get("coach") or {}

    return {
        "team_id": team.get("id"),
        "team_name": team.get("name") or "",
        "team_logo": team.get("logo") or "",
        "coach": coach.get("name") or "",
        "formation": team_lineup.get("formation") or "",
        "start_xi": [_format_lineup_player(p) for p in team_lineup.get("startXI") or []],
        "substitutes": [_format_lineup_player(p) for p in team_lineup.get("substitutes") or []],
    }


@matches_bp.route("/matches/<int:match_id>/h2h", methods=["GET"])
def get_match_h2h(match_id):
    """Return head-to-head history between two teams (last 10 meetings).

    Query params:
        home_id  – numeric team ID for the "home" perspective of the current
                   fixture. Used to attribute wins in the summary.
        away_id  – numeric team ID for the opposing team.

    The match_id in the URL is purely contextual (so the frontend can use
    one consistent URL shape for all match-detail tabs); the H2H lookup
    itself only needs the two team IDs.
    """
    auth_error = _require_login()
    if auth_error:
        return auth_error

    home_id_raw = (request.args.get("home_id") or "").strip()
    away_id_raw = (request.args.get("away_id") or "").strip()

    try:
        home_id = int(home_id_raw)
        away_id = int(away_id_raw)
    except (TypeError, ValueError):
        return jsonify({"error": "home_id and away_id query params are required"}), 400

    if home_id == away_id:
        return jsonify({"error": "home_id and away_id must differ"}), 400

    # NOTE: the "last" parameter is gated to paid plans on API-Football
    # ("Free plans do not have access to the Last parameter."), so we omit
    # it and trim to the 10 most recent finished meetings ourselves below.
    data = call_football_api(
        "fixture_h2h",
        {"h2h": f"{home_id}-{away_id}"},
    )
    if is_rate_limited_response(data):
        return jsonify({"error": "Rate limited by API-Football. Please retry shortly."}), 429

    fixtures = (data or {}).get("response") or []

    # Sort newest-first by fixture date so the slice below keeps the most
    # recent meetings. API order isn't guaranteed.
    fixtures.sort(
        key=lambda entry: ((entry.get("fixture") or {}).get("date") or ""),
        reverse=True,
    )
    fixtures = fixtures[:10]

    summary = {"home_wins": 0, "away_wins": 0, "draws": 0, "total": 0}
    formatted = []

    for entry in fixtures:
        fixture = entry.get("fixture") or {}
        teams = entry.get("teams") or {}
        goals = entry.get("goals") or {}
        league = entry.get("league") or {}
        status_short = (fixture.get("status") or {}).get("short") or ""

        past_home = teams.get("home") or {}
        past_away = teams.get("away") or {}
        past_home_id = past_home.get("id")
        past_away_id = past_away.get("id")
        home_score = goals.get("home")
        away_score = goals.get("away")

        # Only count finished fixtures toward the W/D/L summary.
        # Attribute the win to the team in the CURRENT fixture's perspective
        # (home_id arg), regardless of who was home in the historical match.
        if status_short in ("FT", "AET", "PEN") and home_score is not None and away_score is not None:
            if home_score == away_score:
                summary["draws"] += 1
                winner_id = None
            elif home_score > away_score:
                winner_id = past_home_id
            else:
                winner_id = past_away_id

            if winner_id == home_id:
                summary["home_wins"] += 1
            elif winner_id == away_id:
                summary["away_wins"] += 1

            summary["total"] += 1
        else:
            winner_id = None

        formatted.append({
            "match_id": fixture.get("id"),
            "date": fixture.get("date"),
            "competition": league.get("name") or "",
            "home_team": past_home.get("name") or "",
            "home_team_id": past_home_id,
            "away_team": past_away.get("name") or "",
            "away_team_id": past_away_id,
            "home_score": home_score,
            "away_score": away_score,
            "winner_id": winner_id,
            "status": status_short,
        })

    return jsonify({
        "match_id": match_id,
        "home_team_id": home_id,
        "away_team_id": away_id,
        "summary": summary,
        "fixtures": formatted,
    }), 200


@matches_bp.route("/matches/<int:match_id>/lineups", methods=["GET"])
def get_match_lineups(match_id):
    """Return formation, starting XI (with grid positions), and substitutes
    for both teams in a fixture.

    Used by the match-card details panel to render a pitch view.
    Lineups are typically only published ~30-60 minutes before kickoff,
    so far-future fixtures return {"home": null, "away": null}.
    """
    auth_error = _require_login()
    if auth_error:
        return auth_error

    data = call_football_api("fixture_lineups", {"fixture": match_id})
    if is_rate_limited_response(data):
        return jsonify({"error": "Rate limited by API-Football. Please retry shortly."}), 429

    response = (data or {}).get("response") or []
    home_lineup = _format_team_lineup(response[0]) if len(response) > 0 else None
    away_lineup = _format_team_lineup(response[1]) if len(response) > 1 else None

    return jsonify({
        "match_id": match_id,
        "home": home_lineup,
        "away": away_lineup,
    }), 200


@matches_bp.route("/matches/<int:match_id>/events", methods=["GET"])
def get_match_events(match_id):
    """Return goals, cards, and substitutions for a single fixture.

    Used by the home-page live match cards (and the live-matches page) to
    satisfy FR3: live match details must include yellow/red cards and
    substitutions. Lazy-loaded — only called when the user opens a card.
    """
    auth_error = _require_login()
    if auth_error:
        return auth_error

    data = call_football_api("fixture_events", {"fixture": match_id})
    if is_rate_limited_response(data):
        return jsonify({"error": "Rate limited by API-Football. Please retry shortly."}), 429
    if not data or not data.get("response"):
        return jsonify({"match_id": match_id, "events": []}), 200

    events = [_format_match_event(event) for event in data["response"]]
    # API returns roughly chronological; ensure stable ordering by minute then extra
    events.sort(key=lambda e: ((e.get("minute") or 0), (e.get("extra_minute") or 0)))

    return jsonify({"match_id": match_id, "events": events}), 200


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

    # Free plan only supports date-only queries within ~2 days of today.
    # team/league + date requires season; future seasons are plan-restricted.
    data = call_football_api("fixtures", {"date": _date_offset_string(1)})
    matches = [_map_match(m) for m in (data or {}).get("response", [])]
    matches.sort(key=lambda match: match.get("date") or "")
    return jsonify({"fixtures": matches[:10]}), 200


@matches_bp.route("/results", methods=["GET"])
def get_results():
    auth_error = _require_login()
    if auth_error:
        return auth_error

    league_id = _resolve_league_id(request.args.get("league_id"))
    team_id = request.args.get("team_id")

    if team_id:
        params = {"team": team_id, "season": CURRENT_SEASON, "status": "FT-AET-PEN"}
    else:
        params = {
            "league": league_id,
            "season": CURRENT_SEASON,
            "status": "FT-AET-PEN",
        }

    data = call_football_api("fixtures", params)
    matches = [_map_match(match, include_scores=True) for match in (data or {}).get("response", [])]
    matches.sort(key=lambda match: match.get("date") or "", reverse=True)

    return jsonify({"results": matches[:5]}), 200
