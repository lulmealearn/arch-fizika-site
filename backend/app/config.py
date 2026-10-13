"""Настройки из переменных окружения и файла .env в корне репозитория."""
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / ".env"


def _load_env_file(path: Path) -> None:
    """Простейший парсер .env: KEY=VALUE построчно. Уже заданные переменные окружения не перезаписываются."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_env_file(ENV_FILE)

PUBLIC_DIR = ROOT / "public"
SEED_DIR = ROOT / "seed"
STORAGE_DIR = Path(os.environ.get("STORAGE_DIR", ROOT / "storage")).resolve()
VIZ_DIR = STORAGE_DIR / "viz"
COVERS_DIR = STORAGE_DIR / "covers"
HW_DIR = STORAGE_DIR / "hw"
SUBMISSIONS_DIR = STORAGE_DIR / "submissions"  # сданные ДЗ учеников: фото и PDF
for _d in (STORAGE_DIR, VIZ_DIR, COVERS_DIR, HW_DIR, SUBMISSIONS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# SQLite по умолчанию; для MySQL: mysql+pymysql://user:pass@host:3306/dbname?charset=utf8mb4
DATABASE_URL = os.environ.get("DATABASE_URL") or f"sqlite:///{(STORAGE_DIR / 'site.db').as_posix()}"

ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH", "")

SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    SECRET_KEY = secrets.token_urlsafe(32)
    print("[config] SECRET_KEY не задан: вход в админку сбросится после перезапуска. "
          "Запусти `python run.py set-password`, он пропишет ключ в .env.", file=sys.stderr)

# На сервере с HTTPS поставить COOKIE_SECURE=1
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0") == "1"
SESSION_DAYS = int(os.environ.get("SESSION_DAYS", "14"))

MAX_HTML_BYTES = int(float(os.environ.get("MAX_HTML_MB", "8")) * 1024 * 1024)
MAX_COVER_BYTES = int(float(os.environ.get("MAX_COVER_MB", "3")) * 1024 * 1024)
MAX_PDF_BYTES = int(float(os.environ.get("MAX_PDF_MB", "25")) * 1024 * 1024)

# Сдача ДЗ: фото сжимаются в браузере ученика, на сервер приходят уже лёгкими
MAX_SUB_FILE_BYTES = int(float(os.environ.get("MAX_SUB_FILE_MB", "20")) * 1024 * 1024)
MAX_SUB_FILES = int(os.environ.get("MAX_SUB_FILES", "15"))
# Файлы работ, проверенных больше N дней назад, удаляются (решение владельца: 90 дней после проверки); балл и комментарий
# остаются, копии — у кураторов в Telegram. Непроверенные не удаляются никогда. 0 в .env — не удалять вообще.
SUBMISSION_KEEP_DAYS = int(os.environ.get("SUBMISSION_KEEP_DAYS", "90"))

# Бот @Arch_Tutor_Bot присылает кураторам новые работы. Токен — от @BotFather (`python run.py set-bot`).
def _clean_token(raw: str) -> str:
    """Токен вида 123456789:AAE…: убрать пробелы, кавычки, приставку «bot» и текст, скопированный вместе с токеном."""
    import re
    m = re.search(r"\d{5,}:[A-Za-z0-9_-]{20,}", raw or "")
    return m.group(0) if m else (raw or "").strip()


TELEGRAM_BOT_TOKEN = _clean_token(os.environ.get("TELEGRAM_BOT_TOKEN", ""))
TELEGRAM_API = os.environ.get("TELEGRAM_API", "https://api.telegram.org")  # для тестов можно подменить
# Ваш личный chat id: бот присылает новые работы и вам (необязательно)
ADMIN_TG_CHAT_ID = os.environ.get("ADMIN_TG_CHAT_ID", "").strip()
# Адрес сайта для ссылок в сообщениях бота, например https://arch-fizika.ru
SITE_URL = os.environ.get("SITE_URL", "http://localhost:8000").rstrip("/")
