"""Структура КИМ ЕГЭ по физике (задания 1–26: тема и максимум — из таблицы владельца) и перевод первичных баллов в тестовые.

Шкала по умолчанию — ЕГЭ-2026 (Рособрнадзор, апрель 2026; совпадает в Т—Ж и Ленте). Каждый год её утверждают заново —
владелец меняет её в админке («Пробники» → «Шкала перевода»), значение хранится в таблице settings."""
from typing import List, Optional

from sqlalchemy.orm import Session

from .models import Setting

KEY = "ege_scale"
PART1_MAX, PART2_MAX = 28, 17  # первая часть — 20 заданий (28 первичных), вторая — 6 заданий (17 первичных)
DEFAULT = [0, 5, 9, 14, 18, 23, 27, 32, 36, 39, 41, 43, 44, 46, 48, 49, 51, 53, 54, 56, 58, 59, 61, 62, 64, 65, 67, 68,
           70, 71, 73, 74, 76, 77, 79, 80, 82, 84, 86, 88, 90, 92, 94, 96, 98, 100]


# Задания КИМ (из таблицы владельца): номер, тема, максимум первичных. 1–20 — первая часть (28), 21–26 — вторая (17).
TASKS = [
    (1, "Кинематика", 1), (2, "Динамика", 1), (3, "Импульс. Законы сохранения в механике", 1),
    (4, "Статика. Гидростатика. Механические колебания и волны", 1), (5, "Механика: анализ процессов (верные утверждения)", 2),
    (6, "Механика: изменение величин и соответствие", 2), (7, "Молекулярная физика", 1), (8, "Термодинамика", 1),
    (9, "МКТ и термодинамика: верные утверждения", 2), (10, "МКТ и термодинамика: изменение величин и соответствие", 2),
    (11, "Электрическое поле. Законы постоянного тока", 1), (12, "Магнитное поле. Электромагнитная индукция", 1),
    (13, "Оптика. Электромагнитные колебания и волны", 1), (14, "Электродинамика: верные утверждения", 2),
    (15, "Электродинамика: изменение величин и соответствие", 2), (16, "Квантовая физика", 1),
    (17, "Квантовая физика: изменение величин и соответствие", 2), (18, "Физический смысл величин и законов (верные утверждения)", 2),
    (19, "Показания измерительных приборов", 1), (20, "Планирование эксперимента", 1), (21, "Качественная задача", 3),
    (22, "Механика: расчётная задача", 2), (23, "МКТ и термодинамика: расчётная задача", 2),
    (24, "МКТ и термодинамика: задача высокого уровня", 3), (25, "Электродинамика: задача высокого уровня", 3),
    (26, "Механика: задача высокого уровня + обоснование", 4),
]
DEFAULT_THEMES = {n: theme for n, theme, _mx in TASKS}
PART1_LAST = 20  # задания 1–20 — первая часть, дальше — вторая


def _tasks(v) -> list:
    raw = v.get("tasks") if isinstance(v.get("tasks"), list) and v.get("tasks") else None
    if raw:
        return [{"n": int(t["n"]), "theme": str(t.get("theme", "")), "max": int(t["max"])} for t in raw]
    return [{"n": n, "theme": th, "max": mx} for n, th, mx in TASKS]


def get(db: Session) -> dict:
    row = db.get(Setting, KEY)
    v = row.value if row and isinstance(row.value, dict) else {}
    scale = v.get("scale") if isinstance(v.get("scale"), list) and len(v.get("scale")) == 46 else DEFAULT
    tasks = _tasks(v)
    part2 = [t for t in tasks if t["n"] > PART1_LAST]
    return {"scale": [int(x) for x in scale], "year": v.get("year") or "2026", "tasks": tasks, "part2": part2,
            "part2_max": sum(t["max"] for t in part2) or PART2_MAX,
            "themes": {str(t["n"]): t["theme"] for t in tasks}}


def parse_tasks(text: str) -> list:
    """Строки «номер: максимум: тема» → список заданий."""
    from fastapi import HTTPException
    out, seen = [], set()
    for i, raw in enumerate((text or "").splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(":", 2)]
        if len(parts) < 2 or not parts[0].isdigit() or not parts[1].isdigit():
            raise HTTPException(400, f"Задания, строка {i}: «{line}». Нужно «номер: максимум: тема», например «21: 3: Качественная задача».")
        n, mx = int(parts[0]), int(parts[1])
        if n in seen or not 1 <= mx <= 10:
            raise HTTPException(400, f"Задания, строка {i}: номер повторяется или максимум не от 1 до 10.")
        seen.add(n)
        out.append({"n": n, "max": mx, "theme": parts[2] if len(parts) > 2 else ""})
    if not out:
        raise HTTPException(400, "Список заданий пуст.")
    return sorted(out, key=lambda t: t["n"])


def validate(scale: List[int]) -> None:
    from fastapi import HTTPException
    if len(scale) != 46:
        raise HTTPException(400, f"Нужно 46 чисел — для 0, 1, …, 45 первичных баллов (сейчас {len(scale)}).")
    if scale[0] != 0 or any(not 0 <= x <= 100 for x in scale):
        raise HTTPException(400, "Тестовые баллы — от 0 до 100, для 0 первичных — 0.")
    if any(b < a for a, b in zip(scale, scale[1:])):
        raise HTTPException(400, "Шкала не должна убывать: каждый следующий тестовый балл не меньше предыдущего.")


def save(db: Session, scale: List[int], year: str, tasks_text: Optional[str] = None) -> dict:
    validate(scale)
    row = db.get(Setting, KEY) or Setting(key=KEY)
    old = row.value if isinstance(row.value, dict) else {}
    tasks = parse_tasks(tasks_text) if tasks_text is not None else _tasks(old)
    row.value = {"scale": scale, "year": (year or "").strip()[:20], "tasks": tasks}
    db.add(row)
    db.commit()
    return get(db)


def part2_scores(sc: dict, given: dict) -> dict:
    """Баллы куратора по заданиям второй части: {номер: баллы}, каждое от 0 до максимума задания."""
    from fastapi import HTTPException
    out = {}
    for t in sc["part2"]:
        v = given.get(str(t["n"]), given.get(t["n"]))
        if v is None or v == "":
            raise HTTPException(400, f"Поставьте баллы за задание {t['n']} (от 0 до {t['max']}).")
        v = int(v)
        if not 0 <= v <= t["max"]:
            raise HTTPException(400, f"Задание {t['n']}: от 0 до {t['max']} баллов.")
        out[str(t["n"])] = v
    return out


def total(db_scale: dict, part1, sub) -> Optional[dict]:
    """Итог пробника: первичные за обе части и тестовый балл (только для полного варианта на 45 первичных)."""
    if part1 is None or sub is None or sub.status != "checked" or sub.max_score is None:
        return None
    primary, mx = part1.score + (sub.score or 0), part1.max_score + sub.max_score
    test = db_scale["scale"][primary] if mx == 45 and 0 <= primary <= 45 else None
    return {"primary": primary, "max": mx, "test": test, "year": db_scale["year"]}
