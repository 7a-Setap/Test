"""Tests for profile and notification routes.

These tests are useful coursework because they cover two common forms
of stateful user behaviour:
- editing account data
- saving preference data
"""

from werkzeug.security import generate_password_hash

import routes.notification_routes as notification_routes
import routes.profile_routes as profile_routes
from tests.helpers import build_dbcontext_patch


def test_get_profile_returns_current_user_details(authenticated_client, monkeypatch):
    """Profile GET should return the stored user-facing account fields."""

    db_patch = build_dbcontext_patch(
        fetchone_results=[
            {
                "username": "tester",
                "email": "tester@example.com",
                "display_name": "Test User",
                "bio": "Enjoys football analytics.",
            }
        ]
    )
    monkeypatch.setattr(profile_routes, "DBContext", db_patch.factory)

    response = authenticated_client.get("/api/profile")

    assert response.status_code == 200
    assert response.get_json() == {
        "username": "tester",
        "email": "tester@example.com",
        "display_name": "Test User",
        "bio": "Enjoys football analytics.",
    }


def test_get_profile_returns_404_when_user_row_is_missing(authenticated_client, monkeypatch):
    db_patch = build_dbcontext_patch(fetchone_results=[None])
    monkeypatch.setattr(profile_routes, "DBContext", db_patch.factory)

    response = authenticated_client.get("/api/profile")

    assert response.status_code == 404
    assert response.get_json()["error"] == "User not found"


def test_get_profile_returns_503_when_database_is_unavailable(authenticated_client, monkeypatch):
    class FailingDBContext:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            raise RuntimeError("Database unavailable")

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

    monkeypatch.setattr(profile_routes, "DBContext", FailingDBContext)

    response = authenticated_client.get("/api/profile")

    assert response.status_code == 503
    assert response.get_json()["error"] == "Database unavailable"


def test_update_profile_persists_changes_and_updates_session(authenticated_client, monkeypatch):
    """A valid profile update should:
    - pass uniqueness checks,
    - update the users table,
    - update the session values used by the UI.
    """

    db_patch = build_dbcontext_patch(
        fetchone_results=[
            None,  # no username conflict
            None,  # no email conflict
        ]
    )
    monkeypatch.setattr(profile_routes, "DBContext", db_patch.factory)

    response = authenticated_client.post(
        "/api/profile",
        json={
            "username": "newtester",
            "email": "newtester@example.com",
            "display_name": "New Test User",
            "bio": "Updated bio",
        },
    )

    payload = response.get_json()

    assert response.status_code == 200
    assert payload["message"] == "Profile updated successfully"
    assert payload["username"] == "newtester"
    assert payload["email"] == "newtester@example.com"
    assert db_patch.transaction_state.committed is True

    with authenticated_client.session_transaction() as session_state:
        assert session_state["username"] == "newtester"
        assert session_state["display_name"] == "New Test User"


def test_update_profile_rejects_duplicate_email(authenticated_client, monkeypatch):
    db_patch = build_dbcontext_patch(
        fetchone_results=[
            None,
            {"user_id": 88},
        ]
    )
    monkeypatch.setattr(profile_routes, "DBContext", db_patch.factory)

    response = authenticated_client.post(
        "/api/profile",
        json={
            "username": "freshname",
            "email": "taken@example.com",
            "display_name": "Name",
            "bio": "",
        },
    )

    assert response.status_code == 409
    assert response.get_json()["error"] == "Email already registered"


def test_update_profile_rejects_duplicate_username(authenticated_client, monkeypatch):
    """The route should stop on username conflict before attempting the update."""

    db_patch = build_dbcontext_patch(fetchone_results=[{"user_id": 99}])
    monkeypatch.setattr(profile_routes, "DBContext", db_patch.factory)

    response = authenticated_client.post(
        "/api/profile",
        json={
            "username": "takenname",
            "email": "fresh@example.com",
            "display_name": "Name",
            "bio": "",
        },
    )

    assert response.status_code == 409
    assert response.get_json()["error"] == "Username already taken"


def test_update_profile_rejects_values_that_are_too_long(authenticated_client):
    response = authenticated_client.post(
        "/api/profile",
        json={
            "username": "x" * 51,
            "email": "tester@example.com",
            "display_name": "Name",
            "bio": "",
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Username must be 50 characters or fewer"

    response = authenticated_client.post(
        "/api/profile",
        json={
            "username": "testername",
            "email": "tester@example.com",
            "display_name": "x" * 101,
            "bio": "",
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Display name must be 100 characters or fewer"

    response = authenticated_client.post(
        "/api/profile",
        json={
            "username": "testername",
            "email": "tester@example.com",
            "display_name": "Name",
            "bio": "x" * 501,
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Bio must be 500 characters or fewer"


def test_change_password_updates_hash_when_current_password_matches(authenticated_client, monkeypatch):
    """Password change should verify the current password before writing a new hash."""

    db_patch = build_dbcontext_patch(
        fetchone_results=[
            {"password_hash": generate_password_hash("old-password")}
        ]
    )
    monkeypatch.setattr(profile_routes, "DBContext", db_patch.factory)

    response = authenticated_client.post(
        "/api/change-password",
        json={
            "current_password": "old-password",
            "new_password": "new-password-123",
        },
    )

    assert response.status_code == 200
    assert response.get_json()["message"] == "Password changed successfully"

    # The second SQL statement should be the update that writes the new hash.
    executed_queries = [statement["query"] for statement in db_patch.cursor.executed_statements]
    assert "SELECT password_hash FROM users WHERE user_id = %s" in executed_queries[0]
    assert "UPDATE users SET password_hash = %s WHERE user_id = %s" in executed_queries[1]


def test_change_password_requires_both_current_and_new_password(authenticated_client):
    response = authenticated_client.post(
        "/api/change-password",
        json={
            "current_password": "",
            "new_password": "",
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Current and new password are required"


def test_change_password_rejects_short_new_password(authenticated_client):
    response = authenticated_client.post(
        "/api/change-password",
        json={
            "current_password": "old-password",
            "new_password": "short",
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "New password must be at least 8 characters"


def test_change_password_rejects_wrong_current_password(authenticated_client, monkeypatch):
    """Wrong current password should block the update entirely."""

    db_patch = build_dbcontext_patch(
        fetchone_results=[
            {"password_hash": generate_password_hash("correct-old-password")}
        ]
    )
    monkeypatch.setattr(profile_routes, "DBContext", db_patch.factory)

    response = authenticated_client.post(
        "/api/change-password",
        json={
            "current_password": "wrong-password",
            "new_password": "new-password-123",
        },
    )

    assert response.status_code == 401
    assert response.get_json()["error"] == "Current password is incorrect"
    assert len(db_patch.cursor.executed_statements) == 1


def test_change_password_returns_404_when_user_row_is_missing(authenticated_client, monkeypatch):
    db_patch = build_dbcontext_patch(fetchone_results=[None])
    monkeypatch.setattr(profile_routes, "DBContext", db_patch.factory)

    response = authenticated_client.post(
        "/api/change-password",
        json={
            "current_password": "old-password",
            "new_password": "new-password-123",
        },
    )

    assert response.status_code == 404
    assert response.get_json()["error"] == "User not found"


def test_get_notification_settings_returns_defaults_when_row_is_missing(authenticated_client, monkeypatch):
    """If the user has no settings row yet, the route should return the hard-coded defaults."""

    db_patch = build_dbcontext_patch(fetchone_results=[None])
    monkeypatch.setattr(notification_routes, "DBContext", db_patch.factory)

    response = authenticated_client.get("/api/notifications/settings")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload == {
        "goals_notifications": False,
        "match_start_notifications": False,
        "match_end_notifications": False,
        "favourite_team_notifications": False,
        "favourite_player_notifications": False,
    }


def test_get_notification_settings_returns_503_when_database_is_unavailable(authenticated_client, monkeypatch):
    class FailingDBContext:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            raise RuntimeError("Database unavailable")

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

    monkeypatch.setattr(notification_routes, "DBContext", FailingDBContext)

    response = authenticated_client.get("/api/notifications/settings")

    assert response.status_code == 503
    assert response.get_json()["error"] == "Database unavailable"


def test_update_notification_settings_persists_boolean_preferences(authenticated_client, monkeypatch):
    """Notification preferences should be inserted or updated as booleans."""

    db_patch = build_dbcontext_patch()
    monkeypatch.setattr(notification_routes, "DBContext", db_patch.factory)

    response = authenticated_client.post(
        "/api/notifications/settings",
        json={
            "goals_notifications": True,
            "match_start_notifications": True,
            "match_end_notifications": False,
            "favourite_team_notifications": True,
            "favourite_player_notifications": False,
        },
    )

    assert response.status_code == 200
    assert response.get_json()["message"] == "Notification settings saved"
    assert db_patch.transaction_state.committed is True

    saved_parameters = db_patch.cursor.executed_statements[0]["params"]
    assert saved_parameters[1:6] == (True, True, False, True, False)


def test_update_notification_settings_returns_503_when_database_is_unavailable(authenticated_client, monkeypatch):
    class FailingDBContext:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            raise RuntimeError("Database unavailable")

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

    monkeypatch.setattr(notification_routes, "DBContext", FailingDBContext)

    response = authenticated_client.post(
        "/api/notifications/settings",
        json={"goals_notifications": True},
    )

    assert response.status_code == 503
    assert response.get_json()["error"] == "Database unavailable"


def test_get_notification_settings_returns_existing_row_values(authenticated_client, monkeypatch):
    """When the user already has a settings row the actual stored values must be returned."""

    db_patch = build_dbcontext_patch(
        fetchone_results=[
            {
                "goals_notifications": True,
                "match_start_notifications": False,
                "match_end_notifications": True,
                "favourite_team_notifications": True,
                "favourite_player_notifications": False,
            }
        ]
    )
    monkeypatch.setattr(notification_routes, "DBContext", db_patch.factory)

    response = authenticated_client.get("/api/notifications/settings")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload == {
        "goals_notifications": True,
        "match_start_notifications": False,
        "match_end_notifications": True,
        "favourite_team_notifications": True,
        "favourite_player_notifications": False,
    }


# ---------------------------------------------------------------------------
# Test notification email  (POST /notifications/test)
# ---------------------------------------------------------------------------

def test_send_test_notification_requires_login(client):
    response = client.post("/api/notifications/test")

    assert response.status_code == 401
    assert response.get_json()["error"] == "Not authenticated"


def test_send_test_notification_returns_503_when_database_unavailable(authenticated_client, monkeypatch):
    class FailingDBContext:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            raise RuntimeError("Database unavailable")

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

    monkeypatch.setattr(notification_routes, "DBContext", FailingDBContext)

    response = authenticated_client.post("/api/notifications/test")

    assert response.status_code == 503
    assert response.get_json()["error"] == "Database unavailable"


def test_send_test_notification_returns_400_when_account_has_no_email(authenticated_client, monkeypatch):
    db_patch = build_dbcontext_patch(fetchone_results=[{"email": None}])
    monkeypatch.setattr(notification_routes, "DBContext", db_patch.factory)

    response = authenticated_client.post("/api/notifications/test")

    assert response.status_code == 400
    assert response.get_json()["error"] == "No email address on your account"


def test_send_test_notification_returns_400_when_user_row_missing(authenticated_client, monkeypatch):
    db_patch = build_dbcontext_patch(fetchone_results=[None])
    monkeypatch.setattr(notification_routes, "DBContext", db_patch.factory)

    response = authenticated_client.post("/api/notifications/test")

    assert response.status_code == 400
    assert response.get_json()["error"] == "No email address on your account"


def test_send_test_notification_skips_email_when_smtp_not_configured(authenticated_client, monkeypatch):
    """When SMTP_HOST / SMTP_USER are blank the route should return 200 without
    attempting any network call."""

    db_patch = build_dbcontext_patch(fetchone_results=[{"email": "tester@example.com"}])
    monkeypatch.setattr(notification_routes, "DBContext", db_patch.factory)
    # Ensure SMTP is explicitly blank regardless of any environment variable.
    monkeypatch.setattr(notification_routes, "SMTP_HOST", "")
    monkeypatch.setattr(notification_routes, "SMTP_USER", "")

    response = authenticated_client.post("/api/notifications/test")
    payload = response.get_json()

    assert response.status_code == 200
    assert "SMTP not configured" in payload["message"]


def test_send_test_notification_uses_smtp_ssl_for_port_465(authenticated_client, monkeypatch):
    """Port 465 must use SMTP_SSL (implicit TLS), not plain SMTP + STARTTLS."""

    db_patch = build_dbcontext_patch(fetchone_results=[{"email": "tester@example.com"}])
    monkeypatch.setattr(notification_routes, "DBContext", db_patch.factory)
    monkeypatch.setattr(notification_routes, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(notification_routes, "SMTP_USER", "user@example.com")
    monkeypatch.setattr(notification_routes, "SMTP_PASSWORD", "password")
    monkeypatch.setattr(notification_routes, "SMTP_PORT", 465)

    ssl_calls = []
    plain_calls = []

    class FakeSMTPSSL:
        def __init__(self, *args, **kwargs):
            ssl_calls.append(args)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def login(self, *args):
            pass

        def sendmail(self, *args):
            pass

    class FakeSMTP:
        def __init__(self, *args, **kwargs):
            plain_calls.append(args)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def ehlo(self):
            pass

        def starttls(self):
            pass

        def login(self, *args):
            pass

        def sendmail(self, *args):
            pass

    monkeypatch.setattr(notification_routes.smtplib, "SMTP_SSL", FakeSMTPSSL)
    monkeypatch.setattr(notification_routes.smtplib, "SMTP", FakeSMTP)

    response = authenticated_client.post("/api/notifications/test")

    assert response.status_code == 200
    assert ssl_calls, "Expected SMTP_SSL to be used for port 465"
    assert not plain_calls, "Plain SMTP must NOT be used for port 465"


def test_send_test_notification_uses_starttls_for_port_587(authenticated_client, monkeypatch):
    """Non-465 ports must use plain SMTP + STARTTLS, not SMTP_SSL."""

    db_patch = build_dbcontext_patch(fetchone_results=[{"email": "tester@example.com"}])
    monkeypatch.setattr(notification_routes, "DBContext", db_patch.factory)
    monkeypatch.setattr(notification_routes, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(notification_routes, "SMTP_USER", "user@example.com")
    monkeypatch.setattr(notification_routes, "SMTP_PASSWORD", "password")
    monkeypatch.setattr(notification_routes, "SMTP_PORT", 587)

    ssl_calls = []
    starttls_called = []

    class FakeSMTPSSL:
        def __init__(self, *args, **kwargs):
            ssl_calls.append(args)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def login(self, *args):
            pass

        def sendmail(self, *args):
            pass

    class FakeSMTP:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def ehlo(self):
            pass

        def starttls(self):
            starttls_called.append(True)

        def login(self, *args):
            pass

        def sendmail(self, *args):
            pass

    monkeypatch.setattr(notification_routes.smtplib, "SMTP_SSL", FakeSMTPSSL)
    monkeypatch.setattr(notification_routes.smtplib, "SMTP", FakeSMTP)

    response = authenticated_client.post("/api/notifications/test")

    assert response.status_code == 200
    assert starttls_called, "Expected STARTTLS to be called for port 587"
    assert not ssl_calls, "SMTP_SSL must NOT be used for port 587"


def test_send_test_notification_returns_500_on_smtp_failure(authenticated_client, monkeypatch):
    """An SMTP exception must be caught and returned as a 500, not an unhandled crash."""

    db_patch = build_dbcontext_patch(fetchone_results=[{"email": "tester@example.com"}])
    monkeypatch.setattr(notification_routes, "DBContext", db_patch.factory)
    monkeypatch.setattr(notification_routes, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(notification_routes, "SMTP_USER", "user@example.com")
    monkeypatch.setattr(notification_routes, "SMTP_PASSWORD", "password")
    monkeypatch.setattr(notification_routes, "SMTP_PORT", 587)

    def broken_smtp(*args, **kwargs):
        raise ConnectionRefusedError("Connection refused")

    monkeypatch.setattr(notification_routes.smtplib, "SMTP", broken_smtp)

    response = authenticated_client.post("/api/notifications/test")

    assert response.status_code == 500
    assert "SMTP" in response.get_json()["error"]


# ---------------------------------------------------------------------------
# Delete account
# ---------------------------------------------------------------------------

def test_delete_account_requires_login(client):
    response = client.post("/api/delete-account", json={"password": "secret123", "confirmation": "DELETE"})

    assert response.status_code == 401
    assert response.get_json()["error"] == "Not authenticated"


def test_delete_account_rejects_non_delete_confirmation(authenticated_client):
    response = authenticated_client.post(
        "/api/delete-account",
        json={"password": "secret123", "confirmation": "delete"},
    )

    assert response.status_code == 400
    assert "DELETE" in response.get_json()["error"]


def test_delete_account_rejects_wrong_password(authenticated_client, monkeypatch):
    hashed = generate_password_hash("correct-password")
    db_patch = build_dbcontext_patch(fetchone_results=[{"password_hash": hashed}])
    monkeypatch.setattr(profile_routes, "DBContext", db_patch.factory)

    response = authenticated_client.post(
        "/api/delete-account",
        json={"password": "wrong-password", "confirmation": "DELETE"},
    )

    assert response.status_code == 401
    assert response.get_json()["error"] == "Password is incorrect"


def test_delete_account_clears_session_and_removes_user_on_success(authenticated_client, monkeypatch):
    hashed = generate_password_hash("correct-password")
    db_patch = build_dbcontext_patch(fetchone_results=[{"password_hash": hashed}])
    monkeypatch.setattr(profile_routes, "DBContext", db_patch.factory)

    response = authenticated_client.post(
        "/api/delete-account",
        json={"password": "correct-password", "confirmation": "DELETE"},
    )

    assert response.status_code == 200
    assert response.get_json()["message"] == "Account deleted successfully"
    assert db_patch.transaction_state.committed is True

    executed = [s["query"] for s in db_patch.cursor.executed_statements]
    assert any("DELETE FROM users" in q for q in executed)

    # Session must be cleared after the DB commit succeeds.
    with authenticated_client.session_transaction() as sess:
        assert "user_id" not in sess
