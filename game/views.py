import functools
from dataclasses import dataclass
from datetime import date
from typing import assert_never

from django.conf import settings
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from game.game_clock import today_in_game_tz
from game.game_logic import (
    SHARE_GAME_TITLE,
    format_progress_row,
    format_share_clipboard,
)
from game.models import Episode, Quote
from game.round_session import (
    MAX_ATTEMPTS,
    DailyRoundState,
    Outcome,
    advance_hint,
    apply_guess,
    apply_skip,
    get_round,
    is_stale_for_anchor,
    is_terminal,
    new_round_from_quote,
    save_round,
)
from game.services import (
    episode_by_pk,
    episode_choice_label,
    episode_search_results,
    next_hint_quote_pk,
    quote_for_play_date,
    quotes_for_pks_in_order,
)


def reject_future_play_date(view):
    @functools.wraps(view)
    def wrapper(request, play_date, *args, **kwargs):
        today = today_in_game_tz()
        if play_date > today:
            return redirect("daily_play", play_date=today)
        return view(request, play_date, *args, **kwargs)

    return wrapper


@dataclass(frozen=True)
class GuessForm:
    quote_id: int
    episode_id: int


@dataclass(frozen=True)
class SkipForm:
    quote_id: int


AnswerForm = GuessForm | SkipForm


class _NoQuotesAvailable(Exception):
    """Raised when no anchor quote can be fetched from the DB."""


def _parse_answer_form(request) -> AnswerForm | None:
    try:
        quote_id = int(request.POST.get("quote_id", ""))
    except (TypeError, ValueError):
        return None
    if request.POST.get("skip") == "1":
        return SkipForm(quote_id=quote_id)
    try:
        episode_id = int(request.POST.get("episode_id", ""))
    except (TypeError, ValueError):
        return None
    return GuessForm(quote_id=quote_id, episode_id=episode_id)


def _episode_label(episode: Episode | None) -> str:
    return episode_choice_label(episode) if episode else "Unknown episode"


def _share_text(request, play_date, share_row: str) -> str:
    path = reverse("daily_play", kwargs={"play_date": play_date})
    url = request.build_absolute_uri(path)
    return format_share_clipboard(
        game_title=SHARE_GAME_TITLE,
        play_date=play_date,
        emoji_row=share_row,
        game_url=url,
    )


def _past_guesses(state: DailyRoundState) -> list[str]:
    entries = state["guess_history"]
    if not entries:
        return []

    episode_ids = [
        entry["episode_id"] for entry in entries if entry["guess_type"] == "episode"
    ]
    episodes = Episode.objects.in_bulk(episode_ids) if episode_ids else {}

    past = []
    for entry in entries:
        if entry["guess_type"] == "skip":
            past.append("Skipped")
        else:
            past.append(_episode_label(episodes.get(entry["episode_id"])))
    return past


def _resolve_shown_quotes(state: DailyRoundState) -> list[Quote] | None:
    """Fetch quotes for all shown pks; None if any are missing from the DB."""
    pks = state["shown_quote_ids"]
    shown = quotes_for_pks_in_order(pks)
    return shown if len(shown) == len(pks) else None


def _start_fresh_round(
    request, play_date, anchor: Quote
) -> tuple[DailyRoundState, list[Quote]]:
    state = new_round_from_quote(anchor)
    save_round(request.session, play_date, state)
    return state, [anchor]


def _ensure_valid_round(request, play_date) -> tuple[DailyRoundState, list[Quote]]:
    """Return a renderable (state, shown_quotes) pair.

    Creates or re-anchors the session round when needed. Raises
    _NoQuotesAvailable when the DB has no quotes to anchor on.
    """
    state = get_round(request.session, play_date)

    if state is not None and is_terminal(state):
        return state, quotes_for_pks_in_order(state["shown_quote_ids"])

    try:
        anchor = quote_for_play_date(play_date)
    except LookupError as exc:
        raise _NoQuotesAvailable() from exc

    if state is None or is_stale_for_anchor(state, anchor):
        return _start_fresh_round(request, play_date, anchor)

    shown = _resolve_shown_quotes(state)
    if shown is None:
        return _start_fresh_round(request, play_date, anchor)
    return state, shown


def _build_in_progress_ctx(
    state: DailyRoundState,
    shown_quotes: list[Quote],
    *,
    warning: str | None = None,
    repeat_hint: bool = False,
) -> dict:
    wrong_count = state["wrong_count"]
    ctx: dict = {
        "shown_quotes": shown_quotes,
        "current_quote": shown_quotes[-1],
        "wrong_count": wrong_count,
        "progress_row": format_progress_row(
            wrong_count=wrong_count, max_attempts=MAX_ATTEMPTS
        ),
        "guess_number": wrong_count + 1,
        "max_attempts": MAX_ATTEMPTS,
        "past_guesses": _past_guesses(state),
        "repeat_hint": repeat_hint,
    }
    if warning is not None:
        ctx["warning_message"] = warning
    return ctx


def _build_terminal_ctx(
    request,
    play_date: date,
    state: DailyRoundState,
    shown_quotes: list[Quote],
    answer_episode: Episode | None,
) -> dict:
    return {
        "shown_quotes": shown_quotes,
        "share_text": _share_text(request, play_date, state["share_row"]),
        "episode_title": _episode_label(answer_episode),
        "outcome": state["status"],
        "past_guesses": _past_guesses(state),
    }


def _respond(request, play_date, template: str, ctx: dict):
    ctx["play_date"] = play_date
    if request.htmx:
        return render(request, template, ctx)
    return redirect("daily_play", play_date=play_date)


def _render_in_progress(
    request, play_date, state: DailyRoundState, *, warning=None, repeat_hint=False
):
    shown = _resolve_shown_quotes(state)
    if shown is None:
        return HttpResponseBadRequest("quote missing")
    ctx = _build_in_progress_ctx(state, shown, warning=warning, repeat_hint=repeat_hint)
    return _respond(request, play_date, "game/partials/daily-round.html", ctx)


def _render_terminal(
    request,
    play_date: date,
    state: DailyRoundState,
    *,
    answer_episode: Episode | None = None,
):
    shown = quotes_for_pks_in_order(state["shown_quote_ids"])
    if answer_episode is None:
        answer_episode = episode_by_pk(state["answer_episode_id"])
    ctx = _build_terminal_ctx(request, play_date, state, shown, answer_episode)
    return _respond(request, play_date, "game/partials/daily-complete.html", ctx)


@require_GET
def today_redirect(request):
    d = today_in_game_tz()
    return redirect("daily_play", play_date=d)


@require_http_methods(["GET", "HEAD"])
@reject_future_play_date
def daily_play(request, play_date):
    try:
        state, shown = _ensure_valid_round(request, play_date)
    except _NoQuotesAvailable:
        return render(
            request, "game/no-quotes.html", {"play_date": play_date}, status=503
        )

    terminal = is_terminal(state)
    context: dict = {
        "play_date": play_date,
        "game_timezone": settings.GAME_TIMEZONE,
        "terminal": terminal,
        "max_attempts": MAX_ATTEMPTS,
    }
    if terminal:
        answer_ep = episode_by_pk(state["answer_episode_id"])
        context.update(_build_terminal_ctx(request, play_date, state, shown, answer_ep))
    else:
        context.update(_build_in_progress_ctx(state, shown))

    return render(request, "game/daily-play.html", context)


def _continue_after_attempt(
    state: DailyRoundState, play_date: date
) -> tuple[DailyRoundState, bool]:
    """After a non-terminal attempt, pick the next hint. Returns (state, repeat_hint)."""
    prev_last = state["shown_quote_ids"][-1]
    next_pk = next_hint_quote_pk(
        play_date, state["answer_episode_id"], state["shown_quote_ids"]
    )
    if next_pk is None:
        return state, True
    return advance_hint(state, next_pk), next_pk == prev_last


@require_http_methods(["POST"])
@reject_future_play_date
def daily_answer(request, play_date):
    parsed = _parse_answer_form(request)
    if parsed is None:
        return HttpResponseBadRequest("invalid form")

    state = get_round(request.session, play_date)
    if state is None or state["status"] != "in_progress":
        return HttpResponseBadRequest("no active round")

    if parsed.quote_id != state["shown_quote_ids"][-1]:
        return HttpResponseBadRequest("quote mismatch")

    guessed_episode: Episode | None = None
    match parsed:
        case GuessForm(episode_id=eid):
            guessed_episode = episode_by_pk(eid)
            if guessed_episode is None:
                return HttpResponseBadRequest("unknown episode")
            post_attempt, outcome = apply_guess(state, eid)
        case SkipForm():
            post_attempt, outcome = apply_skip(state)
        case _:
            assert_never(parsed)

    if outcome is Outcome.DUPLICATE:
        return _render_in_progress(
            request, play_date, state, warning="You already guessed that episode."
        )

    if outcome in (Outcome.WON, Outcome.LOST):
        save_round(request.session, play_date, post_attempt)
        # On a win, the guessed episode IS the answer episode — reuse it.
        answer = guessed_episode if outcome is Outcome.WON else None
        return _render_terminal(request, play_date, post_attempt, answer_episode=answer)

    post_hint, repeat_hint = _continue_after_attempt(post_attempt, play_date)
    save_round(request.session, play_date, post_hint)
    return _render_in_progress(request, play_date, post_hint, repeat_hint=repeat_hint)


@require_GET
@reject_future_play_date
def episode_autocomplete(request, play_date):
    q = request.GET.get("q", "")
    pairs = episode_search_results(q, limit=20)
    return render(
        request,
        "game/partials/episode-suggestions.html",
        {"suggestions": pairs, "play_date": play_date},
    )
