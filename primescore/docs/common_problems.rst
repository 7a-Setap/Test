Common Problems
===============

``psql`` is not recognized
--------------------------

PostgreSQL command-line tools are not in your PATH.

PowerShell does not accept ``export``
------------------------------------

Use:

.. code-block:: powershell

   $env:FOOTBALL_API_KEY="YOUR_KEY"

The app starts but football data is missing
-------------------------------------------

Check:

- ``FOOTBALL_API_KEY`` is set
- the key is valid
- the free API plan has not rate-limited you
- the daily request quota has not been exhausted

The app opens but the browser shows stale UI behaviour
------------------------------------------------------

Hard refresh:

.. code-block:: text

   Ctrl + F5

Fixtures or current-season data look empty
------------------------------------------

This can be caused by API-Football plan limits rather than by local code errors. Some routes depend on the seasons and query types allowed by the current plan.
