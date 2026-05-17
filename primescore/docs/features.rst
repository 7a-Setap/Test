Features and Requirements
=========================

Requirement 1: Manage user accounts
-----------------------------------

Users must be able to create and use accounts securely.

Implemented behaviour:

- users can register new accounts
- users can log in with existing credentials
- users can log out
- the app keeps session state for authenticated use
- the app identifies first-time users based on empty favourites
- users can request password reset messaging

Consequences or side-effects:

- protected API routes check ``session["user_id"]``
- registration also seeds default favourites and notification settings rows

Main code:

- ``app.py``
- ``routes/authentication_routes.py``
- ``templates/pages/login_page.html``
- ``static/js/auth_handlers.js``

Requirement 2: Manage favourites
--------------------------------

Users must be able to save and update favourite teams, players, and leagues.

Implemented behaviour:

- users can save up to 5 favourite teams
- users can save up to 10 favourite players
- users can save up to 3 favourite leagues
- favourites are stored with both IDs and display names
- favourites are returned as safe empty lists when logged out

Consequences or side-effects:

- favourites drive parts of the home screen
- player favourites depend on team-aware player resolution when needed

Main code:

- ``routes/favourites_routes.py``
- ``routes/lookup_routes.py``
- ``templates/pages/favourites_page.html``
- ``static/js/favourites_handlers.js``

Requirement 3: Show a personalised home screen
----------------------------------------------

The home screen should show meaningful football data before and after favourites are chosen.

Implemented behaviour:

- before favourites are saved, the home screen defaults to a general Premier League view
- after favourites are saved, the home screen can use favourite teams, favourite players, and favourite leagues
- favourite player cards appear on the home page when player favourites exist
- favourite league tables can be switched with arrows

Consequences or side-effects:

- this route coordinates several data sources, so it is one of the most important orchestration points in the app
- it now also uses a short-lived per-user cache so repeated homepage refreshes do not rebuild the full payload every time
- it is also affected most by API plan limits and quota limits

Main code:

- ``routes/favourites_routes.py``
- ``templates/pages/home_page.html``
- ``static/js/home_page_handlers.js``

Requirement 4: Show live matches fixtures and results
-----------------------------------------------------

Users should be able to see current and recent football matches.

Implemented behaviour:

- live matches come from the API-Football ``fixtures?live=all`` flow
- fixtures are returned through ``/api/fixtures``
- results are returned through ``/api/results``
- routes support league-based and team-based filtering

Consequences or side-effects:

- these flows depend heavily on API availability and plan restrictions
- the frontend needs clear fallback handling when the API returns no data

Main code:

- ``routes/match_routes.py``
- ``templates/pages/live_page.html``
- ``templates/pages/fixtures_page.html``
- ``templates/pages/results_page.html``
- ``static/js/match_page_handlers.js``

Requirement 5: Show league standings
------------------------------------

Users should be able to view current league tables.

Implemented behaviour:

- standings are retrieved using mapped league codes
- the backend formats raw API-Football standings into a UI-friendly shape
- the home page and leagues page both use standings data

Consequences or side-effects:

- the app uses internal codes like ``PL``, ``SA``, ``PD``, and ``BL1`` and translates them to API league IDs

Main code:

- ``routes/statistics_routes.py``
- ``services/football_api_client.py``
- ``templates/pages/leagues_page.html``
- ``static/js/league_search_handlers.js``

Requirement 6: Show team and player statistics
----------------------------------------------

Users should be able to inspect football statistics for teams and players.

Implemented behaviour:

- player statistics are fetched by player ID and season
- team statistics prefer official ``teams/statistics`` API data
- advanced FR7 metrics such as possession, shots, shots on target, fouls, and corners are enriched from recent finished-match statistics
- a dedicated Statistics page lets users inspect team and player stats outside the compare view
- home-page favourite-player cards display quick player stats

Consequences or side-effects:

- statistics quality depends on the external API and the free-plan limits
- team advanced metrics are averaged from recent finished matches rather than claimed as unavailable full-season totals
- player search by name often needs team context to resolve correctly

Main code:

- ``routes/statistics_routes.py``
- ``services/football_api_client.py``
- ``templates/pages/home_page.html``
- ``templates/pages/compare_page.html``
- ``templates/pages/stats_page.html``
- ``static/js/comparison_handlers.js``
- ``static/js/stats_handlers.js``

Requirement 7: Search and compare football data
-----------------------------------------------

Users should be able to search for leagues, teams, and players, then compare relevant data.

Implemented behaviour:

- team names can be resolved to team IDs
- player names can be resolved to player IDs, often using team context
- leagues can be resolved from user-typed names or short codes
- team and player comparison flows depend on those resolvers
- the compare page and the dedicated Statistics page both reuse the same resolution helpers

Consequences or side-effects:

- lookup is one of the most important shared systems because the UI works with names but the API mostly works with IDs
- shared frontend memoization plus backend resolver caching now reduce repeated team and player searches
- fuzzy matching and safe error handling make the UI more usable

Main code:

- ``routes/lookup_routes.py``
- ``routes/statistics_routes.py``
- ``templates/pages/compare_page.html``
- ``static/js/comparison_handlers.js``
- ``static/js/league_search_handlers.js``

Requirement 8: Manage profile and notification settings
-------------------------------------------------------

Users should be able to edit their own account details and preferences.

Implemented behaviour:

- users can update username, email, display name, and bio
- users can change password
- users can save notification preference booleans
- default notification settings are returned if no settings row exists yet

Consequences or side-effects:

- profile updates also update session values where needed
- notification preferences are stored, but real push delivery is not implemented

Main code:

- ``routes/profile_routes.py``
- ``routes/notification_routes.py``
- ``templates/pages/profile_page.html``
- ``templates/pages/settings_page.html``
- ``static/js/profile_handlers.js``
- ``static/js/notification_handlers.js``
