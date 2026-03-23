import csv
from io import StringIO

import pytest
from django.core.management import call_command

from game.models import Episode, Quote


@pytest.mark.django_db
def test_import_quotes_from_csv(tmp_path, settings):
    csv_path = tmp_path / "small.csv"
    buf = StringIO()
    w = csv.writer(buf, dialect="unix")
    w.writerow(["Alpha", "1 Jan 2000", "ALICE: Hello."])
    w.writerow(["Alpha", "1 Jan 2000", "BOB: Hi there."])
    w.writerow(["Beta", "", "CAROL: Other ep."])
    csv_path.write_text(buf.getvalue(), encoding="utf-8")

    call_command("import_quotes", csv=str(csv_path), batch_size=2)

    assert Episode.objects.count() == 2
    assert Quote.objects.count() == 3
    assert Quote.objects.filter(episode__title="Alpha").count() == 2


@pytest.mark.django_db
def test_import_quotes_clear(tmp_path):
    Episode.objects.create(title="Old", airdate="")
    csv_path = tmp_path / "one.csv"
    csv_path.write_text('"New","", "X: only."\n', encoding="utf-8")
    call_command("import_quotes", csv=str(csv_path), clear=True)
    assert Episode.objects.count() == 1
    assert Episode.objects.get().title == "New"
