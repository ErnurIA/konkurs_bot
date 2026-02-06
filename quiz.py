import asyncio
import random
import re
from typing import Dict, Any, List

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, PollAnswer

try:
    from questions import QUESTIONS
except Exception:
    QUESTIONS = {}

router = Router()

QUESTION_TIME_SEC = 90
TEST_QUESTION_COUNT = 25

# poll_id -> state
poll_map: Dict[str, Dict[str, Any]] = {}
# poll_id -> asyncio.Task
poll_tasks: Dict[str, asyncio.Task] = {}


def pick_questions(class_num: int) -> List[Dict[str, Any]]:
    pool = QUESTIONS.get(class_num, [])
    if not pool:
        return []
    if len(pool) <= TEST_QUESTION_COUNT:
        pool = pool.copy()
        random.shuffle(pool)
        return pool
    return random.sample(pool, k=TEST_QUESTION_COUNT)


def diploma_degree(score: int) -> str:
    if score >= 23:
        return "I дәрежелі диплом"
    if score >= 20:
        return "II дәрежелі диплом"
    if score >= 17:
        return "III дәрежелі диплом"
    return "Сертификат"


def clean_question_text(q: str) -> str:
    return re.sub(r"^\s*\d+\s*[\)\.]\s*", "", q).strip()


async def _cleanup_poll(poll_id: str, bot: Bot):
    state = poll_map.get(poll_id)
    if not state:
        return

    # stop timer
    task = poll_tasks.pop(poll_id, None)
    if task:
        try:
            task.cancel()
        except Exception:
            pass

    chat_id = state["chat_id"]
    poll_msg_id = state["poll_msg_id"]

    # close poll
    try:
        await bot.stop_poll(chat_id, poll_msg_id)
    except Exception:
        pass

    # delete poll message
    try:
        await bot.delete_message(chat_id, poll_msg_id)
    except Exception:
        pass

    poll_map.pop(poll_id, None)


async def send_next_question(uid: int, chat_id: int, bot: Bot, user_data: Dict[int, Dict[str, Any]]):
    st = user_data.get(uid, {})
    quiz = st.get("quiz")
    if not quiz:
        return

    idx = quiz["idx"]
    qs = quiz["questions"]
    total = len(qs)

    if idx >= total:
        score = quiz["score"]
        degree = diploma_degree(score)

        await bot.send_message(
            chat_id,
            "Тест аяқталды!\n\n"
            f"ФИО: {st.get('full_name', '')}\n"
            f"Сынып: {st.get('class', '')}\n"
            f"Дұрыс жауаптар: {score}/{total}\n"
            f"Нәтиже: {degree}"
        )
        st["stage"] = "finished"
        st.pop("quiz", None)
        return

    item = qs[idx]
    q_text = clean_question_text(item["q"])
    question = f"Сұрақ {idx + 1}/{total}\n\n{q_text}"

    # 1) send poll
    poll_msg = await bot.send_poll(
        chat_id=chat_id,
        question=question,
        options=item["a"],
        type="quiz",
        correct_option_id=item["correct"],
        is_anonymous=False,
        open_period=QUESTION_TIME_SEC,
    )

    poll_id = poll_msg.poll.id

    # 2) attach button UNDER THE POLL (edit reply markup of poll message)
    # Telegram позволяет inline-клавиатуру на poll-сообщение через edit_message_reply_markup
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Келесі сұрақ ➡️", callback_data=f"next:{poll_id}")]
    ])
    try:
        await bot.edit_message_reply_markup(chat_id=chat_id, message_id=poll_msg.message_id, reply_markup=kb)
    except Exception:
        # если клиент/ситуация не позволяет — кнопка может не прикрепиться
        pass

    poll_map[poll_id] = {
        "uid": uid,
        "chat_id": chat_id,
        "poll_msg_id": poll_msg.message_id,
        "idx": idx,
        "done": False,
    }

    # 3) timeout -> skip -> next
    async def _timeout():
        await asyncio.sleep(QUESTION_TIME_SEC)
        state = poll_map.get(poll_id)
        if not state or state["done"]:
            return

        state["done"] = True
        quiz2 = user_data.get(uid, {}).get("quiz")
        if quiz2:
            quiz2["idx"] += 1  # skip

        await _cleanup_poll(poll_id, bot)
        await send_next_question(uid, chat_id, bot, user_data)

    poll_tasks[poll_id] = asyncio.create_task(_timeout())


@router.callback_query(F.data == "start_test")
async def start_test(cb: CallbackQuery, user_data: Dict[int, Dict[str, Any]]):
    uid = cb.from_user.id
    st = user_data.get(uid)

    if not st or not st.get("class") or not st.get("full_name"):
        await cb.answer("Алдымен сынып пен ФИО енгізіңіз.", show_alert=True)
        return

    class_num = int(st["class"])
    picked = pick_questions(class_num)

    if not picked:
        await cb.message.answer("Бұл сыныпқа сұрақтар әлі қосылмаған. (questions.py керек)")
        await cb.answer()
        return

    st["stage"] = "in_test"
    st["quiz"] = {"questions": picked, "idx": 0, "score": 0}

    await cb.answer()
    await send_next_question(uid, cb.message.chat.id, cb.bot, user_data)


@router.poll_answer()
async def on_poll_answer(poll_answer: PollAnswer, bot: Bot, user_data: Dict[int, Dict[str, Any]]):
    # ДИАГНОСТИКА: если этот print не появляется в консоли — Telegram НЕ присылает poll_answer
    print("POLL_ANSWER UPDATE RECEIVED")

    uid = poll_answer.user.id
    poll_id = poll_answer.poll_id

    state = poll_map.get(poll_id)
    if not state:
        return
    if state["uid"] != uid:
        return
    if state["done"]:
        return

    state["done"] = True

    st = user_data.get(uid, {})
    quiz = st.get("quiz")
    if not quiz:
        await _cleanup_poll(poll_id, bot)
        return

    idx = state["idx"]
    qs = quiz["questions"]

    selected = poll_answer.option_ids[0] if poll_answer.option_ids else None
    correct = qs[idx]["correct"]

    if selected is not None and selected == correct:
        quiz["score"] += 1

    quiz["idx"] += 1

    await asyncio.sleep(1.2)

    await _cleanup_poll(poll_id, bot)
    await send_next_question(uid, state["chat_id"], bot, user_data)


@router.callback_query(F.data.startswith("next:"))
async def on_next(cb: CallbackQuery, user_data: Dict[int, Dict[str, Any]]):
    uid = cb.from_user.id
    poll_id = cb.data.split("next:", 1)[1]

    state = poll_map.get(poll_id)
    if not state:
        await cb.answer()
        return
    if state["uid"] != uid:
        await cb.answer()
        return
    if state["done"]:
        await cb.answer()
        return

    state["done"] = True

    st = user_data.get(uid, {})
    quiz = st.get("quiz")
    if quiz:
        quiz["idx"] += 1  # skip

    await cb.answer()
    await _cleanup_poll(poll_id, cb.bot)
    await send_next_question(uid, state["chat_id"], cb.bot, user_data)
