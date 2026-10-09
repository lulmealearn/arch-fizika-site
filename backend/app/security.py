"""Пароль админа (scrypt), подписанная cookie-сессия и ограничение попыток входа."""
import base64
import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque
from typing import Deque, Dict
from urllib.parse import urlparse

from fastapi import HTTPException, Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from . import config

COOKIE_NAME = "admin_session"
_serializer = URLSafeTimedSerializer(config.SECRET_KEY, salt="admin-session")

# Формат хеша без символа $, чтобы не ломался в EnvironmentFile на сервере
_N, _R, _P = 2 ** 14, 8, 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    b64 = lambda b: base64.urlsafe_b64encode(b).decode("ascii").rstrip("=")
    return f"scrypt:{_N}:{_R}:{_P}:{b64(salt)}:{b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt_b64, hash_b64 = stored.split(":")
        if algo != "scrypt":
            return False
        pad = lambda s: s + "=" * (-len(s) % 4)
        salt = base64.urlsafe_b64decode(pad(salt_b64))
        expected = base64.urlsafe_b64decode(pad(hash_b64))
        got = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=int(n), r=int(r), p=int(p), dklen=len(expected))
        return hmac.compare_digest(got, expected)
    except (ValueError, TypeError):
        return False


def make_session_token() -> str:
    return _serializer.dumps({"admin": True})


def is_admin(request: Request) -> bool:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return False
    try:
        data = _serializer.loads(token, max_age=config.SESSION_DAYS * 86400)
    except (BadSignature, SignatureExpired):
        return False
    return bool(data.get("admin"))


def require_admin(request: Request) -> None:
    """Зависимость для админских маршрутов: сессия + защита от запросов с чужих сайтов."""
    if not is_admin(request):
        raise HTTPException(status_code=401, detail="Нужно войти в админку.")
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin and urlparse(origin).netloc != request.headers.get("host"):
            raise HTTPException(status_code=403, detail="Запрос пришёл с другого сайта.")


# ── Ограничение попыток входа: 8 неудачных за 10 минут с одного адреса ──
_WINDOW, _LIMIT = 600, 8
_failures: Dict[str, Deque[float]] = defaultdict(deque)


def check_login_rate(ip: str) -> None:
    q = _failures[ip]
    now = time.monotonic()
    while q and now - q[0] > _WINDOW:
        q.popleft()
    if len(q) >= _LIMIT:
        raise HTTPException(status_code=429, detail="Слишком много попыток. Подожди 10 минут.")


def record_login_failure(ip: str) -> None:
    _failures[ip].append(time.monotonic())


def clear_login_failures(ip: str) -> None:
    _failures.pop(ip, None)
