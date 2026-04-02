"""
Запись результатов теста в Google Sheets.
Таблица: по SPREADSHEET_ID из .env (из URL https://docs.google.com/spreadsheets/d/<ID>/edit)
или по названию SPREADSHEET_NAME.
"""
import os
import traceback
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


def _get_codes_sheet():
    """Лист 'CODES' для кодов доступа (создаётся при первом обращении). Колонки: CODE, STATUS, CREATED_AT, USED_BY, USED_AT."""
    spreadsheet = _get_spreadsheet()
    try:
        return spreadsheet.worksheet("CODES")
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title="CODES", rows=1000, cols=5)
        ws.append_row(["CODE", "STATUS", "CREATED_AT", "USED_BY", "USED_AT"])
        return ws


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


def append_codes(codes: list, created_at: str):
    """Добавить коды на лист CODES: каждая строка CODE | NEW | created_at | пусто | пусто. Не роняет бот при сбое."""
    if not codes:
        return
    try:
        sheet = _get_codes_sheet()
        created_at_str = created_at if isinstance(created_at, str) else datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        rows = [[c, "NEW", created_at_str, "", ""] for c in codes]
        sheet.append_rows(rows, value_input_option="USER_ENTERED")
    except Exception as e:
        print("Sheets append_codes failed:", e)


def update_code_used(code: str, user_id: int, used_at: str):
    """Найти код на листе CODES, выставить STATUS=USED, USED_BY, USED_AT, оформить строку красным и зачёркнутым. Не роняет бот при сбое."""
    try:
        sheet = _get_codes_sheet()
        cell = sheet.find(code, in_column=1)
        row = cell.row
        sheet.update_cell(row, 2, "USED")
        sheet.update_cell(row, 4, str(user_id))
        sheet.update_cell(row, 5, used_at)
        sheet.format(
            f"A{row}:E{row}",
            {"textFormat": {"foregroundColor": {"red": 1, "green": 0, "blue": 0}, "strikethrough": True}},
        )
    except Exception as e:
        print("Sheets update_code_used failed:", e)


def get_sheet():
    return _get_spreadsheet().sheet1


def save_result(tg_id, username, full_name, grade, score, total, award, pdf_file, errors_text=""):
    try:
        if "Сертификат" in award:
            sheet = _get_spreadsheet().worksheet("Сертификат")
        else:
            sheet = get_sheet()
        print("SHEET OPENED:", sheet.title)
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
        print("APPEND SUCCESS")
    except Exception:
        print("SAVE_RESULT ERROR")
        traceback.print_exc()
        raise


def test_google_sheets():
    print("TEST START")
    sid = os.environ.get("SPREADSHEET_ID", "").strip()
    print("SPREADSHEET_ID:", sid)

    # Тот же файл, что и у бота: корень проекта (рядом с bot.py)
    creds = Credentials.from_service_account_file(
        str(_CREDS_PATH),
        scopes=SCOPE,
    )
    client = gspread.authorize(creds)

    if sid:
        sheet = client.open_by_key(sid).sheet1
    else:
        sheet = client.open(SPREADSHEET_NAME).sheet1

    sheet.append_row(["TEST"])
    print("APPEND SUCCESS")


if __name__ == "__main__":
    test_google_sheets()
