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
    format_share_row,
)
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
    quotes_for_pks_in_order,
)


def _redirect_future_play_date_to_today(request, play_date):
    today = today_in_game_tz()
    if play_date > today:
        return redirect("daily_play", play_date=today)
    return None


def _episode_title(episode_id: int) -> str:
    ep = Episode.objects.filter(pk=episode_id).only("title", "airdate").first()
    if ep is None:
        return "Unknown episode"
    return episode_choice_label(ep)


def _share_text(request, play_date, share_row: str) -> str:
    path = reverse("daily_play", kwargs={"play_date": play_date})
    url = request.build_absolute_uri(path)
    return format_share_clipboard(
        game_title=SHARE_GAME_TITLE,
        play_date=play_date,
        emoji_row=share_row,
        game_url=url,
    )


def _past_guesses(state) -> list[str]:
    entries = list(state.get("guess_history", []))
    if not entries:
        return []

    episode_ids = [
        int(entry.get("episode_id"))
        for entry in entries
        if entry.get("guess_type") == "episode" and entry.get("episode_id") is not None
    ]
    episodes = Episode.objects.in_bulk(episode_ids)

    past = []
    for entry in entries:
        if entry.get("guess_type") == "skip":
            past.append("Skipped")
            continue

        episode_id = entry.get("episode_id")
        if episode_id is None:
            past.append("Unknown episode")
            continue

        episode = episodes.get(int(episode_id))
        if episode is None:
            past.append("Unknown episode")
        else:
            past.append(episode_choice_label(episode))
    return past


@require_GET
def today_redirect(request):
    d = today_in_game_tz()
    return redirect("daily_play", play_date=d)


@require_http_methods(["GET", "HEAD"])
def daily_play(request, play_date):
    early = _redirect_future_play_date_to_today(request, play_date)
    if early is not None:
        return early

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
        share_row = state.get("share_row", "")
        context.update(
            {
                "share_text": _share_text(request, play_date, share_row),
                "episode_title": _episode_title(int(state["answer_episode_id"])),
                "outcome": state.get("status"),
                "shown_quotes": quotes_for_pks_in_order(list(state.get("shown_quote_ids", []))),
                "past_guesses": _past_guesses(state),
            }
        )
    else:
        shown_pks = list(state["shown_quote_ids"])
        shown_quotes = quotes_for_pks_in_order(shown_pks)
        if not shown_quotes:
            last_pk = shown_pks[-1] if shown_pks else quote_for_day.pk
            q = quote_by_pk(last_pk) or quote_for_day
            shown_quotes = [q]
        wrong_count = int(state.get("wrong_count", 0))
        context.update(
            {
                "shown_quotes": shown_quotes,
                "current_quote": shown_quotes[-1],
                "wrong_count": wrong_count,
                "progress_row": format_progress_row(
                    wrong_count=wrong_count, max_attempts=MAX_ATTEMPTS
                ),
                "guess_number": wrong_count + 1,
                "past_guesses": _past_guesses(state),
            }
        )

    return render(request, "game/daily_play.html", context)


@require_http_methods(["POST"])
def daily_answer(request, play_date):
    early = _redirect_future_play_date_to_today(request, play_date)
    if early is not None:
        return early

    try:
        quote_id = int(request.POST.get("quote_id", ""))
    except (TypeError, ValueError):
        return HttpResponseBadRequest("invalid form")

    skip = request.POST.get("skip") == "1"

    if skip:
        episode_id = None
    else:
        try:
            episode_id = int(request.POST.get("episode_id", ""))
        except (TypeError, ValueError):
            return HttpResponseBadRequest("invalid form")

    state = get_round(request.session, play_date)
    if state is None or state.get("status") != "in_progress":
        return HttpResponseBadRequest("no active round")

    if quote_id != state["shown_quote_ids"][-1]:
        return HttpResponseBadRequest("quote mismatch")

    if not skip and not Episode.objects.filter(pk=episode_id).exists():
        return HttpResponseBadRequest("unknown episode")

    answer_episode_id = int(state["answer_episode_id"])
    wrong_count = int(state.get("wrong_count", 0))
    guess_history = list(state.get("guess_history", []))
    if not skip and any(
        entry.get("guess_type") == "episode"
        and entry.get("episode_id") is not None
        and int(entry.get("episode_id")) == episode_id
        for entry in guess_history
    ):
        shown_quotes = quotes_for_pks_in_order(list(state["shown_quote_ids"]))
        if len(shown_quotes) != len(state["shown_quote_ids"]):
            return HttpResponseBadRequest("quote missing")
        ctx = {
            "play_date": play_date,
            "shown_quotes": shown_quotes,
            "current_quote": shown_quotes[-1],
            "wrong_count": wrong_count,
            "progress_row": format_progress_row(
                wrong_count=wrong_count, max_attempts=MAX_ATTEMPTS
            ),
            "guess_number": wrong_count + 1,
            "max_attempts": MAX_ATTEMPTS,
            "past_guesses": _past_guesses(state),
            "warning_message": "You already guessed that episode.",
        }
        if request.htmx:
            return render(request, "game/partials/daily_round.html", ctx)
        return redirect("daily_play", play_date=play_date)

    guess_entry = {"guess_type": "skip", "episode_id": None} if skip else {
        "guess_type": "episode",
        "episode_id": episode_id,
    }
    guess_history.append(guess_entry)

    if not skip and episode_id == answer_episode_id:
        share = format_share_row(won=True, wrong_count=wrong_count, max_attempts=MAX_ATTEMPTS)
        state = {
            "status": "won",
            "shown_quote_ids": list(state["shown_quote_ids"]),
            "wrong_count": wrong_count,
            "answer_episode_id": answer_episode_id,
            "share_row": share,
            "guess_history": guess_history,
        }
        save_round(request.session, play_date, state)
        ctx = {
            "play_date": play_date,
            "won": True,
            "episode_title": _episode_title(answer_episode_id),
            "share_text": _share_text(request, play_date, share),
            "shown_quotes": quotes_for_pks_in_order(state["shown_quote_ids"]),
            "past_guesses": _past_guesses(state),
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
            "guess_history": guess_history,
        }
        save_round(request.session, play_date, state)
        ctx = {
            "play_date": play_date,
            "won": False,
            "episode_title": _episode_title(answer_episode_id),
            "share_text": _share_text(request, play_date, share),
            "shown_quotes": quotes_for_pks_in_order(state["shown_quote_ids"]),
            "past_guesses": _past_guesses(state),
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
        "guess_history": guess_history,
    }
    save_round(request.session, play_date, new_state)

    if quote_by_pk(next_pk) is None:
        return HttpResponseBadRequest("quote missing")

    shown_quotes = quotes_for_pks_in_order(new_state["shown_quote_ids"])
    if len(shown_quotes) != len(new_state["shown_quote_ids"]):
        return HttpResponseBadRequest("quote missing")

    ctx = {
        "play_date": play_date,
        "shown_quotes": shown_quotes,
        "current_quote": shown_quotes[-1],
        "wrong_count": wrong_count,
        "progress_row": format_progress_row(wrong_count=wrong_count, max_attempts=MAX_ATTEMPTS),
        "guess_number": wrong_count + 1,
        "max_attempts": MAX_ATTEMPTS,
        "repeat_hint": repeat_hint,
        "past_guesses": _past_guesses(new_state),
    }
    if request.htmx:
        return render(request, "game/partials/daily_round.html", ctx)
    return redirect("daily_play", play_date=play_date)


@require_GET
def episode_autocomplete(request, play_date):
    early = _redirect_future_play_date_to_today(request, play_date)
    if early is not None:
        return early

    q = request.GET.get("q", "")
    pairs = episode_search_results(q, limit=20)
    return render(
        request,
        "game/partials/episode_suggestions.html",
        {"suggestions": pairs, "play_date": play_date},
    )
