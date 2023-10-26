import asyncio

from .bot import bot, dp

if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))
