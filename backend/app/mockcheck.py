"""Автопроверка первой (тестовой) части пробников.

Ключ ответов — простой текст, по строке на задание:

    1: 2,5
    2: -3 | -3,0              (через «|» — несколько допустимых ответов)
    5: 24 (2, любой порядок)  (2 балла; цифры можно в любом порядке; одна ошибка — 1 балл)
    7: 31 (2)                 (2 балла; цифры по порядку; одна ошибка — 1 балл)

Тот же текст можно вписать прямо в HTML пробника — сервер прочитает его при загрузке и вырежет из страницы:

    <script type="text/plain" id="answer-key">
    1: 2,5
    5: 24 (2, любой порядок)
    </script>
"""
import re
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException

LINE_RE = re.compile(r"^\s*(\d{1,3})\s*[:=.)]\s*(.+?)\s*(?:\((.*)\))?\s*$")
KEY_SCRIPT_RE = re.compile(
    r"<script\b[^>]*\bid\s*=\s*[\"']answer-key[\"'][^>]*>(.*?)</script\s*>", re.IGNORECASE | re.DOTALL)


def parse_key(text: str) -> List[dict]:
    """Текст ключа → [{n, answers: [..], points, any_order}], задания по возрастанию номера."""
    tasks: Dict[int, dict] = {}
    for i, raw in enumerate((text or "").splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        m = LINE_RE.match(line)
        if not m:
            raise HTTPException(400, f"Ключ, строка {i}: «{raw.strip()}». Нужно так: «5: 24 (2, любой порядок)».")
        n, ans, opts = int(m.group(1)), m.group(2), (m.group(3) or "").lower()
        answers = [a.strip() for a in ans.split("|") if a.strip()]
        if not answers:
            raise HTTPException(400, f"Ключ, строка {i}: нет ответа.")
        points = 1
        pm = re.search(r"\b([12])\b", opts)
        if pm:
            points = int(pm.group(1))
        any_order = "порядок" in opts or "order" in opts
        if n in tasks:
            raise HTTPException(400, f"Ключ: задание {n} указано дважды.")
        tasks[n] = {"n": n, "answers": answers, "points": points, "any_order": any_order}
    return [tasks[k] for k in sorted(tasks)]


def key_to_text(key: Optional[List[dict]]) -> str:
    lines = []
    for t in key or []:
        opts = []
        if t["points"] != 1:
            opts.append(str(t["points"]))
        if t.get("any_order"):
            opts.append("любой порядок")
        lines.append(f'{t["n"]}: {" | ".join(t["answers"])}' + (f' ({", ".join(opts)})' if opts else ""))
    return "\n".join(lines)


def extract_key_from_html(html: str) -> Tuple[str, Optional[str]]:
    """Достать ключ из <script id="answer-key"> и убрать его со страницы, чтобы ученик не увидел ответы."""
    m = KEY_SCRIPT_RE.search(html)
    if not m:
        return html, None
    return KEY_SCRIPT_RE.sub("", html), m.group(1).strip()


def _norm(s: str) -> str:
    s = (s or "").strip().lower().replace(",", ".").replace(" ", "").replace(" ", "").replace("−", "-")
    return s


def _num(s: str) -> Optional[float]:
    try:
        return float(s)
    except ValueError:
        return None


def _same(given: str, correct: str) -> bool:
    g, c = _norm(given), _norm(correct)
    if g == c:
        return True
    gn, cn = _num(g), _num(c)
    return gn is not None and cn is not None and abs(gn - cn) < 1e-9


def _errors(given: str, correct: str, any_order: bool) -> int:
    """Число ошибок в ответе из цифр — для частичного балла (как в ЕГЭ: одна ошибка — 1 балл из 2)."""
    g, c = _norm(given), _norm(correct)
    if any_order:
        gs, cs = list(g), list(c)
        missing = sum(max(0, cs.count(ch) - gs.count(ch)) for ch in set(cs))
        extra = sum(max(0, gs.count(ch) - cs.count(ch)) for ch in set(gs))
        return max(missing, extra)
    return sum(1 for a, b in zip(g, c) if a != b) + abs(len(g) - len(c))


def grade(key: List[dict], answers: Dict[str, str]) -> Tuple[int, int, List[dict]]:
    """Проверить ответы ученика. Возвращает (баллы, максимум, подробности по заданиям)."""
    score, total, details = 0, 0, []
    for t in key:
        given = (answers.get(str(t["n"])) or "").strip()[:60]
        pts = 0
        if given:
            if t["any_order"]:
                if any(_errors(given, a, True) == 0 for a in t["answers"]):
                    pts = t["points"]
                elif t["points"] == 2 and any(_errors(given, a, True) == 1 for a in t["answers"]):
                    pts = 1
            elif any(_same(given, a) for a in t["answers"]):
                pts = t["points"]
            elif t["points"] == 2 and _norm(given).isdigit() and any(
                    _norm(a).isdigit() and _errors(given, a, False) == 1 for a in t["answers"]):
                pts = 1  # частичный балл — только для ответов из цифр (соответствия, последовательности)
        score += pts
        total += t["points"]
        details.append({"n": t["n"], "given": given, "correct": t["answers"][0], "points": pts, "max": t["points"]})
    return score, total, details
