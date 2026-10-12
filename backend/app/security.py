"""Пароли (scrypt), подписанные cookie-сессии админа и учеников, ограничение попыток входа."""
import base64
import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Optional
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


def check_same_origin(request: Request) -> None:
    """Запросы, которые что-то меняют, принимаем только со своего сайта."""
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin and urlparse(origin).netloc != request.headers.get("host"):
            raise HTTPException(status_code=403, detail="Запрос пришёл с другого сайта.")


def require_admin(request: Request) -> None:
    """Зависимость для админских маршрутов: сессия + защита от запросов с чужих сайтов."""
    if not is_admin(request):
        raise HTTPException(status_code=401, detail="Нужно войти в админку.")
    check_same_origin(request)


# ── Сессия ученика: в cookie только id и версия сессии, сам ученик читается из базы ──
USER_COOKIE = "user_session"
_user_serializer = URLSafeTimedSerializer(config.SECRET_KEY, salt="user-session")
USER_SESSION_DAYS = 60


def make_user_token(user_id: int, version: int) -> str:
    return _user_serializer.dumps({"u": user_id, "v": version})


def read_user_token(request: Request) -> Optional[Dict[str, int]]:
    token = request.cookies.get(USER_COOKIE)
    if not token:
        return None
    try:
        data = _user_serializer.loads(token, max_age=USER_SESSION_DAYS * 86400)
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("u"), int):
        return None
    return data


class RateLimit:
    """Не больше limit событий за window секунд с одного адреса (в памяти процесса)."""

    def __init__(self, window: int, limit: int, message: str):
        self.window, self.limit, self.message = window, limit, message
        self.events: Dict[str, Deque[float]] = defaultdict(deque)

    def check(self, ip: str) -> None:
        q = self.events[ip]
        now = time.monotonic()
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            raise HTTPException(status_code=429, detail=self.message)

    def hit(self, ip: str) -> None:
        self.events[ip].append(time.monotonic())

    def clear(self, ip: str) -> None:
        self.events.pop(ip, None)


# Админка: 8 неудачных попыток за 10 минут
_admin_login = RateLimit(600, 8, "Слишком много попыток. Подожди 10 минут.")
check_login_rate, record_login_failure, clear_login_failures = _admin_login.check, _admin_login.hit, _admin_login.clear

# Ученики: 10 неудачных входов за 10 минут и 5 регистраций за час с одного адреса
user_login_limit = RateLimit(600, 10, "Слишком много попыток входа. Попробуйте через 10 минут.")
register_limit = RateLimit(3600, 5, "Слишком много регистраций с этого адреса. Попробуйте позже.")
