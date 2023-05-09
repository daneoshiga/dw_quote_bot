import logging
from enum import Enum
from functools import partial

from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.types import InlineQueryResultArticle, InputTextMessageContent, ParseMode
from aiogram.utils.callback_data import CallbackData
from aiogram.utils.exceptions import MessageNotModified
from emoji import emojize

from . import ANY_NAME
from .quotes import Quotes
from .settings import settings

logger = logging.getLogger(__name__)
bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher(bot)

quote_cb = CallbackData("quote", "query_type", "inline_query", "name")
quotes = Quotes()


class QueryType(Enum):
    INLINE = "inline"
    COMMAND = "command"


# Keyboards


def keyboard_factory(query_type, inline_query="", name=ANY_NAME):
    keyboard_markup = types.InlineKeyboardMarkup()

    search_text = {
        QueryType.COMMAND: "Search by character",
        QueryType.INLINE: "Search Again",
    }

    search_button = types.InlineKeyboardButton(
        text=emojize(f":mag_right: {search_text[query_type]}", language="alias"),
        switch_inline_query_current_chat=inline_query,
    )

    refresh_callback = quote_cb.new(
        query_type=query_type.value,
        inline_query=inline_query,
        name=name,
    )
    refresh = types.InlineKeyboardButton(
        text=emojize(":arrows_counterclockwise: Refresh", language="alias"),
        callback_data=refresh_callback,
    )

    keyboard_markup.row(search_button, refresh)
    return keyboard_markup


inline_keyboard_factory = partial(keyboard_factory, QueryType.INLINE)
command_keyboard_factory = partial(keyboard_factory, QueryType.COMMAND)


# Helpers


async def reply_with_quote(message, name):
    keyboard = command_keyboard_factory(name=name)
    response = quotes.quote(name)

    await message.reply(response, parse_mode=ParseMode.HTML, reply_markup=keyboard)


# Handlers


@dp.inline_handler()
async def search_by_name(inline_query: types.InlineQuery):
    query = inline_query.query
    logger.info("inline_query, query=%s", query)
    results = []
    names = quotes.names(query)[:50]

    for index, name in enumerate(names, start=1):
        message = quotes.quote(name)
        content = InputTextMessageContent(message, parse_mode=ParseMode.HTML)
        keyboard = inline_keyboard_factory(inline_query=query, name=name)

        results.append(
            InlineQueryResultArticle(
                id=index,
                title=name.title(),
                input_message_content=content,
                reply_markup=keyboard,
            )
        )
    await bot.answer_inline_query(inline_query.id, results=results, cache_time=1)


@dp.callback_query_handler(quote_cb.filter(query_type=QueryType.INLINE.value))
async def inline_callback_handler(query, callback_data):
    logger.info("inline_callback_handler, callback_data=%r", callback_data)
    message_text = quotes.quote(callback_data["name"])
    keyboard = inline_keyboard_factory(
        inline_query=callback_data["inline_query"],
        name=callback_data["name"],
    )

    try:
        await bot.edit_message_text(
            inline_message_id=query.inline_message_id,
            text=message_text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
        )
    except MessageNotModified:
        await query.answer("Found the same quote! Try again.")


@dp.callback_query_handler(quote_cb.filter(query_type=QueryType.COMMAND.value))
async def command_callback_handler(query, callback_data):
    logger.info("command_callback_handler, callback_data=%r", callback_data)
    message_text = quotes.quote(callback_data["name"])
    keyboard = command_keyboard_factory(
        name=callback_data["name"],
    )

    try:
        await query.message.edit_text(
            text=message_text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
        )
    except MessageNotModified:
        await query.answer("Found the same quote! Try again.")


@dp.message_handler(commands=["quote"])
async def quote(message: types.Message):
    logger.info("quote, %s", message)
    await reply_with_quote(message, ANY_NAME)


@dp.message_handler(commands=["doctor_quote"])
async def doctor_quote(message: types.Message):
    logger.info("doctor_quote, %s", message)
    await reply_with_quote(message, "DOCTOR")


@dp.message_handler(commands=["start", "help"])
async def send_welcome(message: types.Message):
    await message.reply(
        "This is a Doctor Who Quotes Bot\nWith quotes from Doctor Who and"
        " other Spin-offs!\ntype '/quote' to get a random one, and "
        " /doctor_quote for a Doctor specific quote"
    )
