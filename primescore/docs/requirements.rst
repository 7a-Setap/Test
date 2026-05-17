Requirements
============

PrimeScore currently depends on:

- Python 3.10 or newer
- PostgreSQL running locally
- an API-Football API key

Tech stack
----------

- Python
- Flask
- PostgreSQL
- HTML
- CSS
- vanilla JavaScript
- API-Football (``https://v3.football.api-sports.io``)

Environment variables
---------------------

Required:

- ``FOOTBALL_API_KEY``

Usually needed:

- ``DB_HOST``
- ``DB_NAME``
- ``DB_USER``
- ``DB_PASSWORD``
- ``DB_PORT``

Optional:

- ``SECRET_KEY``
- ``CURRENT_SEASON``
- ``FLASK_DEBUG``

Default database values
-----------------------

The defaults in ``config.py`` are:

- host: ``localhost``
- database: ``primescore``
- user: ``postgres``
- port: ``5432``
