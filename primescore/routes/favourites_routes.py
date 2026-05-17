"""Favourites routes and home-page data."""

from copy import deepcopy
import logging
import random
import time
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request, session

from config import CURRENT_SEASON
from db.connection import DBContext
from routes.lookup_routes import (
    LEAGUE_CODE_TO_ID,
    LEAGUE_CODE_TO_NAME,
    is_rate_limited_payload,
    resolve_league_reference,
    resolve_player_reference,
    resolve_team_reference,
)
from services.football_api_client import call_football_api, format_standings, is_in_backoff, is_rate_limited_response

favourites_bp = Blueprint("favourites", __name__)
logger = logging.getLogger(__name__)

DISPLAY_COLUMNS_READY = False
HOME_SCREEN_CACHE = {}
HOME_SCREEN_CACHE_TTL_SECONDS = 45


def _today_string():
    return datetime.now(timezone.utc).date().isoformat()


def _date_offset_string(days):
    return (datetime.now(timezone.utc).date() + timedelta(days=days)).isoformat()


def _map_fixture(match):
    fixture = match.get("fixture", {})
    teams = match.get("teams", {})
    goals = match.get("goals", {})
    league = match.get("league", {})
    status = fixture.get("status") or {}
    home_team = teams.get("home") or {}
    away_team = teams.get("away") or {}

    return {
        "match_id": fixture.get("id"),
        "home_team": home_team.get("name"),
        # Team IDs are surfaced so the frontend can request /h2h without
        # an extra lookup round-trip per click.
        "home_team_id": home_team.get("id"),
        "away_team": away_team.get("name"),
        "away_team_id": away_team.get("id"),
        "home_score": goals.get("home"),
        "away_score": goals.get("away"),
        "status": status.get("long"),
        "minute": status.get("elapsed"),
        "match_date": fixture.get("date"),
        "date": fixture.get("date"),
        "competition": league.get("name"),
    }


def _empty_home_payload(selected_league=None):
    return {
        "live_matches": [],
        "recent_results": [],
        "upcoming_fixtures": [],
        "league_tables": [],
        "selected_league": selected_league
        or {
            "id": LEAGUE_CODE_TO_ID["PL"],
            "code": "PL",
            "name": LEAGUE_CODE_TO_NAME["PL"],
        },
        "favourite_player_stats": [],
        "favourite_team_stats": [],
        "favourite_league_stats": [],
    }


def _ensure_display_columns():
    global DISPLAY_COLUMNS_READY

    if DISPLAY_COLUMNS_READY:
        return

    with DBContext() as (_, cursor):
        cursor.execute(
            "ALTER TABLE user_favourites ADD COLUMN IF NOT EXISTS favourite_team_names TEXT[] DEFAULT '{}'"
        )
        cursor.execute(
            "ALTER TABLE user_favourites ADD COLUMN IF NOT EXISTS favourite_player_names TEXT[] DEFAULT '{}'"
        )
        cursor.execute(
            "ALTER TABLE user_favourites ADD COLUMN IF NOT EXISTS favourite_league_names TEXT[] DEFAULT '{}'"
        )

    DISPLAY_COLUMNS_READY = True


def reset_home_screen_cache():
    HOME_SCREEN_CACHE.clear()


def _cache_home_payload_key(user_id, selected_league, favourites_row, match_feed_mode="all"):
    row = favourites_row or {}
    selected = selected_league or {}

    return (
        user_id or 0,
        str(selected.get("code") or selected.get("id") or ""),
        match_feed_mode,
        tuple(row.get("favourite_teams") or []),
        tuple(row.get("favourite_players") or []),
        tuple(row.get("favourite_leagues") or []),
        tuple(row.get("favourite_team_names") or []),
        tuple(row.get("favourite_player_names") or []),
        tuple(row.get("favourite_league_names") or []),
    )


def _get_cached_home_payload(cache_key):
    cached_entry = HOME_SCREEN_CACHE.get(cache_key)
    if not cached_entry:
        return None

    if cached_entry["expires_at"] <= time.time():
        HOME_SCREEN_CACHE.pop(cache_key, None)
        return None

    return deepcopy(cached_entry["payload"])


def _set_cached_home_payload(cache_key, payload):
    HOME_SCREEN_CACHE[cache_key] = {
        "payload": deepcopy(payload),
        "expires_at": time.time() + HOME_SCREEN_CACHE_TTL_SECONDS,
    }


def _invalidate_home_cache_for_user(user_id):
    if not user_id:
        return

    for cache_key in list(HOME_SCREEN_CACHE.keys()):
        if cache_key[0] == user_id:
            HOME_SCREEN_CACHE.pop(cache_key, None)


def _get_saved_favourites_row(user_id):
    try:
        _ensure_display_columns()
        with DBContext(dict_cursor=True) as (_, cursor):
            cursor.execute(
                """
                SELECT
                    favourite_teams,
                    favourite_players,
                    favourite_leagues,
                    favourite_team_names,
                    favourite_player_names,
                    favourite_league_names
                FROM user_favourites
                WHERE user_id = %s
                """,
                (user_id,),
            )
            return cursor.fetchone()
    except Exception:
        logger.exception("favourites lookup failed")
        return None


def _clean_reference_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        items = value
    else:
        items = str(value).split(",")
    return [str(item).strip() for item in items if str(item).strip()]


def _unpack_id_name_list(raw_list):
    """Accept either plain IDs/strings or {id, name} dicts from the frontend.

    Returns (string_refs, pre_known) where:
    - string_refs  : plain string references suitable for _resolve_*_entries
    - pre_known    : {str(id): name} for items whose name was provided by the
                     client — these skip the API lookup on the backend.
    """
    string_refs = []
    pre_known = {}
    for item in (raw_list or []):
        if isinstance(item, dict):
            item_id = str(item.get("id", "")).strip()
            item_name = str(item.get("name", "")).strip()
            if item_id:
                string_refs.append(item_id)
                if item_name:
                    pre_known[item_id] = item_name
        else:
            string_refs.append(str(item).strip())
    return [r for r in string_refs if r], pre_known


def _split_player_reference(reference):
    value = str(reference or "").strip()
    if not value:
        return "", ""

    for separator in (" - ", " @ ", " | "):
        if separator in value:
            player_name, team_name = value.split(separator, 1)
            return player_name.strip(), team_name.strip()

    return value, ""


def _resolve_team_entries(references, known_id_to_name=None):
    known = known_id_to_name or {}
    team_ids = []
    team_names = []

    for reference in references:
        raw = str(reference).strip()
        # Already-resolved: numeric ID with a stored name → skip the API call
        if raw.isdigit() and raw in known:
            team_id = int(raw)
            if team_id not in team_ids:
                team_ids.append(team_id)
                team_names.append(known[raw])
            continue

        team = resolve_team_reference(reference)
        if is_rate_limited_payload(team):
            return team
        if not team:
            return {"error": f'Team "{reference}" was not found.'}
        if team["id"] in team_ids:
            continue
        team_ids.append(int(team["id"]))
        team_names.append(team["name"])

    return {"ids": team_ids, "names": team_names}


def _resolve_player_entries(references, known_id_to_name=None):
    known = known_id_to_name or {}
    player_ids = []
    player_names = []

    for reference in references:
        player_name, team_name = _split_player_reference(reference)

        if not player_name:
            continue

        # Already-resolved: numeric ID with a stored name → skip the API call
        if player_name.isdigit() and player_name in known:
            player_id = int(player_name)
            if player_id not in player_ids:
                player_ids.append(player_id)
                player_names.append(known[player_name])
            continue

        player = resolve_player_reference(player_name, team_reference=team_name or None)
        if is_rate_limited_payload(player):
            return player
        if not player:
            if not team_name and not player_name.isdigit():
                return {"error": f'Player "{reference}" was not found. Use "Player Name - Team Name".'}
            return {"error": f'Player "{reference}" was not found.'}
        if player["id"] in player_ids:
            continue
        player_ids.append(int(player["id"]))
        player_names.append(player["name"])

    return {"ids": player_ids, "names": player_names}


def _resolve_league_entries(references, known_id_to_name=None):
    known = known_id_to_name or {}
    league_codes = []
    league_names = []

    for reference in references:
        league = resolve_league_reference(reference)
        if is_rate_limited_payload(league):
            return league
        if not league:
            return {"error": f'League "{reference}" was not found.'}
        if league["code"] in league_codes:
            continue
        league_codes.append(str(league["code"]))
        # Prefer client-supplied name when the resolver couldn't find a real one
        # (e.g. non-standard leagues whose numeric ID isn't in our local map).
        resolved_name = league.get("name", "")
        raw = str(reference).strip()
        if known.get(raw) and (not resolved_name or resolved_name == raw):
            resolved_name = known[raw]
        league_names.append(resolved_name)

    return {"codes": league_codes, "names": league_names}


def _display_favourites(row):
    team_names = row.get("favourite_team_names") or []
    player_names = row.get("favourite_player_names") or []
    league_names = row.get("favourite_league_names") or []
    league_codes = row.get("favourite_leagues") or []
    team_ids = row.get("favourite_teams") or []
    player_ids = row.get("favourite_players") or []

    if not league_names and league_codes:
        league_names = [LEAGUE_CODE_TO_NAME.get(str(code), str(code)) for code in league_codes]

    # Old DB rows have empty name columns — resolve IDs to display names on the fly.
    if not team_names and team_ids:
        resolved = []
        for tid in team_ids:
            team = resolve_team_reference(str(tid))
            if team and not is_rate_limited_payload(team):
                resolved.append(team.get("name", str(tid)))
            else:
                resolved.append(str(tid))
        team_names = resolved

    if not player_names and player_ids:
        resolved = []
        for pid in player_ids:
            player = resolve_player_reference(str(pid))
            if player and not is_rate_limited_payload(player):
                resolved.append(player.get("name", str(pid)))
            else:
                resolved.append(str(pid))
        player_names = resolved

    return {
        "favourite_teams": team_names,
        "favourite_players": player_names,
        "favourite_leagues": league_names,
        "favourite_team_ids": team_ids,
        "favourite_player_ids": player_ids,
        "favourite_league_codes": league_codes,
    }


def _get_home_league_context(preferred_reference=None, favourites_row=None):
    default_context = {
        "id": LEAGUE_CODE_TO_ID["PL"],
        "code": "PL",
        "name": LEAGUE_CODE_TO_NAME["PL"],
    }

    if preferred_reference:
        preferred_league = resolve_league_reference(preferred_reference)
        if is_rate_limited_payload(preferred_league):
            return default_context
        if preferred_league:
            return {
                "id": preferred_league["id"],
                "code": str(preferred_league.get("code", preferred_league["id"])),
                "name": preferred_league.get("name", default_context["name"]),
            }

    if favourites_row is not None:
        row = favourites_row
    elif "user_id" not in session:
        return default_context
    else:
        row = _get_saved_favourites_row(session["user_id"])

    if not row:
        return default_context

    favourite_codes = row.get("favourite_leagues") or []
    favourite_names = row.get("favourite_league_names") or []

    for league_code in reversed(favourite_codes):
        code = str(league_code or "").upper()
        if code in LEAGUE_CODE_TO_ID:
            return {
                "id": LEAGUE_CODE_TO_ID[code],
                "code": code,
                "name": LEAGUE_CODE_TO_NAME.get(code, code),
            }

    for league_reference in list(reversed(favourite_codes)) + list(reversed(favourite_names)):
        resolved_league = resolve_league_reference(league_reference)
        if is_rate_limited_payload(resolved_league):
            return default_context
        if resolved_league:
            return {
                "id": resolved_league["id"],
                "code": str(resolved_league.get("code", resolved_league["id"])),
                "name": resolved_league.get("name", default_context["name"]),
            }

    return default_context


def _match_involves_team_ids(match, team_ids):
    home_team = (match.get("teams", {}).get("home") or {}).get("id")
    away_team = (match.get("teams", {}).get("away") or {}).get("id")
    return home_team in team_ids or away_team in team_ids


def _match_involves_league_ids(match, league_ids):
    return (match.get("league") or {}).get("id") in league_ids


def _dedupe_and_slice(matches, *, limit=5, reverse=False, randomize=False):
    items = list(matches)
    if randomize:
        random.shuffle(items)
    else:
        items.sort(key=lambda match: match.get("date") or match.get("match_date") or "", reverse=reverse)

    deduped = []
    seen_match_ids = set()
    for match in items:
        match_id = match.get("match_id")
        dedupe_key = match_id or (
            match.get("home_team"),
            match.get("away_team"),
            match.get("date") or match.get("match_date"),
        )
        if dedupe_key in seen_match_ids:
            continue
        seen_match_ids.add(dedupe_key)
        deduped.append(match)
        if len(deduped) >= limit:
            break

    return deduped


def _load_filtered_live_matches(team_ids=None, league_ids=None):
    live_matches = call_football_api("fixtures", {"live": "all"})
    if is_rate_limited_response(live_matches) or not live_matches or not live_matches.get("response"):
        return []

    response_items = live_matches["response"]
    if team_ids:
        response_items = [match for match in response_items if _match_involves_team_ids(match, team_ids)]
    elif league_ids:
        response_items = [match for match in response_items if _match_involves_league_ids(match, league_ids)]

    mapped_matches = [_map_fixture(match) for match in response_items]
    return _dedupe_and_slice(mapped_matches, limit=5, randomize=not (team_ids or league_ids))


def _load_league_matches(league_id, status, *, limit=5, randomize=False):
    if status == "NS":
        # Free plan only allows date-only queries within ~2 days of today.
        # No team or league filter is possible without season.
        data = call_football_api("fixtures", {"date": _date_offset_string(1)})
        if is_rate_limited_response(data):
            return []
        mapped_matches = [_map_fixture(m) for m in (data or {}).get("response", [])]
        return _dedupe_and_slice(mapped_matches, limit=limit, randomize=randomize)

    params = {"league": league_id, "season": CURRENT_SEASON, "status": status}
    data = call_football_api("fixtures", params)
    if is_rate_limited_response(data):
        return []

    mapped_matches = [_map_fixture(match) for match in (data or {}).get("response", [])]
    return _dedupe_and_slice(mapped_matches, limit=limit, reverse=True, randomize=randomize)


def _load_team_matches(team_ids, status):
    aggregated_matches = []
    for team_id in team_ids:
        if status == "NS":
            # team + date requires season which the free plan restricts for future dates.
            # Fall through to the league-level date query instead.
            continue
        else:
            params = {"team": team_id, "season": CURRENT_SEASON, "status": status}
        data = call_football_api("fixtures", params)
        if is_rate_limited_response(data):
            break
        aggregated_matches.extend(_map_fixture(match) for match in (data or {}).get("response", []))

    return _dedupe_and_slice(aggregated_matches, limit=5, reverse=status != "NS")


def _ordered_league_contexts(home_league, favourite_codes):
    if not favourite_codes:
        return [home_league]

    ordered_codes = []
    selected_code = str(home_league.get("code", "")).upper()
    if selected_code and selected_code in favourite_codes:
        ordered_codes.append(selected_code)

    for league_code in favourite_codes:
        code = str(league_code or "").upper()
        if code not in ordered_codes and code in LEAGUE_CODE_TO_ID:
            ordered_codes.append(code)

    ordered_contexts = []
    for code in ordered_codes:
        ordered_contexts.append(
            {
                "id": LEAGUE_CODE_TO_ID[code],
                "code": code,
                "name": LEAGUE_CODE_TO_NAME.get(code, code),
            }
        )

    return ordered_contexts or [home_league]


def _load_league_tables(league_contexts):
    league_tables = []
    for league_context in league_contexts:
        standings = call_football_api("standings", {"league": league_context["id"], "season": CURRENT_SEASON})
        if is_rate_limited_response(standings):
            break

        formatted = format_standings(standings)
        if formatted.get("standings"):
            league_tables.append(formatted)

    return league_tables


def _sum_player_stats_for_home(stats_list):
    """Aggregate stats across all competition entries for a player (home-card version)."""
    totals = {"goals": 0, "assists": 0, "appearances": 0, "minutes": 0,
              "yellow_cards": 0, "red_cards": 0}
    ratings = []
    position = None
    current_team = None

    for stat in (stats_list or []):
        games = stat.get("games") or {}
        goals_data = stat.get("goals") or {}
        cards_data = stat.get("cards") or {}

        # NOTE: API-Football spells this field "appearences" (their typo)
        totals["appearances"] += games.get("appearences") or 0
        totals["minutes"] += games.get("minutes") or 0
        totals["goals"] += goals_data.get("total") or 0
        totals["assists"] += goals_data.get("assists") or 0
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


def _format_favourite_player_stat(player_id, fallback_name=""):
    best_data = None
    best_appearances = -1

    for season in (CURRENT_SEASON, CURRENT_SEASON - 1, CURRENT_SEASON - 2):
        data = call_football_api("players", {"id": player_id, "season": season})
        if is_rate_limited_response(data) or not data or not data.get("response"):
            continue
        player_entry = data["response"][0]
        stats_list = player_entry.get("statistics") or []
        totals, _, _ = _sum_player_stats_for_home(stats_list)
        appearances = totals["appearances"]
        if best_data is None or appearances > best_appearances:
            best_data = player_entry
            best_appearances = appearances
        if appearances > 0:
            break

    if not best_data:
        return None

    player = best_data.get("player", {})
    stats_list = best_data.get("statistics") or []
    totals, position, current_team = _sum_player_stats_for_home(stats_list)

    return {
        "player_id": player_id,
        "player_name": player.get("name") or fallback_name or f"Player {player_id}",
        "photo": player.get("photo", ""),
        "current_team": current_team or "",
        "position": position or "",
        "statistics": totals,
    }


def _format_favourite_team_stat(team_id, fallback_name=""):
    """Fetch the league standing for a single favourite team."""
    data = call_football_api("standings", {"team": team_id, "season": CURRENT_SEASON})
    if is_rate_limited_response(data) or not data or not data.get("response"):
        return None

    league_entry = (data["response"][0] or {}).get("league", {})
    standings_groups = league_entry.get("standings") or []

    team_standing = None
    for group in standings_groups:
        for entry in group:
            if (entry.get("team") or {}).get("id") == team_id:
                team_standing = entry
                break
        if team_standing:
            break

    if not team_standing:
        return None

    team_info = team_standing.get("team") or {}
    all_stats = team_standing.get("all") or {}
    goals = all_stats.get("goals") or {}

    return {
        "team_id": team_id,
        "team_name": team_info.get("name") or fallback_name or f"Team {team_id}",
        "team_crest": team_info.get("logo", ""),
        "league_name": league_entry.get("name", ""),
        "season": str(league_entry.get("season", CURRENT_SEASON)),
        "position": team_standing.get("rank"),
        "points": team_standing.get("points"),
        "played": all_stats.get("played"),
        "won": all_stats.get("win"),
        "drawn": all_stats.get("draw"),
        "lost": all_stats.get("lose"),
        "goals_for": goals.get("for"),
        "goals_against": goals.get("against"),
        "goal_difference": team_standing.get("goalsDiff"),
        "form": team_standing.get("form", ""),
    }


def _format_favourite_league_stat(league_code):
    """Fetch the full standings for a favourite league and return a card-friendly summary."""
    league_id = LEAGUE_CODE_TO_ID.get(str(league_code).upper())
    if not league_id:
        return None

    league_name = LEAGUE_CODE_TO_NAME.get(str(league_code).upper(), league_code)
    standings_data = call_football_api("standings", {"league": league_id, "season": CURRENT_SEASON})
    if is_rate_limited_response(standings_data) or not standings_data:
        return None

    formatted = format_standings(standings_data)
    if not formatted.get("standings"):
        return None

    league_raw = ((standings_data.get("response") or [{}])[0]).get("league", {})

    return {
        "league_code": league_code,
        "league_name": formatted.get("competition") or league_name,
        "league_logo": league_raw.get("logo", ""),
        "season": formatted.get("season", str(CURRENT_SEASON)),
        "top_teams": formatted["standings"][:5],
    }


@favourites_bp.route("/home-screen", methods=["GET"])
def get_home_screen():
    preferred_league_reference = request.args.get("league")
    match_feed_mode = request.args.get("mode", "all")  # "all" or "my_teams"
    user_id = session.get("user_id")
    favourites_row = _get_saved_favourites_row(user_id) if user_id else None
    home_league = _get_home_league_context(
        preferred_reference=preferred_league_reference,
        favourites_row=favourites_row,
    )
    cache_key = _cache_home_payload_key(user_id, home_league, favourites_row, match_feed_mode)
    cached_payload = _get_cached_home_payload(cache_key)
    if cached_payload is not None:
        return jsonify(cached_payload), 200

    home_data = _empty_home_payload(selected_league=home_league)

    favourite_team_ids = [int(team_id) for team_id in (favourites_row or {}).get("favourite_teams", []) or []]
    favourite_player_ids = [int(player_id) for player_id in (favourites_row or {}).get("favourite_players", []) or []]
    favourite_player_names = (favourites_row or {}).get("favourite_player_names") or []
    favourite_league_codes = [
        str(league_code).upper()
        for league_code in ((favourites_row or {}).get("favourite_leagues") or [])
        if str(league_code).upper() in LEAGUE_CODE_TO_ID
    ]

    has_personalised_home = bool(favourite_team_ids or favourite_player_ids or favourite_league_codes)

    if favourite_league_codes:
        home_data["league_tables"] = _load_league_tables([home_league])
    elif not has_personalised_home:
        home_data["league_tables"] = _load_league_tables([home_league])

    fallback_league_id = home_league["id"]
    use_my_teams = match_feed_mode == "my_teams" and has_personalised_home

    if use_my_teams:
        # My Teams mode — show only favourite team/league matches
        if favourite_team_ids:
            home_data["live_matches"] = _load_filtered_live_matches(team_ids=set(favourite_team_ids))
            home_data["upcoming_fixtures"] = _load_team_matches(favourite_team_ids, "NS")
            home_data["recent_results"] = _load_team_matches(favourite_team_ids, "FT-AET-PEN")
        elif favourite_league_codes:
            selected_league_id = home_league["id"]
            home_data["live_matches"] = _load_filtered_live_matches(league_ids={selected_league_id})
            home_data["upcoming_fixtures"] = _load_league_matches(selected_league_id, "NS")
            home_data["recent_results"] = _load_league_matches(selected_league_id, "FT-AET-PEN")
        # In My Teams mode, no fallback — empty sections show "no matches for your teams"
    else:
        # All Matches mode — show general feed
        home_data["live_matches"] = _load_filtered_live_matches()
        home_data["upcoming_fixtures"] = _load_league_matches(fallback_league_id, "NS", limit=5, randomize=True)
        home_data["recent_results"] = _load_league_matches(fallback_league_id, "FT-AET-PEN", limit=5, randomize=True)

    # Lazy loading: only fetch stats for the FIRST item of each type on initial
    # page load.  The remaining cards are fetched on demand by /api/favourite-stats
    # as the user navigates with the ← → buttons, capping startup API calls at ≤3.
    favourite_team_names = (favourites_row or {}).get("favourite_team_names") or []

    if favourite_player_ids:
        first_player_stat = _format_favourite_player_stat(
            favourite_player_ids[0],
            fallback_name=favourite_player_names[0] if favourite_player_names else "",
        )
        if first_player_stat:
            home_data["favourite_player_stats"].append(first_player_stat)

    if favourite_team_ids:
        first_team_stat = _format_favourite_team_stat(
            favourite_team_ids[0],
            fallback_name=favourite_team_names[0] if favourite_team_names else "",
        )
        if first_team_stat:
            home_data["favourite_team_stats"].append(first_team_stat)

    if favourite_league_codes:
        first_league_stat = _format_favourite_league_stat(favourite_league_codes[0])
        if first_league_stat:
            home_data["favourite_league_stats"].append(first_league_stat)

    # Only cache the payload when the API client is NOT in rate-limit backoff.
    # If backoff is active some calls were skipped and returned empty arrays;
    # caching that would poison subsequent requests for up to 45 seconds.
    if not is_in_backoff():
        _set_cached_home_payload(cache_key, home_data)
    else:
        logger.warning(
            "Home screen built during rate-limit backoff — skipping cache to allow retry."
        )
    return jsonify(home_data), 200


@favourites_bp.route("/favourite-stats", methods=["GET"])
def get_favourite_stat():
    """Lazy-load the stat card for a single favourite item (team / player / league).

    Query parameters:
        type  – "team", "player", or "league"
        id    – numeric team/player ID, or league code (e.g. "PL")
    """
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401

    stat_type = request.args.get("type", "").strip().lower()
    item_id = request.args.get("id", "").strip()

    if not stat_type or not item_id:
        return jsonify({"error": "Missing type or id parameter"}), 400

    row = _get_saved_favourites_row(session["user_id"]) or {}

    if stat_type == "team":
        try:
            team_id = int(item_id)
        except ValueError:
            return jsonify({"error": "Invalid team id"}), 400

        saved_ids = [int(t) for t in (row.get("favourite_teams") or [])]
        if team_id not in saved_ids:
            return jsonify({"error": "Not in favourites"}), 404

        team_names = row.get("favourite_team_names") or []
        try:
            idx = saved_ids.index(team_id)
            fallback_name = team_names[idx] if idx < len(team_names) else ""
        except ValueError:
            fallback_name = ""

        stat = _format_favourite_team_stat(team_id, fallback_name=fallback_name)
        if not stat:
            return jsonify({"error": "Could not load team stats (rate limited or no data)"}), 503
        return jsonify(stat), 200

    elif stat_type == "player":
        try:
            player_id = int(item_id)
        except ValueError:
            return jsonify({"error": "Invalid player id"}), 400

        saved_ids = [int(p) for p in (row.get("favourite_players") or [])]
        if player_id not in saved_ids:
            return jsonify({"error": "Not in favourites"}), 404

        player_names = row.get("favourite_player_names") or []
        try:
            idx = saved_ids.index(player_id)
            fallback_name = player_names[idx] if idx < len(player_names) else ""
        except ValueError:
            fallback_name = ""

        stat = _format_favourite_player_stat(player_id, fallback_name=fallback_name)
        if not stat:
            return jsonify({"error": "Could not load player stats (rate limited or no data)"}), 503
        return jsonify(stat), 200

    elif stat_type == "league":
        saved_codes = [str(c).upper() for c in (row.get("favourite_leagues") or [])]
        league_code = item_id.upper()
        if league_code not in saved_codes:
            return jsonify({"error": "Not in favourites"}), 404

        stat = _format_favourite_league_stat(league_code)
        if not stat:
            return jsonify({"error": "Could not load league stats (rate limited or no data)"}), 503
        return jsonify(stat), 200

    return jsonify({"error": "Invalid type — use team, player or league"}), 400


@favourites_bp.route("/favourites", methods=["GET"])
def get_favourites():
    empty_response = {
        "favourite_teams": [],
        "favourite_players": [],
        "favourite_leagues": [],
        "favourite_team_ids": [],
        "favourite_player_ids": [],
        "favourite_league_codes": [],
    }

    if "user_id" not in session:
        return jsonify(empty_response), 200

    row = _get_saved_favourites_row(session["user_id"])

    if not row:
        return jsonify(empty_response), 200

    return jsonify(_display_favourites(row)), 200


@favourites_bp.route("/favourites", methods=["POST"])
def update_favourites():
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401

    data = request.get_json(silent=True) or {}

    # Accept both plain IDs and {id, name} dicts from the frontend.
    # Names supplied by the client avoid an API round-trip for every item.
    team_references, team_pre_known = _unpack_id_name_list(data.get("favourite_teams", []))
    player_references, player_pre_known = _unpack_id_name_list(data.get("favourite_players", []))
    league_references, league_pre_known = _unpack_id_name_list(data.get("favourite_leagues", []))

    team_references = _clean_reference_list(team_references)
    player_references = _clean_reference_list(player_references)
    league_references = _clean_reference_list(league_references)

    if len(team_references) > 5:
        return jsonify({"error": "You can save up to 5 favourite teams."}), 400
    if len(player_references) > 10:
        return jsonify({"error": "You can save up to 10 favourite players."}), 400
    if len(league_references) > 3:
        return jsonify({"error": "You can save up to 3 favourite leagues."}), 400

    # Merge three sources of known names (DB row wins over client-supplied names
    # to guard against accidental overwrites of verified data):
    #   1. Names sent by the client for newly selected items (team_pre_known)
    #   2. Names already stored in the DB for existing items (existing_row)
    existing_row = _get_saved_favourites_row(session["user_id"]) or {}
    db_team_id_to_name = {
        str(tid): name
        for tid, name in zip(
            existing_row.get("favourite_teams") or [],
            existing_row.get("favourite_team_names") or [],
        )
        if tid and name
    }
    db_player_id_to_name = {
        str(pid): name
        for pid, name in zip(
            existing_row.get("favourite_players") or [],
            existing_row.get("favourite_player_names") or [],
        )
        if pid and name
    }
    known_team_id_to_name = {**team_pre_known, **db_team_id_to_name}
    known_player_id_to_name = {**player_pre_known, **db_player_id_to_name}

    resolved_teams = _resolve_team_entries(team_references, known_id_to_name=known_team_id_to_name)
    if is_rate_limited_payload(resolved_teams):
        return jsonify({"error": "Rate limited by API-Football. Please retry shortly."}), 429
    if resolved_teams.get("error"):
        return jsonify({"error": resolved_teams["error"]}), 404

    resolved_players = _resolve_player_entries(player_references, known_id_to_name=known_player_id_to_name)
    if is_rate_limited_payload(resolved_players):
        return jsonify({"error": "Rate limited by API-Football. Please retry shortly."}), 429
    if resolved_players.get("error"):
        return jsonify({"error": resolved_players["error"]}), 404

    resolved_leagues = _resolve_league_entries(league_references, known_id_to_name=league_pre_known)
    if is_rate_limited_payload(resolved_leagues):
        return jsonify({"error": "Rate limited by API-Football. Please retry shortly."}), 429
    if resolved_leagues.get("error"):
        return jsonify({"error": resolved_leagues["error"]}), 404

    try:
        _ensure_display_columns()
        with DBContext() as (_, cursor):
            cursor.execute(
                """
                INSERT INTO user_favourites (
                    user_id,
                    favourite_teams,
                    favourite_players,
                    favourite_leagues,
                    favourite_team_names,
                    favourite_player_names,
                    favourite_league_names,
                    updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    favourite_teams = EXCLUDED.favourite_teams,
                    favourite_players = EXCLUDED.favourite_players,
                    favourite_leagues = EXCLUDED.favourite_leagues,
                    favourite_team_names = EXCLUDED.favourite_team_names,
                    favourite_player_names = EXCLUDED.favourite_player_names,
                    favourite_league_names = EXCLUDED.favourite_league_names,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    session["user_id"],
                    resolved_teams["ids"],
                    resolved_players["ids"],
                    resolved_leagues["codes"],
                    resolved_teams["names"],
                    resolved_players["names"],
                    resolved_leagues["names"],
                    datetime.now(),
                ),
            )
    except Exception:
        logger.exception("update_favourites DB error")
        return jsonify({"error": "Could not save favourites"}), 500

    _invalidate_home_cache_for_user(session.get("user_id"))
    return jsonify(
        {
            "message": "Saved",
            "favourite_teams": resolved_teams["names"],
            "favourite_players": resolved_players["names"],
            "favourite_leagues": resolved_leagues["names"],
            "favourite_team_ids": resolved_teams["ids"],
            "favourite_player_ids": resolved_players["ids"],
            "favourite_league_codes": resolved_leagues["codes"],
        }
    ), 200
