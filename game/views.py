from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from game.game_logic import format_progress_row, format_share_row
from game.models import Episode
from game.round_session import (
    MAX_ATTEMPTS,
    get_round,
    is_terminal,
    new_round_from_quote,
    save_round,
)
from game.services import (
    episode_choice_label,
    episode_search_results,
    next_hint_quote_pk,
    quote_by_pk,
    quote_for_play_date,
)


def _today_in_game_tz() -> date:
    tz = ZoneInfo(settings.GAME_TIMEZONE)
    return datetime.now(tz).date()


def _episode_title(episode_id: int) -> str:
    ep = Episode.objects.filter(pk=episode_id).only("title", "airdate").first()
    if ep is None:
        return "Unknown episode"
    return episode_choice_label(ep)


@require_GET
def today_redirect(request):
    d = _today_in_game_tz()
    return redirect("daily_play", play_date=d)


@require_http_methods(["GET", "HEAD"])
def daily_play(request, play_date):
    try:
        quote_for_day = quote_for_play_date(play_date)
    except LookupError:
        return render(
            request,
            "game/no_quotes.html",
            {"play_date": play_date},
            status=503,
        )

    state = get_round(request.session, play_date)
    if state is None:
        state = new_round_from_quote(quote_for_day)
        save_round(request.session, play_date, state)
    elif state.get("status") == "in_progress":
        anchor = quote_for_play_date(play_date)
        if state.get("answer_episode_id") != anchor.episode_id:
            state = new_round_from_quote(anchor)
            save_round(request.session, play_date, state)
        elif state["shown_quote_ids"][0] != anchor.pk:
            state = new_round_from_quote(anchor)
            save_round(request.session, play_date, state)

    terminal = is_terminal(state)
    context = {
        "play_date": play_date,
        "game_timezone": settings.GAME_TIMEZONE,
        "terminal": terminal,
        "max_attempts": MAX_ATTEMPTS,
    }

    if terminal:
        context.update(
            {
                "share_row": state.get("share_row", ""),
                "episode_title": _episode_title(int(state["answer_episode_id"])),
                "outcome": state.get("status"),
            }
        )
    else:
        last_pk = state["shown_quote_ids"][-1]
        quote = quote_by_pk(last_pk) or quote_for_day
        wrong_count = int(state.get("wrong_count", 0))
        context.update(
            {
                "quote": quote,
                "wrong_count": wrong_count,
                "progress_row": format_progress_row(
                    wrong_count=wrong_count, max_attempts=MAX_ATTEMPTS
                ),
                "guess_number": wrong_count + 1,
            }
        )

    return render(request, "game/daily_play.html", context)


@require_http_methods(["POST"])
def daily_answer(request, play_date):
    try:
        quote_id = int(request.POST.get("quote_id", ""))
        episode_id = int(request.POST.get("episode_id", ""))
    except (TypeError, ValueError):
        return HttpResponseBadRequest("invalid form")

    state = get_round(request.session, play_date)
    if state is None or state.get("status") != "in_progress":
        return HttpResponseBadRequest("no active round")

    if quote_id != state["shown_quote_ids"][-1]:
        return HttpResponseBadRequest("quote mismatch")

    if not Episode.objects.filter(pk=episode_id).exists():
        return HttpResponseBadRequest("unknown episode")

    answer_episode_id = int(state["answer_episode_id"])
    wrong_count = int(state.get("wrong_count", 0))

    if episode_id == answer_episode_id:
        share = format_share_row(won=True, wrong_count=wrong_count, max_attempts=MAX_ATTEMPTS)
        state = {
            "status": "won",
            "shown_quote_ids": list(state["shown_quote_ids"]),
            "wrong_count": wrong_count,
            "answer_episode_id": answer_episode_id,
            "share_row": share,
        }
        save_round(request.session, play_date, state)
        ctx = {
            "play_date": play_date,
            "won": True,
            "episode_title": _episode_title(answer_episode_id),
            "share_row": share,
        }
        if request.htmx:
            return render(request, "game/partials/daily_complete.html", ctx)
        return redirect("daily_play", play_date=play_date)

    wrong_count += 1
    if wrong_count >= MAX_ATTEMPTS:
        share = format_share_row(won=False, wrong_count=MAX_ATTEMPTS, max_attempts=MAX_ATTEMPTS)
        state = {
            "status": "lost",
            "shown_quote_ids": list(state["shown_quote_ids"]),
            "wrong_count": wrong_count,
            "answer_episode_id": answer_episode_id,
            "share_row": share,
        }
        save_round(request.session, play_date, state)
        ctx = {
            "play_date": play_date,
            "won": False,
            "episode_title": _episode_title(answer_episode_id),
            "share_row": share,
        }
        if request.htmx:
            return render(request, "game/partials/daily_complete.html", ctx)
        return redirect("daily_play", play_date=play_date)

    prev_ids = list(state["shown_quote_ids"])
    prev_last = prev_ids[-1]
    next_pk = next_hint_quote_pk(
        play_date,
        answer_episode_id,
        prev_ids,
        hint_attempt=wrong_count,
    )
    if next_pk is None:
        next_pk = prev_last

    repeat_hint = next_pk == prev_last
    new_state = {
        "status": "in_progress",
        "shown_quote_ids": prev_ids + [next_pk],
        "wrong_count": wrong_count,
        "answer_episode_id": answer_episode_id,
    }
    save_round(request.session, play_date, new_state)

    quote = quote_by_pk(next_pk)
    if quote is None:
        return HttpResponseBadRequest("quote missing")

    ctx = {
        "play_date": play_date,
        "quote": quote,
        "wrong_count": wrong_count,
        "progress_row": format_progress_row(wrong_count=wrong_count, max_attempts=MAX_ATTEMPTS),
        "guess_number": wrong_count + 1,
        "max_attempts": MAX_ATTEMPTS,
        "repeat_hint": repeat_hint,
    }
    if request.htmx:
        return render(request, "game/partials/daily_round.html", ctx)
    return redirect("daily_play", play_date=play_date)


@require_GET
def episode_autocomplete(request, play_date):
    q = request.GET.get("q", "")
    pairs = episode_search_results(q, limit=20)
    return render(
        request,
        "game/partials/episode_suggestions.html",
        {"suggestions": pairs, "play_date": play_date},
    )
