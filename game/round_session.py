"""Session payload for one calendar day's multi-guess round."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal, NotRequired, TypedDict, cast

from game.game_logic import format_share_row


class GuessHistoryEntry(TypedDict):
    guess_type: str  # "episode" | "skip"
    episode_id: int | None


class DailyRoundState(TypedDict):
    status: str  # "in_progress" | "won" | "lost"
    shown_quote_ids: list[int]
    wrong_count: int
    answer_episode_id: int
    share_row: NotRequired[str]
    guess_history: list[GuessHistoryEntry]


SESSION_KEY = "daily_rounds"
MAX_ATTEMPTS = 6


def round_key(play_date: date) -> str:
    return play_date.isoformat()


def get_round(session: dict[str, Any], play_date: date) -> DailyRoundState | None:
    raw = session.get(SESSION_KEY, {})
    entry = raw.get(round_key(play_date))
    return cast("DailyRoundState", entry) if isinstance(entry, dict) else None


def save_round(session: dict[str, Any], play_date: date, state: DailyRoundState) -> None:
    rounds = dict(session.get(SESSION_KEY, {}))
    rounds[round_key(play_date)] = state
    session[SESSION_KEY] = rounds
    session.modified = True  # type: ignore[attr-defined]


def new_round_from_quote(quote) -> DailyRoundState:
    return {
        "status": "in_progress",
        "shown_quote_ids": [quote.pk],
        "wrong_count": 0,
        "answer_episode_id": quote.episode_id,
        "guess_history": [],
    }


def is_terminal(state: DailyRoundState | None) -> bool:
    if state is None:
        return False
    return state["status"] in ("won", "lost")


def apply_guess(
    state: DailyRoundState,
    episode_id: int,
) -> tuple[DailyRoundState, Literal["duplicate", "won", "lost", "continue"]]:
    """Apply an episode guess to state. Returns new state + outcome."""
    for entry in state["guess_history"]:
        if entry["guess_type"] == "episode" and entry["episode_id"] == episode_id:
            return state, "duplicate"

    if episode_id == state["answer_episode_id"]:
        new_history_won = cast(
            "list[GuessHistoryEntry]",
            [*state["guess_history"], {"guess_type": "episode", "episode_id": episode_id}],
        )
        new_state: DailyRoundState = {
            **state,
            "status": "won",
            "share_row": format_share_row(won=True, wrong_count=state["wrong_count"]),
            "guess_history": new_history_won,
        }
        return new_state, "won"

    new_wrong_count = state["wrong_count"] + 1
    new_history = cast(
        "list[GuessHistoryEntry]",
        [*state["guess_history"], {"guess_type": "episode", "episode_id": episode_id}],
    )

    if new_wrong_count >= MAX_ATTEMPTS:
        new_state = {
            **state,
            "status": "lost",
            "wrong_count": MAX_ATTEMPTS,
            "share_row": format_share_row(won=False, wrong_count=MAX_ATTEMPTS),
            "guess_history": new_history,
        }
        return new_state, "lost"

    new_state = {
        **state,
        "wrong_count": new_wrong_count,
        "guess_history": new_history,
    }
    return new_state, "continue"


def apply_skip(
    state: DailyRoundState,
) -> tuple[DailyRoundState, Literal["lost", "continue"]]:
    """Apply a skip to state. Returns new state + outcome."""
    new_wrong_count = state["wrong_count"] + 1
    new_history = cast(
        "list[GuessHistoryEntry]",
        [*state["guess_history"], {"guess_type": "skip", "episode_id": None}],
    )

    if new_wrong_count >= MAX_ATTEMPTS:
        new_state: DailyRoundState = {
            **state,
            "status": "lost",
            "wrong_count": MAX_ATTEMPTS,
            "share_row": format_share_row(won=False, wrong_count=MAX_ATTEMPTS),
            "guess_history": new_history,
        }
        return new_state, "lost"

    new_state = {
        **state,
        "wrong_count": new_wrong_count,
        "guess_history": new_history,
    }
    return new_state, "continue"


def advance_hint(
    state: DailyRoundState,
    next_quote_pk: int,
) -> DailyRoundState:
    """Append next_quote_pk to shown_quote_ids."""
    return {
        **state,
        "shown_quote_ids": [*state["shown_quote_ids"], next_quote_pk],
    }
