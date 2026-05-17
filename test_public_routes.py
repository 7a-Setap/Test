import routes.favourites_routes as favourites_routes
import routes.lookup_routes as lookup_routes


def test_search_rejects_queries_shorter_than_three_characters(client):
    response = client.get("/api/search?q=ar&type=teams")

    assert response.status_code == 400
    assert response.get_json()["error"] == "Query must be at least 3 characters"


def test_health_check_returns_degraded_when_database_is_unavailable(client, monkeypatch):
    monkeypatch.setattr(lookup_routes, "get_db_connection", lambda: None)

    response = client.get("/api/health")

    assert response.status_code == 503
    assert response.get_json()["status"] == "degraded"
    assert response.get_json()["database"] == "unreachable"


def test_resolve_player_requires_team_when_name_is_used(client):
    response = client.get("/api/resolve/player?q=mohamed salah")

    assert response.status_code == 400
    assert response.get_json()["error"] == "Team is required when searching by player name"


def test_get_favourites_returns_empty_lists_when_logged_out(client):
    response = client.get("/api/favourites")

    assert response.status_code == 200
    assert response.get_json() == {
        "favourite_teams": [],
        "favourite_players": [],
        "favourite_leagues": [],
        "favourite_team_ids": [],
        "favourite_player_ids": [],
        "favourite_league_codes": [],
    }


def test_dashboard_html_includes_statistics_page_and_sidebar_link(client):
    response = client.get("/")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'data-page="stats"' in body
    assert 'id="statsPage"' in body


def test_home_screen_returns_default_shape_when_api_returns_no_data(client, monkeypatch):
    monkeypatch.setattr(favourites_routes, "call_football_api", lambda endpoint, params=None: None)

    response = client.get("/api/home-screen")
    payload = response.get_json()

    assert response.status_code == 200
    assert set(payload.keys()) == {
        "favourite_player_stats",
        "favourite_team_stats",
        "favourite_league_stats",
        "league_tables",
        "live_matches",
        "upcoming_fixtures",
        "recent_results",
        "selected_league",
    }
    assert payload["league_tables"] == []
    assert payload["live_matches"] == []

def test_resolve_team_numeric_id_uses_direct_team_lookup(client, monkeypatch):
    calls = []

    def fake_call(endpoint, params=None):
        calls.append((endpoint, params))
        return {"response": [{"team": {"id": 42, "name": "Arsenal", "logo": "crest.png"}}]}

    monkeypatch.setattr(lookup_routes, "call_football_api", fake_call)

    response = client.get("/api/resolve/team?q=42")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload == {
        "id": 42,
        "name": "Arsenal",
        "crest": "crest.png",
    }
    assert calls == [("teams", {"id": 42})]


def test_search_team_results_apply_resolved_league_filter(client, monkeypatch):
    calls = []

    monkeypatch.setattr(
        lookup_routes,
        "resolve_league_reference",
        lambda reference: {"id": 39, "code": "PL", "name": "Premier League"},
    )

    def fake_call(endpoint, params=None):
        calls.append((endpoint, params))
        if endpoint == "teams":
            return {
                "response": [
                    {"team": {"id": 42, "name": "Arsenal", "logo": "crest.png"}},
                ]
            }
        raise AssertionError(f"Unexpected endpoint: {endpoint}")

    monkeypatch.setattr(lookup_routes, "call_football_api", fake_call)

    response = client.get("/api/search?q=arsenal&type=teams&league=PL")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["teams"] == [{"id": 42, "name": "Arsenal", "crest": "crest.png"}]
    assert calls == [("teams", {"search": "arsenal", "league": 39})]


def test_player_search_without_context_uses_player_profiles(client, monkeypatch):
    calls = []

    def fake_call(endpoint, params=None):
        calls.append((endpoint, params))
        if endpoint == "player_profiles":
            return {
                "response": [
                    {
                        "id": 276,
                        "name": "Mohamed Salah",
                        "firstname": "Mohamed",
                        "lastname": "Salah",
                        "photo": "salah.png",
                    }
                ]
            }
        raise AssertionError(f"Unexpected endpoint: {endpoint}")

    monkeypatch.setattr(lookup_routes, "call_football_api", fake_call)

    response = client.get("/api/search?q=salah&type=players")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["players"][0]["name"] == "Mohamed Salah"
    assert calls[0][0] == "player_profiles"


def test_player_search_with_league_context_uses_players_endpoint(client, monkeypatch):
    calls = []

    monkeypatch.setattr(
        lookup_routes,
        "resolve_league_reference",
        lambda reference: {"id": 39, "code": "PL", "name": "Premier League"},
    )

    def fake_call(endpoint, params=None):
        calls.append((endpoint, params))
        if endpoint == "players":
            return {
                "response": [
                    {
                        "player": {
                            "id": 276,
                            "name": "Mohamed Salah",
                            "firstname": "Mohamed",
                            "lastname": "Salah",
                            "photo": "salah.png",
                        },
                        "statistics": [{"team": {"name": "Liverpool"}}],
                    }
                ]
            }
        raise AssertionError(f"Unexpected endpoint: {endpoint}")

    monkeypatch.setattr(lookup_routes, "call_football_api", fake_call)

    response = client.get("/api/search?q=salah&type=players&league=PL")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["players"][0]["team"] == "Liverpool"
    assert calls == [
        (
            "players",
            {"search": "salah", "league": 39, "season": lookup_routes.CURRENT_SEASON},
        )
    ]


def test_player_search_with_team_context_uses_team_lookup_then_players(client, monkeypatch):
    calls = []

    def fake_call(endpoint, params=None):
        calls.append((endpoint, params))
        if endpoint == "teams":
            return {"response": [{"team": {"id": 40, "name": "Liverpool", "logo": "crest.png"}}]}
        if endpoint == "player_squads":
            return {"response": [{"players": []}]}
        if endpoint == "players":
            return {
                "response": [
                    {
                        "player": {
                            "id": 276,
                            "name": "Mohamed Salah",
                            "firstname": "Mohamed",
                            "lastname": "Salah",
                            "photo": "salah.png",
                        },
                        "statistics": [{"team": {"name": "Liverpool"}}],
                    }
                ]
            }
        raise AssertionError(f"Unexpected endpoint: {endpoint}")

    monkeypatch.setattr(lookup_routes, "call_football_api", fake_call)

    response = client.get("/api/search?q=salah&type=players&team=Liverpool")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["players"][0]["team"] == "Liverpool"
    assert ("players", {"search": "salah", "team": 40, "season": lookup_routes.CURRENT_SEASON}) in calls


def test_search_competitions_returns_internal_league_codes(client, monkeypatch):
    def fake_call(endpoint, params=None):
        assert endpoint == "leagues"
        assert params == {"search": "premier"}
        return {
            "response": [
                {"league": {"id": 39, "name": "Premier League"}},
                {"league": {"id": 140, "name": "La Liga"}},
            ]
        }

    monkeypatch.setattr(lookup_routes, "call_football_api", fake_call)

    response = client.get("/api/search?q=premier&type=competitions")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["competitions"][0] == {
        "id": 39,
        "name": "Premier League",
        "code": "PL",
    }


def test_resolve_team_translates_rate_limit_payload_into_429(client, monkeypatch):
    monkeypatch.setattr(
        lookup_routes,
        "resolve_team_reference",
        lambda query, league_filter=None: {"_error": "rate_limit", "status_code": 429},
    )

    response = client.get("/api/resolve/team?q=arsenal")

    assert response.status_code == 429
    assert response.get_json()["error"] == "Rate limited by API-Football. Please retry shortly."


def test_resolve_league_matches_common_competition_names_without_api_call(client, monkeypatch):
    monkeypatch.setattr(
        lookup_routes,
        "call_football_api",
        lambda endpoint, params=None: (_ for _ in ()).throw(AssertionError("API should not be called")),
    )

    response = client.get("/api/resolve/league?q=premierl")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload == {
        "id": 39,
        "code": "PL",
        "name": "Premier League",
    }
