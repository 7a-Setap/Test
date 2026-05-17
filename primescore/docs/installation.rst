Installation
============

Open the project folder
-----------------------

.. code-block:: powershell

   cd C:\path\to\primescore

Create a virtual environment
----------------------------

.. code-block:: powershell

   py -m venv .venv

Activate the virtual environment
--------------------------------

.. code-block:: powershell

   .\.venv\Scripts\Activate.ps1

Install dependencies
--------------------

.. code-block:: powershell

   pip install -r requirements.txt

Create the PostgreSQL database
------------------------------

.. code-block:: powershell

   psql -U postgres -c "CREATE DATABASE primescore;"

Load the schema
---------------

.. code-block:: powershell

   psql -U postgres -d primescore -f db\schema.sql

Set environment variables
-------------------------

.. code-block:: powershell

   $env:FOOTBALL_API_KEY="YOUR_API_FOOTBALL_KEY"
   $env:DB_HOST="localhost"
   $env:DB_NAME="primescore"
   $env:DB_USER="postgres"
   $env:DB_PASSWORD="YOUR_POSTGRES_PASSWORD"
   $env:DB_PORT="5432"

Running the app
---------------

Start the app from the project root:

.. code-block:: powershell

   python app.py

Then open:

- ``http://127.0.0.1:5000``
- ``http://localhost:5000``

Why port 5000?
--------------

The app runs on port ``5000`` because ``app.py`` explicitly starts Flask with:

.. code-block:: python

   app.run(host="0.0.0.0", port=5000, debug=debug_mode)
