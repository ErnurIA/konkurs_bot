import asyncio
from typing import Dict, Any
import re

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

router = Router()


class Form(StatesGroup):
    waiting_name = State()
    waiting_phone = State()

# -------------------
# Кнопки
# -------------------
def kb_start() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Олимпиада шартымен танысу", callback_data="rules")]
    ])

def kb_rules_end() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Байқауға қатысу", callback_data="join")]
    ])

def kb_choose_class() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=str(i), callback_data=f"class_{i}") for i in range(1, 5)],
        [InlineKeyboardButton(text=str(i), callback_data=f"class_{i}") for i in range(5, 9)],
        [InlineKeyboardButton(text=str(i), callback_data=f"class_{i}") for i in range(9, 12)],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_start_test() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Тестті бастау", callback_data="start_test")]
    ])

# -------------------
# /start
# -------------------
@router.message(CommandStart())
async def start(message: Message, state: FSMContext, user_data: Dict[int, Dict[str, Any]]):
    uid = message.from_user.id
    await state.clear()

    user_data[uid] = {
        "stage": "start",
        "class": None,
        "full_name": None,
    }

    await message.answer(
        "Қош келдіңіз!\n🏆 «ЗЕРДЕ» республикалық дарынды оқушылар олимпиадасы",
        reply_markup=kb_start()
    )

# -------------------
# Правила
# -------------------
@router.callback_query(F.data == "rules")
async def show_rules(cb: CallbackQuery):
    text = (
        "🏆 «ЗЕРДЕ» республикалық дарынды оқушылар олимпиадасы\n\n"
        "🔹 ҚАТЫСУ ТЕГІН\n"
        "🔹 Олимпиада бағыты: математика\n\n"
        "🎯 Олимпиаданың мақсаты:\n"
        "<blockquote>\n"
        "• Қазақстан Республикасының білім алушылары арасында математика пәні бойынша білім деңгейін бағалау және математикалық сауаттылықты арттыру;\n"
        "• Оқушылардың логикалық ойлау қабілетін дамыту және математика пәні бойынша дарынды оқушыларды анықтау;\n"
        "• Математикалық тапсырмаларды талдау және дұрыс шешім қабылдау дағдыларын қалыптастыру;\n"
        "• Оқушылардың зияткерлік әлеуетін дамыту және математика пәніне деген қызығушылығын арттыру;\n"
        "• Олимпиада нәтижелері арқылы оқушылардың жеке жетістіктерін айқындау және оларды ресми құжаттармен растау.\n"
        "</blockquote>\n\n"
        "👥 Қатысушылар:\n"
        "Қазақстан Республикасының 1–11 сынып оқушылары.\n\n"
        "📝 Олимпиаданы өткізу тәртібі:\n"
        "- Өткізу форматы: бір кезеңдік, онлайн;\n"
        "- Өткізу платформасы: Telegram-бот;\n"
        "- Әр сыныпқа арналған жеке тапсырмалар;\n"
        "- Тапсырмалар саны: 25 сұрақ;\n"
        "- Тапсырма түрі: жауап нұсқалары бар тест;\n"
        "- Әр сұраққа берілетін уақыт: 90 секунд.\n\n"
        "🏅 Қорытындылау және марапаттау:\n"
        "Олимпиада нәтижесі бойынша қатысушылар келесі марапаттарға ие болады:\n"
        "<blockquote>\n"
        "• I дәрежелі диплом: 23–25 дұрыс жауап\n"
        "• II дәрежелі диплом: 20–22 дұрыс жауап\n"
        "• III дәрежелі диплом: 17–19 дұрыс жауап\n"
        "• Сертификат: 0–16 дұрыс жауап\n"
        "</blockquote>\n\n"
        " ✅ Дипломдар мен сертификаттар педагогтердің аттестаттаудан өтуіне жарамды."
    )

    await cb.message.answer(text, reply_markup=kb_rules_end(), parse_mode="HTML")
    await cb.answer()

# -------------------
# Байқауға қатысу → выбор класса
# -------------------
@router.callback_query(F.data == "join")
async def join(cb: CallbackQuery):
    await cb.message.answer("Сыныбыңызды таңдаңыз:", reply_markup=kb_choose_class())
    await cb.answer()

# -------------------
# Выбор класса
# -------------------
@router.callback_query(F.data.startswith("class_"))
async def on_class_selected(cb: CallbackQuery, state: FSMContext, user_data: Dict[int, Dict[str, Any]]):
    uid = cb.from_user.id
    if uid not in user_data:
        user_data[uid] = {"stage": "start", "class": None, "full_name": None}

    class_num = int(cb.data.split("_")[1])
    user_data[uid]["class"] = class_num
    user_data[uid]["stage"] = "await_fullname"

    await state.set_state(Form.waiting_name)
    await cb.message.answer(
        "Байқауға қатысушының толық аты-жөнін жазыңыз:\n"
        "(Дипломға Сіз жазған ТАЖ жазылады)"
    )
    await cb.answer()


# -------------------
# ФИО → WhatsApp нөмірі → тест
# -------------------
@router.message(Form.waiting_name, F.text & ~F.text.startswith("/"))
async def get_name(message: Message, state: FSMContext, user_data: Dict[int, Dict[str, Any]]):
    uid = message.from_user.id
    st = user_data.get(uid)
    if not st:
        user_data[uid] = {"stage": "start", "class": None, "full_name": None}
        st = user_data[uid]

    full_name = (message.text or "").strip()
    if len(full_name) < 5:
        await message.answer("Толық аты-жөніңізді дұрыс жазыңыз (кемінде 5 таңба).")
        return
    st["full_name"] = full_name
    await message.answer("Ата-ананың немесе жетекшінің WhatsApp нөмірін жазыңыз:")
    await state.set_state(Form.waiting_phone)


@router.message(Form.waiting_phone, F.text & ~F.text.startswith("/"))
async def get_phone(message: Message, state: FSMContext, user_data: Dict[int, Dict[str, Any]]):
    uid = message.from_user.id
    st = user_data.get(uid)
    if not st:
        await state.clear()
        return

    phone = re.sub(r"\D", "", message.text or "")
    st["phone"] = phone
    st["stage"] = "ready_for_test"
    await message.answer("Деректер қабылданды. Тестті бастауға болады", reply_markup=kb_start_test())
    await state.clear()


# -------------------
# Ввод ФИО и проверка кода доступа
# -------------------
@router.message(F.text & ~F.text.startswith("/"))
async def on_fullname(message: Message, user_data: Dict[int, Dict[str, Any]]):
    uid = message.from_user.id
    st = user_data.get(uid)

    # Проверка одноразового кода (любое сообщение 8 символов A-Z/0-9)
    raw = (message.text or "").strip().upper()
    if re.fullmatch(r"[A-Z0-9]{8}", raw):
        from access_control import activate_code
        from services.codes_sheet import mark_code_used
        ok, msg = activate_code(uid, raw)
        if ok:
            await asyncio.to_thread(mark_code_used, raw, uid)
        await message.answer(msg)
