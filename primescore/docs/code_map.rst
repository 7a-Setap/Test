Code Map
========

Application entry point - ``app.py``
------------------------------------

Key responsibilities:

- create the Flask app
- apply configuration from ``config.py``
- register all route blueprints
- serve the main dashboard shell
- define basic HTTP error handlers

Configuration - ``config.py``
-----------------------------

Key responsibilities:

- read environment variables
- store database config
- store session and cookie config
- store the active football API base URL, key, timeout, and season

Database layer - ``db/connection.py``, ``db/schema.sql``
--------------------------------------------------------

``db/connection.py``

- sets up PostgreSQL connection pooling
- provides ``get_db_connection()``
- provides ``release_db_connection()``
- provides ``DBContext`` for safe commit and rollback handling

``db/schema.sql``

- defines the project tables
- stores user accounts
- stores favourites
- stores notification settings

Authentication - ``routes/authentication_routes.py``
----------------------------------------------------

Key responsibilities:

- register
- login
- logout
- session lookup
- forgot password response
- login validation and simple rate-limit protection

Connected frontend:

- ``templates/pages/login_page.html``
- ``static/js/auth_handlers.js``

Home and favourites - ``routes/favourites_routes.py``
-----------------------------------------------------

Key responsibilities:

- get favourites
- save favourites
- build the ``/api/home-screen`` payload
- decide whether to show generic or favourite-driven content
- short-term cache repeated home-screen payloads per user and selected league
- invalidate cached home data when favourites change
- shape favourite player cards for the home page

Connected frontend:

- ``templates/pages/home_page.html``
- ``templates/pages/favourites_page.html``
- ``static/js/home_page_handlers.js``
- ``static/js/favourites_handlers.js``

Match data - ``routes/match_routes.py``
---------------------------------------

Key responsibilities:

- live matches
- upcoming fixtures
- recent results
- league or team filtering
- route-level mapping of match data for the UI

Connected frontend:

- ``templates/pages/live_page.html``
- ``templates/pages/fixtures_page.html``
- ``templates/pages/results_page.html``
- ``static/js/match_page_handlers.js``

Standings and statistics - ``routes/statistics_routes.py``
----------------------------------------------------------

Key responsibilities:

- league standings
- team statistics
- player statistics
- dedicated Statistics page data support
- standings lookup used by the homepage and league screens
- official team-statistics path plus recent-match fallback
- route-level caching for assembled team and player stat payloads

Connected frontend:

- ``templates/pages/leagues_page.html``
- ``templates/pages/compare_page.html``
- ``static/js/comparison_handlers.js``
- ``static/js/league_search_handlers.js``

Search and resolution - ``routes/lookup_routes.py``
---------------------------------------------------

Key responsibilities:

- health check
- search endpoint
- resolve team endpoint
- resolve player endpoint
- resolve league endpoint
- shared helper functions for name matching and API-friendly resolution
- short-lived caches for repeated league, team, and player resolution results

Why it matters:

- this file is one of the most important pieces in the app because many UI features depend on turning free text into IDs safely

Profile and notifications - ``routes/profile_routes.py``, ``routes/notification_routes.py``
--------------------------------------------------------------------------------------------

``routes/profile_routes.py``

- load profile data
- update profile fields
- change password

``routes/notification_routes.py``

- load notification settings
- save notification settings

Connected frontend:

- ``templates/pages/profile_page.html``
- ``templates/pages/settings_page.html``
- ``static/js/profile_handlers.js``
- ``static/js/notification_handlers.js``

External football API integration - ``services/football_api_client.py``
-----------------------------------------------------------------------

Key responsibilities:

- define supported endpoint mappings
- make HTTP requests to API-Football
- add request headers
- cache selected responses in memory
- back off after rate-limit responses
- retry with supported seasons after plan restrictions
- format standings
- compute team stats from finished matches
- fetch per-fixture advanced statistics used by FR7 team metrics

Why it matters:

- this is the main boundary between PrimeScore and the external football API
- many routes stay simpler because this file centralizes common API behaviour

Layout and page shell - ``templates/base_layout.html``, ``templates/dashboard_page.html``
------------------------------------------------------------------------------------------

``templates/base_layout.html``

- global page structure
- includes header, sidebar, footer, and scripts

``templates/dashboard_page.html``

- includes all page sections into one shell
- login, home, live, fixtures, results, leagues, compare, favourites, settings, and profile are all mounted here

Shared partials - ``templates/partials/``
-----------------------------------------

Important files:

- ``site_header.html``
- ``site_sidebar.html``
- ``site_footer.html``
- ``app_scripts.html``

Page sections - ``templates/pages/``
------------------------------------

Important files:

- ``login_page.html``
- ``home_page.html``
- ``live_page.html``
- ``fixtures_page.html``
- ``results_page.html``
- ``leagues_page.html``
- ``compare_page.html``
- ``favourites_page.html``
- ``settings_page.html``
- ``profile_page.html``

Frontend scripts - ``static/js/``
---------------------------------

Important files:

- ``app_helpers.js`` - shared client-side utilities, state helpers, and memoized lookup fetch logic
- ``ui_helpers.js`` - small shared UI helper functions
- ``auth_handlers.js`` - registration, login, logout, and session checks
- ``home_page_handlers.js`` - home screen rendering, favourite player cards, and league switcher behaviour
- ``favourites_handlers.js`` - favourites form, saving, and summary updates
- ``match_page_handlers.js`` - live, fixtures, and results page behaviour
- ``comparison_handlers.js`` - team and player comparison behaviour
- ``stats_handlers.js`` - dedicated Statistics page searches, stat requests, and rendering
- ``notification_handlers.js`` - notification settings form
- ``profile_handlers.js`` - profile editing and password change flows
- ``league_search_handlers.js`` - league resolution and standings search
- ``navigation_handlers.js`` - page switching and sidebar behaviour
- ``app_bootstrap.js`` - starts the client-side app
