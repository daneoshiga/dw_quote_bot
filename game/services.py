"""Database-backed helpers for the daily game."""

from __future__ import annotations

from datetime import date

from django.conf import settings

from game.game_logic import build_mcq_episode_ids, mcq_rng_for_day, resolve_quote_pk
from game.models import Episode, Quote


def quote_pk_for_play_date(play_date: date) -> int:
    game_seed = settings.GAME_SEED
    max_pk = Quote.objects.order_by("-id").values_list("id", flat=True).first()
    if max_pk is None:
        raise LookupError("no quotes in database")

    def exists(pk: int) -> bool:
        return Quote.objects.filter(pk=pk).exists()

    return resolve_quote_pk(play_date, max_pk, exists, game_seed=game_seed)


def quote_for_play_date(play_date: date) -> Quote:
    pk = quote_pk_for_play_date(play_date)
    return Quote.objects.select_related("episode").get(pk=pk)


def episode_ids_ordered() -> list[int]:
    return list(Episode.objects.values_list("id", flat=True).order_by("id"))


def mcq_episode_ids_for_quote(play_date: date, quote: Quote) -> list[int]:
    episode_ids = episode_ids_ordered()
    rng = mcq_rng_for_day(play_date, settings.GAME_SEED)
    k = settings.DISTRACTOR_COUNT
    if len(episode_ids) <= k:
        raise ValueError("need more episodes than distractor count")
    k = min(k, len(episode_ids) - 1)
    return build_mcq_episode_ids(quote.episode_id, episode_ids, k, rng)


def choices_for_daily_play(play_date: date) -> tuple[Quote, list[tuple[int, str]]]:
    quote = quote_for_play_date(play_date)
    option_ids = mcq_episode_ids_for_quote(play_date, quote)
    episodes = Episode.objects.in_bulk(option_ids)
    rows = [(eid, episodes[eid].title) for eid in option_ids]
    return quote, rows
