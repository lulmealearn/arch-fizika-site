"""Отправка сообщений от имени бота @Arch_Tutor_Bot (Bot API, без сторонних библиотек).

Сайт только отправляет: обновления бота он не читает, поэтому не мешает коду самого бота (polling или webhook).
Кому писать — chat id куратора (он должен один раз нажать /start у бота, иначе Telegram не даст боту ему написать)."""
import json
import mimetypes
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib import error, request

from . import config

TIMEOUT = 60


class TelegramError(Exception):
    pass


def enabled() -> bool:
    return bool(config.TELEGRAM_BOT_TOKEN)


def _multipart(fields: Dict[str, str], files: List[Tuple[str, str, bytes, str]]) -> Tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    out = bytearray()
    for k, v in fields.items():
        out += f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n'.encode() + v.encode("utf-8") + b"\r\n"
    for field, filename, data, ctype in files:
        out += (f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
                f"Content-Type: {ctype}\r\n\r\n").encode("utf-8") + data + b"\r\n"
    out += f"--{boundary}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={boundary}"


def _call(method: str, fields: Dict[str, str], files: Optional[List[Tuple[str, str, bytes, str]]] = None) -> dict:
    if not enabled():
        raise TelegramError("Бот не настроен: нет TELEGRAM_BOT_TOKEN в .env.")
    url = f"{config.TELEGRAM_API}/bot{config.TELEGRAM_BOT_TOKEN}/{method}"
    body, ctype = _multipart(fields, files or [])
    req = request.Request(url, data=body, headers={"Content-Type": ctype}, method="POST")
    try:
        with request.urlopen(req, timeout=TIMEOUT) as r:
            data = json.loads(r.read().decode("utf-8"))
    except error.HTTPError as e:
        try:
            data = json.loads(e.read().decode("utf-8"))
        except ValueError:
            raise TelegramError(f"Telegram ответил {e.code}.")
    except (error.URLError, TimeoutError, OSError) as e:
        raise TelegramError(f"Нет связи с Telegram: {getattr(e, 'reason', e)}")
    if not data.get("ok"):
        desc = data.get("description", "неизвестная ошибка")
        if "chat not found" in desc or "bot was blocked" in desc or "initiate conversation" in desc:
            desc += " — куратор должен открыть бота и нажать /start, и chat id должен быть верным"
        raise TelegramError(f"Telegram: {desc}")
    return data


def send_text(chat_id: str, text: str) -> None:
    _call("sendMessage", {"chat_id": chat_id, "text": text, "disable_web_page_preview": "true"})


def send_files(chat_id: str, paths: List[Tuple[Path, str]], caption: str = "") -> None:
    """Фото — альбомами по 10, PDF — документами (Telegram не смешивает их в одном альбоме)."""
    photos = [(p, n) for p, n in paths if (mimetypes.guess_type(n)[0] or "").startswith("image/")]
    docs = [(p, n) for p, n in paths if (p, n) not in photos]
    first = True
    for group, kind in ((photos, "photo"), (docs, "document")):
        for i in range(0, len(group), 10):
            chunk = group[i:i + 10]
            if len(chunk) == 1:
                p, n = chunk[0]
                f = {"chat_id": chat_id}
                if first and caption:
                    f["caption"] = caption
                _call("sendPhoto" if kind == "photo" else "sendDocument", f,
                      [(kind, n, p.read_bytes(), mimetypes.guess_type(n)[0] or "application/octet-stream")])
            else:
                media, up = [], []
                for j, (p, n) in enumerate(chunk):
                    item = {"type": kind, "media": f"attach://f{j}"}
                    if first and j == 0 and caption:
                        item["caption"] = caption
                    media.append(item)
                    up.append((f"f{j}", n, p.read_bytes(), mimetypes.guess_type(n)[0] or "application/octet-stream"))
                _call("sendMediaGroup", {"chat_id": chat_id, "media": json.dumps(media, ensure_ascii=False)}, up)
            first = False
