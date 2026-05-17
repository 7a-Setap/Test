# PrimeScore

Welcome to PrimeScore's documentation.

PrimeScore is a Flask and PostgreSQL football statistics application built around API-Football. It lets users register, log in, manage favourites, view live matches, check fixtures and results, browse league tables, compare teams and players, and manage profile and notification settings from one browser-based dashboard.

This README is written as a GitHub-friendly documentation page. It is meant to help a new teammate, marker, or developer understand:

- what the project does
- how to install and run it
- which requirements it implements
- how the files connect to each other
- where the important logic lives
- how the project is tested

## Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Running the app](#running-the-app)
- [Version control](#version-control)
- [Definitions](#definitions)
- [Requirement 1: Manage user accounts](#requirement-1-manage-user-accounts)
- [Requirement 2: Manage favourites](#requirement-2-manage-favourites)
- [Requirement 3: Show a personalised home screen](#requirement-3-show-a-personalised-home-screen)
- [Requirement 4: Show live matches fixtures and results](#requirement-4-show-live-matches-fixtures-and-results)
- [Requirement 5: Show league standings](#requirement-5-show-league-standings)
- [Requirement 6: Show team and player statistics](#requirement-6-show-team-and-player-statistics)
- [Requirement 7: Search and compare football data](#requirement-7-search-and-compare-football-data)
- [Requirement 8: Manage profile and notification settings](#requirement-8-manage-profile-and-notification-settings)
- [Architecture and data flow](#architecture-and-data-flow)
- [Code map](#code-map)
- [Testing](#testing)
- [Common problems](#common-problems)

## Requirements

PrimeScore currently depends on:

- Python 3.10 or newer
- PostgreSQL running locally
- an API-Football API key

Tech stack:

- Python
- Flask
- PostgreSQL
- HTML
- CSS
- vanilla JavaScript
- API-Football (`https://v3.football.api-sports.io`)

Environment variables used by the app:

Required:

- `FOOTBALL_API_KEY`

Usually needed:

- `DB_HOST`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_PORT`

Optional:

- `SECRET_KEY`
- `CURRENT_SEASON`
- `FLASK_DEBUG`
- `SMTP_HOST`       (e.g. sandbox.smtp.mailtrap.io — leave blank to disable email)
- `SMTP_PORT`       (default: 587)
- `SMTP_USER`
- `SMTP_PASSWORD`
- `SMTP_FROM`       (defaults to SMTP_USER if not set)

Default database values in `config.py`:

- host: `localhost`
- database: `primescore`
- user: `postgres`
- port: `5432`

## Installation

### 1. Open the project folder

```powershell
cd C:\path\to\primescore
```

### 2. Create a virtual environment

```powershell
py -m venv .venv
```

### 3. Activate the virtual environment

```powershell
.\.venv\Scripts\Activate.ps1
```

### 4. Install dependencies

```powershell
pip install -r requirements.txt
```

### 5. Create the PostgreSQL database

```powershell
psql -U postgres -c "CREATE DATABASE primescore;"
```

### 6. Load the schema

```powershell
psql -U postgres -d primescore -f db\schema.sql
```

### 7. Set environment variables for the current PowerShell session

```powershell
$env:FOOTBALL_API_KEY="YOUR_API_FOOTBALL_KEY"
$env:DB_HOST="localhost"
$env:DB_NAME="primescore"
$env:DB_USER="postgres"
$env:DB_PASSWORD="YOUR_POSTGRES_PASSWORD"
$env:DB_PORT="5432"

# Optional — required only for email notifications
$env:CURRENT_SEASON="2024" #fixes seasonal fallback issues 
$env:SMTP_HOST="sandbox.smtp.mailtrap.io"
$env:SMTP_PORT="587"
$env:SMTP_USER="your_mailtrap_username"
$env:SMTP_PASSWORD="your_mailtrap_password"
```

## Running the app

Start the server from the project root:

```powershell
python app.py
```

Then open:

- `http://127.0.0.1:5000`
- or `http://localhost:5000`

The app runs on port `5000` because `app.py` explicitly starts Flask with:

```python
app.run(host="0.0.0.0", port=5000, debug=debug_mode)
```

## Version control

Suggested Git workflow for the repository:

```powershell
git clone <your-repo-url>
cd primescore
git checkout -b feature/short-description
```

Good practice for this project:

- keep commits focused on one feature or bug fix
- write clear commit messages
- avoid committing `.venv`, `__pycache__`, local coverage files, or local editor folders
- run the automated test suite before pushing

Typical commands:

```powershell
git add .
git commit -m "Add favourites route tests and update matrix"
git push origin feature/short-description
```

## Definitions

### A. User account

A PrimeScore account stores:

- username
- email
- password hash
- optional display name
- optional bio

### B. Favourite team

A favourite team is a club selected by the user so the app can show team-focused fixtures, results, live matches, and comparisons.

### C. Favourite player

A favourite player is a player selected by the user so the app can show player cards and player statistics on the home screen and in comparison tools.

### D. Favourite league

A favourite league is a saved competition such as the Premier League, Serie A, or La Liga. Favourite leagues drive the league-table section and can also be cycled on the home page.

### E. Match

A match is a fixture returned by API-Football. Depending on status, it may be:

- live
- not started
- finished

### F. Statistics

Statistics are football-specific values returned by API-Football or derived from returned fixtures, such as:

- goals
- assists
- appearances
- wins
- draws
- losses
- clean sheets

## Requirement 1: Manage user accounts

Users must be able to create and use accounts securely.

Implemented behaviour:

- users can register new accounts
- users can log in with existing credentials
- users can log out
- the app keeps session state for authenticated use
- the app identifies first-time users based on empty favourites
- users can request password reset messaging

Consequences or side-effects:

- session-based authentication means protected API routes check `session["user_id"]`
- registration also seeds default favourites and notification settings rows

Main code:

- `app.py`
- `routes/authentication_routes.py`
- `templates/pages/login_page.html`
- `static/js/auth_handlers.js`

## Requirement 2: Manage favourites

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

- `routes/favourites_routes.py`
- `routes/lookup_routes.py`
- `templates/pages/favourites_page.html`
- `static/js/favourites_handlers.js`

## Requirement 3: Show a personalised home screen

The home screen should show meaningful football data before and after favourites are chosen.

Implemented behaviour:

- before favourites are saved, the home screen defaults to a general Premier League view
- after favourites are saved, the home screen can use favourite teams, favourite players, and favourite leagues
- favourite player cards appear on the home page when player favourites exist
- favourite league tables can be switched with arrows

Consequences or side-effects:

- this route coordinates several data sources, so it is one of the most important orchestration points in the app
- it is also affected most by API plan limits and quota limits

Main code:

- `routes/favourites_routes.py`
- `templates/pages/home_page.html`
- `static/js/home_page_handlers.js`

## Requirement 4: Show live matches fixtures and results

Users should be able to see current and recent football matches.

Implemented behaviour:

- live matches come from the API-Football `fixtures?live=all` flow
- fixtures are returned through `/api/fixtures`
- results are returned through `/api/results`
- routes support league-based and team-based filtering

Consequences or side-effects:

- these flows depend heavily on API availability and plan restrictions
- the frontend needs clear fallback handling when the API returns no data

Main code:

- `routes/match_routes.py`
- `templates/pages/live_page.html`
- `templates/pages/fixtures_page.html`
- `templates/pages/results_page.html`
- `static/js/match_page_handlers.js`

## Requirement 5: Show league standings

Users should be able to view current league tables.

Implemented behaviour:

- standings are retrieved using mapped league codes
- the backend formats raw API-Football standings into a UI-friendly shape
- the home page and leagues page both use standings data

Consequences or side-effects:

- the app uses internal codes like `PL`, `SA`, `PD`, and `BL1` and translates them to API league IDs

Main code:

- `routes/statistics_routes.py`
- `services/football_api_client.py`
- `templates/pages/leagues_page.html`
- `static/js/league_search_handlers.js`

## Requirement 6: Show team and player statistics

Users should be able to inspect football statistics for teams and players.

Implemented behaviour:

- player statistics are fetched by player ID and season
- team statistics prefer official `teams/statistics` API data
- advanced FR7 metrics such as possession, shots, shots on target, fouls, and corners are enriched from recent finished-match statistics
- a dedicated Statistics page lets users inspect team and player stats outside the compare view
- home-page favourite-player cards display quick player stats

Consequences or side-effects:

- statistics quality depends on the external API and the free-plan limits
- player search by name often needs team context to resolve correctly

Main code:

- `routes/statistics_routes.py`
- `services/football_api_client.py`
- `templates/pages/home_page.html`
- `templates/pages/compare_page.html`
- `static/js/comparison_handlers.js`

## Requirement 7: Search and compare football data

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

- `routes/lookup_routes.py`
- `routes/statistics_routes.py`
- `templates/pages/compare_page.html`
- `static/js/comparison_handlers.js`
- `static/js/league_search_handlers.js`

## Requirement 8: Manage profile and notification settings

Users should be able to edit their own account details and preferences.

Implemented behaviour:

- users can update username, email, display name, and bio
- users can change password
- users can save notification preference booleans
- default notification settings are returned if no settings row exists yet

Consequences or side-effects:

- profile updates also update session values where needed
- a demo notification button fires a browser notification and sends an email
  via SMTP (Mailtrap sandbox recommended for local development)

Main code:

- `routes/profile_routes.py`
- `routes/notification_routes.py`
- `templates/pages/profile_page.html`
- `templates/pages/settings_page.html`
- `static/js/profile_handlers.js`
- `static/js/notification_handlers.js`

## Architecture and data flow

PrimeScore follows a simple 3-layer structure:

1. Presentation layer
   - HTML templates
   - CSS
   - JavaScript handlers
2. Application layer
   - Flask routes and orchestration logic
3. Data and integration layer
   - PostgreSQL
   - API-Football

Typical request flow:

```text
Browser UI
  -> JavaScript handler
  -> Flask route (/api/...)
  -> DB lookup and/or API-Football call
  -> response formatting
  -> JSON returned to frontend
  -> UI updated in the page
```

The biggest connection points in the system are:

- `app.py`
  - creates the Flask app
  - registers all blueprints
  - serves `dashboard_page.html`
- `routes/lookup_routes.py`
  - converts typed team, player, and league names into IDs and caches successful resolutions
- `routes/favourites_routes.py`
  - builds and short-term caches personalised `/api/home-screen` payloads
- `routes/statistics_routes.py`
  - serves standings plus cached team and player statistics payloads
- `services/football_api_client.py`
  - centralizes external API requests, caching, fallback handling, and formatting
- `db/connection.py`
  - centralizes DB access through pooled connections and `DBContext`

## Code map

This section is the closest equivalent to the "Login page - main.dart" style module list in your example, but adapted to PrimeScore.

### Application entry point - `app.py`

Key responsibilities:

- create the Flask app
- apply configuration from `config.py`
- register all route blueprints
- serve the main dashboard shell
- define basic HTTP error handlers

### Configuration - `config.py`

Key responsibilities:

- read environment variables
- store database config
- store session/cookie config
- store the active football API base URL, key, timeout, and season

### Database layer - `db/connection.py`, `db/schema.sql`

`db/connection.py`

- sets up PostgreSQL connection pooling
- provides `get_db_connection()`
- provides `release_db_connection()`
- provides `DBContext` for safe commit/rollback handling

`db/schema.sql`

- defines the project tables
- stores user accounts
- stores favourites
- stores notification settings

### Authentication - `routes/authentication_routes.py`

Key responsibilities:

- register
- login
- logout
- session lookup
- forgot password response
- login validation and simple rate-limit protection

Connected frontend:

- `templates/pages/login_page.html`
- `static/js/auth_handlers.js`

### Home and favourites - `routes/favourites_routes.py`

Key responsibilities:

- get favourites
- save favourites
- build the `/api/home-screen` payload
- decide whether to show generic or favourite-driven content
- short-term cache repeated home-screen payloads per user and selected league
- invalidate cached home data when favourites change
- shape favourite player cards for the home page

Connected frontend:

- `templates/pages/home_page.html`
- `templates/pages/favourites_page.html`
- `static/js/home_page_handlers.js`
- `static/js/favourites_handlers.js`

### Match data - `routes/match_routes.py`

Key responsibilities:

- live matches
- upcoming fixtures
- recent results
- league or team filtering
- route-level mapping of match data for the UI

Connected frontend:

- `templates/pages/live_page.html`
- `templates/pages/fixtures_page.html`
- `templates/pages/results_page.html`
- `static/js/match_page_handlers.js`

### Standings and statistics - `routes/statistics_routes.py`

Key responsibilities:

- league standings
- team statistics
- player statistics
- a dedicated Statistics page for individual team and player views
- standings lookup used by the homepage and league screens
- official team-statistics path plus recent-match fallback
- route-level caching for assembled team and player stat payloads

Connected frontend:

- `templates/pages/leagues_page.html`
- `templates/pages/compare_page.html`
- `static/js/comparison_handlers.js`
- `static/js/league_search_handlers.js`

### Search and resolution - `routes/lookup_routes.py`

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

### Profile and notifications - `routes/profile_routes.py`, `routes/notification_routes.py`

`routes/profile_routes.py`

- load profile data
- update profile fields
- change password
- send test notification (browser alert + SMTP email)

`routes/notification_routes.py`

- load notification settings
- save notification settings

Connected frontend:

- `templates/pages/profile_page.html`
- `templates/pages/settings_page.html`
- `static/js/profile_handlers.js`
- `static/js/notification_handlers.js`

### External football API integration - `services/football_api_client.py`

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

### Layout and page shell - `templates/base_layout.html`, `templates/dashboard_page.html`

`templates/base_layout.html`

- global page structure
- includes header, sidebar, footer, and scripts

`templates/dashboard_page.html`

- includes all page sections into one shell
- login, home, live, fixtures, results, leagues, compare, favourites, settings, and profile are all mounted here

### Shared partials - `templates/partials/`

Important files:

- `site_header.html`
- `site_sidebar.html`
- `site_footer.html`
- `app_scripts.html`

These partials keep shared UI structure out of individual page fragments.

### Page sections - `templates/pages/`

Important files:

- `login_page.html`
- `home_page.html`
- `live_page.html`
- `fixtures_page.html`
- `results_page.html`
- `leagues_page.html`
- `compare_page.html`
- `favourites_page.html`
- `settings_page.html`
- `profile_page.html`

Each file represents a feature area rendered inside the main dashboard layout.

### Frontend scripts - `static/js/`

Important files:

- `app_helpers.js`
  - shared client-side utilities, state helpers, and memoized lookup fetch logic
- `ui_helpers.js`
  - small shared UI helper functions
- `auth_handlers.js`
  - registration, login, logout, session checks
- `home_page_handlers.js`
  - home screen rendering, favourite player cards, league switcher behaviour
- `favourites_handlers.js`
  - favourites form, saving, and summary updates
- `match_page_handlers.js`
  - live, fixtures, and results page behaviour
- `comparison_handlers.js`
  - team and player comparison behaviour
- `stats_handlers.js`
  - dedicated Statistics page searches, stat requests, and rendering
- `notification_handlers.js`
  - notification settings form and demo test notification button
- `profile_handlers.js`
  - profile editing and password change flows
- `league_search_handlers.js`
  - league resolution and standings search
- `navigation_handlers.js`
  - page switching and sidebar behaviour
- `app_bootstrap.js`
  - starts the client-side app



## Common problems

### `psql` is not recognized

PostgreSQL command-line tools are not in your PATH.

### PowerShell does not accept `export`

Use:

```powershell
$env:FOOTBALL_API_KEY="YOUR_KEY"
```

### The app starts but football data is missing

Check:

- `FOOTBALL_API_KEY` is set
- the key is valid
- the free API plan has not rate-limited you
- the daily request quota has not been exhausted

### The app opens but the browser shows stale UI behaviour

Hard refresh:

```text
Ctrl + F5
```

### Test notification says "Email could not be sent"
The SMTP environment variables are not set or are incorrect.
For a local demo, sign up at https://mailtrap.io, create a sandbox inbox,
and copy the SMTP credentials from the inbox SMTP Settings tab.

### Fixtures or current-season data look empty

This can be caused by API-Football plan limits rather than by local code errors. Some routes depend on the seasons and query types allowed by the current plan.

## Note

PrimeScore is still under active development. The backend foundation, testing, and documentation are now much stronger, but the project can still be improved further with:

- more browser-based end-to-end testing
- fuller API quota and plan-limit messaging
- more frontend automation
- more documentation split across dedicated docs pages if the repository later moves to GitHub Pages or Read the Docs
