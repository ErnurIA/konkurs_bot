"""
Запись результатов теста в Google Sheets.
Таблица: по SPREADSHEET_ID из .env (из URL https://docs.google.com/spreadsheets/d/<ID>/edit)
или по названию SPREADSHEET_NAME.
"""
import os
import gspread
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
from google.oauth2.service_account import Credentials

load_dotenv()

SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Путь к ключу: корень проекта (рядом с bot.py и sheets_logger.py)
_CREDS_PATH = Path(__file__).resolve().parent / "google_credentials.json"
SPREADSHEET_NAME = "konkurs_bot_results"


def _get_client():
    creds = Credentials.from_service_account_file(str(_CREDS_PATH), scopes=SCOPE)
    return gspread.authorize(creds)


def test_sheets_connection():
    """Проверка подключения: открывает таблицу и возвращает название первого листа. Не вызывать автоматически."""
    sheet = get_sheet()
    return sheet.title


def _get_spreadsheet():
    client = _get_client()
    spreadsheet_id = os.environ.get("SPREADSHEET_ID", "").strip()
    if spreadsheet_id:
        return client.open_by_key(spreadsheet_id)
    return client.open(SPREADSHEET_NAME)


def _get_errors_sheet():
    """Лист 'errors' для логов ошибок (создаётся при первом обращении)."""
    spreadsheet = _get_spreadsheet()
    try:
        return spreadsheet.worksheet("errors")
    except gspread.WorksheetNotFound:
        return spreadsheet.add_worksheet(title="errors", rows=1000, cols=10)


def log_error(module: str, message: str, detail: str = ""):
    """Записать ошибку в Google Sheets (лист 'errors'). Не роняет бот при сбое."""
    try:
        sheet = _get_errors_sheet()
        row = [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            str(module),
            str(message)[:500],
            str(detail)[:500],
        ]
        sheet.append_row(row)
    except Exception as e:
        print("Sheets log_error failed:", e)


def get_sheet():
    return _get_spreadsheet().sheet1


def save_result(tg_id, username, full_name, grade, score, total, award, pdf_file, errors_text=""):
    sheet = get_sheet()
    # Колонки A–I (1–9): дата, tg_id, username, full_name, grade, score, total, award, pdf_file
    # Колонка J (10): errors_text — детализация ошибок ученика
    row = [
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        str(tg_id) if tg_id is not None else "",
        str(username) if username else "",
        str(full_name) if full_name else "",
        str(grade) if grade is not None else "",
        int(score) if score is not None else 0,
        int(total) if total is not None else 0,
        str(award) if award else "",
        str(pdf_file) if pdf_file else "",
        str(errors_text) if errors_text else "",
    ]
    sheet.append_row(row)
