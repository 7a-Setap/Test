"""
PrimeScore - Profile routes
GET  /api/profile          → return username, email, display_name, bio
POST /api/profile          → save display_name and bio
POST /api/change-password  → verify current password, save new one
"""

import logging
from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash

from db.connection import DBContext

profile_bp = Blueprint('profile', __name__)
logger = logging.getLogger(__name__)


@profile_bp.route('/profile', methods=['GET'])
def get_profile():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    try:
        with DBContext(dict_cursor=True) as (_, cur):
            cur.execute(
                'SELECT username, email, display_name, bio FROM users WHERE user_id = %s',
                (session['user_id'],)
            )
            row = cur.fetchone()
    except RuntimeError:
        return jsonify({'error': 'Database unavailable'}), 503
    except Exception:
        logger.exception("get_profile error")   # FIX: was print()
        return jsonify({'error': 'Could not load profile'}), 500

    if not row:
        return jsonify({'error': 'User not found'}), 404

    return jsonify({
        'username':     row['username'],
        'email':        row['email']        or '',
        'display_name': row['display_name'] or '',
        'bio':          row['bio']          or '',
    }), 200


@profile_bp.route('/profile', methods=['POST'])
def update_profile():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    data         = request.get_json(silent=True) or {}
    display_name = (data.get('display_name') or '').strip()
    bio          = (data.get('bio')          or '').strip()

    if len(display_name) > 100:
        return jsonify({'error': 'Display name must be 100 characters or fewer'}), 400
    if len(bio) > 500:
        return jsonify({'error': 'Bio must be 500 characters or fewer'}), 400

    try:
        with DBContext() as (_, cur):
            cur.execute(
                'UPDATE users SET display_name = %s, bio = %s WHERE user_id = %s',
                (display_name or None, bio or None, session['user_id'])
            )
    except RuntimeError:
        return jsonify({'error': 'Database unavailable'}), 503
    except Exception:
        logger.exception("update_profile error")   # FIX: was print()
        return jsonify({'error': 'Could not save profile'}), 500

    session['display_name'] = display_name
    return jsonify({'message': 'Profile updated successfully', 'display_name': display_name}), 200


@profile_bp.route('/change-password', methods=['POST'])
def change_password():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401

    data             = request.get_json(silent=True) or {}
    current_password = data.get('current_password', '')
    new_password     = data.get('new_password', '')

    if not current_password or not new_password:
        return jsonify({'error': 'Current and new password are required'}), 400
    if len(new_password) < 8:
        return jsonify({'error': 'New password must be at least 8 characters'}), 400

    try:
        with DBContext(dict_cursor=True) as (_, cur):
            cur.execute(
                'SELECT password_hash FROM users WHERE user_id = %s',
                (session['user_id'],)
            )
            row = cur.fetchone()
            if not row:
                return jsonify({'error': 'User not found'}), 404
            if not check_password_hash(row['password_hash'], current_password):
                return jsonify({'error': 'Current password is incorrect'}), 401

            cur.execute(
                'UPDATE users SET password_hash = %s WHERE user_id = %s',
                (generate_password_hash(new_password), session['user_id'])
            )
    except RuntimeError:
        return jsonify({'error': 'Database unavailable'}), 503
    except Exception:
        logger.exception("change_password error")   # FIX: was print()
        return jsonify({'error': 'Could not change password'}), 500

    return jsonify({'message': 'Password changed successfully'}), 200