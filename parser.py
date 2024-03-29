import csv
from pathlib import Path

import html2text
from chardet.universaldetector import UniversalDetector

RAW_PATH = Path("raw_data/www.chakoteya.net/")

detector = UniversalDetector()

IGNORED_LINES = ("announcer", "chapter:")


def parse_file(file_path):
    detector.reset()
    episode_title = airdate = ""
    lines = []

    for line in open(file_path, "rb"):
        detector.feed(line)
        if detector.done:
            break
    detector.close()
    encoding = detector.result["encoding"]

    with open(file_path, errors="replace", encoding=encoding) as episode_file:
        h = html2text.HTML2Text(bodywidth=0)
        result = h.handle(episode_file.read())
        for num, line in enumerate(result.split("\n")):
            if any(ignored in line.lower() for ignored in IGNORED_LINES):
                continue

            if "Airdate: " in line:
                airdate = line.split(": ")[1].strip()
                continue

            if not episode_title and "**" in line:
                episode_title = line.split("**")[1]
                continue

            if ": " in line:
                lines.append(line.strip())

    return episode_title, airdate, lines


def parse_all(path):
    lines_data = []
    for file_path in path.glob("**/*.htm*"):
        print(file_path)
        episode_title, airdate, lines = parse_file(file_path)
        print(episode_title)
        for line in lines:
            data = {"episode_title": episode_title, "airdate": airdate, "line": line}
            lines_data.append(data)

    return lines_data


if __name__ == "__main__":
    lines_data = parse_all(RAW_PATH)
    with open("./data.csv", "w", encoding="utf-8", newline="") as csvfile:
        fieldnames = ["episode_title", "airdate", "line"]
        writer = csv.DictWriter(csvfile, fieldnames, dialect="unix")
        for quote in lines_data:
            writer.writerow(quote)
