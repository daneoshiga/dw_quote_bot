import asyncio
import functools
import itertools
import logging

import sentry_sdk
from aiogram import types
from aiogram.dispatcher.webhook import BaseResponse, _check_ip
from bottle import Bottle, abort, request
from sentry_sdk.integrations.aiohttp import AioHttpIntegration
from sentry_sdk.integrations.bottle import BottleIntegration

from .settings import settings

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=[AioHttpIntegration(), BottleIntegration()],
    )

logger = logging.getLogger(__name__)


app = Bottle()

RESPONSE_TIMEOUT = 55


def check_ip():
    """
    Check client IP. Accept requests only from telegram servers.

    :return:
    """
    # For reverse proxy (nginx)
    forwarded_for = request.environ.get("HTTP-X-FORWARDED-FOR", None)
    if forwarded_for:
        return forwarded_for, _check_ip(forwarded_for)

    # For default method
    host = request.environ.get("REMOTE_ADDR")
    if host is not None:
        return host, _check_ip(host)


def validate_ip():
    """
    Check ip if that is needed. Return 401 access denied
    """
    if request.app.config.get("check_ip", True):
        ip_address, accept = check_ip()
        if not accept:
            logger.warning(f"Blocking request from an unauthorized IP: {ip_address}")
            abort(401, "Access denied.")


def get_dispatcher(app):
    """
    Get Dispatcher instance from environment

    :return: :class:`aiogram.Dispatcher`
    """
    dispatcher = app.config.get("dispatcher")
    try:
        from aiogram import Bot, Dispatcher

        Dispatcher.set_current(dispatcher)
        Bot.set_current(dispatcher.bot)
    except RuntimeError:
        pass
    return dispatcher


def parse_update():
    return types.Update(**request.json)


async def process_update(dispatcher, update):
    """
    Need respond in less than 60 seconds in to webhook.

    So... If you respond greater than 55 seconds webhook automatically respond
    'ok' and execute callback response via simple HTTP request.

    :param update:
    :return:
    """
    dispatcher = get_dispatcher(app)
    loop = dispatcher.loop

    # Analog of `asyncio.wait_for` but without cancelling task
    waiter = loop.create_future()
    timeout_handle = loop.call_later(
        RESPONSE_TIMEOUT, asyncio.tasks._release_waiter, waiter
    )
    cb = functools.partial(asyncio.tasks._release_waiter, waiter)

    fut = asyncio.ensure_future(dispatcher.updates_handler.notify(update))
    fut.add_done_callback(cb)

    try:
        try:
            await waiter
        except asyncio.CancelledError:
            fut.remove_done_callback(cb)
            fut.cancel()
            raise

        if fut.done():
            return fut.result()
        else:
            fut.remove_done_callback(cb)
    finally:
        timeout_handle.cancel()


def sync_process_update(dispatcher, update):
    loop = dispatcher.loop
    return loop.run_until_complete(process_update(dispatcher, update))


def get_response(results):
    """
    Get response object from results.

    :param results: list
    :return:
    """
    if results is None:
        return None
    for result in itertools.chain.from_iterable(results):
        if isinstance(result, BaseResponse):
            return result


@app.post("/webhook/")
def webhook():
    validate_ip()

    update = parse_update()

    dispatcher = get_dispatcher(app)
    results = sync_process_update(dispatcher, update)
    response = get_response(results)

    if response:
        web_response = response.get_web_response()
    else:
        return "ok"

    if request.headers.get("RETRY_AFTER", None):
        web_response.headers["Retry-After"] = request.headers["RETRY_AFTER"]

    return web_response


@app.hook("config")
def set_webhook(key, value):
    if key != "dispatcher":
        return

    dispatcher = value
    loop = dispatcher.loop

    result = loop.run_until_complete(dispatcher.bot.set_webhook(settings.WEBHOOK_URL))
    logger.info("set_webhook_result=%s", result)
