import re
from datetime import date
from unittest.mock import patch

import pytest
from django.test import Client

from game.models import Episode, Quote
from game.round_session import SESSION_KEY, get_round
from game.services import quote_for_play_date


def _quote_id_from_response(response):
    text = response.content.decode()
    m = re.search(r'name="quote_id"\s+value="(\d+)"', text)
    assert m, "quote_id hidden input not found"
    return int(m.group(1))


@pytest.mark.django_db
def test_today_redirect_uses_game_clock(client: Client):
    with patch("game.views.today_in_game_tz", return_value=date(2030, 4, 5)):
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
def test_future_play_date_redirects_to_today(client: Client, populated_quotes):
    with patch("game.views.today_in_game_tz", return_value=date(2020, 1, 1)):
        r = client.get("/play/2020-01-02/", follow=False)
    assert r.status_code == 302
    assert r["Location"].endswith("/play/2020-01-01/")


@pytest.mark.django_db
def test_future_play_date_answer_redirects_to_today(client: Client, populated_quotes):
    with patch("game.views.today_in_game_tz", return_value=date(2020, 1, 1)):
        r = client.post(
            "/play/2020-01-02/answer/",
            {"quote_id": "1", "skip": "1"},
            follow=False,
        )
    assert r.status_code == 302
    assert r["Location"].endswith("/play/2020-01-01/")


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
def test_episode_autocomplete_short_query_returns_empty(
    client: Client, populated_quotes
):
    d = date(2016, 8, 8)
    r = client.get(f"/play/{d.isoformat()}/episodes/?q=Ep")
    assert r.status_code == 200
    assert b"suggestion-pick" not in r.content


@pytest.mark.django_db
def test_episode_autocomplete_finds_episode(client: Client, populated_quotes):
    d = date(2016, 8, 8)
    r = client.get(f"/play/{d.isoformat()}/episodes/?q=Epi")
    assert r.status_code == 200
    assert b"Episode 0" in r.content or b"Episode 1" in r.content


@pytest.mark.django_db
def test_answer_correct_htmx_and_session(client: Client, populated_quotes):
    play_date = date(2016, 8, 8)
    assert client.get(f"/play/{play_date.isoformat()}/").status_code == 200
    quote = quote_for_play_date(play_date)
    url = f"/play/{play_date.isoformat()}/answer/"
    r = client.post(
        url,
        {"quote_id": str(quote.pk), "episode_id": str(quote.episode_id)},
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 200
    htmx_body = r.content.decode()
    assert b"Correct" in r.content
    assert "🟩" in htmx_body
    assert "⬛" in htmx_body
    assert f"Doctor Who Daily Quote #{play_date.isoformat()}" in htmx_body
    assert ("http://testserver/play/" + play_date.isoformat() + "/") in htmx_body

    page = client.get(f"/play/{play_date.isoformat()}/")
    assert page.status_code == 200
    body = page.content.decode()
    assert "already finished" in body.lower()
    assert "won" in body.lower()
    assert f"Doctor Who Daily Quote #{play_date.isoformat()}" in body
    assert ("http://testserver/play/" + play_date.isoformat() + "/") in body


@pytest.mark.django_db
def test_answer_wrong_advances_quote_same_episode(client: Client, populated_quotes):
    play_date = date(2016, 8, 8)
    assert client.get(f"/play/{play_date.isoformat()}/").status_code == 200
    quote = quote_for_play_date(play_date)
    wrong = Episode.objects.exclude(pk=quote.episode_id).first()
    assert wrong is not None
    url = f"/play/{play_date.isoformat()}/answer/"
    r = client.post(
        url,
        {"quote_id": str(quote.pk), "episode_id": str(wrong.pk)},
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 200
    body = r.content.decode()
    assert quote.text in body
    q2_id = _quote_id_from_response(r)
    assert q2_id != quote.pk
    q2 = Quote.objects.get(pk=q2_id)
    assert q2.episode_id == quote.episode_id
    assert q2.text in body


@pytest.mark.django_db
def test_skip_advances_like_wrong_guess(client: Client, populated_quotes):
    play_date = date(2016, 8, 8)
    assert client.get(f"/play/{play_date.isoformat()}/").status_code == 200
    quote = quote_for_play_date(play_date)
    url = f"/play/{play_date.isoformat()}/answer/"
    r = client.post(
        url,
        {"quote_id": str(quote.pk), "skip": "1"},
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 200
    body = r.content.decode()
    assert quote.text in body
    q2_id = _quote_id_from_response(r)
    assert q2_id != quote.pk
    q2 = Quote.objects.get(pk=q2_id)
    assert q2.episode_id == quote.episode_id
    assert q2.text in body


@pytest.mark.django_db
def test_six_skips_ends_game_with_six_reds(client: Client, populated_quotes):
    play_date = date(2015, 5, 5)
    assert client.get(f"/play/{play_date.isoformat()}/").status_code == 200
    quote = quote_for_play_date(play_date)
    url = f"/play/{play_date.isoformat()}/answer/"
    quote_id = quote.pk
    for _ in range(6):
        r = client.post(
            url,
            {"quote_id": str(quote_id), "skip": "1"},
            HTTP_HX_REQUEST="true",
        )
        assert r.status_code == 200
        if "Out of guesses" in r.content.decode():
            break
        quote_id = _quote_id_from_response(r)
    final = r.content.decode()
    assert "Out of guesses" in final
    assert final.count("🟥") == 6
    assert "🟩" not in final
    assert f"Doctor Who Daily Quote #{play_date.isoformat()}" in final
    assert ("http://testserver/play/" + play_date.isoformat() + "/") in final


@pytest.mark.django_db
def test_answer_rejects_empty_episode_without_skip(client: Client, populated_quotes):
    play_date = date(2016, 8, 8)
    assert client.get(f"/play/{play_date.isoformat()}/").status_code == 200
    quote = quote_for_play_date(play_date)
    url = f"/play/{play_date.isoformat()}/answer/"
    r = client.post(
        url,
        {"quote_id": str(quote.pk), "episode_id": ""},
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 400


@pytest.mark.django_db
def test_skip_with_correct_episode_id_still_counts_as_wrong(
    client: Client, populated_quotes
):
    play_date = date(2016, 8, 8)
    assert client.get(f"/play/{play_date.isoformat()}/").status_code == 200
    quote = quote_for_play_date(play_date)
    url = f"/play/{play_date.isoformat()}/answer/"
    r = client.post(
        url,
        {
            "quote_id": str(quote.pk),
            "skip": "1",
            "episode_id": str(quote.episode_id),
        },
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 200
    q2_id = _quote_id_from_response(r)
    assert q2_id != quote.pk


@pytest.mark.django_db
def test_six_wrong_ends_game_with_six_reds(client: Client, populated_quotes):
    play_date = date(2015, 5, 5)
    assert client.get(f"/play/{play_date.isoformat()}/").status_code == 200
    quote = quote_for_play_date(play_date)
    wrong_eps = list(Episode.objects.exclude(pk=quote.episode_id).order_by("pk"))
    assert wrong_eps
    url = f"/play/{play_date.isoformat()}/answer/"
    quote_id = quote.pk
    for attempt in range(6):
        if attempt < len(wrong_eps):
            payload = {
                "quote_id": str(quote_id),
                "episode_id": str(wrong_eps[attempt].pk),
            }
        else:
            payload = {"quote_id": str(quote_id), "skip": "1"}
        r = client.post(
            url,
            payload,
            HTTP_HX_REQUEST="true",
        )
        assert r.status_code == 200
        if "Out of guesses" in r.content.decode():
            break
        quote_id = _quote_id_from_response(r)
    final = r.content.decode()
    assert "Out of guesses" in final
    assert final.count("🟥") == 6
    assert "🟩" not in final


@pytest.mark.django_db
def test_session_persists_mid_round(client: Client, populated_quotes):
    play_date = date(2014, 4, 4)
    assert client.get(f"/play/{play_date.isoformat()}/").status_code == 200
    quote = quote_for_play_date(play_date)
    wrong_ep = Episode.objects.exclude(pk=quote.episode_id).first()
    url = f"/play/{play_date.isoformat()}/answer/"
    r = client.post(
        url,
        {"quote_id": str(quote.pk), "episode_id": str(wrong_ep.pk)},
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 200
    expected_next = _quote_id_from_response(r)

    page = client.get(f"/play/{play_date.isoformat()}/")
    assert page.status_code == 200
    assert _quote_id_from_response(page) == expected_next


@pytest.mark.django_db
def test_wrong_guess_shows_visible_past_guess_history(client: Client, populated_quotes):
    play_date = date(2014, 6, 6)
    assert client.get(f"/play/{play_date.isoformat()}/").status_code == 200
    quote = quote_for_play_date(play_date)
    wrong_ep = Episode.objects.exclude(pk=quote.episode_id).first()
    assert wrong_ep is not None

    response = client.post(
        f"/play/{play_date.isoformat()}/answer/",
        {"quote_id": str(quote.pk), "episode_id": str(wrong_ep.pk)},
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    body = response.content.decode()
    assert "Past guesses" in body
    assert "<li>" in body
    assert wrong_ep.title in body


@pytest.mark.django_db
def test_duplicate_episode_guess_warns_and_does_not_consume_attempt(
    client: Client, populated_quotes
):
    play_date = date(2014, 6, 7)
    assert client.get(f"/play/{play_date.isoformat()}/").status_code == 200
    quote = quote_for_play_date(play_date)
    wrong_ep = Episode.objects.exclude(pk=quote.episode_id).first()
    assert wrong_ep is not None

    first = client.post(
        f"/play/{play_date.isoformat()}/answer/",
        {"quote_id": str(quote.pk), "episode_id": str(wrong_ep.pk)},
        HTTP_HX_REQUEST="true",
    )
    assert first.status_code == 200
    second_quote_id = _quote_id_from_response(first)

    state_before = get_round(client.session, play_date)
    assert state_before is not None
    wrong_before = int(state_before["wrong_count"])
    history_before = list(state_before.get("guess_history", []))

    duplicate = client.post(
        f"/play/{play_date.isoformat()}/answer/",
        {"quote_id": str(second_quote_id), "episode_id": str(wrong_ep.pk)},
        HTTP_HX_REQUEST="true",
    )
    assert duplicate.status_code == 200
    body = duplicate.content.decode()
    assert "You already guessed that episode." in body
    assert _quote_id_from_response(duplicate) == second_quote_id

    state_after = get_round(client.session, play_date)
    assert state_after is not None
    assert int(state_after["wrong_count"]) == wrong_before
    assert list(state_after.get("guess_history", [])) == history_before


@pytest.mark.django_db
def test_skip_shows_visible_past_guess_history(client: Client, populated_quotes):
    play_date = date(2014, 7, 7)
    assert client.get(f"/play/{play_date.isoformat()}/").status_code == 200
    quote = quote_for_play_date(play_date)

    response = client.post(
        f"/play/{play_date.isoformat()}/answer/",
        {"quote_id": str(quote.pk), "skip": "1"},
        HTTP_HX_REQUEST="true",
    )
    assert response.status_code == 200
    body = response.content.decode()
    assert "Past guesses" in body
    assert "<li>" in body
    assert "Skipped" in body


@pytest.mark.django_db
def test_terminal_screen_shows_full_past_guess_history(
    client: Client, populated_quotes
):
    play_date = date(2014, 8, 8)
    assert client.get(f"/play/{play_date.isoformat()}/").status_code == 200
    quote = quote_for_play_date(play_date)
    wrong_ep = Episode.objects.exclude(pk=quote.episode_id).first()
    assert wrong_ep is not None

    first = client.post(
        f"/play/{play_date.isoformat()}/answer/",
        {"quote_id": str(quote.pk), "episode_id": str(wrong_ep.pk)},
        HTTP_HX_REQUEST="true",
    )
    assert first.status_code == 200
    second_quote_id = _quote_id_from_response(first)

    second = client.post(
        f"/play/{play_date.isoformat()}/answer/",
        {"quote_id": str(second_quote_id), "episode_id": str(quote.episode_id)},
        HTTP_HX_REQUEST="true",
    )
    assert second.status_code == 200
    final_body = second.content.decode()
    assert "Correct" in final_body
    assert "Past guesses" in final_body
    assert final_body.count("<li>") >= 2
    assert wrong_ep.title in final_body


@pytest.mark.django_db
def test_answer_rejects_unknown_episode(client: Client, populated_quotes):
    play_date = date(2016, 8, 8)
    assert client.get(f"/play/{play_date.isoformat()}/").status_code == 200
    quote = quote_for_play_date(play_date)
    url = f"/play/{play_date.isoformat()}/answer/"
    r = client.post(
        url,
        {"quote_id": str(quote.pk), "episode_id": "999999"},
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 400


@pytest.mark.django_db
def test_answer_rejects_quote_mismatch(client: Client, populated_quotes):
    play_date = date(2016, 8, 8)
    assert client.get(f"/play/{play_date.isoformat()}/").status_code == 200
    quote = quote_for_play_date(play_date)
    url = f"/play/{play_date.isoformat()}/answer/"
    r = client.post(
        url,
        {"quote_id": str(quote.pk + 99999), "episode_id": str(quote.episode_id)},
        HTTP_HX_REQUEST="true",
    )
    assert r.status_code == 400


@pytest.mark.django_db
def test_round_session_stored_under_daily_rounds(client: Client, populated_quotes):
    play_date = date(2013, 3, 3)
    client.get(f"/play/{play_date.isoformat()}/")
    session = client.session
    assert SESSION_KEY in session
    st = get_round(session, play_date)
    assert st is not None
    assert st["status"] == "in_progress"
