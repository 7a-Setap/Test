Version Control
===============

Suggested workflow
------------------

.. code-block:: powershell

   git clone <your-repo-url>
   cd primescore
   git checkout -b feature/short-description

Good practice
-------------

- keep commits focused on one feature or bug fix
- write clear commit messages
- avoid committing ``.venv``, ``__pycache__``, local coverage files, or editor folders
- run the automated test suite before pushing

Typical commands
----------------

.. code-block:: powershell

   git add .
   git commit -m "Add favourites route tests and update matrix"
   git push origin feature/short-description
