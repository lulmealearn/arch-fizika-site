"""Запуск сайта и служебные команды.

    python run.py                 — сайт на http://localhost:8000 (только этот компьютер)
    python run.py --lan           — открыть и для телефона в той же Wi-Fi сети
    python run.py --port 8080     — другой порт
    python run.py set-password    — задать или сменить пароль админки
"""
import argparse
import getpass
import secrets
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"


def _update_env(values: dict) -> None:
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    seen = set()
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if key in values:
            lines[i] = f"{key}={values[key]}"
            seen.add(key)
    lines += [f"{k}={v}" for k, v in values.items() if k not in seen]
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def set_password() -> None:
    sys.path.insert(0, str(ROOT))
    from backend.app.security import hash_password  # noqa: E402

    while True:
        pw = getpass.getpass("Новый пароль админки (символы не отображаются): ")
        if len(pw) < 8:
            print("Минимум 8 символов.")
            continue
        if pw != getpass.getpass("Ещё раз: "):
            print("Не совпало, попробуй снова.")
            continue
        break
    values = {"ADMIN_PASSWORD_HASH": hash_password(pw)}
    existing = ENV_FILE.read_text(encoding="utf-8") if ENV_FILE.exists() else ""
    if "SECRET_KEY=" not in existing:
        values["SECRET_KEY"] = secrets.token_urlsafe(32)
    _update_env(values)
    print(f"Готово. Пароль сохранён в {ENV_FILE.name} (в git этот файл не попадает). Перезапусти сайт.")


def lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return "IP-компьютера"


def main() -> None:
    parser = argparse.ArgumentParser(description="Сайт Arch / Физика")
    parser.add_argument("command", nargs="?", choices=["set-password"], help="служебная команда")
    parser.add_argument("--lan", action="store_true", help="доступ с телефона в той же сети")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-reload", action="store_true", help="не перезапускать при правке кода")
    args = parser.parse_args()

    if args.command == "set-password":
        set_password()
        return

    import uvicorn

    host = "0.0.0.0" if args.lan else "127.0.0.1"
    print(f"\n  Сайт:    http://localhost:{args.port}")
    print(f"  Админка: http://localhost:{args.port}/admin/")
    if args.lan:
        print(f"  С телефона: http://{lan_ip()}:{args.port}")
    print("  Остановить: Ctrl+C\n")
    opts = {"reload": True, "reload_dirs": [str(ROOT / "backend")]} if not args.no_reload else {}
    uvicorn.run("backend.app.main:app", host=host, port=args.port, app_dir=str(ROOT), **opts)


if __name__ == "__main__":
    main()
