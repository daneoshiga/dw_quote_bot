"""Pure unit tests for round_session transition functions (no DB, no Django)."""

from types import SimpleNamespace

from game.round_session import (
    MAX_ATTEMPTS,
    DailyRoundState,
    Outcome,
    advance_hint,
    apply_guess,
    apply_skip,
    is_stale_for_anchor,
)


def make_state(
    *,
    status: str = "in_progress",
    shown_quote_ids: list[int] | None = None,
    wrong_count: int = 0,
    answer_episode_id: int = 10,
    share_row: str = "",
    guess_history: list | None = None,
) -> DailyRoundState:
    return {
        "status": status,
        "shown_quote_ids": shown_quote_ids if shown_quote_ids is not None else [100],
        "wrong_count": wrong_count,
        "answer_episode_id": answer_episode_id,
        "share_row": share_row,
        "guess_history": guess_history if guess_history is not None else [],
    }


# --- apply_guess ---


def test_apply_guess_duplicate_detection():
    state = make_state(
        guess_history=[{"guess_type": "episode", "episode_id": 5}],
    )
    new_state, outcome = apply_guess(state, 5)
    assert outcome is Outcome.DUPLICATE
    assert new_state is state  # unchanged reference


def test_apply_guess_duplicate_ignores_skip_entries():
    state = make_state(
        guess_history=[{"guess_type": "skip"}],
    )
    new_state, outcome = apply_guess(state, 99)
    assert outcome is Outcome.CONTINUE
    assert new_state["wrong_count"] == 1


def test_apply_guess_win():
    state = make_state(answer_episode_id=10, wrong_count=2)
    new_state, outcome = apply_guess(state, 10)
    assert outcome is Outcome.WON
    assert new_state["status"] == "won"
    assert new_state["share_row"]
    history = new_state["guess_history"]
    assert history[-1] == {"guess_type": "episode", "episode_id": 10}


def test_apply_guess_win_on_last_attempt():
    state = make_state(answer_episode_id=10, wrong_count=MAX_ATTEMPTS - 1)
    new_state, outcome = apply_guess(state, 10)
    assert outcome is Outcome.WON
    assert new_state["status"] == "won"
    assert new_state["wrong_count"] == MAX_ATTEMPTS - 1
    assert new_state["share_row"]


def test_apply_guess_continue():
    state = make_state(answer_episode_id=10, wrong_count=0)
    new_state, outcome = apply_guess(state, 99)
    assert outcome is Outcome.CONTINUE
    assert new_state["wrong_count"] == 1
    assert new_state["status"] == "in_progress"
    assert new_state["shown_quote_ids"] == state["shown_quote_ids"]
    assert new_state["guess_history"][-1] == {"guess_type": "episode", "episode_id": 99}


def test_apply_guess_lost_at_last_attempt():
    state = make_state(answer_episode_id=10, wrong_count=MAX_ATTEMPTS - 1)
    new_state, outcome = apply_guess(state, 99)
    assert outcome is Outcome.LOST
    assert new_state["status"] == "lost"
    assert new_state["wrong_count"] == MAX_ATTEMPTS
    assert new_state["share_row"]


# --- apply_skip ---


def test_apply_skip_continue():
    state = make_state(wrong_count=0)
    new_state, outcome = apply_skip(state)
    assert outcome is Outcome.CONTINUE
    assert new_state["wrong_count"] == 1
    assert new_state["status"] == "in_progress"
    assert new_state["guess_history"][-1] == {"guess_type": "skip"}


def test_apply_skip_lost_at_last_attempt():
    state = make_state(wrong_count=MAX_ATTEMPTS - 1)
    new_state, outcome = apply_skip(state)
    assert outcome is Outcome.LOST
    assert new_state["status"] == "lost"
    assert new_state["wrong_count"] == MAX_ATTEMPTS
    assert new_state["share_row"]


# --- advance_hint ---


def test_advance_hint_appends_pk():
    state = make_state(shown_quote_ids=[100, 200])
    new_state = advance_hint(state, 300)
    assert new_state["shown_quote_ids"] == [100, 200, 300]
    # other fields unchanged
    assert new_state["status"] == state["status"]
    assert new_state["wrong_count"] == state["wrong_count"]
    assert new_state["answer_episode_id"] == state["answer_episode_id"]
    assert new_state["guess_history"] == state["guess_history"]


# --- is_stale_for_anchor ---


def test_is_stale_for_anchor_fresh():
    state = make_state(answer_episode_id=10, shown_quote_ids=[100])
    anchor = SimpleNamespace(pk=100, episode_id=10)
    assert is_stale_for_anchor(state, anchor) is False


def test_is_stale_for_anchor_different_episode():
    state = make_state(answer_episode_id=10, shown_quote_ids=[100])
    anchor = SimpleNamespace(pk=100, episode_id=11)
    assert is_stale_for_anchor(state, anchor) is True


def test_is_stale_for_anchor_different_first_quote():
    state = make_state(answer_episode_id=10, shown_quote_ids=[100])
    anchor = SimpleNamespace(pk=101, episode_id=10)
    assert is_stale_for_anchor(state, anchor) is True
