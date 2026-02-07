# questions.py
# Формат: QUESTIONS[класс] = список вопросов
# Каждый вопрос:
# {
#   "q": "текст вопроса",
#   "a": ["вариант1","вариант2","вариант3","вариант4","вариант5"],
#   "correct": индекс_правильного (0–4)
# }

QUESTIONS = {
    1: [
        {
            "q": "1) 5 + 3 = ?",
            "a": ["6", "7", "8", "9", "10"],
            "correct": 2
        },
        {
            "q": "2) 9 - 3 = ?",
            "a": ["4", "5", "6", "7", "8"],
            "correct": 2
        },
    ],

    2: [],
    3: [],
    4: [],
    5: [],
    6: [],
    7: [],
    8: [],
    9: [],
    10: [],
    11: [],
}

if __name__ == "__main__":
    total = sum(len(v) for v in QUESTIONS.values())
    print("TOTAL:", total)

    # Проверка структуры
    for grade, qs in QUESTIONS.items():
        for i, it in enumerate(qs, 1):
            assert "q" in it and "a" in it and "correct" in it
            assert isinstance(it["a"], list) and len(it["a"]) == 5
            assert isinstance(it["correct"], int) and 0 <= it["correct"] <= 4

    print("OK")
