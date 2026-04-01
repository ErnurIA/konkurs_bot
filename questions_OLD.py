# questions.py
# Центральный сборщик и валидатор вопросов

from questions.grade1 import QUESTIONS_GRADE_1
# позже добавим:
# from questions.grade2 import QUESTIONS_GRADE_2
# ...
# from questions.grade11 import QUESTIONS_GRADE_11


def validate_questions(questions: dict):
    """
    Жёсткая валидация:
    - уникальность id
    - ровно 5 вариантов ответа
    - correct в диапазоне 0–4
    """

    ids = set()

    for grade, grade_data in questions.items():
        for level, items in grade_data.items():
            for q in items:
                qid = q["id"]

                # 1. Проверка уникальности ID
                if qid in ids:
                    raise ValueError(f"❌ Duplicate question ID: {qid}")
                ids.add(qid)

                # 2. Проверка количества вариантов
                if "options" not in q or len(q["options"]) != 5:
                    raise ValueError(f"❌ Invalid options count in {qid}")

                # 3. Проверка correct
                if "correct" not in q or not isinstance(q["correct"], int) or not (0 <= q["correct"] <= 4):
                    raise ValueError(f"❌ Invalid correct index in {qid}")


QUESTIONS = {
    1: QUESTIONS_GRADE_1,
    # 2: QUESTIONS_GRADE_2,
    # ...
    # 11: QUESTIONS_GRADE_11,
}

# Автопроверка при старте проекта
validate_questions(QUESTIONS)
if __name__ == "__main__":
    from pprint import pprint

    grade = 1
    data = QUESTIONS[grade]["easy"]

    print(f"Easy questions count: {len(data)}")
    pprint(data)
