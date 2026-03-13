"""
Подключение системы кодов доступа к Google Sheets (лист codes).
Структура: A=code, B=attempts, C=used, D=user_id, E=used_at.
Использует тот же google_credentials.json, что и sheets_logger.
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

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CREDS_PATH = _PROJECT_ROOT / "google_credentials.json"
SPREADSHEET_NAME = "konkurs_bot_results"
SHEET_NAME = "codes"


def _get_client():
    creds = Credentials.from_service_account_file(str(_CREDS_PATH), scopes=SCOPE)
    return gspread.authorize(creds)


def _get_spreadsheet():
    client = _get_client()
    spreadsheet_id = os.environ.get("SPREADSHEET_ID", "").strip()
    if spreadsheet_id:
        return client.open_by_key(spreadsheet_id)
    return client.open(SPREADSHEET_NAME)


def connect_sheet():
    """
    Возвращает лист 'codes'. Если листа нет — создаёт с заголовками:
    code | attempts | used | user_id | used_at
    """
    try:
        spreadsheet = _get_spreadsheet()
        try:
            return spreadsheet.worksheet(SHEET_NAME)
        except gspread.WorksheetNotFound:
            ws = spreadsheet.add_worksheet(title=SHEET_NAME, rows=1000, cols=5)
            ws.append_row(["code", "attempts", "used", "user_id", "used_at"])
            return ws
    except Exception as e:
        print("codes_sheet connect_sheet failed:", e)
        return None


def add_codes_to_sheet(codes):
    """
    Добавляет коды на лист codes.
    Каждая строка: code | 1 | FALSE | | 
    Не блокирует бота, логирует ошибки.
    """
    if not codes:
        return
    try:
        sheet = connect_sheet()
        if not sheet:
            return
        rows = [[c, 1, "FALSE", "", ""] for c in codes]
        sheet.append_rows(rows, value_input_option="USER_ENTERED")
    except Exception as e:
        print("codes_sheet add_codes_to_sheet failed:", e)


def mark_code_used(code: str, user_id: int):
    """
    Находит строку с code в колонке A, обновляет:
    used = TRUE, user_id = telegram id, used_at = текущее время ISO.
    Не блокирует бота, логирует ошибки.
    """
    try:
        sheet = connect_sheet()
        if not sheet:
            return
        cell = sheet.find(code.strip().upper(), in_column=1)
        row = cell.row
        used_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
        sheet.update_cell(row, 3, "TRUE")
        sheet.update_cell(row, 4, str(user_id))
        sheet.update_cell(row, 5, used_at)
    except gspread.exceptions.CellNotFound:
        print("codes_sheet mark_code_used: code not found in sheet:", code)
    except Exception as e:
        print("codes_sheet mark_code_used failed:", e)
