"""PrimeScore - Favourites routes (FR1, FR2)"""

import logging
from flask import Blueprint, request, jsonify, session
from datetime import datetime, timedelta

from db.connection import DBContext
from services.api import call_football_api, format_standings
from config import CURRENT_SEASON

favourites_bp = Blueprint('favourites', __name__)
logger = logging.getLogger(__name__)

# Map fixture response to frontend shape
def _map_fixture(match):
    fixture = match.get('fixture', {})
    teams   = match.get('teams',   {})
    goals   = match.get('goals',   {})
    league  = match.get('league',  {})
    return {
        'match_id':   fixture.get('id'),
        'home_team':  teams.get('home', {}).get('name'),
        'away_team':  teams.get('away', {}).get('name'),
        'home_score': goals.get('home'),
        'away_score': goals.get('away'),
        'status':     (fixture.get('status') or {}).get('long'),
        'minute':     (fixture.get('status') or {}).get('elapsed'),
        'match_date': fixture.get('date'),
        'date':       fixture.get('date'),
        'competition': league.get('name'),
    }


@favourites_bp.route('/home-screen', methods=['GET'])
def get_home_screen():
    # Public home: show default PL table even when not logged in
    raw = call_football_api('standings', {'league': 39, 'season': CURRENT_SEASON})
    home_data = {
        'live_matches':      [],
        'recent_results':    [],
        'upcoming_fixtures': [],
        'league_tables':     []
    }

    if raw:
        formatted = format_standings(raw)
        if formatted:
            home_data['league_tables'].append(formatted)

    # Live matches (status live: all)
    live_resp = call_football_api('fixtures', {'live': 'all'})
    if live_resp and live_resp.get('response'):
        home_data['live_matches'] = [_map_fixture(m) for m in live_resp['response']][:5]

    # Upcoming fixtures: query by tomorrow's date (free plan supports date filter)
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    upcoming_resp = call_football_api('fixtures', {'date': tomorrow})
    if upcoming_resp and upcoming_resp.get('response'):
        upcoming = [_map_fixture(m) for m in upcoming_resp['response']]
        upcoming.sort(key=lambda x: x.get('date') or '')
        home_data['upcoming_fixtures'] = upcoming[:5]

    # Recent results: Premier League, current season, finished
    results_resp = call_football_api('fixtures', {
        'league': 39, 'season': CURRENT_SEASON, 'status': 'FT'
    })
    if results_resp and results_resp.get('response'):
        results = [_map_fixture(m) for m in results_resp['response']]
        results.sort(key=lambda x: x.get('date') or '', reverse=True)
        home_data['recent_results'] = results[:5]

    return jsonify(home_data), 200


@favourites_bp.route('/favourites', methods=['GET'])
def get_favourites():
    empty = {'favourite_teams': [], 'favourite_players': [], 'favourite_leagues': []}

    if 'user_id' not in session:
        return jsonify(empty), 200

    try:
        with DBContext(dict_cursor=True) as (_, cur):
            cur.execute(
                'SELECT favourite_teams, favourite_players, favourite_leagues '
                'FROM user_favourites WHERE user_id = %s',
                (session['user_id'],)
            )
            row = cur.fetchone()
    except Exception:
        logger.exception("get_favourites DB error")
        return jsonify(empty), 200

    if not row:
        return jsonify(empty), 200

    return jsonify({
        'favourite_teams':   row['favourite_teams']   or [],
        'favourite_players': row['favourite_players'] or [],
        'favourite_leagues': row['favourite_leagues'] or [],
    }), 200


@favourites_bp.route('/favourites', methods=['POST'])
def update_favourites():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    data    = request.get_json(silent=True) or {}
    teams   = data.get('favourite_teams',   [])
    players = data.get('favourite_players', [])
    leagues = data.get('favourite_leagues', [])

    try:
        with DBContext() as (_, cur):
            cur.execute(
                '''INSERT INTO user_favourites
                       (user_id, favourite_teams, favourite_players, favourite_leagues, updated_at)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (user_id) DO UPDATE SET
                       favourite_teams   = EXCLUDED.favourite_teams,
                       favourite_players = EXCLUDED.favourite_players,
                       favourite_leagues = EXCLUDED.favourite_leagues,
                       updated_at        = EXCLUDED.updated_at''',
                (session['user_id'], teams, players, leagues, datetime.now())
            )
    except Exception:
        logger.exception("update_favourites DB error")
        return jsonify({'error': 'Could not save favourites'}), 500

    return jsonify({'message': 'Saved'}), 200
