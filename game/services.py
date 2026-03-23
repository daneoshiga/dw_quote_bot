"""Database-backed helpers for the daily game."""

from __future__ import annotations

from datetime import date

from django.conf import settings

from game.game_logic import pick_next_quote_pk, resolve_quote_pk, rng_for_date
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


def episode_choice_label(ep: Episode) -> str:
    title = (ep.title or "").strip()
    air = (ep.airdate or "").strip()
    if air:
        return f"{title} ({air})"
    return title


def episode_search_results(q: str, *, limit: int = 20) -> list[tuple[int, str]]:
    """Return (episode_id, display label) for autocomplete."""
    q = (q or "").strip()
    if len(q) < 3:
        return []
    qs = (
        Episode.objects.filter(title__icontains=q)
        .order_by("title", "id")
        .distinct()[:limit]
    )
    return [(ep.pk, episode_choice_label(ep)) for ep in qs]


def quote_pks_for_episode(episode_id: int) -> list[int]:
    return list(
        Quote.objects.filter(episode_id=episode_id)
        .order_by("id")
        .values_list("id", flat=True)
    )


def next_hint_quote_pk(
    play_date: date,
    episode_id: int,
    shown_quote_ids: list[int],
    hint_attempt: int,
) -> int | None:
    """
    Deterministic next quote from the answer episode, excluding already-shown pks.

    hint_attempt: 1-based index of this hint draw (first extra quote after wrong #1 uses 1).
    """
    game_seed = settings.GAME_SEED
    rng = rng_for_date(play_date, f"{game_seed}:hint:{hint_attempt}")
    candidates = quote_pks_for_episode(episode_id)
    shown = set(shown_quote_ids)
    return pick_next_quote_pk(candidates, shown, rng)


def quote_by_pk(pk: int) -> Quote | None:
    return Quote.objects.select_related("episode").filter(pk=pk).first()


def quotes_for_pks_in_order(pks: list[int]) -> list[Quote]:
    """Fetch quotes for primary keys, preserving the order of ``pks``."""
    if not pks:
        return []
    rows = list(
        Quote.objects.select_related("episode").filter(pk__in=pks),
    )
    by_id = {q.pk: q for q in rows}
    return [by_id[pk] for pk in pks if pk in by_id]
