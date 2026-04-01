# quiz.py
from __future__ import annotations

import asyncio
import random
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

from aiogram import Router, F, Bot
from aiogram.types import (
    CallbackQuery,
    PollAnswer,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
)

from pdf_utils import AwardData, award_from_score, generate_award_pdf
from sheets_logger import save_result

try:
    from questions import QUESTIONS
except Exception:
    QUESTIONS = {}

router = Router()

QUESTION_TIME_SEC = 90
TEST_QUESTION_COUNT = 25

# poll_id -> state
poll_map: Dict[str, Dict[str, Any]] = {}

# Один глобальный watcher (автопереход по таймеру)
_watcher_task: Optional[asyncio.Task] = None


def pick_questions(class_num: int) -> List[Dict[str, Any]]:
    """
    Формат QUESTIONS: { class_num: {"easy": [...], "medium": [...], "hard": [...]} }.
    Схема 10-12-3: перемешиваем каждую категорию, берём первые 10 easy, 12 medium, 3 hard.
    Порядок в тесте: сначала лёгкие, потом средние, в конце сложные (всего 25).
    При нехватке вопросов в категории берётся min(нужно, len(списка)) — бот не падает.
    """
    grade = QUESTIONS.get(class_num)
    if not grade or not isinstance(grade, dict):
        return []

    easy = list(grade.get("easy") or [])
    medium = list(grade.get("medium") or [])
    hard = list(grade.get("hard") or [])

    if not easy and not medium and not hard:
        return []

    random.shuffle(easy)
    random.shuffle(medium)
    random.shuffle(hard)

    n_easy = min(10, len(easy))
    n_med = min(12, len(medium))
    n_hard = min(3, len(hard))

    selected: List[Dict[str, Any]] = []
    selected += easy[:n_easy]
    selected += medium[:n_med]
    selected += hard[:n_hard]

    return selected


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
            expired: List[str] = []

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
                    if quiz.get("idx") == idx:
                        qs = quiz["questions"]
                        if idx < len(qs):
                            item = qs[idx]
                            question_num = idx + 1  # номер вопроса в сессии (1..25)
                            q_text = clean_question_text(item.get("question") or item.get("q", ""))
                            correct_text = item["options"][item["correct"]]
                            quiz.setdefault("user_errors", []).append(
                                f"{question_num}. {q_text} | О: Уақыт аяқталды | Пр: {correct_text}"
                            )
                        quiz["idx"] += 1

                await _cleanup_poll(poll_id, bot)
                await send_next_question(uid, chat_id, bot, user_data)

    except Exception as e:
        print("WATCHER ERROR:", repr(e))


def _ensure_watcher(bot: Bot, user_data: Dict[int, Dict[str, Any]]):
    global _watcher_task
    if _watcher_task is None or _watcher_task.done():
        _watcher_task = asyncio.create_task(_watch_expired(bot, user_data))


async def _send_award_pdf(
    chat_id: int,
    uid: int,
    st: Dict[str, Any],
    score: int,
    total: int,
    bot: Bot,
):
    """
    Генерирует и отправляет PDF по готовым шаблонам:
    assets/templates/diploma_I.pdf, diploma_II.pdf, diploma_III.pdf, certificate.pdf
    Пишет ФИО на стр.1 и стр.2 (если есть).
    """
    award_code = award_from_score(score)  # "I" | "II" | "III" | "CERT"

    data = AwardData(
        full_name=st.get("full_name", ""),
        grade=int(st.get("class")),
        correct=score,
        total=total,
        award=award_code,
        doc_no=str(uid),  # временно tg_id как номер
        date_str=datetime.now().strftime("%d.%m.%Y"),
    )

    pdf_path_str, overlay_path_str = await asyncio.to_thread(
        generate_award_pdf, data
    )
    pdf_path = Path(pdf_path_str)
    overlay_path = Path(overlay_path_str)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if pdf_path.stat().st_size == 0:
        raise RuntimeError(f"PDF empty: {pdf_path}")

    await asyncio.sleep(0.3)

    doc = FSInputFile(path=str(pdf_path), filename=pdf_path.name)
    caption = "Сертификат" if award_from_score(score) == "CERT" else "Диплом"
    for attempt in range(3):
        try:
            await bot.send_document(
                chat_id=chat_id,
                document=doc,
                caption=caption,
            )
            break
        except Exception:
            if attempt == 2:
                raise
            await asyncio.sleep(1.5)
    try:
        pdf_path.unlink(missing_ok=True)
    except Exception:
        pass
    try:
        overlay_path.unlink(missing_ok=True)
    except Exception:
        pass
    return pdf_path.name


async def send_next_question(uid: int, chat_id: int, bot: Bot, user_data: Dict[int, Dict[str, Any]]):
    _ensure_watcher(bot, user_data)

    st = user_data.get(uid, {})
    quiz = st.get("quiz")
    if not quiz:
        return

    idx = quiz["idx"]
    qs = quiz["questions"]
    total = len(qs)

    # ======== КОНЕЦ ТЕСТА ========
    if idx >= total:
        score = quiz["score"]
        award_code = award_from_score(score)

        if award_code == "I":
            result_text = "I дәрежелі Диплом"
            wait_text = "Диплом 1 минут аралығында келеді"
        elif award_code == "II":
            result_text = "II дәрежелі Диплом"
            wait_text = "Диплом 1 минут аралығында келеді"
        elif award_code == "III":
            result_text = "III дәрежелі Диплом"
            wait_text = "Диплом 1 минут аралығында келеді"
        else:
            result_text = "Сертификат"
            wait_text = "Сертификат 1 минут аралығында келеді"

        # 1) сначала итоговое сообщение
        await bot.send_message(
            chat_id,
            "✅ Тест аяқталды!\n\n"
            f"ФИО: {st.get('full_name', '')}\n"
            f"Сынып: {st.get('class', '')}\n"
            f"Дұрыс жауаптар: {score}/{total}\n"
            f"Нәтиже: {result_text}\n\n"
            f"{wait_text}"
        )

        # 2) потом PDF
        try:
            pdf_filename = await _send_award_pdf(chat_id=chat_id, uid=uid, st=st, score=score, total=total, bot=bot)
            # Запись в Google Sheets только после успешной отправки PDF
            errors_text = "\n".join(quiz.get("user_errors", [])) if quiz.get("user_errors") else "Ошибок нет"
            try:
                await asyncio.to_thread(
                    save_result,
                    tg_id=uid,
                    username=st.get("username", ""),
                    full_name=st.get("full_name", ""),
                    grade=st.get("class", ""),
                    score=score,
                    total=total,
                    award=result_text,
                    pdf_file=pdf_filename,
                    errors_text=errors_text,
                )
            except Exception as e:
                import traceback
                print("Sheets save error:", e)
                traceback.print_exc()
        except Exception as e:
            print("PDF ERROR:", repr(e))
            await bot.send_message(chat_id, "⚠️ PDF жіберу кезінде қате шықты.")

        st["stage"] = "finished"
        st.pop("quiz", None)
        return

    # ======== СЛЕД. ВОПРОС ========
    item = qs[idx]

    q_text = clean_question_text(item.get("question") or item.get("q", ""))
    question = f"Сұрақ {idx + 1}/{total}\n\n{q_text}"

    poll_msg = await bot.send_poll(
        chat_id=chat_id,
        question=question,
        options=item["options"],
        type="quiz",
        correct_option_id=item["correct"],
        is_anonymous=False,
        open_period=QUESTION_TIME_SEC,  # таймер в UI
    )

    poll_id = poll_msg.poll.id

    # Кнопка пропуска
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Келесі сұрақ ➡️", callback_data=f"next:{poll_id}")]
    ])
    try:
        await bot.edit_message_reply_markup(
            chat_id=chat_id,
            message_id=poll_msg.message_id,
            reply_markup=kb
        )
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
    from access_control import can_take_test, use_attempt

    uid = cb.from_user.id
    st = user_data.get(uid)

    if not st or not st.get("class") or not st.get("full_name"):
        await cb.answer("Алдымен сынып пен ФИО енгізіңіз.", show_alert=True)
        return

    if not can_take_test(uid):
        await cb.message.answer(
            "Сіз бұл тестті тапсырдыңыз.\n"
            "Қосымша мүмкіндік алу үшін ұйымдастырушыларға WhatsApp қа жазыңыз.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="WhatsApp", url="https://wa.me/77082443606?text=")]
            ]),
        )
        await cb.answer()
        return

    class_num = int(st["class"])
    picked = pick_questions(class_num)

    if not picked:
        await cb.message.answer("Бұл сыныпқа сұрақтар әлі қосылмаған. (questions.py керек)")
        await cb.answer()
        return

    use_attempt(uid)
    st["stage"] = "in_test"
    st["quiz"] = {"questions": picked, "idx": 0, "score": 0, "user_errors": []}

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
    item = qs[idx]

    selected = poll_answer.option_ids[0] if poll_answer.option_ids else None
    correct = item["correct"]

    if selected is not None and selected == correct:
        quiz["score"] += 1
    else:
        question_num = idx + 1  # номер вопроса в сессии (1..25)
        q_text = clean_question_text(item.get("question") or item.get("q", ""))
        user_answer_text = item["options"][selected] if selected is not None else "Жауап берілмеді"
        correct_text = item["options"][correct]
        quiz.setdefault("user_errors", []).append(
            f"{question_num}. {q_text} | О: {user_answer_text} | Пр: {correct_text}"
        )

    if quiz.get("idx") == idx:
        quiz["idx"] += 1

    await asyncio.sleep(0.6)

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
        idx = state["idx"]
        qs = quiz["questions"]
        if idx < len(qs):
            item = qs[idx]
            question_num = idx + 1  # номер вопроса в сессии (1..25)
            q_text = clean_question_text(item.get("question") or item.get("q", ""))
            correct_text = item["options"][item["correct"]]
            quiz.setdefault("user_errors", []).append(
                f"{question_num}. {q_text} | О: Пропуск | Пр: {correct_text}"
            )
        quiz["idx"] += 1  # skip (минус)

    await cb.answer()
    await _cleanup_poll(poll_id, cb.bot)
    await send_next_question(uid, state["chat_id"], cb.bot, user_data)
