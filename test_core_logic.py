from routes.authentication_routes import _validate_registration
import services.football_api_client as football_api_client
from services.football_api_client import call_football_api, compute_team_stats, format_standings


def test_validate_registration_rejects_invalid_values():
    assert _validate_registration("", "user@example.com", "password123") == "Username, email and password are required"
    assert _validate_registration("ab", "user@example.com", "password123") == "Username must be at least 3 characters"
    assert _validate_registration("validuser", "invalid-email", "password123") == "Please enter a valid email address"
    assert _validate_registration("validuser", "user@example.com", "short") == "Password must be at least 8 characters"


def test_format_standings_maps_api_payload():
    payload = {
        "response": [
            {
                "league": {
                    "name": "Premier League",
                    "season": 2024,
                    "standings": [
                        [
                            {
                                "rank": 1,
                                "team": {"name": "Liverpool", "logo": "crest.png"},
                                "all": {
                                    "played": 38,
                                    "win": 25,
                                    "draw": 9,
                                    "lose": 4,
                                    "goals": {"for": 86, "against": 41},
                                },
                                "goalsDiff": 45,
                                "points": 84,
                            }
                        ]
                    ],
                }
            }
        ]
    }

    formatted = format_standings(payload)

    assert formatted["competition"] == "Premier League"
    assert formatted["season"] == "2024"
    assert formatted["standings"][0]["team"] == "Liverpool"
    assert formatted["standings"][0]["points"] == 84


def test_format_standings_returns_safe_defaults_when_response_is_missing():
    formatted = format_standings({"response": []})

    assert formatted == {
        "competition": "Unknown",
        "season": "",
        "standings": [],
    }


def test_compute_team_stats_ignores_unfinished_matches():
    payload = {
        "response": [
            {
                "fixture": {"status": {"short": "FT"}},
                "teams": {"home": {"id": 40}, "away": {"id": 41}},
                "goals": {"home": 2, "away": 0},
            },
            {
                "fixture": {"status": {"short": "FT"}},
                "teams": {"home": {"id": 42}, "away": {"id": 40}},
                "goals": {"home": 1, "away": 1},
            },
            {
                "fixture": {"status": {"short": "NS"}},
                "teams": {"home": {"id": 40}, "away": {"id": 43}},
                "goals": {"home": None, "away": None},
            },
        ]
    }

    stats = compute_team_stats(40, {"name": "Liverpool", "logo": "crest.png"}, payload)

    assert stats["team_name"] == "Liverpool"
    assert stats["matches_played"] == 2
    assert stats["wins"] == 1
    assert stats["draws"] == 1
    assert stats["losses"] == 0
    assert stats["goals_scored"] == 3
    assert stats["goals_conceded"] == 1
    assert stats["clean_sheets"] == 1


def test_compute_team_stats_uses_only_the_ten_most_recent_finished_matches():
    response_items = []
    for day_index in range(1, 13):
        response_items.append(
            {
                "fixture": {
                    "status": {"short": "FT"},
                    "date": f"2026-04-{day_index:02d}T19:00:00+00:00",
                },
                "teams": {"home": {"id": 40}, "away": {"id": 41}},
                "goals": {"home": day_index, "away": 0},
            }
        )

    stats = compute_team_stats(
        40,
        {"name": "Liverpool", "logo": "crest.png"},
        {"response": response_items},
    )

    assert stats["matches_played"] == 10
    assert stats["wins"] == 10
    assert stats["goals_scored"] == sum(range(3, 13))
    assert stats["clean_sheets"] == 10


def test_clean_params_removes_empty_values():
    cleaned = football_api_client._clean_params(
        {
            "league": 39,
            "season": None,
            "search": "",
            "players": [],
            "live": "all",
        }
    )

    assert cleaned == {
        "league": 39,
        "live": "all",
    }


def test_season_retry_params_descend_through_supported_years():
    retry_params = football_api_client._season_retry_params(
        {"league": 39, "season": 2026},
        {"plan": "Free plans do not have access to this season, try from 2022 to 2024."},
    )

    assert retry_params == [
        {"league": 39, "season": 2024},
        {"league": 39, "season": 2023},
        {"league": 39, "season": 2022},
    ]


def test_call_football_api_reuses_cached_response(monkeypatch):
    request_count = {"value": 0}

    class FakeResponse:
        status_code = 200
        headers = {}

        @staticmethod
        def json():
            return {"response": [{"league": {"name": "Premier League"}}]}

    def fake_get(*args, **kwargs):
        request_count["value"] += 1
        return FakeResponse()

    monkeypatch.setattr(football_api_client.requests, "get", fake_get)

    first_response = call_football_api("standings", {"league": 39, "season": 2025})
    second_response = call_football_api("standings", {"season": 2025, "league": 39})

    assert first_response == second_response
    assert request_count["value"] == 1


def test_call_football_api_caches_fallback_response_under_original_request(monkeypatch):
    request_count = {"value": 0}

    class FakeResponse:
        headers = {}

        def __init__(self, payload):
            self.status_code = 200
            self._payload = payload

        def json(self):
            return self._payload

    responses = iter(
        [
            FakeResponse({"errors": {"plan": "Free plans do not have access to this season, try from 2022 to 2024."}}),
            FakeResponse({"errors": [], "response": [{"league": {"season": 2024, "name": "Premier League"}}]}),
        ]
    )

    def fake_get(*args, **kwargs):
        request_count["value"] += 1
        return next(responses)

    monkeypatch.setattr(football_api_client.requests, "get", fake_get)

    first_response = call_football_api("standings", {"league": 39, "season": 2025})
    second_response = call_football_api("standings", {"league": 39, "season": 2025})

    assert first_response == second_response
    assert first_response["response"][0]["league"]["season"] == 2024
    assert request_count["value"] == 2


def test_call_football_api_backs_off_after_rate_limit(monkeypatch):
    request_count = {"value": 0}

    class FakeResponse:
        status_code = 429
        headers = {}

        @staticmethod
        def json():
            return {}

    def fake_get(*args, **kwargs):
        request_count["value"] += 1
        return FakeResponse()

    monkeypatch.setattr(football_api_client.requests, "get", fake_get)

    first_response = call_football_api("fixtures", {"live": "all"})
    second_response = call_football_api("fixtures", {"live": "all"})

    assert first_response["_error"] == "rate_limit"
    assert second_response["_error"] == "rate_limit"
    assert request_count["value"] == 1


def test_call_football_api_treats_embedded_rate_limit_errors_as_backoff(monkeypatch):
    request_count = {"value": 0}

    class FakeResponse:
        status_code = 200
        headers = {}

        @staticmethod
        def json():
            return {"errors": {"rateLimit": "Too many requests"}}

    def fake_get(*args, **kwargs):
        request_count["value"] += 1
        return FakeResponse()

    monkeypatch.setattr(football_api_client.requests, "get", fake_get)

    response = call_football_api("fixtures", {"league": 39, "season": 2025, "status": "NS"})

    assert response["_error"] == "rate_limit"
    assert response["status_code"] == 429
    assert request_count["value"] == 1


def test_call_football_api_retries_with_supported_season_after_plan_error(monkeypatch):
    requested_params = []

    class FakeResponse:
        headers = {}

        def __init__(self, payload):
            self.status_code = 200
            self._payload = payload

        def json(self):
            return self._payload

    responses = iter(
        [
            FakeResponse({"errors": {"plan": "Free plans do not have access to this season, try from 2022 to 2024."}}),
            FakeResponse({"errors": [], "response": [{"league": {"season": 2024, "name": "Premier League"}}]}),
        ]
    )

    def fake_get(*args, **kwargs):
        requested_params.append(dict(kwargs.get("params") or {}))
        return next(responses)

    monkeypatch.setattr(football_api_client.requests, "get", fake_get)

    response = call_football_api("standings", {"league": 39, "season": 2025})

    assert response["response"][0]["league"]["season"] == 2024
    assert requested_params == [
        {"league": 39, "season": 2025},
        {"league": 39, "season": 2024},
    ]
