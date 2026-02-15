# quiz_bag.py — мешок вопросов по классам, состояние в out/

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Dict, Any, List

# Папка out/ рядом со скриптом
OUT_DIR = Path(__file__).resolve().parent / "out"
BAG_PREFIX = "quiz_bag_"


def _ensure_out_dir() -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUT_DIR


def _bag_path(grade: int) -> Path:
    _ensure_out_dir()
    return OUT_DIR / f"{BAG_PREFIX}{grade}.json"


def _normalize_grade_data(grade_data: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Приводим к ключам easy, normal, hard (medium → normal)."""
    return {
        "easy": list(grade_data.get("easy") or []),
        "normal": list(grade_data.get("normal") or grade_data.get("medium") or []),
        "hard": list(grade_data.get("hard") or []),
    }


def _build_id_to_question(normalized: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
    """Словарь id вопроса -> полный словарь вопроса (для всех уровней)."""
    by_id: Dict[str, Dict[str, Any]] = {}
    for level in ("easy", "normal", "hard"):
        for q in normalized[level]:
            qid = q.get("id")
            if qid:
                by_id[qid] = q
    return by_id


def _init_bag(normalized: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[str]]:
    """Мешок: по уровню — список id в случайном порядке."""
    bag: Dict[str, List[str]] = {
        "easy": [q["id"] for q in normalized["easy"] if q.get("id")],
        "normal": [q["id"] for q in normalized["normal"] if q.get("id")],
        "hard": [q["id"] for q in normalized["hard"] if q.get("id")],
    }
    for key in bag:
        random.shuffle(bag[key])
    return bag


def load_bag(grade: int) -> Dict[str, List[str]] | None:
    """Загрузить мешок из out/quiz_bag_{grade}.json. Если файла нет — None."""
    path = _bag_path(grade)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "easy" in data and "normal" in data and "hard" in data:
            return {
                "easy": list(data["easy"]),
                "normal": list(data["normal"]),
                "hard": list(data["hard"]),
            }
    except (json.JSONDecodeError, OSError):
        pass
    return None


def save_bag(grade: int, bag: Dict[str, List[str]]) -> None:
    """Сохранить мешок в out/quiz_bag_{grade}.json."""
    path = _bag_path(grade)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(bag, f, ensure_ascii=False, indent=0)


def ensure_bag(grade: int, normalized: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[str]]:
    """Загрузить мешок или инициализировать из банка и сохранить."""
    bag = load_bag(grade)
    if bag is not None:
        return bag
    bag = _init_bag(normalized)
    save_bag(grade, bag)
    return bag


def _refill_level(bag: Dict[str, List[str]], level: str, normalized: Dict[str, List[Dict[str, Any]]]) -> None:
    """Перемешать уровень заново из полного банка."""
    bag[level] = [q["id"] for q in normalized[level] if q.get("id")]
    random.shuffle(bag[level])


def _draw_ids(
    bag: Dict[str, List[str]],
    normalized: Dict[str, List[Dict[str, Any]]],
    n_easy: int,
    n_normal: int,
    n_hard: int,
) -> List[str]:
    """
    Взять из мешка n_easy + n_normal + n_hard id (без повторов в одной попытке).
    Если уровня не хватает — перемешать уровень заново и добирать.
    Возвращает список из 25 id (или меньше, если банк маленький).
    """
    drawn: List[str] = []

    def take(level: str, n: int) -> None:
        nonlocal drawn
        need = n
        while need > 0:
            if not bag[level]:
                _refill_level(bag, level, normalized)
            if not bag[level]:
                break
            take_count = min(need, len(bag[level]))
            for _ in range(take_count):
                drawn.append(bag[level].pop(0))
            need -= take_count

    take("easy", n_easy)
    take("normal", n_normal)
    take("hard", n_hard)

    return drawn


def draw_questions(
    grade: int,
    grade_data: Dict[str, Any],
    n_easy: int = 12,
    n_normal: int = 10,
    n_hard: int = 3,
) -> List[Dict[str, Any]]:
    """
    Выдать один набор вопросов для одной попытки: 12 easy + 10 normal + 3 hard (всего 25).
    Состояние мешка хранится в out/quiz_bag_{grade}.json.
    При нехватке уровня уровень перемешивается заново.
    Возвращает список словарей вопросов (тот же формат, что и в grade*.py).
    """
    normalized = _normalize_grade_data(grade_data)
    id_to_question = _build_id_to_question(normalized)

    bag = ensure_bag(grade, normalized)
    ids = _draw_ids(bag, normalized, n_easy, n_normal, n_hard)
    save_bag(grade, bag)

    # В одной попытке без повторов; порядок: сначала easy, потом normal, в конце hard
    seen: set = set()
    unique_ids = [qid for qid in ids if qid not in seen and not seen.add(qid)]
    questions = [id_to_question[qid] for qid in unique_ids if qid in id_to_question]
    return questions[:25]  # всегда не более 25, порядок не перемешиваем
