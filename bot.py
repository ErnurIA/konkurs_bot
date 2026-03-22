import os
import asyncio
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message

import Admin
import flow
import quiz

from access_control import init_access_db, create_access_codes
from services.codes_sheet import add_codes_to_sheet


# Загружаем .env
load_dotenv()

# Инициализация базы лимитов и кодов
init_access_db()

# Получаем токен
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не найден. Проверь файл .env")


# ID администратора (твой Telegram ID)
ADMIN_IDS = [573722456]


# Создаем бота и диспетчер
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Общее хранилище данных
user_data = {}

# Подключаем роутеры (Admin первым: у flow есть широкий @router.message())
dp.include_router(Admin.router)
dp.include_router(flow.router)
dp.include_router(quiz.router)


# Скрытая админ-команда генерации кодов
@dp.message(Command("codes"))
async def admin_codes(message: Message):
    if not message.from_user or message.from_user.id not in ADMIN_IDS:
        return

    codes = create_access_codes(100)
    add_codes_to_sheet(codes)

    text = "Сгенерировано 100 кодов доступа:\n\n" + "\n".join(codes)

    await message.answer(text)


# Запуск бота
async def main():
    await dp.start_polling(
        bot,
        user_data=user_data,
        allowed_updates=["message", "callback_query", "poll_answer"],
    )


if __name__ == "__main__":
    asyncio.run(main())