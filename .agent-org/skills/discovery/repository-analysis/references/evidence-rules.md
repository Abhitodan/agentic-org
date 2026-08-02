# Evidence rules for repository-analysis

1. Every file counted must exist on disk at map time.
2. Python imports are parsed via `ast` — syntax errors yield empty import lists, not guesses.
3. Tests are discovered by filename convention (`test_*.py`, `*_test.py`) and common test dirs.
4. Do not invent frameworks absent from files (e.g. do not claim Django because of a single `django` string in a comment unless imports prove it — current mapper reports imports only).
5. Output must remain usable offline with no API keys.
