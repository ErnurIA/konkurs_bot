import asyncio
from pathlib import Path

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import FSInputFile, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from pdf_utils import AwardData, generate_award_pdf
from access_control import create_access_codes

router = Router()

ADMIN_ID = 573722456  # как в bot.py ADMIN_IDS


# ===== FSM =====
class AdminStates(StatesGroup):
    waiting_name = State()
    waiting_type = State()


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


# ===== СТАРТ =====
# Command("pdf") ловит /pdf и /pdf@BotName
@router.message(Command("pdf"))
async def start_pdf(message: Message, state: FSMContext):
    print("ADMIN ROUTER WORKING: Command /pdf", getattr(message.from_user, "id", None))
    if not message.from_user or not is_admin(message.from_user.id):
        return

    await message.answer("Напиши ФИО:")
    await state.set_state(AdminStates.waiting_name)


@router.message(Command("codes5"))
async def codes5(message: Message):
    if not message.from_user or not is_admin(message.from_user.id):
        return

    codes = create_access_codes(50, bonus_attempts=5)
    await message.answer("\n".join(codes))


@router.message(Command("codes10"))
async def codes10(message: Message):
    if not message.from_user or not is_admin(message.from_user.id):
        return

    codes = create_access_codes(50, bonus_attempts=10)
    await message.answer("\n".join(codes))


# Временный DEBUG: смотри консоль при /pdf (не трогаем остальные сообщения — см. порядок router в bot.py)
print("ADMIN ROUTER MODULE LOADED")


# ===== ПОЛУЧИЛИ ФИО =====
@router.message(AdminStates.waiting_name)
async def get_name(message: Message, state: FSMContext):
    await state.update_data(full_name=message.text)

    await message.answer("Тип:\n/d1 /d2 /d3 /cert")
    await state.set_state(AdminStates.waiting_type)


# ===== ВЫБОР ТИПА =====
@router.message(AdminStates.waiting_type)
async def generate_pdf(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    try:
        award_map = {
            "/d1": "I",
            "/d2": "II",
            "/d3": "III",
            "/cert": "CERT"
        }

        raw = (message.text or "").strip()
        cmd = raw.split("@", 1)[0].strip()

        if cmd not in award_map:
            await message.answer("Выбери: /d1 /d2 /d3 /cert")
            return

        data = await state.get_data()
        full_name = data["full_name"]

        award = award_map[cmd]

        pdf_data = AwardData(
            full_name=full_name,
            grade=1,
            correct=25,
            total=25,
            award=award,
            doc_no="auto",
            date_str="2026"
        )

        print("PDF START ADMIN")
        generated = await asyncio.to_thread(generate_award_pdf, pdf_data)
        if isinstance(generated, tuple):
            pdf_path_str, overlay_path_str = generated
            overlay_path = Path(overlay_path_str)
        else:
            pdf_path_str = generated
            overlay_path = None
        p = Path(pdf_path_str)
        pdf_path = str(p.resolve())
        file = FSInputFile(pdf_path)
        caption = "Сертификат" if award == "CERT" else "Диплом"

        await message.answer("📄 Құжат дайындалуда...")
        for attempt in range(3):
            try:
                await message.bot.send_document(
                    chat_id=message.chat.id,
                    document=file,
                    caption=caption,
                    request_timeout=60
                )
                break
            except Exception:
                if attempt == 2:
                    raise
                await asyncio.sleep(1.5)

        if overlay_path is not None:
            try:
                overlay_path.unlink(missing_ok=True)
            except Exception:
                pass

        await state.clear()
    except Exception as e:
        print("PDF ERROR:", repr(e))
        await message.answer(f"Ошибка PDF: {e}")