"""Session payload for one calendar day's multi-guess round."""

from __future__ import annotations

from datetime import date
from typing import Any, TypedDict


class DailyRoundState(TypedDict, total=False):
    status: str  # "in_progress" | "won" | "lost"
    shown_quote_ids: list[int]
    wrong_count: int
    answer_episode_id: int
    share_row: str


SESSION_KEY = "daily_rounds"
MAX_ATTEMPTS = 6


def round_key(play_date: date) -> str:
    return play_date.isoformat()


def get_round(session: dict[str, Any], play_date: date) -> DailyRoundState | None:
    raw = session.get(SESSION_KEY, {})
    entry = raw.get(round_key(play_date))
    return entry if isinstance(entry, dict) else None


def save_round(session: dict[str, Any], play_date: date, state: DailyRoundState) -> None:
    rounds = dict(session.get(SESSION_KEY, {}))
    rounds[round_key(play_date)] = state
    session[SESSION_KEY] = rounds
    session.modified = True


def new_round_from_quote(quote) -> DailyRoundState:
    return {
        "status": "in_progress",
        "shown_quote_ids": [quote.pk],
        "wrong_count": 0,
        "answer_episode_id": quote.episode_id,
    }


def is_terminal(state: DailyRoundState | None) -> bool:
    if state is None:
        return False
    return state.get("status") in ("won", "lost")
