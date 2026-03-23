from datetime import date, datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from game.services import choices_for_daily_play, mcq_episode_ids_for_quote, quote_for_play_date


def _today_in_game_tz() -> date:
    tz = ZoneInfo(settings.GAME_TIMEZONE)
    return datetime.now(tz).date()


@require_GET
def today_redirect(request):
    d = _today_in_game_tz()
    return redirect("daily_play", play_date=d)


@require_http_methods(["GET", "HEAD"])
def daily_play(request, play_date):
    try:
        quote, choice_rows = choices_for_daily_play(play_date)
    except LookupError:
        return render(
            request,
            "game/no_quotes.html",
            {"play_date": play_date},
            status=503,
        )
    except ValueError:
        return render(
            request,
            "game/no_quotes.html",
            {"play_date": play_date},
            status=503,
        )

    session_results = request.session.get("daily_results", {})
    prior = session_results.get(play_date.isoformat())

    context = {
        "play_date": play_date,
        "quote": quote,
        "choices": choice_rows,
        "prior_result": prior,
        "game_timezone": settings.GAME_TIMEZONE,
    }
    return render(request, "game/daily_play.html", context)


@require_http_methods(["POST"])
def daily_answer(request, play_date):
    try:
        quote_id = int(request.POST.get("quote_id", ""))
        episode_id = int(request.POST.get("episode_id", ""))
    except (TypeError, ValueError):
        return HttpResponseBadRequest("invalid form")

    try:
        quote = quote_for_play_date(play_date)
    except LookupError:
        return HttpResponseBadRequest("no quote for day")

    if quote.pk != quote_id:
        return HttpResponseBadRequest("quote mismatch")

    try:
        allowed = set(mcq_episode_ids_for_quote(play_date, quote))
    except ValueError:
        return HttpResponseBadRequest("cannot build choices")

    if episode_id not in allowed:
        return HttpResponseBadRequest("invalid episode choice")

    correct = episode_id == quote.episode_id
    results = dict(request.session.get("daily_results", {}))
    results[play_date.isoformat()] = {"correct": correct}
    request.session["daily_results"] = results

    context = {
        "correct": correct,
        "episode_title": quote.episode.title,
        "play_date": play_date,
        "quote_text": quote.text,
    }
    if request.htmx:
        return render(request, "game/partials/answer_result.html", context)
    return redirect("daily_play", play_date=play_date)
