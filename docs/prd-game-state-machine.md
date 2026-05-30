# PRD: Game State Machine Refactor

## Problem

`views.py::daily_answer` owns all game state transition logic — 150 lines of manual dict construction for win/loss/continue/duplicate branches. `round_session.py` exists as a seam but is hollow (only stores/retrieves state). State transition rules are untestable without a Django request and database.

Secondary issues:
- `next_hint_quote_pk` leaks an internal seeding detail (`hint_attempt`) that callers must compute themselves from `wrong_count`
- `DailyRoundState` and `GuessHistoryEntry` are `total=False`, causing defensive `.get()` calls everywhere that mask bugs; mypy sees all fields as optional

## Goals

- Move all game state transition logic into `round_session.py` (pure Python, no Django imports)
- Make game rules unit-testable without DB or HTTP
- Remove the `hint_attempt` footgun from `next_hint_quote_pk`
- Make TypedDicts honest about which fields are required

## Non-Goals

- Moving `_past_guesses` DB query out of views (separate candidate, not addressed here)
- Moving the `daily_play` staleness check out of views
- Any UI or template changes

---

## Changes

### 1. `game/round_session.py`

**Fix TypedDicts:**

```python
from typing import NotRequired

class GuessHistoryEntry(TypedDict):           # total=True (default)
    guess_type: str                            # "episode" | "skip"
    episode_id: int | None

class DailyRoundState(TypedDict):             # total=True (default)
    status: str                                # "in_progress" | "won" | "lost"
    shown_quote_ids: list[int]
    wrong_count: int
    answer_episode_id: int
    share_row: NotRequired[str]               # only set on terminal states
    guess_history: list[GuessHistoryEntry]
```

**Add three transition functions** (import `format_share_row` from `game_logic`):

```python
def apply_guess(
    state: DailyRoundState,
    episode_id: int,
) -> tuple[DailyRoundState, Literal["duplicate", "won", "lost", "continue"]]:
    """
    Apply an episode guess to state. Returns new state + outcome.
    - "duplicate": episode already guessed; state unchanged
    - "won": correct guess; terminal state with share_row set
    - "lost": wrong guess and out of attempts; terminal state with share_row set
    - "continue": wrong guess with attempts remaining; wrong_count incremented,
                  guess appended to history, shown_quote_ids NOT yet updated
                  (caller must call advance_hint to append next quote pk)
    """

def apply_skip(
    state: DailyRoundState,
) -> tuple[DailyRoundState, Literal["lost", "continue"]]:
    """
    Apply a skip to state. Returns new state + outcome.
    - "lost": out of attempts; terminal state with share_row set
    - "continue": attempts remaining; wrong_count incremented,
                  skip appended to history, shown_quote_ids NOT yet updated
    """

def advance_hint(
    state: DailyRoundState,
    next_quote_pk: int,
) -> DailyRoundState:
    """
    Append next_quote_pk to shown_quote_ids. Called by views only on "continue".
    """
```

### 2. `game/services.py`

Drop `hint_attempt` parameter from `next_hint_quote_pk`; derive internally:

```python
def next_hint_quote_pk(
    play_date: date,
    episode_id: int,
    shown_quote_ids: list[int],
    # hint_attempt removed — derived as len(shown_quote_ids)
) -> int | None:
    hint_attempt = len(shown_quote_ids)
    ...
```

### 3. `game/views.py`

`daily_answer` shrinks from ~150 lines to ~60. Replace manual state-dict branches with:

```python
if skip:
    new_state, outcome = apply_skip(state)
else:
    new_state, outcome = apply_guess(state, episode_id)

if outcome == "continue":
    next_pk = next_hint_quote_pk(play_date, int(new_state["answer_episode_id"]), list(new_state["shown_quote_ids"]))
    new_state = advance_hint(new_state, next_pk or new_state["shown_quote_ids"][-1])

save_round(request.session, play_date, new_state)
# render based on outcome
```

Update all `state.get("field", default)` → `state["field"]` for required fields. Update `entry.get("guess_type")` → `entry["guess_type"]` in `_past_guesses`.

### 4. `game/tests/test_round_session.py` (new)

Pure unit tests for `apply_guess`, `apply_skip`, `advance_hint`. No DB, no request. Cover:
- `apply_guess` → duplicate detection
- `apply_guess` → win (correct episode)
- `apply_guess` → continue (wrong, attempts remain)
- `apply_guess` → lost (wrong, last attempt)
- `apply_skip` → continue
- `apply_skip` → lost (last attempt)
- `advance_hint` → appends pk correctly

---

## Invariants to Preserve

- `hint_attempt` seeding: after refactor, `len(shown_quote_ids)` at call time equals the old `wrong_count` (post-increment, pre-advance). Must verify RNG seeds are identical before/after for existing games.
- `repeat_hint` flag: views currently set `repeat_hint = next_pk == prev_last` for the template. Must preserve this after advance_hint.
- Non-HTMX paths: views redirect to `daily_play` on non-HTMX requests; these are unchanged.
