import csv
import logging
import random
from collections import defaultdict

from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher

from .settings import settings

logger = logging.getLogger(__name__)
bot = Bot(token=settings.bot_token)
dp = Dispatcher(bot)

with open("data.csv", newline="") as quotes_file:
    quotes = defaultdict(list)
    fieldnames = ["episode_title", "airdate", "line"]
    quotes["Any Name"] = [q for q in csv.DictReader(quotes_file, fieldnames)]

    for quote in quotes["Any Name"]:
        name = quote["line"]
        stop_strings = [":", "(", "["]
        stop_strings.extend([str(n) for n in range(0, 10)])

        for string in stop_strings:
            name = name.split(string)[0]
        if name.startswith("DOCTOR"):
            name = "DOCTOR"
        quotes[name.strip()].append(quote)


def format_quote(quote):
    response = "{}\n*{}*".format(quote["line"], quote["episode_title"])
    if quote["airdate"]:
        response += " | _{}_".format(quote["airdate"])
    return response


async def return_quote(chat_id, quotes):
    quote = random.choice(quotes)
    logger.info("return_quote, quote=%r", quote)
    response = format_quote(quote)

    await bot.send_message(chat_id, response, parse_mode=types.ParseMode.MARKDOWN)


@dp.inline_handler()
async def search_by_name(inline_query: types.InlineQuery):
    logger.info("inline_query, query=%s", inline_query.query)
    results = []
    names = []
    for name in quotes.keys():
        if inline_query.query and name.startswith(inline_query.query.upper()):
            names.append(name)
    names = sorted(names) if names else ["Any Name"]

    for index, char in enumerate(names[:50], start=1):
        message = format_quote(random.choice(quotes[char]))
        content = types.InputTextMessageContent(
            message, parse_mode=types.ParseMode.MARKDOWN
        )
        results.append(
            types.InlineQueryResultArticle(
                id=index, title=char.title(), input_message_content=content
            )
        )
    await bot.answer_inline_query(inline_query.id, results=results, cache_time=1)


@dp.message_handler(commands=["start", "help"])
async def send_welcome(message: types.Message):
    await message.reply(
        "This is a Doctor Who Quotes Bot\nWith quotes from Doctor Who and"
        " other Spin-offs!\ntype '/quote' to get a random one, and "
        " /doctor_quote for a Doctor specific quote"
    )


@dp.message_handler(commands=["quote"])
async def quote(message: types.Message):
    logger.info("quote, %s", message)
    await return_quote(message.chat.id, quotes["Any Name"])


@dp.message_handler(commands=["doctor_quote"])
async def doctor_quote(message: types.Message):
    logger.info("doctor_quote, %s", message)
    await return_quote(message.chat.id, quotes["DOCTOR"])
