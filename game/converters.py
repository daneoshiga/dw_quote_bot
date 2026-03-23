from datetime import date

from game.game_logic import parse_game_date


class GameDateConverter:
    regex = r"\d{4}-\d{2}-\d{2}"

    def to_python(self, value: str):
        return parse_game_date(value)

    def to_url(self, value):
        if isinstance(value, date):
            return value.isoformat()
        return str(value)
