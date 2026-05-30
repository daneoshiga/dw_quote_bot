"""Pure unit tests for round_session transition functions (no DB, no Django)."""

from game.round_session import MAX_ATTEMPTS, DailyRoundState, advance_hint, apply_guess, apply_skip


def make_state(
    *,
    status: str = "in_progress",
    shown_quote_ids: list[int] | None = None,
    wrong_count: int = 0,
    answer_episode_id: int = 10,
    guess_history: list | None = None,
) -> DailyRoundState:
    return {
        "status": status,
        "shown_quote_ids": shown_quote_ids if shown_quote_ids is not None else [100],
        "wrong_count": wrong_count,
        "answer_episode_id": answer_episode_id,
        "guess_history": guess_history if guess_history is not None else [],
    }


# --- apply_guess ---


def test_apply_guess_duplicate_detection():
    state = make_state(
        guess_history=[{"guess_type": "episode", "episode_id": 5}],
    )
    new_state, outcome = apply_guess(state, 5)
    assert outcome == "duplicate"
    assert new_state is state  # unchanged reference


def test_apply_guess_win():
    state = make_state(answer_episode_id=10, wrong_count=2)
    new_state, outcome = apply_guess(state, 10)
    assert outcome == "won"
    assert new_state["status"] == "won"
    assert "share_row" in new_state
    assert new_state["share_row"]
    history = new_state["guess_history"]
    assert history[-1] == {"guess_type": "episode", "episode_id": 10}


def test_apply_guess_continue():
    state = make_state(answer_episode_id=10, wrong_count=0)
    new_state, outcome = apply_guess(state, 99)
    assert outcome == "continue"
    assert new_state["wrong_count"] == 1
    assert new_state["status"] == "in_progress"
    assert new_state["shown_quote_ids"] == state["shown_quote_ids"]
    assert new_state["guess_history"][-1] == {"guess_type": "episode", "episode_id": 99}


def test_apply_guess_lost_at_last_attempt():
    state = make_state(answer_episode_id=10, wrong_count=MAX_ATTEMPTS - 1)
    new_state, outcome = apply_guess(state, 99)
    assert outcome == "lost"
    assert new_state["status"] == "lost"
    assert new_state["wrong_count"] == MAX_ATTEMPTS
    assert "share_row" in new_state
    assert new_state["share_row"]


# --- apply_skip ---


def test_apply_skip_continue():
    state = make_state(wrong_count=0)
    new_state, outcome = apply_skip(state)
    assert outcome == "continue"
    assert new_state["wrong_count"] == 1
    assert new_state["status"] == "in_progress"
    assert new_state["guess_history"][-1] == {"guess_type": "skip", "episode_id": None}


def test_apply_skip_lost_at_last_attempt():
    state = make_state(wrong_count=MAX_ATTEMPTS - 1)
    new_state, outcome = apply_skip(state)
    assert outcome == "lost"
    assert new_state["status"] == "lost"
    assert new_state["wrong_count"] == MAX_ATTEMPTS
    assert "share_row" in new_state
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
