"""
PrimeScore - Notification Settings routes (FR9)
"""

import logging
from flask import Blueprint, request, jsonify, session
from datetime import datetime

from db.connection import DBContext

notifications_bp = Blueprint('notifications', __name__)
logger = logging.getLogger(__name__)

_DEFAULT_SETTINGS = {
    'goals_notifications':            False,
    'match_start_notifications':      False,
    'match_end_notifications':        False,
    'favourite_team_notifications':   False,
    'favourite_player_notifications': False,
}


@notifications_bp.route('/notifications/settings', methods=['GET'])
def get_notification_settings():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    try:
        with DBContext(dict_cursor=True) as (_, cur):
            cur.execute(
                '''SELECT goals_notifications, match_start_notifications,
                          match_end_notifications, favourite_team_notifications,
                          favourite_player_notifications
                   FROM notification_settings WHERE user_id = %s''',
                (session['user_id'],)
            )
            row = cur.fetchone()
    except RuntimeError:
        return jsonify({'error': 'Database unavailable'}), 503
    except Exception:
        logger.exception("get_notification_settings error")   # FIX: was print()
        return jsonify({'error': 'Could not load notification settings'}), 500

    return jsonify(dict(row) if row else _DEFAULT_SETTINGS), 200


@notifications_bp.route('/notifications/settings', methods=['POST'])
def update_notification_settings():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    data  = request.get_json(silent=True) or {}
    goals = bool(data.get('goals_notifications',            False))
    start = bool(data.get('match_start_notifications',      False))
    end   = bool(data.get('match_end_notifications',        False))
    fav_t = bool(data.get('favourite_team_notifications',   False))
    fav_p = bool(data.get('favourite_player_notifications', False))

    try:
        with DBContext() as (_, cur):
            cur.execute(
                '''INSERT INTO notification_settings
                       (user_id, goals_notifications, match_start_notifications,
                        match_end_notifications, favourite_team_notifications,
                        favourite_player_notifications, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (user_id) DO UPDATE SET
                       goals_notifications            = EXCLUDED.goals_notifications,
                       match_start_notifications      = EXCLUDED.match_start_notifications,
                       match_end_notifications        = EXCLUDED.match_end_notifications,
                       favourite_team_notifications   = EXCLUDED.favourite_team_notifications,
                       favourite_player_notifications = EXCLUDED.favourite_player_notifications,
                       updated_at                     = EXCLUDED.updated_at''',
                (session['user_id'], goals, start, end, fav_t, fav_p, datetime.now())
            )
    except RuntimeError:
        return jsonify({'error': 'Database unavailable'}), 503
    except Exception:
        logger.exception("update_notification_settings error")   # FIX: was print()
        return jsonify({'error': 'Could not save notification settings'}), 500

    return jsonify({'message': 'Notification settings saved'}), 200