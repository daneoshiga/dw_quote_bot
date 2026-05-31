"""Session payload for one calendar day's multi-guess round."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Literal, Protocol, TypedDict

from django.contrib.sessions.backends.base import SessionBase

from game.game_logic import format_share_row


class Outcome(StrEnum):
    DUPLICATE = "duplicate"
    WON = "won"
    LOST = "lost"
    CONTINUE = "continue"


AttemptOutcome = Literal[Outcome.LOST, Outcome.CONTINUE]
Status = Literal["in_progress", "won", "lost"]


class AnchorQuote(Protocol):
    pk: int
    episode_id: int


class EpisodeGuess(TypedDict):
    guess_type: Literal["episode"]
    episode_id: int


class SkipGuess(TypedDict):
    guess_type: Literal["skip"]


GuessHistoryEntry = EpisodeGuess | SkipGuess


class DailyRoundState(TypedDict):
    status: Status
    shown_quote_ids: list[int]
    wrong_count: int
    answer_episode_id: int
    share_row: str
    guess_history: list[GuessHistoryEntry]


SESSION_KEY = "daily_rounds"
MAX_ATTEMPTS = 6


def round_key(play_date: date) -> str:
    return play_date.isoformat()


def get_round(session: SessionBase, play_date: date) -> DailyRoundState | None:
    raw = session.get(SESSION_KEY, {})
    entry = raw.get(round_key(play_date))
    if not isinstance(entry, dict):
        return None
    return entry  # type: ignore[return-value]


def save_round(session: SessionBase, play_date: date, state: DailyRoundState) -> None:
    state.setdefault("share_row", "")  # Backfill legacy sessions on next write.
    rounds = dict(session.get(SESSION_KEY, {}))
    rounds[round_key(play_date)] = state
    session[SESSION_KEY] = rounds
    session.modified = True


def new_round_from_quote(quote: AnchorQuote) -> DailyRoundState:
    return {
        "status": "in_progress",
        "shown_quote_ids": [quote.pk],
        "wrong_count": 0,
        "answer_episode_id": quote.episode_id,
        "share_row": "",
        "guess_history": [],
    }


def is_terminal(state: DailyRoundState) -> bool:
    return state["status"] in ("won", "lost")


def is_stale_for_anchor(state: DailyRoundState, anchor_quote: AnchorQuote) -> bool:
    """True if state was started against a different anchor than today's quote."""
    return (
        state["answer_episode_id"] != anchor_quote.episode_id
        or state["shown_quote_ids"][0] != anchor_quote.pk
    )


def _record_attempt(
    state: DailyRoundState,
    entry: GuessHistoryEntry,
) -> tuple[DailyRoundState, AttemptOutcome]:
    new_wrong = state["wrong_count"] + 1
    history = [*state["guess_history"], entry]
    if new_wrong >= MAX_ATTEMPTS:
        return {
            **state,
            "status": "lost",
            "wrong_count": MAX_ATTEMPTS,
            "share_row": format_share_row(won=False, wrong_count=MAX_ATTEMPTS),
            "guess_history": history,
        }, Outcome.LOST
    return {
        **state,
        "wrong_count": new_wrong,
        "guess_history": history,
    }, Outcome.CONTINUE


def apply_guess(
    state: DailyRoundState,
    episode_id: int,
) -> tuple[DailyRoundState, Outcome]:
    """Apply an episode guess to state. Returns new state + outcome."""
    for prev in state["guess_history"]:
        if prev["guess_type"] == "episode" and prev["episode_id"] == episode_id:
            return state, Outcome.DUPLICATE

    entry: EpisodeGuess = {"guess_type": "episode", "episode_id": episode_id}

    if episode_id == state["answer_episode_id"]:
        return {
            **state,
            "status": "won",
            "share_row": format_share_row(won=True, wrong_count=state["wrong_count"]),
            "guess_history": [*state["guess_history"], entry],
        }, Outcome.WON

    return _record_attempt(state, entry)


def apply_skip(state: DailyRoundState) -> tuple[DailyRoundState, AttemptOutcome]:
    """Apply a skip to state. Returns new state + outcome."""
    entry: SkipGuess = {"guess_type": "skip"}
    return _record_attempt(state, entry)


def advance_hint(
    state: DailyRoundState,
    next_quote_pk: int,
) -> DailyRoundState:
    """Append next_quote_pk to shown_quote_ids."""
    return {
        **state,
        "shown_quote_ids": [*state["shown_quote_ids"], next_quote_pk],
    }
