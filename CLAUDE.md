# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Two separate components in one repo:

1. **Telegram bot** (`dw_quote/`) — sends random Doctor Who quotes. Entry point: `python -m dw_quote`. Run in watch mode: `make dev`.
2. **Django daily web game** (`game/`) — a Wordle-style game where users guess which episode a quote is from. Uses Django + HTMX; no JavaScript framework.

## Commands

```bash
# Setup
uv venv && uv pip install -r requirements/game.txt
export DJANGO_SECRET_KEY="dev-only"
python manage.py migrate
python manage.py import_quotes --clear   # loads data.csv

# Run
python manage.py runserver

# Test
pytest                                   # all tests (game/tests/)
pytest game/tests/test_game_logic.py    # single file
pytest -k test_name                      # single test

# Lint
make lint                                # runs pre-commit on all files
```

## Architecture: the game

The game separates concerns into four layers:

- **`game_logic.py`** — pure Python, no Django. Deterministic RNG, share-row formatting, date parsing. All business rules live here; test this without the DB.
- **`services.py`** — Django ORM layer. Translates `game_logic` functions into DB queries (`quote_for_play_date`, `next_hint_quote_pk`, `episode_search_results`).
- **`round_session.py`** — TypedDict-based session state. Reads/writes `request.session["daily_rounds"][YYYY-MM-DD]`. No Django ORM.
- **`views.py`** — orchestrates the above. Handles HTMX vs full-page responses by checking `request.htmx` and rendering the appropriate partial.

**Daily puzzle selection:** `resolve_quote_pk` in `game_logic.py` uses `sha256(date|branch)` as a seed to deterministically pick a quote PK for each calendar day, retrying on gaps in auto-increment IDs. The `GAME_SEED` env var rotates picks without changing dates.

**Session state shape** (`DailyRoundState`):
```
status: "in_progress" | "won" | "lost"
shown_quote_ids: list[int]   # PKs revealed as hints
wrong_count: int
answer_episode_id: int
share_row: str               # set on terminal states
guess_history: list[{guess_type, episode_id}]
```

**HTMX partials:**
- `partials/daily_round.html` — in-progress game state (returned on wrong guess)
- `partials/daily_complete.html` — win/loss result (returned on terminal state)
- `partials/episode_suggestions.html` — autocomplete dropdown (returned from `episode_autocomplete` view)

## Data model

- `Episode(title, airdate)` — unique on `(title, airdate)`
- `Quote(episode FK, text)` — many quotes per episode; PKs are used directly by `game_logic`

Data loaded from `data.csv` via `python manage.py import_quotes`.

## URL structure

```
/                           → redirect to /play/YYYY-MM-DD/
/play/<date>/               → daily_play (GET)
/play/<date>/answer/        → daily_answer (POST)
/play/<date>/episodes/      → episode_autocomplete (GET, HTMX)
```

The `<gdate>` URL converter (`game/converters.py`) parses and validates date segments.

## Settings

Django `config/settings.py` is the only settings file (no split dev/prod). Key game settings read from environment:

| Variable | Default | Purpose |
|---|---|---|
| `GAME_TIMEZONE` | `UTC` | IANA zone for "today" |
| `GAME_SEED` | `""` | Salt for rotating daily picks |
| `DJANGO_SECRET_KEY` | insecure default | Must be set in production |
| `DJANGO_DEBUG` | `true` | |

SQLite DB at `game.sqlite3` (project root).
