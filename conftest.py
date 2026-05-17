"""Shared pytest fixtures for the PrimeScore test suite.

These fixtures are intentionally lightweight so the starter suite can run without needing the full application stack to be online.

Key design choices:
- The Flask app is created once per test through the real application factory.
- Tests use Flask's built-in test client instead of a live server.
- Environment variables are given safe defaults so imports do not fail.
- Auth rate-limit state is reset between tests so cases stay independent.
"""

import os
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[0]
PRIMESCORE_ROOT = PROJECT_ROOT / "primescore"

if str(PRIMESCORE_ROOT) not in sys.path:
    sys.path.insert(0, str(PRIMESCORE_ROOT))

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("FOOTBALL_API_KEY", "test-api-key")

from app import create_app
from routes import authentication_routes
from routes import favourites_routes
from routes import lookup_routes
from routes import statistics_routes
from services import football_api_client


@pytest.fixture()
def app():
    """Create a Flask app configured for testing."""

    flask_app = create_app()
    flask_app.config.update(TESTING=True)
    return flask_app


@pytest.fixture()
def client(app):
    """Return an unauthenticated Flask test client."""

    return app.test_client()


@pytest.fixture()
def authenticated_client(client):
    """Return a test client that already contains a logged-in session."""

    with client.session_transaction() as session_state:
        session_state["user_id"] = 1
        session_state["username"] = "tester"
        session_state["display_name"] = "Test User"
    return client


@pytest.fixture(autouse=True)
def clear_login_attempts():
    """Reset in-memory login rate-limit data before and after every test.

    The authentication module stores failed login timestamps in a module-level
    dictionary. If we do not clear that state, one test can accidentally affect
    another test by making later requests appear rate-limited.
    """

    authentication_routes.login_attempts.clear()
    yield
    authentication_routes.login_attempts.clear()


@pytest.fixture(autouse=True)
def reset_api_client_state():
    """Keep API client cache/backoff state isolated between tests."""

    football_api_client.reset_api_client_state()
    yield
    football_api_client.reset_api_client_state()


@pytest.fixture(autouse=True)
def reset_route_caches():
    """Keep route-level caches isolated between tests."""

    favourites_routes.reset_home_screen_cache()
    lookup_routes.reset_lookup_caches()
    statistics_routes.reset_statistics_route_caches()
    yield
    favourites_routes.reset_home_screen_cache()
    lookup_routes.reset_lookup_caches()
    statistics_routes.reset_statistics_route_caches()
