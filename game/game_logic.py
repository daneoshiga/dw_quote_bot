"""Pure, testable rules for the daily quote game (no Django imports)."""

from __future__ import annotations

import hashlib
import random
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
    rng = rng_for_date(play_date, f"{game_seed}:quote")
    return rng.randint(1, max_pk)


def resolve_quote_pk(
    play_date: date,
    max_pk: int,
    exists,
    game_seed: str = "",
    max_attempts: int = 64,
) -> int:
    """
    Deterministic quote pk: try successive random draws until exists(pk).

    exists: callable taking int -> bool
    """
    rng = rng_for_date(play_date, f"{game_seed}:quote")
    for _ in range(max_attempts):
        pk = rng.randint(1, max_pk)
        if exists(pk):
            return pk
    raise LookupError("no existing quote pk found within attempt limit")


def build_mcq_episode_ids(
    correct_episode_id: int,
    all_episode_ids: list[int],
    k: int,
    rng: random.Random,
) -> list[int]:
    """Return shuffled list of (k distractors + correct), all distinct."""
    wrong = [eid for eid in all_episode_ids if eid != correct_episode_id]
    if len(wrong) < k:
        raise ValueError("not enough episodes for distractors")
    distractors = rng.sample(wrong, k)
    options = distractors + [correct_episode_id]
    rng.shuffle(options)
    return options


def mcq_rng_for_day(play_date: date, game_seed: str = "") -> random.Random:
    """RNG branch used only for MCQ construction for this day."""
    return rng_for_date(play_date, f"{game_seed}:mcq")
