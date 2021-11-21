import csv
import logging
import random
from collections import defaultdict

from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.utils.callback_data import CallbackData
from aiogram.utils.emoji import emojize
from aiogram.utils.exceptions import MessageNotModified

from .settings import settings

logger = logging.getLogger(__name__)
bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher(bot)

quote_cb = CallbackData("quote", "query_type", "inline_query", "char_name")

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


async def return_quote(message, char_name):
    keyboard = keyboard_factory(query_type="command", char_name=char_name)
    quote = random.choice(quotes[char_name])
    logger.info("return_quote, quote=%r", quote)
    response = format_quote(quote)

    await message.reply(
        response, parse_mode=types.ParseMode.MARKDOWN, reply_markup=keyboard
    )


def keyboard_factory(query_type="inline", inline_query="", char_name="Any Name"):
    keyboard_markup = types.InlineKeyboardMarkup()

    search_text = "Search Again"
    if query_type == "command":
        search_text = "Search by Character"

    search_button = types.InlineKeyboardButton(
        text=emojize(f":mag_right: {search_text}"),
        switch_inline_query_current_chat=inline_query,
        selective=True,
    )

    refresh = types.InlineKeyboardButton(
        text=emojize(":arrows_counterclockwise: Other"),
        callback_data=quote_cb.new(
            query_type=query_type, inline_query=inline_query, char_name=char_name
        ),
        selective=True,
    )

    keyboard_markup.row(search_button, refresh)
    return keyboard_markup


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
                id=index,
                title=char.title(),
                input_message_content=content,
                reply_markup=keyboard_factory(
                    inline_query=inline_query.query, char_name=char
                ),
            )
        )
    await bot.answer_inline_query(inline_query.id, results=results, cache_time=1)


@dp.callback_query_handler(quote_cb.filter(query_type="inline"))
async def inline_callback_handler(query, callback_data):
    message_text = format_quote(random.choice(quotes[callback_data["char_name"]]))
    try:
        await bot.edit_message_text(
            inline_message_id=query.inline_message_id,
            text=message_text,
            parse_mode=types.ParseMode.MARKDOWN,
            reply_markup=keyboard_factory(
                query_type="inline",
                inline_query=callback_data["inline_query"],
                char_name=callback_data["char_name"],
            ),
        )
    except MessageNotModified:
        await query.answer("Found the same quote! Try again.")


@dp.callback_query_handler(quote_cb.filter(query_type="command"))
async def command_callback_handler(query, callback_data):
    message_text = format_quote(random.choice(quotes[callback_data["char_name"]]))
    try:
        await query.message.edit_text(
            text=message_text,
            parse_mode=types.ParseMode.MARKDOWN,
            reply_markup=keyboard_factory(
                query_type="command",
                char_name=callback_data["char_name"],
            ),
        )
    except MessageNotModified:
        await query.answer("Found the same quote! Try again in a moment.")


@dp.message_handler(commands=["quote"])
async def quote(message: types.Message):
    logger.info("quote, %s", message)
    await return_quote(message, "Any Name")


@dp.message_handler(commands=["doctor_quote"])
async def doctor_quote(message: types.Message):
    logger.info("doctor_quote, %s", message)
    await return_quote(message, "DOCTOR")


@dp.message_handler(commands=["start", "help"])
async def send_welcome(message: types.Message):
    await message.reply(
        "This is a Doctor Who Quotes Bot\nWith quotes from Doctor Who and"
        " other Spin-offs!\ntype '/quote' to get a random one, and "
        " /doctor_quote for a Doctor specific quote"
    )
