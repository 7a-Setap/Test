def test_live_matches_requires_login(client):
    response = client.get("/api/matches/live")

    assert response.status_code == 401
    assert response.get_json()["error"] == "Not authenticated"


def test_profile_requires_login(client):
    response = client.get("/api/profile")

    assert response.status_code == 401
    assert response.get_json()["error"] == "Not authenticated"


def test_notification_settings_requires_login(client):
    response = client.get("/api/notifications/settings")

    assert response.status_code == 401
    assert response.get_json()["error"] == "Not authenticated"


def test_save_favourites_requires_login(client):
    response = client.post("/api/favourites", json={"favourite_teams": ["Arsenal"]})

    assert response.status_code == 401
    assert response.get_json()["error"] == "Not authenticated"


def test_profile_validation_happens_before_database_write(authenticated_client):
    response = authenticated_client.post(
        "/api/profile",
        json={
            "username": "ab",
            "email": "invalid-email",
            "display_name": "Name",
            "bio": "Short bio",
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Username must be at least 3 characters"


def test_favourites_limit_validation_happens_before_resolution(authenticated_client):
    response = authenticated_client.post(
        "/api/favourites",
        json={
            "favourite_teams": ["One", "Two", "Three", "Four", "Five", "Six"],
            "favourite_players": [],
            "favourite_leagues": [],
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "You can save up to 5 favourite teams."
