import pytest

from game.models import Episode, Quote


@pytest.fixture
def populated_quotes(db):
    """At least five episodes and several quotes for MCQ + daily pick."""
    episodes = [
        Episode.objects.create(title=f"Episode {i}", airdate="")
        for i in range(5)
    ]
    quotes = []
    for ep in episodes:
        for j in range(4):
            quotes.append(
                Quote(episode=ep, text=f"Quote {ep.pk}-{j} on {ep.title}.")
            )
    Quote.objects.bulk_create(quotes)
    return episodes
