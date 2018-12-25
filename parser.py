from pathlib import Path

import html2text

RAW_PATH = Path('raw_data/www.chakoteya.net/')

test_html_file = RAW_PATH / 'DoctorWho/37-10.html'


def parse_file(file_path):
    episode_title = ''
    lines = []
    with open(file_path, errors='replace') as episode_file:
        h = html2text.HTML2Text()
        result = h.handle(episode_file.read())
        for num, line in enumerate(result.split('\n')):
            if 'Airdate' in line:
                continue

            if not episode_title and '**' in line:
                episode_title = line.split('**')[1]

            if ': ' in line:
                lines.append(line.strip())

    return episode_title, lines


def parse_all(path):
    for file_path in path.glob('**/*.htm*'):
        print(file_path)
        episode_title, lines = parse_file(file_path)
        print(episode_title)


episode_title, lines = parse_file(test_html_file)
print(episode_title)

parse_all(RAW_PATH)
