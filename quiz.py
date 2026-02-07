import asyncio
import random
import re
from typing import Dict, Any, List, Optional

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

# Один глобальный watcher (самый надёжный способ)
_watcher_task: Optional[asyncio.Task] = None


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

    chat_id = state.get("chat_id")
    poll_msg_id = state.get("poll_msg_id")

    # close poll (на всякий случай)
    try:
        if chat_id and poll_msg_id:
            await bot.stop_poll(chat_id, poll_msg_id)
    except Exception:
        pass

    # delete poll message
    try:
        if chat_id and poll_msg_id:
            await bot.delete_message(chat_id, poll_msg_id)
    except Exception:
        pass

    poll_map.pop(poll_id, None)


async def _watch_expired(bot: Bot, user_data: Dict[int, Dict[str, Any]]):
    """Железный автопереход: каждые 1 сек проверяет истекшие вопросы."""
    try:
        while True:
            await asyncio.sleep(1)

            if not poll_map:
                continue

            now = asyncio.get_running_loop().time()
            expired = []

            for poll_id, stp in list(poll_map.items()):
                if stp.get("done"):
                    continue
                deadline = stp.get("deadline")
                if deadline is not None and now >= deadline:
                    expired.append(poll_id)

            for poll_id in expired:
                stp = poll_map.get(poll_id)
                if not stp or stp.get("done"):
                    continue

                stp["done"] = True
                uid = stp["uid"]
                chat_id = stp["chat_id"]
                idx = stp["idx"]

                st = user_data.get(uid)
                if st and st.get("quiz"):
                    quiz = st["quiz"]
                    # если пользователь всё ещё на этом вопросе — пропуск (минус)
                    if quiz.get("idx") == idx:
                        quiz["idx"] += 1

                await _cleanup_poll(poll_id, bot)
                await send_next_question(uid, chat_id, bot, user_data)

    except Exception as e:
        print("WATCHER ERROR:", repr(e))


def _ensure_watcher(bot: Bot, user_data: Dict[int, Dict[str, Any]]):
    global _watcher_task
    if _watcher_task is None or _watcher_task.done():
        _watcher_task = asyncio.create_task(_watch_expired(bot, user_data))


async def send_next_question(uid: int, chat_id: int, bot: Bot, user_data: Dict[int, Dict[str, Any]]):
    _ensure_watcher(bot, user_data)

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

    poll_msg = await bot.send_poll(
        chat_id=chat_id,
        question=question,
        options=item["a"],
        type="quiz",
        correct_option_id=item["correct"],
        is_anonymous=False,
        open_period=QUESTION_TIME_SEC,  # оставляем таймер в UI
    )

    poll_id = poll_msg.poll.id

    # Кнопка пропуска
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Келесі сұрақ ➡️", callback_data=f"next:{poll_id}")]
    ])
    try:
        await bot.edit_message_reply_markup(chat_id=chat_id, message_id=poll_msg.message_id, reply_markup=kb)
    except Exception:
        pass

    poll_map[poll_id] = {
        "uid": uid,
        "chat_id": chat_id,
        "poll_msg_id": poll_msg.message_id,
        "idx": idx,
        "done": False,
        "deadline": asyncio.get_running_loop().time() + QUESTION_TIME_SEC + 1,  # +1 запас
    }


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

    if quiz.get("idx") == idx:
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
    if quiz and quiz.get("idx") == state["idx"]:
        quiz["idx"] += 1  # skip

    await cb.answer()
    await _cleanup_poll(poll_id, cb.bot)
    await send_next_question(uid, state["chat_id"], cb.bot, user_data)
