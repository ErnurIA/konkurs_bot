from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
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
    doc_no: str
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


# ================== OVERLAY ==================
NAME_PAGE1_XY = (301.3, 347.4)
NAME_PAGE2_XY = (311.8, 569.5)
NAME_FONT_SIZE = 16


def _make_overlay_pages(full_name: str, pages_count: int, out_path: Path):
    if not full_name:
        full_name = " "

    font_name = _register_font()
    c = canvas.Canvas(str(out_path), pagesize=A4)

    for i in range(pages_count):
        x, y = NAME_PAGE1_XY if i == 0 else NAME_PAGE2_XY
        c.setFont(font_name, NAME_FONT_SIZE)
        c.setFillColorRGB(1, 0, 0)  # красный
        c.drawCentredString(x, y, full_name)
        c.setFillColorRGB(0, 0, 0)  # вернуть чёрный
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

    out_file = out_dir_p / f"award_{data.doc_no}_{data.award}.pdf"
    overlay_file = out_dir_p / f"_overlay_{data.doc_no}.pdf"

    reader = PdfReader(str(template))
    if not reader.pages:
        raise ValueError(f"Template has no pages: {template}")

    merge_pages = 2 if len(reader.pages) >= 2 else 1

    _make_overlay_pages(data.full_name, merge_pages, overlay_file)
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
