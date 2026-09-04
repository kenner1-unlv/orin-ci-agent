# Quickstart

Run `uv run --project reviewer --python 3.12 python -m unittest discover -s reviewer/tests -v`. A passing run proves a reviewed patch can be committed and stale, unapproved, failed-check, extra-path, and dirty-index submissions cannot be committed.
