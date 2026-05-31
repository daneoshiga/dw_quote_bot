"""Pure, testable rules for the daily quote game (no Django imports)."""

from __future__ import annotations

import hashlib
import random
from collections.abc import Callable
from datetime import date


class InvalidGameDate(ValueError):
    """Path segment is not a valid calendar YYYY-MM-DD."""


def parse_game_date(s: str) -> date:
    """Parse YYYY-MM-DD; raise InvalidGameDate if malformed or not a real calendar day."""
    if not isinstance(s, str) or len(s) != 10:
        raise InvalidGameDate("expected YYYY-MM-DD")
    try:
        return date.fromisoformat(s)
    except ValueError as exc:
        raise InvalidGameDate(str(exc)) from exc


def rng_for_date(play_date: date, branch: str = "") -> random.Random:
    """Return a deterministic RNG for (calendar day, branch label)."""
    payload = play_date.isoformat().encode("utf-8")
    branch_b = branch.encode("utf-8") if branch else b""
    digest = hashlib.sha256(payload + b"|" + branch_b).digest()
    seed = int.from_bytes(digest[:8], "big")
    return random.Random(seed)


def quote_pk_for_day(play_date: date, max_pk: int, game_seed: str = "") -> int:
    """Pick a candidate primary key in [1, max_pk] for this day (may need gap retry elsewhere)."""
    if max_pk < 1:
        raise ValueError("max_pk must be at least 1")
    rng = rng_for_date(play_date, game_seed + ":quote")
    return rng.randint(1, max_pk)


def resolve_quote_pk(
    play_date: date,
    max_pk: int,
    exists: Callable[[int], bool],
    game_seed: str = "",
    max_attempts: int = 64,
) -> int:
    """Deterministic quote pk: try successive random draws until exists(pk)."""
    rng = rng_for_date(play_date, game_seed + ":quote")
    for _ in range(max_attempts):
        pk = rng.randint(1, max_pk)
        if exists(pk):
            return pk
    raise LookupError("no existing quote pk found within attempt limit")


RED = "🟥"
GREEN = "🟩"
BLACK = "⬛"

SHARE_GAME_TITLE = "Doctor Who Daily Quote"


def format_share_clipboard(
    *, game_title: str, play_date: date, emoji_row: str, game_url: str
) -> str:
    """Multiline text for social paste: headline with date, emoji result row, link to the day."""
    headline = f"{game_title} #{play_date.isoformat()}"
    return f"{headline}\n{emoji_row}\n{game_url}"


def format_share_row(*, won: bool, wrong_count: int, max_attempts: int = 6) -> str:
    """
    Space-separated emoji row for sharing: wrong guesses, then green if won, then unused slots.

    wrong_count: number of incorrect guesses. On a win, the successful guess is one green after those reds.
    On a loss, wrong_count must equal max_attempts (all reds).
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    if won:
        if not 0 <= wrong_count < max_attempts:
            raise ValueError("wrong_count must be in [0, max_attempts) when won")
        reds = wrong_count
        greens = 1
        blacks = max_attempts - wrong_count - 1
    else:
        if wrong_count != max_attempts:
            raise ValueError("wrong_count must equal max_attempts when lost")
        reds = max_attempts
        greens = 0
        blacks = 0
    parts = [RED] * reds + [GREEN] * greens + [BLACK] * blacks
    return " ".join(parts)


def pick_next_quote_pk(
    candidate_pks: list[int],
    shown: set[int],
    rng: random.Random,
) -> int | None:
    """Pick a quote pk from candidates not in shown; None if no unseen candidate."""
    available = sorted(pk for pk in candidate_pks if pk not in shown)
    if not available:
        return None
    return rng.choice(available)


def format_progress_row(*, wrong_count: int, max_attempts: int = 6) -> str:
    """While playing: one red per wrong guess, black for remaining slots."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    if not 0 <= wrong_count <= max_attempts:
        raise ValueError("wrong_count must be in [0, max_attempts]")
    return " ".join([RED] * wrong_count + [BLACK] * (max_attempts - wrong_count))
