"""Deeper tests for authentication routes.

These tests intentionally focus on route behaviour rather than real database
integration. The database layer is replaced with a documented fake context
manager so we can verify:
- validation
- duplicate checks
- seeded companion rows
- session creation
- first-time-user logic
- password-reset endpoint behaviour
"""
#bloom 

from werkzeug.security import generate_password_hash

import routes.authentication_routes as authentication_routes
from tests.helpers import build_dbcontext_patch


def test_register_creates_user_and_seeds_companion_rows(client, monkeypatch):
    """A successful registration should:
    - reject neither username nor email duplicates,
    - create the user,
    - seed default favourites and notification rows,
    - return the created user id.
    """

    db_patch = build_dbcontext_patch(
        fetchone_results=[
            None,   # username duplicate check -> no existing user
            None,   # email duplicate check -> no existing user
            (7,),   # INSERT ... RETURNING user_id
        ]
    )
    monkeypatch.setattr(authentication_routes, "DBContext", db_patch.factory)

    response = client.post(
        "/api/register",
        json={
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "password123",
        },
    )

    payload = response.get_json()

    assert response.status_code == 201
    assert payload["message"] == "Registration successful"
    assert payload["user_id"] == 7
    assert db_patch.transaction_state.committed is True

    # We expect four SQL statements in order:
    # 1) username duplicate check
    # 2) email duplicate check
    # 3) insert into users
    # 4) seed favourites row
    # 5) seed notification settings row
    executed_queries = [statement["query"] for statement in db_patch.cursor.executed_statements]
    assert "SELECT user_id FROM users WHERE username = %s" in executed_queries[0]
    assert "SELECT user_id FROM users WHERE email = %s" in executed_queries[1]
    assert "INSERT INTO users (username, email, password_hash, created_at)" in executed_queries[2]
    assert "INSERT INTO user_favourites (user_id) VALUES (%s) ON CONFLICT DO NOTHING" in executed_queries[3]
    assert "INSERT INTO notification_settings (user_id) VALUES (%s) ON CONFLICT DO NOTHING" in executed_queries[4]


def test_register_rejects_duplicate_username(client, monkeypatch):
    """If the username already exists, registration should stop early."""

    db_patch = build_dbcontext_patch(fetchone_results=[(1,)])
    monkeypatch.setattr(authentication_routes, "DBContext", db_patch.factory)

    response = client.post(
        "/api/register",
        json={
            "username": "existinguser",
            "email": "fresh@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 409
    assert response.get_json()["error"] == "Username already taken"
    assert len(db_patch.cursor.executed_statements) == 1


def test_register_rejects_duplicate_email(client, monkeypatch):
    """If the email already exists, the route should return 409."""

    db_patch = build_dbcontext_patch(
        fetchone_results=[
            None,   # username check
            (2,),   # email check finds an existing user
        ]
    )
    monkeypatch.setattr(authentication_routes, "DBContext", db_patch.factory)

    response = client.post(
        "/api/register",
        json={
            "username": "freshuser",
            "email": "existing@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 409
    assert response.get_json()["error"] == "Email already registered"
    assert len(db_patch.cursor.executed_statements) == 2


def test_login_sets_session_and_marks_first_time_user(client, monkeypatch):
    """A valid login should create a session and calculate first-time status.

    The route defines first-time users as users whose favourites row exists but
    all three favourites arrays are still empty.
    """

    password_hash = generate_password_hash("password123")
    db_patch = build_dbcontext_patch(
        fetchone_results=[
            {
                "user_id": 11,
                "username": "tester",
                "email": "tester@example.com",
                "display_name": "Test User",
                "password_hash": password_hash,
            },
            {
                "favourite_teams": [],
                "favourite_players": [],
                "favourite_leagues": [],
            },
        ]
    )
    monkeypatch.setattr(authentication_routes, "DBContext", db_patch.factory)

    response = client.post(
        "/api/login",
        json={
            "username": "tester",
            "password": "password123",
        },
    )

    payload = response.get_json()

    assert response.status_code == 200
    assert payload["message"] == "Login successful"
    assert payload["user_id"] == 11
    assert payload["first_time_user"] is True

    with client.session_transaction() as session_state:
        assert session_state["user_id"] == 11
        assert session_state["username"] == "tester"
        assert session_state["display_name"] == "Test User"


def test_login_marks_returning_user_when_favourites_exist(client, monkeypatch):
    """Once a user has any favourites saved, first_time_user should be false."""

    password_hash = generate_password_hash("password123")
    db_patch = build_dbcontext_patch(
        fetchone_results=[
            {
                "user_id": 12,
                "username": "returninguser",
                "email": "returning@example.com",
                "display_name": "",
                "password_hash": password_hash,
            },
            {
                "favourite_teams": [42],
                "favourite_players": [],
                "favourite_leagues": [],
            },
        ]
    )
    monkeypatch.setattr(authentication_routes, "DBContext", db_patch.factory)

    response = client.post(
        "/api/login",
        json={
            "username": "returninguser",
            "password": "password123",
        },
    )

    assert response.status_code == 200
    assert response.get_json()["first_time_user"] is False


def test_login_rejects_invalid_password(client, monkeypatch):
    """The route should reject a valid username with the wrong password."""

    db_patch = build_dbcontext_patch(
        fetchone_results=[
            {
                "user_id": 3,
                "username": "tester",
                "email": "tester@example.com",
                "display_name": "",
                "password_hash": generate_password_hash("correct-password"),
            }
        ]
    )
    monkeypatch.setattr(authentication_routes, "DBContext", db_patch.factory)

    response = client.post(
        "/api/login",
        json={
            "username": "tester",
            "password": "wrong-password",
        },
    )

    assert response.status_code == 401
    assert response.get_json()["error"] == "Invalid username or password"


def test_session_endpoint_returns_email_for_logged_in_user(authenticated_client, monkeypatch):
    """The session route should enrich the session payload with database email."""

    db_patch = build_dbcontext_patch(fetchone_results=[{"email": "tester@example.com"}])
    monkeypatch.setattr(authentication_routes, "DBContext", db_patch.factory)

    response = authenticated_client.get("/api/session")

    assert response.status_code == 200
    assert response.get_json()["authenticated"] is True
    assert response.get_json()["email"] == "tester@example.com"


def test_forgot_password_returns_success_message_without_revealing_account_state(client, monkeypatch):
    """The password-reset route should always return a neutral success message.

    This avoids exposing whether an email address is registered, which is a
    small but useful security measure.
    """

    db_patch = build_dbcontext_patch(fetchone_results=[None])
    monkeypatch.setattr(authentication_routes, "DBContext", db_patch.factory)

    response = client.post("/api/forgot-password", json={"email": "nobody@example.com"})

    assert response.status_code == 200
    assert "If an account exists with nobody@example.com" in response.get_json()["message"]


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

def test_logout_clears_session(authenticated_client):
    with authenticated_client.session_transaction() as sess:
        assert "user_id" in sess

    response = authenticated_client.post("/api/logout")

    assert response.status_code == 200
    assert response.get_json()["message"] == "Logged out successfully"

    with authenticated_client.session_transaction() as sess:
        assert "user_id" not in sess


# ---------------------------------------------------------------------------
# Login rate limiting
# ---------------------------------------------------------------------------

def test_login_blocks_after_five_failed_attempts(client):
    """The sixth login attempt from the same IP must be rejected with 429.

    We seed the attempt counter directly rather than making five mocked DB
    round-trips — the unit under test is the rate-limit gate, not the DB layer.
    """

    for _ in range(5):
        authentication_routes.record_login_attempt("127.0.0.1")

    response = client.post(
        "/api/login",
        json={"username": "tester", "password": "password123"},
    )

    assert response.status_code == 429
    assert response.get_json()["error"] == "Too many login attempts. Try again later."


# ---------------------------------------------------------------------------
# Database unavailable paths
# ---------------------------------------------------------------------------

class _FailingDBContext:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        raise RuntimeError("Database unavailable")

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


def test_register_returns_503_when_database_unavailable(client, monkeypatch):
    monkeypatch.setattr(authentication_routes, "DBContext", _FailingDBContext)

    response = client.post(
        "/api/register",
        json={"username": "newuser", "email": "new@example.com", "password": "password123"},
    )

    assert response.status_code == 503
    assert response.get_json()["error"] == "Database unavailable"


def test_login_returns_503_when_database_unavailable(client, monkeypatch):
    monkeypatch.setattr(authentication_routes, "DBContext", _FailingDBContext)

    response = client.post(
        "/api/login",
        json={"username": "tester", "password": "password123"},
    )

    assert response.status_code == 503
    assert response.get_json()["error"] == "Database unavailable"
