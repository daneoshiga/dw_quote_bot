from django.urls import path, register_converter

from game import views
from game.converters import GameDateConverter

register_converter(GameDateConverter, "gdate")

urlpatterns = [
    path("", views.today_redirect, name="today_redirect"),
    path("play/<gdate:play_date>/", views.daily_play, name="daily_play"),
    path("play/<gdate:play_date>/answer/", views.daily_answer, name="daily_answer"),
    path(
        "play/<gdate:play_date>/episodes/",
        views.episode_autocomplete,
        name="episode_autocomplete",
    ),
]
