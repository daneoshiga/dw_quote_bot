"""Unit tests for game_logic (no database)."""

from datetime import date

import pytest

from game.game_logic import (
    SHARE_GAME_TITLE,
    InvalidGameDate,
    format_progress_row,
    format_share_clipboard,
    format_share_row,
    parse_game_date,
    pick_next_quote_pk,
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


@pytest.mark.parametrize(
    ("won", "wrong_count", "expected"),
    [
        (True, 4, "🟥 🟥 🟥 🟥 🟩 ⬛"),
        (True, 0, "🟩 ⬛ ⬛ ⬛ ⬛ ⬛"),
        (True, 5, "🟥 🟥 🟥 🟥 🟥 🟩"),
        (False, 6, "🟥 🟥 🟥 🟥 🟥 🟥"),
    ],
)
def test_format_share_row(won, wrong_count, expected):
    assert format_share_row(won=won, wrong_count=wrong_count) == expected


def test_format_share_row_invalid_win_wrong_count():
    with pytest.raises(ValueError, match="wrong_count"):
        format_share_row(won=True, wrong_count=6)


def test_format_share_clipboard_loss_emoji_and_url():
    d = date(2026, 3, 25)
    emoji = format_share_row(won=False, wrong_count=6)
    url = "https://example.com/play/2026-03-25/"
    assert (
        format_share_clipboard(
            game_title=SHARE_GAME_TITLE,
            play_date=d,
            emoji_row=emoji,
            game_url=url,
        )
        == "Doctor Who Daily Quote #2026-03-25\n"
        f"{emoji}\n"
        f"{url}"
    )


def test_format_share_clipboard_win_emoji_and_url():
    d = date(2025, 1, 1)
    emoji = format_share_row(won=True, wrong_count=0)
    url = "http://testserver/play/2025-01-01/"
    assert (
        format_share_clipboard(
            game_title=SHARE_GAME_TITLE,
            play_date=d,
            emoji_row=emoji,
            game_url=url,
        )
        == "Doctor Who Daily Quote #2025-01-01\n"
        f"{emoji}\n"
        f"{url}"
    )


def test_format_share_row_invalid_loss_wrong_count():
    with pytest.raises(ValueError, match="wrong_count"):
        format_share_row(won=False, wrong_count=5)


def test_pick_next_quote_pk_excludes_shown():
    rng = rng_for_date(date(2020, 1, 1), "hint")
    assert pick_next_quote_pk([3, 1, 2], {1}, rng) in {2, 3}


def test_pick_next_quote_pk_deterministic():
    d = date(2020, 6, 15)
    rng = rng_for_date(d, "hint-test")
    first = pick_next_quote_pk([10, 20, 30], set(), rng)
    rng2 = rng_for_date(d, "hint-test")
    second = pick_next_quote_pk([10, 20, 30], set(), rng2)
    assert first == second


def test_pick_next_quote_pk_none_when_all_shown():
    rng = rng_for_date(date(2019, 3, 3), "x")
    assert pick_next_quote_pk([5], {5}, rng) is None


def test_pick_next_quote_pk_empty_candidates():
    rng = rng_for_date(date(2019, 3, 3), "x")
    assert pick_next_quote_pk([], set(), rng) is None


def test_format_progress_row():
    assert format_progress_row(wrong_count=2) == "🟥 🟥 ⬛ ⬛ ⬛ ⬛"
    assert format_progress_row(wrong_count=0) == "⬛ ⬛ ⬛ ⬛ ⬛ ⬛"


def test_format_progress_row_invalid():
    with pytest.raises(ValueError):
        format_progress_row(wrong_count=7)
