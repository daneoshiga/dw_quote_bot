import pytest

from game.services import quotes_for_pks_in_order


@pytest.mark.django_db
def test_quotes_for_pks_in_order_preserves_order(populated_quotes):
    from game.models import Quote

    qs = list(Quote.objects.order_by("id").values_list("id", flat=True))
    assert len(qs) >= 3
    pks = [qs[2], qs[0], qs[1]]
    out = quotes_for_pks_in_order(pks)
    assert [q.pk for q in out] == pks


@pytest.mark.django_db
def test_quotes_for_pks_in_order_empty():
    assert quotes_for_pks_in_order([]) == []
