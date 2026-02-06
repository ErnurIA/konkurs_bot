from typing import Dict, Any

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

router = Router()

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
async def start(message: Message, user_data: Dict[int, Dict[str, Any]]):
    uid = message.from_user.id

    user_data[uid] = {
        "stage": "start",
        "class": None,
        "full_name": None,
    }

    await message.answer(
        "Қош келдіңіз!\n🏆 «ҮЗДІК МАТЕМАТИК» республикалық онлайн олимпиадасы",
        reply_markup=kb_start()
    )

# -------------------
# Правила
# -------------------
@router.callback_query(F.data == "rules")
async def show_rules(cb: CallbackQuery):
    text = (
        "🏆  «ҮЗДІК МАТЕМАТИК» республикалық онлайн олимпиадасы  Қазақстан Республикасының білім алушылары "
        "арасында математикалық сауаттылықты арттыру, логикалық ойлау қабілетін дамыту және дарынды оқушыларды "
        "анықтау мақсатында «Үздік математик» республикалық онлайн олимпиадасы ұйымдастырылады.\n\n"
        "🔹 Олимпиаданың мақсаты:\n"
        "– Оқушылардың математика пәні бойынша білім деңгейін анықтау;\n"
        "– Зияткерлік әлеуетін дамыту және пәнге деген қызығушылығын арттыру;\n"
        "– Оқушылардың жеке жетістіктерін ресми құжатпен растау.\n\n"
        "👥 Қатысушылар:\n"
        "Қазақстан Республикасының 1–11 сынып оқушылары.\n\n"
        "📝 Олимпиаданы өткізу тәртібі:\n"
        "– Өткізу форматы: бір кезеңдік, онлайн;\n"
        "– Өткізу платформасы: Telegram-бот;\n"
        "– Әр сыныпқа арналған жеке тапсырмалар;\n"
        "– Тапсырмалар саны: 20–25 сұрақ;\n"
        "– Тапсырма түрі: жауап нұсқалары бар тест;\n"
        "– Әр сұраққа берілетін уақыт: 90 секунд.\n\n"
        "🏅 Қорытындылау және марапаттау:\n"
        "Олимпиада нәтижесі бойынша қатысушылар келесі марапаттарға ие болады:\n"
        "• I дәрежелі диплом – 23–25 дұрыс жауап\n"
        "• II дәрежелі диплом – 20–22 дұрыс жауап\n"
        "• III дәрежелі диплом – 17–19 дұрыс жауап\n"
        "• Сертификат – 0–16 дұрыс жауап\n\n"
        "📜 Дипломдар мен сертификаттар оқушының портфолиосына, мектепішілік және "
        "республикалық деңгейдегі жетістіктер қатарына енгізуге жарамды."
    )

    await cb.message.answer(text, reply_markup=kb_rules_end())
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
async def on_class_selected(cb: CallbackQuery, user_data: Dict[int, Dict[str, Any]]):
    uid = cb.from_user.id
    if uid not in user_data:
        user_data[uid] = {"stage": "start", "class": None, "full_name": None}

    class_num = int(cb.data.split("_")[1])
    user_data[uid]["class"] = class_num
    user_data[uid]["stage"] = "await_fullname"

    await cb.message.answer(
        "Байқауға қатысушының толық аты-жөнін жазыңыз:\n"
        "(Дипломға Сіз жазған ТАЖ жазылады)"
    )
    await cb.answer()

# -------------------
# Ввод ФИО
# -------------------
@router.message()
async def on_fullname(message: Message, user_data: Dict[int, Dict[str, Any]]):
    uid = message.from_user.id
    st = user_data.get(uid)
    if not st:
        return

    if st.get("stage") != "await_fullname":
        return

    full_name = (message.text or "").strip()
    if len(full_name) < 5:
        await message.answer("Толық аты-жөніңізді дұрыс жазыңыз (кемінде 5 таңба).")
        return

    st["full_name"] = full_name
    st["stage"] = "ready_for_test"

    await message.answer(
        "Деректер қабылданды. Тестті бастауға болады:",
        reply_markup=kb_start_test()
    )
