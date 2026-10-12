"""Работа с файлами визуализаций и обложек на диске."""
import hashlib
import os
import re
from pathlib import Path
from typing import Optional, Tuple

from fastapi import HTTPException, UploadFile

from . import config

_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z",
    "и": "i", "й": "j", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
    "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def slugify(text: str, max_len: int = 60) -> str:
    out = "".join(_TRANSLIT.get(ch, ch) for ch in text.lower())
    out = re.sub(r"[^a-z0-9]+", "-", out).strip("-")
    return out[:max_len].rstrip("-") or "vizualizaciya"


def validate_slug(slug: str) -> str:
    slug = slug.strip().lower()
    if not slug or len(slug) > 80 or not SLUG_RE.match(slug) or slug == "index":
        raise HTTPException(400, "Адрес страницы: только латиница, цифры и дефисы, например «zakon-oma».")
    return slug


async def read_limited(upload: UploadFile, limit: int, what: str) -> bytes:
    data = await upload.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"{what} больше {limit // (1024 * 1024)} МБ.")
    if not data:
        raise HTTPException(400, f"{what}: пустой файл.")
    return data


# ── Визуализации ──
BACKLINK_MARK = "<!-- site-backlink -->"
BACKLINK_TEMPLATE = BACKLINK_MARK + """
<a href="{href}" aria-label="{aria}"
   style="position:fixed;left:max(12px,env(safe-area-inset-left,0px));bottom:calc(12px + env(safe-area-inset-bottom,0px));z-index:2147483000;
          display:inline-flex;align-items:center;gap:8px;min-height:44px;padding:0 16px;border-radius:999px;
          background:rgba(24,24,32,.88);color:#fff;text-decoration:none;
          font:500 12px/1 'JetBrains Mono',Menlo,Consolas,monospace;letter-spacing:.06em;
          box-shadow:0 8px 20px -10px rgba(24,24,32,.6);-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px)">
  <span aria-hidden="true" style="font-size:15px">←</span> {label}
</a>
"""
BACKLINK = BACKLINK_TEMPLATE.format(href="index.html", aria="Все визуализации", label="ВСЕ ВИЗУАЛИЗАЦИИ")
# пробник открывается из личного кабинета — туда и возвращаемся
MOCK_BACKLINK = BACKLINK_TEMPLATE.format(href="/account/#probniki", aria="Назад в личный кабинет", label="В ЛИЧНЫЙ КАБИНЕТ")


def prepare_html(raw: bytes, backlink: str = BACKLINK) -> str:
    """Проверяет, что это текстовый HTML, и добавляет кнопку возврата («← Все визуализации» по умолчанию)."""
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(400, "Файл не в кодировке UTF-8. Пересохрани его как UTF-8.")
    low = text.lower()
    if "<html" not in low and "<body" not in low and "<!doctype html" not in low:
        raise HTTPException(400, "Это не похоже на HTML-страницу.")
    if BACKLINK_MARK not in text:
        idx = low.rfind("</body>")
        text = text[:idx] + backlink + text[idx:] if idx != -1 else text + backlink
    return text


def _atomic_write(path: Path, data: bytes) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def write_viz(file_name: str, html: str) -> None:
    _atomic_write(config.VIZ_DIR / file_name, html.encode("utf-8"))


def viz_path(file_name: str) -> Path:
    return config.VIZ_DIR / file_name


def rename_viz(old: str, new: str) -> None:
    src = config.VIZ_DIR / old
    if src.exists():
        os.replace(src, config.VIZ_DIR / new)


def delete_viz(file_name: Optional[str]) -> None:
    if file_name:
        (config.VIZ_DIR / file_name).unlink(missing_ok=True)


# ── Обложки ──
_RASTER = {
    b"\x89PNG\r\n\x1a\n": "png",
    b"\xff\xd8\xff": "jpg",
}


def _detect_image(data: bytes) -> Optional[str]:
    for magic, ext in _RASTER.items():
        if data.startswith(magic):
            return ext
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    head = data[:512].lstrip().lower()
    if head.startswith(b"<svg") or (head.startswith(b"<?xml") and b"<svg" in data[:2048].lower()):
        return "svg"
    return None


async def save_cover(slug: str, upload: UploadFile) -> str:
    data = await read_limited(upload, config.MAX_COVER_BYTES, "Обложка")
    ext = _detect_image(data)
    if not ext:
        raise HTTPException(400, "Обложка должна быть PNG, JPG, WebP или SVG.")
    digest = hashlib.sha1(data).hexdigest()[:8]
    name = f"{slug}-{digest}.{ext}"
    _atomic_write(config.COVERS_DIR / name, data)
    return name


def delete_cover(name: Optional[str]) -> None:
    if name:
        (config.COVERS_DIR / name).unlink(missing_ok=True)


def cover_path(name: str) -> Path:
    return config.COVERS_DIR / name


# ── PDF занятий: конспекты и домашние задания (storage/hw/) ──
PDF_WHAT = {"hw": "ДЗ", "notes": "Конспект", "mock": "Пробник", "mocksol": "Решения", "report": "Отчёт"}


async def save_lesson_pdf(kind: str, number: int, upload: UploadFile) -> str:
    """kind: hw, notes, mock, mocksol или report. Имя файла с хешем содержимого — замена не путается со старым в кэше."""
    what = PDF_WHAT.get(kind, "Файл")
    data = await read_limited(upload, config.MAX_PDF_BYTES, f"{what} (PDF)")
    if not data.lstrip()[:5] == b"%PDF-":
        raise HTTPException(400, f"{what}: нужен PDF-файл.")
    digest = hashlib.sha1(data).hexdigest()[:8]
    name = f"{kind}-{number}-{digest}.pdf"
    _atomic_write(config.HW_DIR / name, data)
    return name


async def save_mock_file(kind: str, number: int, upload: UploadFile) -> str:
    """Пробник или решения: HTML (как визуализация, с кнопкой «В личный кабинет») или PDF."""
    data = await read_limited(upload, max(config.MAX_PDF_BYTES, config.MAX_HTML_BYTES), "Файл пробника")
    digest = hashlib.sha1(data).hexdigest()[:8]
    if data.lstrip()[:5] == b"%PDF-":
        name = f"{kind}-{number}-{digest}.pdf"
        _atomic_write(config.HW_DIR / name, data)
        return name
    if len(data) > config.MAX_HTML_BYTES:
        raise HTTPException(413, f"HTML-файл больше {config.MAX_HTML_BYTES // (1024 * 1024)} МБ.")
    html = prepare_html(data, MOCK_BACKLINK)
    name = f"{kind}-{number}-{digest}.html"
    _atomic_write(config.HW_DIR / name, html.encode("utf-8"))
    return name


def hw_path(name: str) -> Path:
    return config.HW_DIR / name


def delete_hw(name: Optional[str]) -> None:
    if name:
        (config.HW_DIR / name).unlink(missing_ok=True)


def safe_name(name: str) -> bool:
    """Имя файла без путей и спецсимволов: защита от ../ в адресе."""
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9.-]{0,159}", name)) and ".." not in name


def media_type_for(name: str) -> Tuple[str, bool]:
    ext = name.rsplit(".", 1)[-1]
    return {
        "png": ("image/png", True), "jpg": ("image/jpeg", True),
        "webp": ("image/webp", True), "svg": ("image/svg+xml", True),
    }.get(ext, ("application/octet-stream", False))
