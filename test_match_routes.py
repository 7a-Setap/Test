import routes.match_routes as match_routes
from routes.match_routes import _format_match_event


def test_fixtures_route_requires_login(client):
    response = client.get("/api/fixtures?league_id=PL")

    assert response.status_code == 401
    assert response.get_json()["error"] == "Not authenticated"


def test_results_route_requires_login(client):
    response = client.get("/api/results?league_id=PL")

    assert response.status_code == 401
    assert response.get_json()["error"] == "Not authenticated"


def test_live_matches_route_maps_scores_and_minutes(authenticated_client, monkeypatch):
    def fake_call(endpoint, params=None):
        assert endpoint == "fixtures"
        assert params == {"live": "all"}
        return {
            "response": [
                {
                    "fixture": {
                        "id": 1,
                        "date": "2026-04-29T19:00:00+00:00",
                        "status": {"long": "First Half", "elapsed": 34},
                    },
                    "teams": {
                        "home": {"id": 42, "name": "Arsenal"},
                        "away": {"id": 49, "name": "Chelsea"},
                    },
                    "league": {"name": "Premier League"},
                    "goals": {"home": 2, "away": 1},
                }
            ]
        }

    monkeypatch.setattr(match_routes, "call_football_api", fake_call)

    response = authenticated_client.get("/api/matches/live")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["matches"] == [
        {
            "match_id": 1,
            "home_team": "Arsenal",
            "home_team_id": 42,
            "away_team": "Chelsea",
            "away_team_id": 49,
            "competition": "Premier League",
            "date": "2026-04-29T19:00:00+00:00",
            "match_date": "2026-04-29T19:00:00+00:00",
            "status": "First Half",
            "home_score": 2,
            "away_score": 1,
            "minute": 34,
        }
    ]


def test_fixtures_route_always_uses_date_window(authenticated_client, monkeypatch):
    recorded_calls = []

    def fake_call(endpoint, params=None):
        recorded_calls.append((endpoint, params))
        return {
            "response": [
                {
                    "fixture": {"id": 1, "date": "2026-05-01T19:00:00+00:00", "status": {"long": "Not Started"}},
                    "teams": {"home": {"name": "Arsenal"}, "away": {"name": "Chelsea"}},
                    "league": {"name": "Premier League"},
                    "goals": {"home": None, "away": None},
                }
            ]
        }

    monkeypatch.setattr(match_routes, "call_football_api", fake_call)

    response = authenticated_client.get("/api/fixtures?league_id=PL")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["fixtures"][0]["home_team"] == "Arsenal"
    assert recorded_calls == [
        (
            "fixtures",
            {
                "date": match_routes._date_offset_string(1),
            },
        )
    ]

def test_results_route_uses_league_and_season_filter(authenticated_client, monkeypatch):
    recorded_calls = []

    def fake_call(endpoint, params=None):
        recorded_calls.append((endpoint, params))
        return {
            "response": [
                {
                    "fixture": {"id": 2, "date": "2026-04-20T19:00:00+00:00", "status": {"long": "Match Finished"}},
                    "teams": {"home": {"name": "Liverpool"}, "away": {"name": "Everton"}},
                    "league": {"name": "Premier League"},
                    "goals": {"home": 2, "away": 1},
                }
            ]
        }

    monkeypatch.setattr(match_routes, "call_football_api", fake_call)

    response = authenticated_client.get("/api/results?league_id=PL")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["results"][0]["home_score"] == 2
    assert recorded_calls == [
        (
            "fixtures",
            {
                "league": 39,
                "season": match_routes.CURRENT_SEASON,
                "status": "FT-AET-PEN",
            },
        )
    ]

def test_fixtures_route_ignores_team_id_param(authenticated_client, monkeypatch):
    recorded_calls = []

    def fake_call(endpoint, params=None):
        recorded_calls.append((endpoint, params))
        return {
            "response": [
                {
                    "fixture": {"id": 3, "date": "2026-05-03T19:00:00+00:00", "status": {"long": "Not Started"}},
                    "teams": {"home": {"name": "Liverpool"}, "away": {"name": "Spurs"}},
                    "league": {"name": "Premier League"},
                    "goals": {"home": None, "away": None},
                }
            ]
        }

    monkeypatch.setattr(match_routes, "call_football_api", fake_call)

    response = authenticated_client.get("/api/fixtures?team_id=40")

    assert response.status_code == 200
    assert recorded_calls == [
        (
            "fixtures",
            {
                "date": match_routes._date_offset_string(1),
            },
        )
    ]

def test_results_route_supports_team_filter_and_descending_order(authenticated_client, monkeypatch):
    def fake_call(endpoint, params=None):
        assert endpoint == "fixtures"
        assert params == {
            "team": "40",
            "season": match_routes.CURRENT_SEASON,
            "status": "FT-AET-PEN",
        }
        return {
            "response": [
                {
                    "fixture": {"id": 4, "date": "2026-04-15T19:00:00+00:00", "status": {"long": "Match Finished"}},
                    "teams": {"home": {"name": "Liverpool"}, "away": {"name": "Villa"}},
                    "league": {"name": "Premier League"},
                    "goals": {"home": 1, "away": 0},
                },
                {
                    "fixture": {"id": 5, "date": "2026-04-22T19:00:00+00:00", "status": {"long": "Match Finished"}},
                    "teams": {"home": {"name": "Arsenal"}, "away": {"name": "Liverpool"}},
                    "league": {"name": "Premier League"},
                    "goals": {"home": 0, "away": 2},
                },
            ]
        }

    monkeypatch.setattr(match_routes, "call_football_api", fake_call)

    response = authenticated_client.get("/api/results?team_id=40")
    payload = response.get_json()

    assert response.status_code == 200
    assert [result["match_id"] for result in payload["results"]] == [5, 4]


# ---------------------------------------------------------------------------
# Lineups endpoint
# ---------------------------------------------------------------------------

def test_lineups_requires_login(client):
    response = client.get("/api/matches/1/lineups")

    assert response.status_code == 401
    assert response.get_json()["error"] == "Not authenticated"


def test_lineups_returns_null_when_not_yet_published(authenticated_client, monkeypatch):
    """Pre-kickoff fixtures return an empty response list from the API.
    The route must return null for both sides rather than crashing."""

    monkeypatch.setattr(match_routes, "call_football_api", lambda *a, **kw: {"response": []})

    response = authenticated_client.get("/api/matches/1/lineups")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload == {"match_id": 1, "home": None, "away": None}


def test_lineups_returns_429_when_rate_limited(authenticated_client, monkeypatch):
    monkeypatch.setattr(
        match_routes, "call_football_api",
        lambda *a, **kw: {"_error": "rate_limit", "status_code": 429},
    )

    response = authenticated_client.get("/api/matches/1/lineups")

    assert response.status_code == 429


def test_lineups_maps_formation_coach_and_players(authenticated_client, monkeypatch):
    def fake_call(endpoint, params=None):
        assert endpoint == "fixture_lineups"
        assert params == {"fixture": 1}
        return {
            "response": [
                {
                    "team": {"id": 42, "name": "Arsenal", "logo": "arsenal.png"},
                    "coach": {"name": "Mikel Arteta"},
                    "formation": "4-3-3",
                    "startXI": [
                        {"player": {"id": 100, "name": "Raya", "number": 22, "pos": "G", "grid": "1:1"}},
                        {"player": {"id": 101, "name": "Saka", "number": 7, "pos": "F", "grid": "4:3"}},
                    ],
                    "substitutes": [
                        {"player": {"id": 200, "name": "Tierney", "number": 3, "pos": "D", "grid": None}},
                    ],
                },
                {
                    "team": {"id": 49, "name": "Chelsea", "logo": "chelsea.png"},
                    "coach": {"name": "Enzo Maresca"},
                    "formation": "4-2-3-1",
                    "startXI": [
                        {"player": {"id": 300, "name": "Sanchez", "number": 1, "pos": "G", "grid": "1:1"}},
                    ],
                    "substitutes": [],
                },
            ]
        }

    monkeypatch.setattr(match_routes, "call_football_api", fake_call)

    response = authenticated_client.get("/api/matches/1/lineups")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["match_id"] == 1

    home = payload["home"]
    assert home["team_name"] == "Arsenal"
    assert home["team_id"] == 42
    assert home["formation"] == "4-3-3"
    assert home["coach"] == "Mikel Arteta"
    assert len(home["start_xi"]) == 2
    assert home["start_xi"][0] == {"id": 100, "name": "Raya", "number": 22, "position": "G", "grid": "1:1"}
    assert home["substitutes"][0]["name"] == "Tierney"

    away = payload["away"]
    assert away["team_name"] == "Chelsea"
    assert away["formation"] == "4-2-3-1"
    assert away["substitutes"] == []


# ---------------------------------------------------------------------------
# H2H endpoint
# ---------------------------------------------------------------------------

def test_h2h_requires_login(client):
    response = client.get("/api/matches/1/h2h?home_id=42&away_id=49")

    assert response.status_code == 401
    assert response.get_json()["error"] == "Not authenticated"


def test_h2h_rejects_missing_team_ids(authenticated_client):
    response = authenticated_client.get("/api/matches/1/h2h")

    assert response.status_code == 400
    assert "home_id" in response.get_json()["error"]


def test_h2h_rejects_identical_team_ids(authenticated_client):
    response = authenticated_client.get("/api/matches/1/h2h?home_id=42&away_id=42")

    assert response.status_code == 400
    assert response.get_json()["error"] == "home_id and away_id must differ"


def test_h2h_returns_429_when_api_is_rate_limited(authenticated_client, monkeypatch):
    monkeypatch.setattr(match_routes, "call_football_api", lambda *a, **kw: {"_error": "rate_limit", "status_code": 429})

    response = authenticated_client.get("/api/matches/1/h2h?home_id=42&away_id=49")

    assert response.status_code == 429


def test_h2h_attributes_wins_to_current_fixture_perspective(authenticated_client, monkeypatch):
    """Win attribution must follow the current fixture's home_id/away_id, not the
    historical match's home/away side. Here team 42 was the *away* team in the
    historical match but is the *home* perspective in the current fixture, so a
    historical away win must be counted as a home_wins for this H2H summary."""

    def fake_call(endpoint, params=None):
        return {
            "response": [
                {
                    "fixture": {
                        "id": 99,
                        "date": "2025-01-10T15:00:00+00:00",
                        "status": {"long": "Match Finished", "short": "FT", "elapsed": 90},
                    },
                    "teams": {
                        # In the historical match, team 49 was home and team 42 was away.
                        "home": {"id": 49, "name": "Chelsea"},
                        "away": {"id": 42, "name": "Arsenal"},
                    },
                    "league": {"id": 39, "name": "Premier League"},
                    "goals": {"home": 1, "away": 3},  # team 42 (away) won
                    "score": {},
                }
            ]
        }

    monkeypatch.setattr(match_routes, "call_football_api", fake_call)

    # Current fixture has team 42 as home perspective and team 49 as away.
    response = authenticated_client.get("/api/matches/1/h2h?home_id=42&away_id=49")
    payload = response.get_json()

    assert response.status_code == 200
    # Team 42 won the historical match (as away side) → must count as a home_win
    # in the current-fixture perspective where 42 is "home".
    assert payload["summary"]["home_wins"] == 1
    assert payload["summary"]["away_wins"] == 0
    assert payload["summary"]["draws"] == 0


# ---------------------------------------------------------------------------
# Events endpoint
# ---------------------------------------------------------------------------

def test_match_events_requires_login(client):
    response = client.get("/api/matches/1/events")

    assert response.status_code == 401


def test_match_events_returns_empty_list_when_api_has_no_events(authenticated_client, monkeypatch):
    monkeypatch.setattr(match_routes, "call_football_api", lambda *a, **kw: {"response": []})

    response = authenticated_client.get("/api/matches/1/events")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload == {"match_id": 1, "events": []}


def test_match_events_returns_429_when_api_is_rate_limited(authenticated_client, monkeypatch):
    monkeypatch.setattr(match_routes, "call_football_api", lambda *a, **kw: {"_error": "rate_limit", "status_code": 429})

    response = authenticated_client.get("/api/matches/1/events")

    assert response.status_code == 429


# ---------------------------------------------------------------------------
# _format_match_event subtype classification
# ---------------------------------------------------------------------------

def test_format_match_event_classifies_goal_subtypes():
    assert _format_match_event({"type": "Goal", "detail": "Normal Goal", "time": {}, "team": {}, "player": {}, "assist": {}})["subtype"] == "goal"
    assert _format_match_event({"type": "Goal", "detail": "Own Goal", "time": {}, "team": {}, "player": {}, "assist": {}})["subtype"] == "own_goal"
    assert _format_match_event({"type": "Goal", "detail": "Penalty", "time": {}, "team": {}, "player": {}, "assist": {}})["subtype"] == "penalty_goal"


def test_format_match_event_classifies_card_subtypes():
    assert _format_match_event({"type": "Card", "detail": "Yellow Card", "time": {}, "team": {}, "player": {}, "assist": {}})["subtype"] == "yellow_card"
    assert _format_match_event({"type": "Card", "detail": "Red Card", "time": {}, "team": {}, "player": {}, "assist": {}})["subtype"] == "red_card"


def test_format_match_event_handles_missing_assist_gracefully():
    event = _format_match_event({"type": "Goal", "detail": "Normal Goal", "time": {"elapsed": 55}, "team": {"name": "Arsenal"}, "player": {"name": "Saka"}, "assist": None})

    assert event["assist"] is None
    assert event["player"] == "Saka"

