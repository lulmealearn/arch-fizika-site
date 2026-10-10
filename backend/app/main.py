"""Точка входа: API, визуализации, админка и статика сайта из public/."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from . import config
from .routes_admin import router as admin_router
from .routes_public import router as public_router
from .seed import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Arch / Физика", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if path.startswith("/admin") or path.startswith("/api/admin"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
    elif request.method in ("GET", "HEAD") and not path.startswith("/api/"):
        # Страницы, стили и скрипты: браузер каждый раз сверяет ETag (быстрый 304), поэтому после
        # обновления сайта никто не застревает на старом main.js/CSS.
        response.headers.setdefault("Cache-Control", "no-cache")
    return response


app.include_router(public_router)
app.include_router(admin_router)
# Статика — последней, чтобы маршруты выше имели приоритет. Наружу отдаётся только папка public/.
app.mount("/", StaticFiles(directory=config.PUBLIC_DIR, html=True), name="public")
