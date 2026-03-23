import re
from datetime import date
from unittest.mock import patch

import pytest
from django.test import Client

from game.services import choices_for_daily_play


def _quote_id_from_response(response):
    text = response.content.decode()
    m = re.search(r'name="quote_id"\s+value="(\d+)"', text)
    assert m, "quote_id hidden input not found"
    return int(m.group(1))


@pytest.mark.django_db
def test_today_redirect_uses_game_clock(client: Client):
    with patch("game.views._today_in_game_tz", return_value=date(2030, 4, 5)):
        r = client.get("/", follow=False)
    assert r.status_code == 302
    assert r["Location"].endswith("/play/2030-04-05/")


@pytest.mark.django_db
def test_invalid_calendar_date_returns_404(client: Client, populated_quotes):
    assert client.get("/play/2025-02-30/").status_code == 404


@pytest.mark.django_db
def test_malformed_date_returns_404(client: Client, populated_quotes):
    assert client.get("/play/not-a-date/").status_code == 404


@pytest.mark.django_db
def test_daily_play_same_quote_for_same_date(client: Client, populated_quotes):
    d = date(2018, 3, 20)
    first = client.get(f"/play/{d.isoformat()}/")
    second = client.get(f"/play/{d.isoformat()}/")
    assert first.status_code == 200
    assert second.status_code == 200
    assert _quote_id_from_response(first) == _quote_id_from_response(second)


@pytest.mark.django_db
def test_daily_play_no_quotes_returns_503(client: Client):
    r = client.get("/play/2017-01-01/")
    assert r.status_code == 503


@pytest.mark.django_db
def test_answer_correct_htmx_and_session(client: Client, populated_quotes):
    play_date = date(2016, 8, 8)
    quote, _choices = choices_for_daily_play(play_date)
    url = f"/play/{play_date.isoformat()}/answer/"
    r = client.post(
        url,
        {"quote_id": str(quote.pk), "episode_id": str(quote.episode_id)},
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 200
    assert b"Correct" in r.content

    page = client.get(f"/play/{play_date.isoformat()}/")
    assert page.status_code == 200
    body = page.content.decode()
    assert "already played" in body.lower()
    assert "correct" in body.lower()


@pytest.mark.django_db
def test_answer_wrong_shows_title(client: Client, populated_quotes):
    play_date = date(2016, 8, 8)
    quote, choices = choices_for_daily_play(play_date)
    wrong_id = next(eid for eid, _ in choices if eid != quote.episode_id)
    url = f"/play/{play_date.isoformat()}/answer/"
    r = client.post(
        url,
        {"quote_id": str(quote.pk), "episode_id": str(wrong_id)},
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 200
    assert b"Not this time" in r.content


@pytest.mark.django_db
def test_answer_rejects_episode_not_in_mcq(client: Client, populated_quotes):
    play_date = date(2016, 8, 8)
    quote, _choices = choices_for_daily_play(play_date)
    url = f"/play/{play_date.isoformat()}/answer/"
    r = client.post(
        url,
        {"quote_id": str(quote.pk), "episode_id": "999999"},
    )
    assert r.status_code == 400
