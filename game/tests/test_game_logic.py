"""Unit tests for game_logic (no database)."""

from datetime import date

import pytest

from game.game_logic import (
    InvalidGameDate,
    build_mcq_episode_ids,
    mcq_rng_for_day,
    parse_game_date,
    quote_pk_for_day,
    resolve_quote_pk,
    rng_for_date,
)


def test_parse_game_date_accepts_valid():
    assert parse_game_date("2025-01-15") == date(2025, 1, 15)


@pytest.mark.parametrize(
    "bad",
    ["", "2025-1-15", "25-01-15", "2025-02-30", "not-a-date", "2025-13-01"],
)
def test_parse_game_date_rejects_invalid(bad):
    with pytest.raises(InvalidGameDate):
        parse_game_date(bad)


def test_rng_for_date_stable_for_same_day_and_branch():
    d = date(2024, 6, 1)
    a = rng_for_date(d, "x")
    b = rng_for_date(d, "x")
    assert a.randint(0, 10**9) == b.randint(0, 10**9)


def test_rng_branch_changes_sequence():
    d = date(2024, 6, 1)
    assert rng_for_date(d, "a").random() != rng_for_date(d, "b").random()


def test_quote_pk_for_day_deterministic():
    d = date(2023, 12, 25)
    assert quote_pk_for_day(d, 1000, "") == quote_pk_for_day(d, 1000, "")
    assert quote_pk_for_day(d, 1000, "salt") == quote_pk_for_day(d, 1000, "salt")


def test_quote_pk_for_day_changes_with_game_seed():
    d = date(2023, 12, 25)
    assert quote_pk_for_day(d, 100_000, "a") != quote_pk_for_day(d, 100_000, "b")


def test_quote_pk_for_day_bounds():
    d = date(2022, 3, 3)
    for _ in range(50):
        pk = quote_pk_for_day(d, 10, "")
        assert 1 <= pk <= 10


def test_quote_pk_for_day_requires_positive_max():
    with pytest.raises(ValueError, match="max_pk"):
        quote_pk_for_day(date(2020, 1, 1), 0, "")


def test_resolve_quote_pk_skips_gaps():
    d = date(2021, 7, 7)

    def exists(pk: int) -> bool:
        return pk in {3, 7}

    assert resolve_quote_pk(d, 10, exists, max_attempts=100) in {3, 7}


def test_resolve_quote_pk_deterministic_with_same_exists():
    d = date(2021, 7, 7)
    existing = {2, 5, 9}

    def exists(pk: int) -> bool:
        return pk in existing

    first = resolve_quote_pk(d, 20, exists)
    second = resolve_quote_pk(d, 20, exists)
    assert first == second
    assert first in existing


def test_resolve_quote_pk_raises_when_impossible():
    d = date(2021, 7, 7)

    def exists(_pk: int) -> bool:
        return False

    with pytest.raises(LookupError):
        resolve_quote_pk(d, 5, exists, max_attempts=3)


def test_build_mcq_episode_ids_size_and_membership():
    rng = rng_for_date(date(2019, 1, 1), "mcq-test")
    pool = [10, 20, 30, 40]
    out = build_mcq_episode_ids(30, pool, k=2, rng=rng)
    assert len(out) == 3
    assert len(set(out)) == 3
    assert 30 in out
    assert all(x in pool for x in out)


def test_build_mcq_episode_ids_deterministic():
    d = date(2018, 5, 5)
    rng = mcq_rng_for_day(d, "")
    pool = list(range(1, 50))
    first = build_mcq_episode_ids(7, pool, k=3, rng=rng)
    rng2 = mcq_rng_for_day(d, "")
    second = build_mcq_episode_ids(7, pool, k=3, rng=rng2)
    assert first == second


def test_build_mcq_episode_ids_not_enough_distractors():
    rng = rng_for_date(date(2017, 1, 1), "x")
    with pytest.raises(ValueError, match="not enough"):
        build_mcq_episode_ids(1, [1], k=1, rng=rng)
