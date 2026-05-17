import os
import sys


sys.path.insert(0, os.path.abspath(".."))

project = "PrimeScore"
copyright = "2026, Group 7A"
author = "Group 7A"
release = "latest"

extensions = [
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_title = "PrimeScore documentation"
