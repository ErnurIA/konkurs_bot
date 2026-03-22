from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from pypdf import PdfReader, PdfWriter


# ================== BASE DIR ==================
BASE_DIR = Path(__file__).resolve().parent


# ================== DATA ==================
@dataclass
class AwardData:
    full_name: str
    grade: int
    correct: int
    total: int
    award: str          # "I" | "II" | "III" | "CERT"
    doc_no: str         # больше не используется как номер
    date_str: str


def award_from_score(score: int) -> str:
    if score >= 23:
        return "I"
    if score >= 20:
        return "II"
    if score >= 17:
        return "III"
    return "CERT"


# ================== PATHS ==================
TEMPLATE_MAP = {
    "I": BASE_DIR / "assets/templates/diploma_I.pdf",
    "II": BASE_DIR / "assets/templates/diploma_II.pdf",
    "III": BASE_DIR / "assets/templates/diploma_III.pdf",
    "CERT": BASE_DIR / "assets/templates/certificate.pdf",
}


def _template_path(award: str) -> Path:
    if award not in TEMPLATE_MAP:
        raise ValueError(f"Unknown award code: {award}")
    path = TEMPLATE_MAP[award]
    if not path.exists():
        raise FileNotFoundError(f"Template not found: {path}")
    return path


# ================== FONT ==================
_FONT_REGISTERED = False


def _register_font() -> str:
    global _FONT_REGISTERED

    font_path = BASE_DIR / "assets/fonts/timesbd.ttf"
    if not font_path.exists():
        raise FileNotFoundError(f"Font not found: {font_path}")

    if not _FONT_REGISTERED:
        pdfmetrics.registerFont(TTFont("TimesNewRomanBold", str(font_path)))
        _FONT_REGISTERED = True

    return "TimesNewRomanBold"


def _register_number_font() -> str:
    from reportlab.pdfbase import pdfmetrics as _pm
    from reportlab.pdfbase.ttfonts import TTFont as _TTFont

    font_path = BASE_DIR / "assets/fonts/times.ttf"

    if not font_path.exists():
        raise FileNotFoundError("times.ttf not found in assets/fonts")

    try:
        _pm.getFont("TimesNewRoman")
    except Exception:
        _pm.registerFont(_TTFont("TimesNewRoman", str(font_path)))

    return "TimesNewRoman"


# ================== COUNTER ==================
COUNTER_FILE = BASE_DIR / "counter.json"


def _load_counter():
    if not COUNTER_FILE.exists():
        data = {"diploma": 1, "certificate": 1}
        COUNTER_FILE.write_text(json.dumps(data))
        return data
    return json.loads(COUNTER_FILE.read_text())


def _save_counter(data):
    COUNTER_FILE.write_text(json.dumps(data))


def _get_next_number(award: str) -> int:
    data = _load_counter()

    if award == "CERT":
        num = data["certificate"]
        data["certificate"] += 1
    else:
        num = data["diploma"]
        data["diploma"] += 1

    _save_counter(data)
    return num


# ================== OVERLAY ==================
# Шаблоны: 1-я страница диплома и сертификата — альбом A4 (297×210 мм),
# 2-я страница диплома — книжный A4 (210×297 мм). Оверлей должен совпадать по формату.
LANDSCAPE_A4 = landscape(A4)
NAME_FONT_SIZE = 16
DIP_NAME_FONT_SIZE = 18
NUM_FONT_SIZE = 12
CERT_NAME_FONT_SIZE = 18

# Альбом: центр по длинной стороне X = 297/2 мм; Y — от низа (baseline).
CERT_LAND_FIO_X_MM = 149.7
CERT_LAND_FIO_Y_MM = 81.35
# Номер: те же мм, что DIP_LAND_NUM_* (1-й лист диплома).
CERT_LAND_NUM_X_MM = 71.8
CERT_LAND_NUM_Y_MM = 12.0

# Альбомный 1-й лист диплома: нормализованные bbox 1000×1000 → мм (297×210), Y от низа страницы.
# ФИО [627,476,656,523] → центр; номер [925,235,955,290] → левый край + baseline в полосе текста.
DIP_LAND_FIO_X_MM = 150.35
DIP_LAND_FIO_Y_MM = 73.3
DIP_LAND_NUM_X_MM = 71.8
DIP_LAND_NUM_Y_MM = 12.0

# Книжный 2-й лист диплома (шағыру хаты): A4 210×297 мм, Y — от низа, baseline для drawCentredString.
DIP_PORT_FIO_X_MM = 99.0
DIP_PORT_FIO_Y_MM = 203.85


def _make_overlay_pages(
    full_name: str,
    pages_count: int,
    out_path: Path,
    *,
    award: str,
    number: int,
):
    if not full_name:
        full_name = " "

    font_name = _register_font()
    is_cert = award == "CERT"

    c = canvas.Canvas(str(out_path), pagesize=LANDSCAPE_A4)

    for i in range(pages_count):
        if is_cert:
            c.setPageSize(LANDSCAPE_A4)
        else:
            c.setPageSize(LANDSCAPE_A4 if i == 0 else A4)

        c.setFont(font_name, NAME_FONT_SIZE)

        # ===== СЕРТИФИКАТ (альбомный) =====
        if is_cert:
            c.setFillColorRGB(1, 0, 0)
            c.setFont("TimesNewRomanBold", CERT_NAME_FONT_SIZE)
            c.drawCentredString(CERT_LAND_FIO_X_MM * mm, CERT_LAND_FIO_Y_MM * mm, full_name)

            c.setFillColorRGB(0, 0, 0)
            num_font = _register_number_font()
            c.setFont(num_font, NUM_FONT_SIZE)
            c.drawString(CERT_LAND_NUM_X_MM * mm, CERT_LAND_NUM_Y_MM * mm, f"{number:05d}")

        # ===== ДИПЛОМ (I / II / III) =====
        else:
            if i == 0:
                # 1 лист (альбомный)
                c.setFillColorRGB(1, 0, 0)
                c.setFont("TimesNewRomanBold", DIP_NAME_FONT_SIZE)
                c.drawCentredString(DIP_LAND_FIO_X_MM * mm, DIP_LAND_FIO_Y_MM * mm, full_name)

                c.setFillColorRGB(0, 0, 0)
                num_font = _register_number_font()
                c.setFont(num_font, NUM_FONT_SIZE)
                c.drawString(DIP_LAND_NUM_X_MM * mm, DIP_LAND_NUM_Y_MM * mm, f"{number:04d}")

            elif i == 1:
                # 2 лист (книжный)
                c.setFillColorRGB(1, 0, 0)
                c.setFont("TimesNewRomanBold", DIP_NAME_FONT_SIZE)
                c.drawCentredString(DIP_PORT_FIO_X_MM * mm, DIP_PORT_FIO_Y_MM * mm, full_name)

        c.showPage()

    c.save()

    if not out_path.exists() or out_path.stat().st_size == 0:
        raise RuntimeError(f"Overlay PDF not created: {out_path}")


# ================== MAIN ==================
def generate_award_pdf(data: AwardData, out_dir: str = "out") -> str:
    if not data.full_name:
        raise ValueError("full_name is empty")

    template = _template_path(data.award)

    out_dir_p = BASE_DIR / out_dir
    out_dir_p.mkdir(parents=True, exist_ok=True)

    # 🔥 ГЛАВНОЕ: получаем нормальный номер
    number = _get_next_number(data.award)

    out_file = out_dir_p / f"award_{number}_{data.award}.pdf"
    overlay_file = out_dir_p / f"_overlay_{number}.pdf"

    reader = PdfReader(str(template))
    if not reader.pages:
        raise ValueError(f"Template has no pages: {template}")

    merge_pages = 2 if len(reader.pages) >= 2 else 1

    _make_overlay_pages(
        data.full_name,
        merge_pages,
        overlay_file,
        award=data.award,
        number=number,
    )

    overlay = PdfReader(str(overlay_file))
    writer = PdfWriter()

    for i in range(merge_pages):
        page = reader.pages[i]
        page.merge_page(overlay.pages[i])
        writer.add_page(page)

    for i in range(merge_pages, len(reader.pages)):
        writer.add_page(reader.pages[i])

    with open(out_file, "wb") as f:
        writer.write(f)

    if not out_file.exists() or out_file.stat().st_size == 0:
        raise RuntimeError(f"Final PDF not created: {out_file}")

    try:
        overlay_file.unlink(missing_ok=True)
    except Exception:
        pass

    return str(out_file.resolve())