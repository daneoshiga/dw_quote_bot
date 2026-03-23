from django.urls import path, register_converter

from game.converters import GameDateConverter
from game import views

register_converter(GameDateConverter, "gdate")

urlpatterns = [
    path("", views.today_redirect, name="today_redirect"),
    path("play/<gdate:play_date>/", views.daily_play, name="daily_play"),
    path("play/<gdate:play_date>/answer/", views.daily_answer, name="daily_answer"),
]
