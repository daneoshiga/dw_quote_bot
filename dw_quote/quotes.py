import csv
import logging
import random
from collections import defaultdict

from . import ANY_NAME

logger = logging.getLogger(__name__)


class Quotes:
    quotes = defaultdict(list)

    def __init__(self):
        with open("data.csv", newline="") as quotes_file:
            fieldnames = "episode_title", "airdate", "line"
            self.quotes[ANY_NAME] = [q for q in csv.DictReader(quotes_file, fieldnames)]

            stop_strings = [":", "(", "["]
            stop_strings.extend([str(n) for n in range(0, 10)])

            for quote in self.quotes[ANY_NAME]:
                name = quote["line"]

                for string in stop_strings:
                    name = name.split(string)[0]
                if name.startswith("DOCTOR"):
                    name = "DOCTOR"
                self.quotes[name.strip()].append(quote)

    def format_quote(self, quote):
        response = "{}\n*{}*".format(quote["line"], quote["episode_title"])
        if quote["airdate"]:
            response += " | _{}_".format(quote["airdate"])
        return response

    def names(self, search_name):
        if not search_name:
            return [ANY_NAME]

        names = []
        for name in self.quotes.keys():
            if search_name and name.startswith(search_name.upper()):
                names.append(name)
        names = sorted(names)
        return names

    def quote(self, name):
        choosen_quote = random.choice(self.quotes[name])
        return self.format_quote(choosen_quote)
