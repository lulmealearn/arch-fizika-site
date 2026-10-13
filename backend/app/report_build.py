"""Ежемесячный отчёт для родителей, собранный из Google-таблицы (решение владельца: сайт сам готовит отчёт раз в месяц,
владелец проверяет, дописывает комментарий и публикует в кабинет ученика).

collect() — взять у таблицы занятия и пробники ученика и посчитать цифры за период (снимок хранится в reports.data,
чтобы опубликованный отчёт не менялся, если таблицу потом поправят). render() — HTML-страницы в вёрстке отчётов
владельца (та же, что у примера на главной, tools/report_sample): обложка, сводка, ДЗ, журнал, пробники, задания, итог."""
import html
import math
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from . import scale, sheets
from .models import Report, User

MSK = timezone(timedelta(hours=3))
THRESHOLD = 65  # ниже — обязательна работа над ошибками (РНО), как в отчётах владельца
JOURNAL_ROWS = 14  # строк журнала на листе; больше — журнал делится на листы поровну
# Короткие подписи заданий для сот (как в примере отчёта); если тему в таблице переименовали — берём её, обрезав
SHORT = {1: "Кинематика", 2: "Динамика", 3: "Законы сохранения", 4: "Статика. Колебания", 5: "Механика: верные утверждения",
         6: "Механика: изменение величин", 7: "МКТ", 8: "Термо\u00adдинамика", 9: "МКТ и термо\u00adдинамика: утверждения",
         10: "МКТ: изменение величин", 11: "Электро\u00adстатика, ток", 12: "Магнитное поле", 13: "Электро\u00adмагнитные колебания",
         14: "Оптика", 15: "Электро\u00adдинамика: утверждения", 16: "Квантовая физика", 17: "Кванты: изменение величин",
         18: "Обобщённые утверждения", 19: "Показания приборов", 20: "Выбор установки", 21: "Качест\u00adвенная задача",
         22: "Механика: расчёт", 23: "МКТ: расчёт", 24: "МКТ: высокий уровень", 25: "Электро\u00adдинамика: высокий уровень",
         26: "Механика: обоснование"}
MONTHS = ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь"]
MONTHS_GEN = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]
# Ответы бота на «Что мешало?» (в таблице несколько ответов склеены через запятую, а в двух ответах запятая своя)
HINDERS = ["Ничего, всё ок", "Связь и звук", "Объяснял непонятно", "Тема слишком сложная", "Слишком быстрый темп",
           "Непонятно, что делать в ДЗ"]
NOTHING = "Ничего, всё ок"


# ── Период ──
def previous_month(today: Optional[date] = None):
    today = today or datetime.now(MSK).date()
    last = today.replace(day=1) - timedelta(days=1)
    return last.replace(day=1), last


def period_label(d_from: date, d_to: date) -> str:
    nxt = d_to + timedelta(days=1)
    if d_from.day == 1 and nxt.day == 1 and d_from.month == d_to.month and d_from.year == d_to.year:
        return f"{MONTHS[d_from.month - 1]} {d_from.year}"
    return f"с {d_from:%d.%m} по {d_to:%d.%m.%Y}"


def report_title(d_from: date, d_to: date) -> str:
    label = period_label(d_from, d_to)
    return ("Отчёт " if label.startswith("с ") else "Отчёт за ") + label


def _day(iso: Optional[str]) -> Optional[date]:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=MSK)
    return dt.astimezone(MSK).date()


def split_hinders(text: str) -> List[str]:
    rest, found = text or "", []
    for h in sorted(HINDERS, key=len, reverse=True):
        if h.lower() in rest.lower():
            i = rest.lower().index(h.lower())
            found.append(h)
            rest = rest[:i] + rest[i + len(h):]
    found += [p.strip() for p in re.split(r"[,;\n]", rest) if p.strip()]
    return found


def student_name(tab: str, fallback: str) -> str:
    m = re.search(r"\(([^)]+)\)", tab or "")
    return m.group(1).strip() if m else fallback


# ── Сбор ──
def collect(db, user: User, d_from: date, d_to: date) -> dict:
    """Данные таблицы → цифры отчёта. Бросает sheets.SheetsError, если таблица недоступна или ученик не найден."""
    raw = sheets.call("report", **sheets.who(user))
    return compute(raw, d_from, d_to, user.nickname, scale.get(db))


def compute(raw: dict, d_from: date, d_to: date, nickname: str, sc: dict) -> dict:
    lessons, hinders = [], Counter()
    for r in raw.get("lessons") or []:
        d = _day(r.get("date"))
        if d is None or not d_from <= d <= d_to:
            continue
        has_hw = r.get("hw") is not None
        correct, total = r.get("correct"), r.get("total")
        if has_hw and correct is not None and total:
            state, pct = "ok", round(100 * correct / total)
        elif has_hw and r.get("done"):
            state, pct = "pending", None
        elif has_hw:
            state, pct = "missing", None
        else:
            state, pct = "none", None
        conf = r.get("conf")
        lessons.append({"day": d.isoformat(), "date": f"{d:%d.%m}", "topic": r.get("topic") or "",
                        "conf": int(round(conf)) if conf is not None else None,
                        "hw": int(r["hw"]) if has_hw else None, "state": state, "pct": pct,
                        "correct": int(correct) if correct is not None else None, "total": int(total) if total else None,
                        "rno": bool(r.get("rno"))})
        for h in split_hinders(r.get("hinder") or ""):
            if h != NOTHING:
                hinders[h] += 1
    lessons.sort(key=lambda x: (x["day"], x["hw"] or 0))
    issued = [l for l in lessons if l["hw"] is not None]
    checked = [l for l in issued if l["state"] == "ok"]
    pcts = [l["pct"] for l in checked]
    below = [l for l in checked if l["pct"] < THRESHOLD]
    confs = [l["conf"] for l in lessons if l["conf"] is not None]

    tasks = [{"n": int(t["n"]), "theme": t.get("theme") or "", "max": int(t["max"] or 0)} for t in raw.get("tasks") or []
             if t.get("max")]
    tmax = {str(t["n"]): t["max"] for t in tasks}
    full_max = sum(tmax.values())
    mocks = []
    for m in sorted(raw.get("mocks") or [], key=lambda x: x["n"]):
        d = _day(m.get("date"))
        if d is not None and d > d_to:
            continue
        sc_ = {k: v for k, v in (m.get("scores") or {}).items() if k in tmax}
        primary = round(sum(sc_.values()))
        mx = sum(tmax[k] for k in sc_)
        test = sc["scale"][primary] if mx == full_max == 45 and 0 <= primary <= 45 else None
        mocks.append({"n": int(m["n"]), "date": f"{d:%d.%m.%Y}" if d else "", "primary": primary, "max": mx,
                      "test": test, "scores": sc_})
    task_pct = []
    for t in tasks:
        got = [m["scores"][str(t["n"])] for m in mocks if str(t["n"]) in m["scores"]]
        task_pct.append({"n": t["n"], "theme": t["theme"],
                         "pct": round(100 * sum(got) / (t["max"] * len(got))) if got else None, "tries": len(got)})
    for m in mocks:
        m.pop("scores")
    return {
        "name": student_name(raw.get("tab") or "", nickname), "tab": raw.get("tab") or "",
        "from": d_from.isoformat(), "to": d_to.isoformat(), "label": period_label(d_from, d_to),
        "dates": f"{d_from:%d.%m.%Y} — {d_to:%d.%m.%Y}",
        "lessons": lessons,
        "sum": {"lessons": len(lessons), "issued": len(issued), "done": sum(1 for l in issued if l["state"] in ("ok", "pending")),
                "checked": len(checked), "avg": round(sum(pcts) / len(pcts)) if pcts else None,
                "min": min(pcts) if pcts else None, "max": max(pcts) if pcts else None,
                "below": [{"hw": l["hw"], "pct": l["pct"], "rno": l["rno"]} for l in below],
                "missed": [l["hw"] for l in issued if l["state"] == "missing"],
                "pending": [l["hw"] for l in issued if l["state"] == "pending"],
                "conf_avg": round(sum(confs) / len(confs), 1) if confs else None, "answered": len(confs)},
        "hinders": hinders.most_common(),
        "mocks": mocks, "tasks": task_pct, "threshold": THRESHOLD,
    }


# ── Вёрстка ──
def e(s) -> str:
    return html.escape(str(s if s is not None else ""))


def comma(x, d=1) -> str:
    return f"{x:.{d}f}".replace(".", ",")


def nums(xs) -> str:
    return ", ".join(f"№{x}" for x in xs)


def head(n: int, eyebrow: str, title: str) -> str:
    return (f'<div class="top"><span class="brand"><i></i><i></i><i></i>@Arch_Tutor_Bot</span><span class="num">{n:02d}</span></div>'
            f'<div class="eyebrow">{eyebrow}</div><h1>{title}</h1>')


def donut(p: int, color="var(--v)") -> str:
    r, c = 70, 2 * math.pi * 70
    return (f'<svg viewBox="0 0 180 180" class="donut"><circle cx="90" cy="90" r="{r}" stroke="var(--gray)"/>'
            f'<circle cx="90" cy="90" r="{r}" stroke="{color}" stroke-dasharray="{c * p / 100:.1f} {c:.1f}" transform="rotate(-90 90 90)"/>'
            f'<text x="90" y="104" text-anchor="middle">{p}%</text></svg>')


def _pct(a: int, b: int) -> int:
    return round(100 * a / b) if b else 0


def pages(d: dict, comment: str) -> List[str]:
    s, L, M = d["sum"], d["lessons"], d["mocks"]
    thr = d["threshold"]
    last = M[-1] if M else None
    last_val = (last["test"] if last and last["test"] is not None else None)
    out = []

    def k4():
        if last_val is not None:
            return f'<div class="kpi kpi--k"><b>{last_val}</b><span>тестовых баллов<br>в последнем пробнике</span></div>'
        if s["conf_avg"] is not None:
            return f'<div class="kpi kpi--k"><b>{comma(s["conf_avg"])}</b><span>средняя уверенность<br>после урока, из 5</span></div>'
        return f'<div class="kpi kpi--k"><b>{len(M)}</b><span>пробников ЕГЭ<br>с начала года</span></div>'

    avg = f'{s["avg"]}<small>%</small>' if s["avg"] is not None else "—"
    out.append(f'''<div class="page cover">
  <div class="cover__l"><div class="cover__ring"></div><div class="cover__arch"></div>
    <span class="brand brand--w"><i></i><i></i><i></i></span>
    <div class="cover__mid"><div class="cover__eb">Отчёт об обучении</div><div class="cover__name">{e(d["name"])}</div><div class="cover__dates">{e(d["dates"])}</div></div>
    <div class="cover__bot">@Arch_Tutor_Bot</div></div>
  <div class="cover__r">
    <div class="kpi"><b>{s["lessons"]}</b><span>занятий<br>за период</span></div>
    <div class="kpi kpi--k"><b>{s["done"]}<small>/{s["issued"]}</small></b><span>домашних заданий<br>сдано</span></div>
    <div class="kpi"><b>{avg}</b><span>средний результат<br>по домашним заданиям</span></div>
    {k4()}
  </div></div>''')

    n = 2
    below, rno_done = s["below"], sum(1 for b in s["below"] if b["rno"])
    rings = [
        (_pct(s["done"], s["issued"]), f'{s["done"]} из {s["issued"]}', "Сдача ДЗ",
         ("не сдано: " + nums(s["missed"])) if s["missed"] else ("все сданы" if s["issued"] else "ДЗ не задавались"), "var(--v)"),
        (s["avg"] or 0, f'{s["checked"]} проверенных', "Средний результат",
         f'от {s["min"]}% до {s["max"]}%' if s["checked"] else "проверенных работ нет", "var(--v)"),
        ((_pct(rno_done, len(below)) if below else 100), (f"{rno_done} из {len(below)}" if below else "не понадобилась"),
         "Работа над ошибками", f"обязательна ниже {thr}%", "var(--v)"),
        (_pct(s["answered"], s["lessons"]), f'{s["answered"]} из {s["lessons"]} опросов', "Обратная связь",
         f'уверенность {comma(s["conf_avg"])} из 5' if s["conf_avg"] is not None else "ответов нет", "var(--ink)"),
    ]
    cards = "".join(f'<div class="ring">{donut(p, col)}<b>{e(a)}</b><span>{t}</span><i></i><small>{e(sm)}</small></div>'
                    for p, a, t, sm, col in rings)
    strip4 = (f'<div><b>{last_val}</b><span>тестовых в последнем пробнике</span></div>' if last_val is not None else
              f'<div><b>{last["primary"]}</b><span>первичных в последнем пробнике</span></div>' if last else
              f'<div><b>{s["checked"]}</b><span>проверенных домашних заданий</span></div>')
    out.append(f'''<div class="page">{head(n, "01 · Сводка", "Коротко о периоде")}
  <div class="rings">{cards}</div>
  <div class="strip"><div><b>{s["lessons"]}</b><span>занятий</span></div>
    <div><b>{comma(s["conf_avg"]) if s["conf_avg"] is not None else "—"}</b><span>средняя уверенность после урока, из 5</span></div>
    <div><b>{len(M)}</b><span>пробников ЕГЭ с начала года</span></div>{strip4}</div></div>''')
    n += 1

    hw = [l for l in L if l["hw"] is not None]
    if hw:
        W, H, X0, Y0, PH = 760, 400, 60, 30, 300
        step = (W - X0 - 30) / len(hw)
        bars = []
        for i, l in enumerate(hw):
            bw = min(step * 0.6, 56)
            x = X0 + i * step + (step - bw) / 2
            cx = x + bw / 2
            if l["state"] == "ok":
                h = PH * l["pct"] / 100
                col = "var(--v)" if l["pct"] >= thr else "var(--ink)"
                bars.append(f'<rect x="{x:.1f}" y="{Y0 + PH - h:.1f}" width="{bw:.1f}" height="{max(h, 1):.1f}" rx="2" fill="{col}"/>'
                            f'<text class="bv" x="{cx:.1f}" y="{Y0 + PH - h - 7:.1f}">{l["pct"]}%</text>')
            else:
                word = "на проверке" if l["state"] == "pending" else "не сдано"
                bars.append(f'<rect x="{x:.1f}" y="{Y0}" width="{bw:.1f}" height="{PH}" fill="url(#hatch)" stroke="var(--line)"/>'
                            f'<text class="bn" transform="translate({cx + 4:.1f} {Y0 + PH / 2}) rotate(-90)">{word}</text>')
            bars.append(f'<text class="bx" x="{cx:.1f}" y="{Y0 + PH + 18}">№{l["hw"]}</text>'
                        f'<text class="bd" x="{cx:.1f}" y="{Y0 + PH + 33}">{l["date"]}</text>')
        grid = "".join(f'<line x1="{X0}" x2="{W - 30}" y1="{Y0 + PH - PH * g / 100}" y2="{Y0 + PH - PH * g / 100}" class="gl"/>'
                       f'<text class="gy" x="{X0 - 10}" y="{Y0 + PH - PH * g / 100 + 4}">{g}%</text>' for g in (0, 25, 50, 75, 100))
        ty = Y0 + PH - PH * thr / 100
        chart = (f'<svg viewBox="0 0 {W} {H}" class="bars"><defs><pattern id="hatch" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
                 f'<line x1="0" y1="0" x2="0" y2="8" stroke="#e4e2ea" stroke-width="3"/></pattern></defs>{grid}{"".join(bars)}'
                 f'<line x1="{X0}" x2="{W - 30}" y1="{ty}" y2="{ty}" class="thr"/></svg>')
        tiles = []
        if s["checked"]:
            best = s["max"]
            best_list = [l["hw"] for l in hw if l["state"] == "ok" and l["pct"] == best]
            tiles.append(f'<div class="tile tile--v"><b>{best}%</b><span>лучший результат: {nums(best_list)}</span></div>')
        tiles.append(f'<div class="tile tile--k"><b>{len(below)}</b><span>'
                     + (("ниже порога: " + ", ".join(f'№{b["hw"]} ({b["pct"]}%)' for b in below)) if below else "работ ниже порога нет")
                     + '</span></div>')
        if s["missed"]:
            tiles.append(f'<div class="tile tile--d"><b>{len(s["missed"])}</b><span>не сдано: {nums(s["missed"])}</span></div>')
        if s["pending"]:
            tiles.append(f'<div class="tile tile--d"><b>{len(s["pending"])}</b><span>на проверке: {nums(s["pending"])}</span></div>')
        out.append(f'''<div class="page">{head(n, "02 · Динамика", "Результаты домашних заданий")}
  <div class="dyn"><div class="card chartcard">{chart}<span class="thr__tag" style="top:{8 + ty * 0.922:.0f}px">порог · {thr}%</span>
    <div class="legend"><span><i class="lg-v"></i>{thr}% и выше</span><span><i class="lg-k"></i>ниже порога — нужна работа над ошибками</span><span><i class="lg-h"></i>не сдано или на проверке</span></div></div>
  <div class="side">{"".join(tiles)}</div></div></div>''')
        n += 1

    rows = []
    for l in L:
        c = l["conf"]
        dots = (f'<span class="dots">{"".join("<i class=on></i>" if k < c else "<i></i>" for k in range(5))}<b>{c}</b></span>'
                if c is not None else '<em>нет ответа</em>')
        if l["state"] == "ok":
            p = l["pct"]
            res = (f'<span class="res"><span class="rb"><i style="width:{p}%;background:{"var(--v)" if p >= thr else "var(--ink)"}"></i></span>'
                   f'<small>{l["correct"]}/{l["total"]}</small><b>{p}%</b></span>')
            if p < thr:
                res += ' <span class="pill pill--ok">РНО сделана</span>' if l["rno"] else ' <span class="pill">РНО</span>'
        elif l["state"] == "pending":
            res = '<span class="pill">на проверке</span>'
        elif l["state"] == "missing":
            res = '<span class="pill">не сдано</span>'
        else:
            res = '<em>без ДЗ</em>'
        rows.append(f'<tr><td class="td-d">{l["date"]}</td><td>{e(l["topic"])}</td><td>{dots}</td>'
                    f'<td class="td-h">{"№" + str(l["hw"]) if l["hw"] is not None else "—"}</td><td>{res}</td></tr>')
    parts = max(1, math.ceil(len(rows) / JOURNAL_ROWS))
    per = math.ceil(len(rows) / parts) if rows else 1
    chunks = [rows[i:i + per] for i in range(0, len(rows), per)] or [[]]
    for i, ch in enumerate(chunks):
        title = "Занятия по порядку" + (f" · {i + 1}/{len(chunks)}" if len(chunks) > 1 else "")
        body = "".join(ch) or '<tr><td colspan="5"><em>За этот период занятий в таблице нет.</em></td></tr>'
        foot = ('<p class="foot">Дата — день занятия. Уверенность — самооценка сразу после урока: «смогу ли решить задачу '
                'на эту тему сам», от 1 до 5. РНО — работа над ошибками.</p>') if i == len(chunks) - 1 else ""
        out.append(f'''<div class="page">{head(n, "03 · Журнал", title)}
  <table class="jr"><thead><tr><th>Дата</th><th>Тема</th><th>Уверенность</th><th>ДЗ</th><th>Результат</th></tr></thead>
  <tbody>{body}</tbody></table>{foot}</div>''')
        n += 1

    if M:
        vals = [m["test"] if m["test"] is not None else m["primary"] for m in M]
        use_test = all(m["test"] is not None for m in M)
        last = M[-1]
        big = last["test"] if last["test"] is not None else last["primary"]
        sub = (f'из 100 тестовых · пробник №{last["n"]}' if last["test"] is not None else f'из {last["max"]} первичных · пробник №{last["n"]}')
        g = big / (100 if last["test"] is not None else max(last["max"], 1))
        arc = math.pi * 150
        delta = vals[-1] - vals[0]
        last5 = round(sum(vals[-5:]) / len(vals[-5:]))
        LW, LH, LX0, LY0, LPH = 640, 380, 46, 24, 300
        lo = 0 if not use_test else max(0, (min(vals) // 20) * 20)
        hi = 100 if use_test else max(45, max(vals))
        def ly(v): return LY0 + LPH - LPH * (v - lo) / ((hi - lo) or 1)
        lstep = (LW - LX0 - 24) / max(len(vals) - 1, 1)
        pts = [(LX0 + (i * lstep if len(vals) > 1 else (LW - LX0 - 24) / 2), ly(v)) for i, v in enumerate(vals)]
        path = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)
        area = path + f" L{pts[-1][0]:.1f} {ly(lo):.1f} L{pts[0][0]:.1f} {ly(lo):.1f} Z"
        gstep = 20 if use_test else 15
        lgrid = "".join(f'<line x1="{LX0}" x2="{LW - 24}" y1="{ly(v):.1f}" y2="{ly(v):.1f}" class="gl"/>'
                        f'<text class="gy" x="{LX0 - 10}" y="{ly(v) + 4:.1f}">{v}</text>' for v in range(int(lo), int(hi) + 1, gstep))
        every = max(1, math.ceil(len(pts) / 12))
        lx = "".join(f'<text class="bd" x="{x:.1f}" y="{LY0 + LPH + 20}">{M[i]["n"]}</text>'
                     for i, (x, y) in enumerate(pts) if i % every == 0 or i == len(pts) - 1)
        dots_svg = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{5.5 if i == len(pts) - 1 else 3.2}" class="{"pt pt--last" if i == len(pts) - 1 else "pt"}"/>'
                           for i, (x, y) in enumerate(pts))
        marks = sorted({0, len(vals) - 1, vals.index(max(vals))})
        lbl = "".join(f'<text class="bv" x="{pts[i][0]:.1f}" y="{pts[i][1] - 12:.1f}">{vals[i]}</text>' for i in marks)
        line = (f'<svg viewBox="0 0 {LW} {LH}" class="lines"><defs><linearGradient id="ar" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5b1fd6" stop-opacity=".22"/><stop offset="1" stop-color="#5b1fd6" stop-opacity="0"/></linearGradient></defs>'
                f'{lgrid}' + (f'<path d="{area}" fill="url(#ar)"/><path d="{path}" class="ln"/>' if len(pts) > 1 else "")
                + f'{dots_svg}{lbl}{lx}<text class="gx" x="{(LX0 + LW - 24) / 2:.1f}" y="{LY0 + LPH + 44}">номер пробника</text></svg>')
        out.append(f'''<div class="page">{head(n, "04 · Экзамен", "Пробники ЕГЭ")}
  <div class="mk"><div class="card gauge">
      <svg viewBox="0 0 360 200"><path d="M30 180 A150 150 0 0 1 330 180" class="g-bg"/><path d="M30 180 A150 150 0 0 1 330 180" class="g-fg" stroke-dasharray="{arc * min(g, 1):.1f} {arc:.1f}"/>
      <text x="180" y="160" class="g-n">{big}</text><text x="180" y="190" class="g-s">{sub}</text></svg>
      <div class="g-row"><div><b>{last["primary"]}</b><span>из {last["max"]} первичных</span></div><div><b>{"+" if delta > 0 else ""}{delta}</b><span>с пробника №{M[0]["n"]}</span></div><div><b>{last5}</b><span>в среднем за {min(5, len(vals))} последних</span></div></div>
    </div>
    <div class="card linecard"><div class="lc-h"><b>{"Тестовые" if use_test else "Первичные"} баллы по пробникам</b><span class="thr__tag thr__tag--in">{len(M)} {plural(len(M), "пробник", "пробника", "пробников")}</span></div>{line}</div>
  </div></div>''')
        n += 1

        def lvl(p):
            if p is None:
                return "h-none"
            return "h-bad" if p < 50 else "h-mid" if p < 70 else "h-ok" if p < 90 else "h-top"
        hexes = "".join(f'<div class="hex {lvl(t["pct"])}"><b>{t["n"]}</b><span>{e(short_theme(t["theme"], t["n"]))}</span>'
                        f'<em>{str(t["pct"]) + "%" if t["pct"] is not None else "—"}</em></div>' for t in d["tasks"])
        weak = sorted([t for t in d["tasks"] if t["pct"] is not None], key=lambda t: t["pct"])[:3]
        nxt = date.fromisoformat(d["to"]) + timedelta(days=1)
        focus = (f'<div class="focus"><b>В фокусе {MONTHS_GEN[nxt.month - 1]}:</b> '
                 + ", ".join(f'№{t["n"]} ({e(lower_first(short_theme(t["theme"], t["n"]).replace(chr(173), "")))})' for t in weak) + '</div>') if weak else ""
        out.append(f'''<div class="page">{head(n, "05 · Экзамен", "Задания по номерам")}
  <p class="lead6">Доля баллов по каждому заданию КИМ за {"все " + str(len(M)) + " " + plural(len(M), "пробник", "пробника", "пробников") if len(M) > 1 else "пробник"}. Чем темнее ячейка, тем хуже получается задание.</p>
  <div class="hexes">{hexes}</div>
  <div class="hx-foot"><div class="legend"><span><i class="lg h-top"></i>90% и выше</span><span><i class="lg h-ok"></i>70–89%</span><span><i class="lg h-mid"></i>50–69%</span><span><i class="lg h-bad"></i>ниже 50%</span></div>{focus}</div></div>''')
        n += 1

    paras = "".join(f"<p>{e(p)}</p>" for p in re.split(r"\n\s*\n", (comment or "").strip()) if p.strip())
    quote = f'<div class="quote"><span class="q">“</span><div>{paras}</div></div>' if paras else \
        '<div class="quote quote--empty"><p>Комментарий преподавателя появится здесь.</p></div>'
    hind = ""
    if d.get("hinders"):
        hind = ('<div class="hind"><b>Что мешало на занятиях</b> <span>(по опросам после уроков)</span><ul>'
                + "".join(f"<li>{e(h)} — {c}</li>" for h, c in d["hinders"]) + "</ul></div>")
    out.append(f'''<div class="page">{head(n, f"{'06' if M else '04'} · Итог", "Комментарий преподавателя")}
  {quote}{hind}
  <div class="gloss"><div><b>РНО</b><span>работа над ошибками: обязательна, если за домашнее задание меньше {thr}%.</span></div>
  <div><b>Первичный балл</b><span>сумма баллов за задания пробника; тестовый — перевод по шкале ЕГЭ в 100.</span></div>
  <div><b>Уверенность</b><span>ученик сам оценивает после урока, насколько готов решать задачи по теме.</span></div></div></div>''')
    return out


def plural(n: int, one: str, few: str, many: str) -> str:
    n = abs(n) % 100
    if 10 < n < 20:
        return many
    n %= 10
    return one if n == 1 else few if 2 <= n <= 4 else many


def short_theme(t: str, n: Optional[int] = None) -> str:
    t = (t or "").strip()
    if n in SHORT and t == scale.DEFAULT_THEMES.get(n):
        return SHORT[n]
    return t if len(t) <= 40 else t[:38].rstrip(" ,.:;") + "…"


def lower_first(t: str) -> str:
    return t if t[:3].isupper() else t[:1].lower() + t[1:]


def render(r: Report, viewer: str = "student") -> str:
    """Страница отчёта. viewer: student | admin (у админа над черновиком — пометка)."""
    d = r.data or {}
    body = "".join(pages(d, r.comment or "")) if d else '<div class="page"><h1>Нет данных</h1></div>'
    draft = ('<span class="rep-bar__draft">Черновик — ученик его не видит</span>'
             if r.status != "published" else "")
    back = "/admin/#users" if viewer == "admin" else "/account/#otchety"
    back_t = "← В админку" if viewer == "admin" else "← В личный кабинет"
    return f'''<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(r.title)} — {e(d.get("name", ""))}</title><meta name="robots" content="noindex">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Montserrat:wght@600;700;800;900&family=Manrope:wght@400;500;600;700&display=swap">
<link rel="stylesheet" href="/assets/css/report.css">
</head><body class="rep">
<div class="rep-bar"><a class="rep-bar__back" href="{back}">{back_t}</a><span class="rep-bar__t">{e(r.title)}</span>{draft}
<button class="rep-bar__pdf" type="button" id="rep-print">Сохранить PDF</button></div>
<main class="rep-pages">{body}</main>
<script src="/assets/js/report.js"></script>
</body></html>'''
