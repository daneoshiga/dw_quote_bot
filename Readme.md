# Doctor Who Quote Bot

[@dw_quote_bot](https://t.me/@dw_quote_bot)

Bot that replies random quotes from Doctor Who

Quotes from: http://www.chakoteya.net/

## Commands

**/quote** Returns any quote

**/doctor_quote** Returns any Doctor quote

**inline (@dw_quote_bot character name)** Makes it possible to filter by character name

All results will have two buttons, one for searching again to get a new quote as a new message, and another to refresh
the current message with a new quote.

## Daily web game (Django + HTMX)

Guess which episode a quote is from. **One puzzle per calendar day** in `GAME_TIMEZONE` (default `UTC`). Each day has a stable URL: `/play/YYYY-MM-DD/` so you can replay or share a specific day. `/` redirects to today’s path.

### Setup

Use a virtualenv and install game dependencies, for example:

```bash
uv venv && uv pip install -r requirements/game.txt
```

Or compile locks from `requirements/game.in` with `pip-compile` (see the `Makefile`).

```bash
export DJANGO_SECRET_KEY="dev-only"
python manage.py migrate
python manage.py import_quotes --clear   # loads data.csv; use --csv PATH for another file
python manage.py runserver
```

Environment variables (optional):

| Variable | Purpose |
| -------- | ------- |
| `GAME_TIMEZONE` | IANA zone for “today” on `/` (default `UTC`) |
| `GAME_SEED` | Salt so daily picks can be rotated without changing dates |
| `DATA_CSV_PATH` | CSV path (default: project root `data.csv`) |
| `DISTRACTOR_COUNT` | Wrong answers shown (default `3`) |
| `DJANGO_DEBUG` | `true` / `false` |

### Tests

```bash
pytest
```
