Testing
=======

PrimeScore includes an automated backend-oriented pytest suite.

Current measured position
-------------------------

- ``90`` automated tests passing
- ``84%`` total line coverage

Main test files
---------------

- ``tests/conftest.py``
- ``tests/helpers.py``
- ``tests/test_authenticated_routes.py``
- ``tests/test_authentication_routes.py``
- ``tests/test_core_logic.py``
- ``tests/test_db_connection.py``
- ``tests/test_favourites_routes.py``
- ``tests/test_match_routes.py``
- ``tests/test_profile_notification_routes.py``
- ``tests/test_public_routes.py``
- ``tests/test_statistics_routes.py``

Testing style
-------------

The suite mixes:

- unit-style tests
  - helper logic
  - formatting
  - API fallback logic
  - DB context-manager behaviour
- integration-style backend tests
  - Flask route tests using the test client
  - mocked API and DB behaviour
  - session and persistence-flow checks
  - home-screen and statistics-route cache reuse checks

Run the tests
-------------

Install test dependencies:

.. code-block:: powershell

   pip install -r requirements.txt -r requirements-dev.txt

Run all tests:

.. code-block:: powershell

   python -m pytest -v

Run coverage:

.. code-block:: powershell

   python -m pytest --cov=. --cov-report=term-missing

Saved evidence
--------------

- ``coursework/test-evidence/pytest-results.txt``
- ``coursework/test-evidence/coverage-summary.txt``
- ``coursework/test-evidence/htmlcov/index.html``
- ``coursework/CW2_Test_Matrix.csv``
- ``coursework/CW2_Test_Plan_Styled.xlsx``
