# access_control.py — ограничение попыток и одноразовые коды доступа

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List

DEFAULT_ATTEMPTS = 1
BONUS_PER_CODE = 1
DB_DIR = Path(__file__).resolve().parent / "data"
DB_PATH = DB_DIR / "access.db"


def _get_conn() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_access_db() -> None:
    """Создаёт data/access.db и таблицы user_limits, access_codes."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = _get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_limits (
                user_id INTEGER PRIMARY KEY,
                used_attempts INTEGER NOT NULL DEFAULT 0,
                bonus_attempts INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS access_codes (
                code TEXT PRIMARY KEY,
                bonus_attempts INTEGER NOT NULL,
                is_used INTEGER NOT NULL DEFAULT 0,
                used_by INTEGER,
                used_at TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()
    finally:
        conn.close()


def _now_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _ensure_user(conn: sqlite3.Connection, user_id: int) -> None:
    row = conn.execute(
        "SELECT 1 FROM user_limits WHERE user_id = ?", (user_id,)
    ).fetchone()
    if not row:
        now = _now_iso()
        conn.execute(
            "INSERT INTO user_limits (user_id, used_attempts, bonus_attempts, created_at, updated_at) VALUES (?, 0, 0, ?, ?)",
            (user_id, now, now),
        )


def can_take_test(user_id: int) -> bool:
    """
    Проверяет, может ли пользователь начать тест.
    allowed_attempts = DEFAULT_ATTEMPTS (1) + bonus_attempts.
    """
    conn = _get_conn()
    try:
        _ensure_user(conn, user_id)
        conn.commit()
        row = conn.execute(
            "SELECT used_attempts, bonus_attempts FROM user_limits WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            return True
        total_allowed = DEFAULT_ATTEMPTS + row["bonus_attempts"]
        return row["used_attempts"] < total_allowed
    finally:
        conn.close()


def use_attempt(user_id: int) -> None:
    """Списывает одну попытку у пользователя."""
    conn = _get_conn()
    try:
        _ensure_user(conn, user_id)
        conn.commit()
        now = _now_iso()
        conn.execute(
            "UPDATE user_limits SET used_attempts = used_attempts + 1, updated_at = ? WHERE user_id = ?",
            (now, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_user_limit_info(user_id: int) -> dict:
    """Возвращает used_attempts, bonus_attempts и общий лимит для пользователя."""
    conn = _get_conn()
    try:
        _ensure_user(conn, user_id)
        conn.commit()
        row = conn.execute(
            "SELECT used_attempts, bonus_attempts FROM user_limits WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            return {"used_attempts": 0, "bonus_attempts": 0, "total_allowed": DEFAULT_ATTEMPTS}
        total = DEFAULT_ATTEMPTS + row["bonus_attempts"]
        return {
            "used_attempts": row["used_attempts"],
            "bonus_attempts": row["bonus_attempts"],
            "total_allowed": total,
        }
    finally:
        conn.close()


def activate_code(user_id: int, code: str) -> Tuple[bool, str]:
    """
    Активирует одноразовый код для пользователя.
    Возвращает (успех, сообщение для пользователя).
    """
    code = (code or "").strip().upper()
    if not code:
        return False, "Код жарамсыз немесе бұрын пайдаланылған."

    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT code, bonus_attempts, is_used FROM access_codes WHERE code = ?",
            (code,),
        ).fetchone()
        if not row:
            return False, "Код жарамсыз немесе бұрын пайдаланылған."
        if row["is_used"]:
            return False, "Код жарамсыз немесе бұрын пайдаланылған."

        _ensure_user(conn, user_id)
        now = _now_iso()
        conn.execute(
            "UPDATE access_codes SET is_used = 1, used_by = ?, used_at = ? WHERE code = ?",
            (user_id, now, code),
        )
        conn.execute(
            "UPDATE user_limits SET bonus_attempts = bonus_attempts + ?, updated_at = ? WHERE user_id = ?",
            (row["bonus_attempts"], now, user_id),
        )
        conn.commit()
        n = int(row["bonus_attempts"])
        return True, f"Сізге қосымша {n} мүмкіндік берілді."
    finally:
        conn.close()


def create_access_codes(count: int, bonus_attempts: int = BONUS_PER_CODE) -> List[str]:
    """
    Генерирует count одноразовых кодов (8 символов A-Z + цифры), сохраняет в БД.
    Возвращает список созданных кодов.
    """
    import random
    import string
    chars = string.ascii_uppercase + string.digits
    codes = []
    conn = _get_conn()
    try:
        now = _now_iso()
        for _ in range(count):
            while True:
                code = "".join(random.choices(chars, k=8))
                if code not in codes:
                    try:
                        conn.execute(
                            "INSERT INTO access_codes (code, bonus_attempts, is_used, created_at) VALUES (?, ?, 0, ?)",
                            (code, bonus_attempts, now),
                        )
                        codes.append(code)
                        break
                    except sqlite3.IntegrityError:
                        continue
        conn.commit()
        return codes
    finally:
        conn.close()
