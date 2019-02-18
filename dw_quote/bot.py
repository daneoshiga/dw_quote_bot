import json
import logging
import random

from prettyconf import config
from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher

logger = logging.getLogger(__name__)
bot = Bot(token=config('BOT_TOKEN'))
dp = Dispatcher(bot)

with open('data.json') as quotes_file:
    quotes = json.load(quotes_file)

doctor_quotes = []

for quote in quotes:
    if quote['line'].startswith('DOCTOR'):
        doctor_quotes.append(quote)


@dp.message_handler(commands=['start', 'help'])
async def send_welcome(message: types.Message):
    await message.reply(
        "This is a Doctor Who Quotes Bot\nWith quotes from Doctor Who and"
        " other Spin-offs!\ntype '/quote' to get a random one, and "
        " /doctor_quote for a Doctor specific quote"
    )


async def return_quote(chat_id, quotes):
    quote = random.choice(quotes)
    logger.info('return_quote, %r', quote)
    response = "{}\n*{}*".format(quote['line'], quote['episode_title'])
    if quote['airdate']:
        response += " | _{}_".format(quote['airdate'])

    await bot.send_message(chat_id, response, parse_mode=types.ParseMode.MARKDOWN)


@dp.message_handler(commands=['quote'])
async def quote(message: types.Message):
    logger.info('message, %s', message)
    await return_quote(message.chat.id, quotes)


@dp.message_handler(commands=['doctor_quote'])
async def doctor_quote(message: types.Message):
    logger.info('doctor_quote, %s', message)
    await return_quote(message.chat.id, doctor_quotes)
