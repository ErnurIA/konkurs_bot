import os
import asyncio
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher

import flow
import quiz

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не найден. Проверь файл .env (должен лежать рядом с bot.py)")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Общее хранилище данных
user_data = {}

# Подключаем роутеры
dp.include_router(flow.router)
dp.include_router(quiz.router)


async def main():
    await dp.start_polling(
        bot,
        user_data=user_data,
        allowed_updates=[
            "message",
            "callback_query",
            "poll_answer",
        ],
    )


if __name__ == "__main__":
    asyncio.run(main())
