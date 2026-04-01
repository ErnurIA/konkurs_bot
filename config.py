# Общие настройки бота (чтобы не дублировать ID в Admin.py и bot.py)
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Несколько ID через запятую: "123,456" или один. Переопредели на сервере через .env
_raw = os.getenv("ADMIN_TELEGRAM_IDS", "573722456").strip()
ADMIN_IDS = [int(x.strip()) for x in _raw.split(",") if x.strip()]
