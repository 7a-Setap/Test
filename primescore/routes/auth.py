"""
PrimeScore - Auth routes
"""

from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from collections import defaultdict
from time import time
import logging

from db.connection import DBContext
from psycopg2.extras import RealDictCursor

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

# Rate limiting (max 5 attempts per 5 minutes per IP)
login_attempts = defaultdict(list)
MAX_LOGIN_ATTEMPTS = 5
LOGIN_WINDOW = 300


def check_rate_limit(ip):
    now = time()
    login_attempts[ip] = [t for t in login_attempts[ip] if now - t < LOGIN_WINDOW]
    return len(login_attempts[ip]) < MAX_LOGIN_ATTEMPTS


def record_login_attempt(ip):
    login_attempts[ip].append(time())


def _validate_registration(username, email, password):
    if not username or not password or not email:
        return 'Username, email and password are required'
    if len(username) < 3:
        return 'Username must be at least 3 characters'
    if len(password) < 8:
        return 'Password must be at least 8 characters'
    if '@' not in email:
        return 'Please enter a valid email address'
    return None


@auth_bp.route('/register', methods=['POST'])
def register():
    data     = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    email    = (data.get('email')    or '').strip()
    password = (data.get('password') or '')

    err = _validate_registration(username, email, password)
    if err:
        return jsonify({'error': err}), 400

    try:
        with DBContext() as (conn, cur):
            cur.execute('SELECT user_id FROM users WHERE username = %s', (username,))
            if cur.fetchone():
                return jsonify({'error': 'Username already taken'}), 409

            cur.execute('SELECT user_id FROM users WHERE email = %s', (email,))
            if cur.fetchone():
                return jsonify({'error': 'Email already registered'}), 409

            cur.execute(
                '''INSERT INTO users (username, email, password_hash, created_at)
                   VALUES (%s, %s, %s, %s) RETURNING user_id''',
                (username, email, generate_password_hash(password), datetime.now())
            )
            user_id = cur.fetchone()[0]

            # FIX: Seed companion rows so FK constraints never fail on first login
            cur.execute(
                'INSERT INTO user_favourites (user_id) VALUES (%s) ON CONFLICT DO NOTHING',
                (user_id,)
            )
            cur.execute(
                'INSERT INTO notification_settings (user_id) VALUES (%s) ON CONFLICT DO NOTHING',
                (user_id,)
            )

    except RuntimeError:
        return jsonify({'error': 'Database unavailable'}), 503
    except Exception:
        logger.exception("Registration error")
        return jsonify({'error': 'Registration failed'}), 500

    return jsonify({'message': 'Registration successful', 'user_id': user_id}), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    client_ip = request.remote_addr
    if not check_rate_limit(client_ip):
        return jsonify({'error': 'Too many login attempts. Try again later.'}), 429

    data     = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = (data.get('password') or '')

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400

    try:
        with DBContext(dict_cursor=True) as (conn, cur):
            cur.execute(
                'SELECT user_id, username, email, display_name, password_hash FROM users WHERE username = %s',
                (username,)
            )
            user = cur.fetchone()

            if not user or not check_password_hash(user['password_hash'], password):
                record_login_attempt(client_ip)
                return jsonify({'error': 'Invalid username or password'}), 401

            cur.execute(
                'UPDATE users SET last_login = %s WHERE user_id = %s',
                (datetime.now(), user['user_id'])
            )

            session.permanent = True
            session['user_id']      = user['user_id']
            session['username']     = user['username']
            session['display_name'] = user['display_name'] or ''

            cur.execute(
                'SELECT favourite_teams, favourite_players, favourite_leagues '
                'FROM user_favourites WHERE user_id = %s',
                (user['user_id'],)
            )
            fav_row = cur.fetchone()
            first_time_user = (
                not fav_row
                or not (fav_row.get('favourite_teams') or [])
                and not (fav_row.get('favourite_players') or [])
                and not (fav_row.get('favourite_leagues') or [])
            )

            return jsonify({
                'message':        'Login successful',
                'user_id':        user['user_id'],
                'username':       user['username'],
                'email':          user['email'] or '',
                'display_name':   user['display_name'] or '',
                'first_time_user': first_time_user,
            }), 200

    except RuntimeError:
        return jsonify({'error': 'Database unavailable'}), 503
    except Exception:
        logger.exception("Login error")
        return jsonify({'error': 'Login failed'}), 500


@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Logged out successfully'}), 200


@auth_bp.route('/session', methods=['GET'])
def check_session():
    """Check whether the current cookie session is valid and return user data."""
    if 'user_id' not in session:
        return jsonify({'authenticated': False}), 401   # 401 so apiFetch throws

    email = ''
    try:
        with DBContext(dict_cursor=True) as (_, cur):
            cur.execute('SELECT email FROM users WHERE user_id = %s', (session['user_id'],))
            row = cur.fetchone()
            email = row['email'] if row else ''
    except Exception:
        logger.exception("check_session DB error")

    return jsonify({
        'authenticated': True,
        'user_id':       session['user_id'],
        'username':      session['username'],
        'display_name':  session.get('display_name', ''),
        'email':         email,
    }), 200


@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    data  = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip()
    if not email:
        return jsonify({'error': 'Email is required'}), 400
    try:
        with DBContext() as (_, cur):
            cur.execute('SELECT user_id FROM users WHERE email = %s', (email,))
            logger.info(f"Password reset requested for: {email}")
            return jsonify({'message': f'If an account exists with {email}, a reset link has been sent'}), 200
    except Exception:
        return jsonify({'error': 'Could not process request'}), 500


@auth_bp.route('/forgot-password-settings', methods=['POST'])
def forgot_password_settings():
    return forgot_password()
