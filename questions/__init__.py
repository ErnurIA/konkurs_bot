# questions/__init__.py
# Динамическая загрузка grade1.py ... grade11.py, переменная в каждом: QUESTIONS_GRADE_<N>

import importlib

QUESTIONS = {}


def _load_grade(n: int):
    """Импортировать questions.grade<n>. Данные: QUESTIONS_DATA или QUESTIONS_GRADE_<n> (dict с easy/medium/hard)."""
    try:
        mod = importlib.import_module(f".grade{n}", package=__name__)
        data = getattr(mod, "QUESTIONS_DATA", None) or getattr(mod, f"QUESTIONS_GRADE_{n}", None)
        if data is not None and isinstance(data, dict):
            return data
    except Exception as e:
        try:
            from sheets_logger import log_error
            log_error("questions", f"grade{n} load failed", str(e))
        except Exception:
            pass
    return None


for _n in range(1, 12):
    _data = _load_grade(_n)
    if _data is not None:
        QUESTIONS[_n] = _data


def validate_questions(questions: dict):
    ids = set()
    for grade, grade_data in questions.items():
        for level, items in grade_data.items():
            for q in items:
                qid = q.get("id")
                if not qid:
                    continue
                if qid in ids:
                    raise ValueError(f"❌ Duplicate question ID: {qid}")
                ids.add(qid)
                if "options" not in q or len(q["options"]) != 5:
                    raise ValueError(f"❌ Invalid options count in {qid}")
                if "correct" not in q or not isinstance(q["correct"], int) or not (0 <= q["correct"] <= 4):
                    raise ValueError(f"❌ Invalid correct index in {qid}")


if QUESTIONS:
    validate_questions(QUESTIONS)
