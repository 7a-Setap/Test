import routes.statistics_routes as statistics_routes


def test_standings_route_formats_the_response(client, monkeypatch):
    def fake_call(endpoint, params=None):
        assert endpoint == "standings"
        assert params["league"] == 39
        return {
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

    monkeypatch.setattr(statistics_routes, "call_football_api", fake_call)

    response = client.get("/api/leagues/PL/standings")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["competition"] == "Premier League"
    assert payload["standings"][0]["team"] == "Liverpool"


def test_standings_lookup_returns_minimal_payload_shape(client, monkeypatch):
    def fake_call(endpoint, params=None):
        assert endpoint == "standings"
        assert params["league"] == 135
        return {
            "response": [
                {
                    "league": {
                        "name": "Serie A",
                        "season": 2024,
                        "standings": [[{"rank": 1, "team": {"name": "Inter", "logo": "crest.png"}, "all": {"played": 38, "win": 27, "draw": 7, "lose": 4, "goals": {"for": 80, "against": 30}}, "goalsDiff": 50, "points": 88}]],
                    }
                }
            ]
        }

    monkeypatch.setattr(statistics_routes, "call_football_api", fake_call)

    response = client.get("/api/standings/lookup?league=SA")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["competition"] == "Serie A"
    assert payload["season"] == "2024"
    assert payload["standings"][0]["team"] == "Inter"


def test_team_statistics_route_uses_recent_matches_first(client, monkeypatch):
    def fake_call(endpoint, params=None):
        if endpoint == "teams":
            return {"response": [{"team": {"id": 40, "name": "Liverpool", "logo": "crest.png"}}]}
        if endpoint == "matches":
            assert params == {
                "team": 40,
                "season": statistics_routes.CURRENT_SEASON,
                "status": "FT-AET-PEN",
            }
            return {
                "response": [
                    {
                        "fixture": {"id": 1001, "status": {"short": "FT"}, "date": "2026-04-20T19:00:00+00:00"},
                        "teams": {"home": {"id": 40}, "away": {"id": 41}},
                        "goals": {"home": 2, "away": 0},
                    },
                    {
                        "fixture": {"id": 1002, "status": {"short": "FT"}, "date": "2026-04-13T19:00:00+00:00"},
                        "teams": {"home": {"id": 42}, "away": {"id": 40}},
                        "goals": {"home": 1, "away": 1},
                    },
                    {
                        "fixture": {"id": 1003, "status": {"short": "NS"}, "date": "2026-05-04T19:00:00+00:00"},
                        "teams": {"home": {"id": 40}, "away": {"id": 43}},
                        "goals": {"home": None, "away": None},
                    },
                ]
            }
        if endpoint == "fixture_statistics" and params == {"fixture": 1001}:
            return {
                "response": [
                    {
                        "team": {"id": 40},
                        "statistics": [
                            {"type": "Ball Possession", "value": "60%"},
                            {"type": "Total Shots", "value": 14},
                            {"type": "Shots on Goal", "value": 6},
                            {"type": "Fouls", "value": 10},
                            {"type": "Corner Kicks", "value": 7},
                        ],
                    }
                ]
            }
        if endpoint == "fixture_statistics" and params == {"fixture": 1002}:
            return {
                "response": [
                    {
                        "team": {"id": 40},
                        "statistics": [
                            {"type": "Ball Possession", "value": "50%"},
                            {"type": "Total Shots", "value": 10},
                            {"type": "Shots on Goal", "value": 4},
                            {"type": "Fouls", "value": 12},
                            {"type": "Corner Kicks", "value": 5},
                        ],
                    }
                ]
            }
        if endpoint in {"standings", "team_statistics", "leagues"}:
            raise AssertionError(f"{endpoint} should not be called when recent matches exist")
        raise AssertionError(f"Unexpected endpoint: {endpoint}")

    monkeypatch.setattr(statistics_routes, "call_football_api", fake_call)

    response = client.get("/api/teams/40/statistics?name=Liverpool")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["team_name"] == "Liverpool"
    assert payload["matches_played"] == 2
    assert payload["wins"] == 1
    assert payload["draws"] == 1
    assert payload["clean_sheets"] == 1
    assert payload["advanced_stats_matches"] == 2
    assert payload["average_possession"] == 55.0
    assert payload["average_shots"] == 12.0
    assert payload["average_shots_on_target"] == 5.0
    assert payload["average_fouls_committed"] == 11.0
    assert payload["average_corners"] == 6.0

def test_team_statistics_route_falls_back_to_team_name_search_when_id_lookup_is_empty(client, monkeypatch):
    calls = []

    def fake_call(endpoint, params=None):
        calls.append((endpoint, params))
        if endpoint == "teams" and params == {"id": 40}:
            return {"response": []}
        if endpoint == "teams" and params == {"search": "Liverpool"}:
            return {"response": [{"team": {"id": 40, "name": "Liverpool", "logo": "crest.png"}}]}
        if endpoint == "matches":
            return {
                "response": [
                    {
                        "fixture": {"id": 1001, "status": {"short": "FT"}, "date": "2026-04-20T19:00:00+00:00"},
                        "teams": {"home": {"id": 40}, "away": {"id": 41}},
                        "goals": {"home": 2, "away": 0},
                    }
                ]
            }
        if endpoint == "fixture_statistics":
            return {"response": []}
        raise AssertionError(f"Unexpected endpoint: {endpoint} {params}")

    monkeypatch.setattr(statistics_routes, "call_football_api", fake_call)

    response = client.get("/api/teams/40/statistics?name=Liverpool")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["team_name"] == "Liverpool"
    assert payload["wins"] == 1
    assert payload["advanced_stats_matches"] == 0
    assert payload["average_possession"] == 0.0
    assert ("teams", {"search": "Liverpool"}) in calls


def test_team_statistics_route_falls_back_to_official_endpoint_when_recent_matches_missing(client, monkeypatch):
    def fake_call(endpoint, params=None):
        if endpoint == "teams":
            return {"response": [{"team": {"id": 40, "name": "Liverpool", "logo": "crest.png"}}]}
        if endpoint == "standings":
            return {"response": [{"league": {"id": 39}}]}
        if endpoint == "matches":
            assert params == {
                "team": 40,
                "season": statistics_routes.CURRENT_SEASON,
                "status": "FT-AET-PEN",
            }
            return {"response": []}
        if endpoint == "team_statistics":
            return {
                "response": {
                    "team": {"id": 40, "name": "Liverpool", "logo": "crest.png"},
                    "fixtures": {
                        "played": {"total": 30},
                        "wins": {"total": 20},
                        "draws": {"total": 5},
                        "loses": {"total": 5},
                    },
                    "goals": {
                        "for": {"total": {"total": 70}},
                        "against": {"total": {"total": 28}},
                    },
                    "clean_sheet": {"total": 12},
                }
            }
        if endpoint == "leagues":
            return {
                "response": [{"league": {"id": 39, "type": "league"}}]
            }
        raise AssertionError(f"Unexpected endpoint: {endpoint}")

    monkeypatch.setattr(statistics_routes, "call_football_api", fake_call)

    response = client.get("/api/teams/40/statistics?name=Liverpool")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["team_name"] == "Liverpool"
    assert payload["matches_played"] == 30
    assert payload["wins"] == 20
    assert payload["draws"] == 5
    assert payload["average_possession"] == 0.0
    assert payload["average_shots"] == 0.0


def test_player_statistics_maps_statistics_fields(client, monkeypatch):
    def fake_call(endpoint, params=None):
        assert endpoint == "players"
        assert params == {"id": 306, "season": statistics_routes.CURRENT_SEASON}
        return {
            "response": [
                {
                    "player": {"id": 306, "name": "Mohamed Salah"},
                    "statistics": [
                        {
                            "team": {"name": "Liverpool"},
                            "games": {
                                "position": "Attacker",
                                "appearences": 30,
                                "minutes": 2620,
                                "rating": "7.30",
                            },
                            "goals": {"total": 21, "assists": 9},
                            "shots": {"total": 88, "on": 41},
                            "fouls": {"committed": 17},
                            "cards": {"yellow": 2, "red": 0},
                        }
                    ],
                }
            ]
        }

    monkeypatch.setattr(statistics_routes, "call_football_api", fake_call)

    response = client.get("/api/players/306/statistics")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload == {
        "player_id": 306,
        "player_name": "Mohamed Salah",
        "current_team": "Liverpool",
        "position": "Attacker",
        "statistics": {
            "goals": 21,
            "assists": 9,
            "appearances": 30,
            "minutes": 2620,
            "rating": "7.30",
            "shots": 88,
            "shots_on_target": 41,
            "fouls_committed": 17,
            "yellow_cards": 2,
            "red_cards": 0,
        },
        "stats_available": True,
    }

def test_player_statistics_returns_404_for_unknown_player(client, monkeypatch):
    monkeypatch.setattr(
        statistics_routes,
        "call_football_api",
        lambda endpoint, params=None: {"response": []},
    )

    response = client.get("/api/players/999999/statistics")

    assert response.status_code == 404
    assert response.get_json()["error"] == "Player not found"


def test_team_statistics_route_reuses_cached_payload(client, monkeypatch):
    call_counts = {
        "teams": 0,
        "matches": 0,
        "fixture_statistics": 0,
    }

    def fake_call(endpoint, params=None):
        call_counts[endpoint] = call_counts.get(endpoint, 0) + 1
        if endpoint == "teams":
            return {"response": [{"team": {"id": 40, "name": "Liverpool", "logo": "crest.png"}}]}
        if endpoint == "matches":
            return {
                "response": [
                    {
                        "fixture": {"id": 1001, "status": {"short": "FT"}, "date": "2026-04-20T19:00:00+00:00"},
                        "teams": {"home": {"id": 40}, "away": {"id": 41}},
                        "goals": {"home": 2, "away": 0},
                    }
                ]
            }
        if endpoint == "fixture_statistics":
            return {
                "response": [
                    {
                        "team": {"id": 40},
                        "statistics": [
                            {"type": "Ball Possession", "value": "61%"},
                            {"type": "Total Shots", "value": 15},
                            {"type": "Shots on Goal", "value": 7},
                            {"type": "Fouls", "value": 9},
                            {"type": "Corner Kicks", "value": 6},
                        ],
                    }
                ]
            }
        raise AssertionError(f"Unexpected endpoint: {endpoint} {params}")

    monkeypatch.setattr(statistics_routes, "call_football_api", fake_call)

    first_response = client.get("/api/teams/40/statistics?name=Liverpool")
    second_response = client.get("/api/teams/40/statistics?name=Liverpool")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.get_json() == second_response.get_json()
    assert call_counts["teams"] == 1
    assert call_counts["matches"] == 1
    assert call_counts["fixture_statistics"] == 1

