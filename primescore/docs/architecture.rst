Architecture and Data Flow
==========================

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

Typical request flow
--------------------

.. code-block:: text

   Browser UI
     -> JavaScript handler
     -> Flask route (/api/...)
     -> DB lookup and/or API-Football call
     -> response formatting
     -> JSON returned to frontend
     -> UI updated in the page

Most important connection points
--------------------------------

``app.py``

- creates the Flask app
- registers all blueprints
- serves ``dashboard_page.html``

``routes/lookup_routes.py``

- converts typed team, player, and league names into IDs
- caches successful resolution results for repeated lookups

``routes/favourites_routes.py``

- builds and short-term caches personalised ``/api/home-screen`` payloads

``routes/statistics_routes.py``

- serves standings plus cached team and player statistics payloads

``services/football_api_client.py``

- centralizes external API requests, caching, fallback handling, and formatting

``db/connection.py``

- centralizes DB access through pooled connections and ``DBContext``
