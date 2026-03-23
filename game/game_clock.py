"""Calendar day in the game timezone (URL validation and redirects)."""

from datetime import datetime
from zoneinfo import ZoneInfo

from django.conf import settings


def today_in_game_tz():
    return datetime.now(ZoneInfo(settings.GAME_TIMEZONE)).date()
