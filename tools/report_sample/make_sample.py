"""Пример ежемесячного отчёта для главной: та же вёрстка, что у настоящих отчётов, но данные выдуманы.
Данные выдуманы (владелец попросил: имя «Имя», показатели случайные, 20 пробников — чтобы было видно накопленную статистику).
Рендер: python tools/report_sample/make_sample.py --render --publish → public/assets/img/report-N.webp и report-N-s.webp.
Шрифты Montserrat и Manrope берутся из npm-пакетов @fontsource (не в git):
    cd tools/report_sample && mkdir -p fonts && cd fonts
    npm pack @fontsource/montserrat@5.0.19 && tar xzf fontsource-montserrat-*.tgz
    mkdir man && npm pack @fontsource/manrope@5.0.20 && tar xzf fontsource-manrope-*.tgz -C man"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "fonts")
OUT = os.path.join(HERE, "..", "..", "public", "assets", "img")

# ── Данные (выдуманные, но согласованные между страницами) ──
PERIOD = "01.03.2027 — 31.03.2027"
LESSONS = [  # дата, тема, уверенность (None — нет ответа), ДЗ, верно, всего (None — не сдано)
    ("03.03", "Закон Кулона", 5, 41, 17, 18),
    ("05.03", "Напряжённость и потенциал", 4, 42, 14, 16),
    ("10.03", "Конденсаторы", 4, 43, 12, 17),
    ("12.03", "Законы постоянного тока", 5, 44, 20, 20),
    ("17.03", "Правила Кирхгофа", 3, 45, 9, 15),
    ("19.03", "Работа и мощность тока", None, 46, 13, 14),
    ("24.03", "Магнитное поле, сила Ампера", 4, 47, 15, 18),
    ("26.03", "Сила Лоренца", 4, 48, 8, 14),
    ("29.03", "Электромагнитная индукция", 5, 49, 16, 16),
    ("31.03", "Самоиндукция", None, 50, None, None),
]
THRESHOLD = 65
MOCKS = [54, 58, 57, 61, 63, 62, 66, 68, 67, 71, 70, 74, 73, 76, 78, 77, 80, 82, 81, 84]
LAST_PRIMARY = "38"
GOAL = 90
# Доля решений по номерам КИМ за все пробники (в процентах от максимального балла)
TASKS = [
    (1, "Кинематика", 100), (2, "Динамика", 95), (3, "Законы сохранения", 90), (4, "Статика. Колебания", 85),
    (5, "Механика: верные утверждения", 80), (6, "Механика: изменение величин", 88), (7, "МКТ", 95),
    (8, "Термо&shy;динамика", 90), (9, "МКТ и термо&shy;динамика: утверждения", 70), (10, "МКТ: изменение величин", 83),
    (11, "Электро&shy;статика, ток", 90), (12, "Магнитное поле", 85), (13, "Электро&shy;магнитные колебания", 60),
    (14, "Оптика", 80), (15, "Электро&shy;динамика: утверждения", 75), (16, "Квантовая физика", 85),
    (17, "Кванты: изменение величин", 65), (18, "Обобщённые утверждения", 78), (19, "Показания приборов", 95),
    (20, "Выбор установки", 90), (21, "Качест&shy;венная задача", 55), (22, "Механика: расчёт", 70),
    (23, "МКТ: расчёт", 75), (24, "МКТ: высокий уровень", 45), (25, "Электро&shy;динамика: высокий уровень", 50),
    (26, "Механика: обоснование", 35),
]

done = [l for l in LESSONS if l[5]]
pcts = [round(100 * l[4] / l[5]) for l in done]
avg = round(sum(pcts) / len(pcts))
conf = [l[2] for l in LESSONS if l[2]]
conf_avg = sum(conf) / len(conf)
below = [(l[3], p) for l, p in zip(done, pcts) if p < THRESHOLD]
best = max(pcts)
best_list = [l[3] for l, p in zip(done, pcts) if p == best]
missed = [l[3] for l in LESSONS if not l[5]]


def comma(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")


def font_faces():
    css = []
    for fam, pkg, weights in (("Montserrat", "package", (600, 700, 800, 900)), ("Manrope", "man/package", (400, 500, 600, 700))):
        for w in weights:
            for sub in ("latin", "cyrillic"):
                path = os.path.join(FONTS, pkg, "files", f"{fam.lower()}-{sub}-{w}-normal.woff2")
                css.append(f"@font-face{{font-family:{fam};font-weight:{w};src:url('file://{path}') format('woff2');}}")
    return "\n".join(css)


def head(n, eyebrow, title):
    return (f'<div class="top"><span class="brand"><i></i><i></i><i></i>@Arch_Tutor_Bot</span><span class="num">{n:02d}</span></div>'
            f'<div class="eyebrow">{eyebrow}</div><h1>{title}</h1>')


def donut(p, color="var(--v)"):
    r, c = 70, 2 * math.pi * 70
    return (f'<svg viewBox="0 0 180 180" class="donut"><circle cx="90" cy="90" r="{r}" stroke="var(--gray)"/>'
            f'<circle cx="90" cy="90" r="{r}" stroke="{color}" stroke-dasharray="{c * p / 100:.1f} {c:.1f}" transform="rotate(-90 90 90)"/>'
            f'<text x="90" y="104" text-anchor="middle">{p}%</text></svg>')


# ── Страница 1: обложка ──
p1 = f'''
<div class="page cover">
  <div class="cover__l">
    <div class="cover__ring"></div><div class="cover__arch"></div>
    <span class="brand brand--w"><i></i><i></i><i></i></span>
    <div class="cover__mid"><div class="cover__eb">Отчёт об обучении</div><div class="cover__name">Имя</div><div class="cover__dates">{PERIOD}</div></div>
    <div class="cover__bot">@Arch_Tutor_Bot</div>
  </div>
  <div class="cover__r">
    <div class="kpi"><b>{len(LESSONS)}</b><span>занятий<br>за период</span></div>
    <div class="kpi kpi--k"><b>{len(done)}<small>/{len(LESSONS)}</small></b><span>домашних заданий<br>сдано</span></div>
    <div class="kpi"><b>{avg}<small>%</small></b><span>средний результат<br>по домашним заданиям</span></div>
    <div class="kpi kpi--k"><b>{MOCKS[-1]}</b><span>тестовых баллов<br>в последнем пробнике</span></div>
  </div>
</div>'''

# ── Страница 2: сводка ──
answered = len(conf)
rings = [
    (round(100 * len(done) / len(LESSONS)), f"{len(done)} из {len(LESSONS)}", "Сдача ДЗ", "не сдано: " + ", ".join(f"№{m}" for m in missed), "var(--v)"),
    (avg, f"{len(done)} проверенных", "Средний результат", f"от {min(pcts)}% до {max(pcts)}%", "var(--v)"),
    (100, f"{len(below)} из {len(below)}", "Работа над ошибками", f"обязательна ниже {THRESHOLD}%", "var(--v)"),
    (round(100 * answered / len(LESSONS)), f"{answered} из {len(LESSONS)} опросов", "Обратная связь", f"уверенность {comma(conf_avg)} из 5", "var(--ink)"),
]
cards = "".join(f'<div class="ring">{donut(p, col)}<b>{a}</b><span>{t}</span><i></i><small>{s}</small></div>' for p, a, t, s, col in rings)
p2 = f'''
<div class="page">{head(2, "01 · Сводка", "Коротко о периоде")}
  <div class="rings">{cards}</div>
  <div class="strip">
    <div><b>{len(LESSONS)}</b><span>занятий</span></div>
    <div><b>{comma(conf_avg)}</b><span>средняя уверенность после урока, из 5</span></div>
    <div><b>{len(MOCKS)}</b><span>пробников ЕГЭ с начала года</span></div>
    <div><b>{MOCKS[-1]}</b><span>тестовых в последнем пробнике</span></div>
  </div>
</div>'''

# ── Страница 3: столбцы по домашним заданиям ──
W, H, X0, Y0, PH = 760, 400, 60, 30, 300  # область графика
n = len(LESSONS)
step = (W - X0 - 30) / n
bars = []
for i, (d, t, c, hw, ok, tot) in enumerate(LESSONS):
    x = X0 + i * step + step * 0.2
    bw = step * 0.6
    if tot:
        p = round(100 * ok / tot)
        h = PH * p / 100
        col = "var(--v)" if p >= THRESHOLD else "var(--ink)"
        bars.append(f'<rect x="{x:.1f}" y="{Y0 + PH - h:.1f}" width="{bw:.1f}" height="{h:.1f}" rx="2" fill="{col}"/>'
                    f'<text class="bv" x="{x + bw / 2:.1f}" y="{Y0 + PH - h - 7:.1f}">{p}%</text>')
    else:
        bars.append(f'<rect x="{x:.1f}" y="{Y0}" width="{bw:.1f}" height="{PH}" fill="url(#hatch)" stroke="var(--line)"/>'
                    f'<text class="bn" transform="translate({x + bw / 2 + 4:.1f} {Y0 + PH / 2}) rotate(-90)">не сдано</text>')
    bars.append(f'<text class="bx" x="{x + bw / 2:.1f}" y="{Y0 + PH + 18}">№{hw}</text><text class="bd" x="{x + bw / 2:.1f}" y="{Y0 + PH + 33}">{d}</text>')
grid = "".join(f'<line x1="{X0}" x2="{W - 30}" y1="{Y0 + PH - PH * g / 100}" y2="{Y0 + PH - PH * g / 100}" class="gl"/>'
               f'<text class="gy" x="{X0 - 10}" y="{Y0 + PH - PH * g / 100 + 4}">{g}%</text>' for g in (0, 25, 50, 75, 100))
ty = Y0 + PH - PH * THRESHOLD / 100
chart = (f'<svg viewBox="0 0 {W} {H}" class="bars"><defs><pattern id="hatch" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
         f'<line x1="0" y1="0" x2="0" y2="8" stroke="#e4e2ea" stroke-width="3"/></pattern></defs>{grid}{"".join(bars)}'
         f'<line x1="{X0}" x2="{W - 30}" y1="{ty}" y2="{ty}" class="thr"/></svg>')
p3 = f'''
<div class="page">{head(3, "02 · Динамика", "Результаты домашних заданий")}
  <div class="dyn">
    <div class="card chartcard">{chart}<span class="thr__tag">порог · {THRESHOLD}%</span>
      <div class="legend"><span><i class="lg-v"></i>{THRESHOLD}% и выше</span><span><i class="lg-k"></i>ниже порога — нужна работа над ошибками</span><span><i class="lg-h"></i>не сдано</span></div>
    </div>
    <div class="side">
      <div class="tile tile--v"><b>{best}%</b><span>лучший результат — у {len(best_list)} работ: {", ".join(f"№{b}" for b in best_list)}</span></div>
      <div class="tile tile--k"><b>{len(below)}</b><span>работы ниже порога: {", ".join(f"№{h} ({p}%)" for h, p in below)}</span></div>
      <div class="tile tile--d"><b>{len(missed)}</b><span>не сдана: {", ".join(f"№{m}" for m in missed)}</span></div>
    </div>
  </div>
</div>'''

# ── Страница 4: журнал ──
rows = []
for d, t, c, hw, ok, tot in LESSONS:
    dots = (f'<span class="dots">{"".join("<i class=on></i>" if k < c else "<i></i>" for k in range(5))}<b>{c}</b></span>' if c else '<em>нет ответа</em>')
    if tot:
        p = round(100 * ok / tot)
        res = (f'<span class="res"><span class="rb"><i style="width:{p}%;background:{"var(--v)" if p >= THRESHOLD else "var(--ink)"}"></i></span>'
               f'<small>{ok}/{tot}</small><b>{p}%</b></span>')
    else:
        res = '<span class="pill">не сдано</span>'
    rows.append(f'<tr><td class="td-d">{d}</td><td>{t}</td><td>{dots}</td><td class="td-h">№{hw}</td><td>{res}</td></tr>')
p4 = f'''
<div class="page">{head(4, "03 · Журнал", "Занятия по порядку")}
  <table class="jr"><thead><tr><th>Дата<br>опроса</th><th>Тема</th><th>Уверенность</th><th>ДЗ</th><th>Результат</th></tr></thead>
  <tbody>{"".join(rows)}</tbody></table>
  <p class="foot">Дата опроса — день, когда ученику ушёл опрос после занятия. Уверенность — самооценка сразу после урока: «смогу ли решить задачу на эту тему сам», от 1 до 5.</p>
</div>'''

# ── Страница 5: пробники — динамика ──
LW, LH, LX0, LY0, LPH = 640, 380, 46, 24, 300
lo, hi = 40, 100
def ly(v): return LY0 + LPH - LPH * (v - lo) / (hi - lo)
lstep = (LW - LX0 - 24) / (len(MOCKS) - 1)
pts = [(LX0 + i * lstep, ly(v)) for i, v in enumerate(MOCKS)]
path = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)
area = path + f" L{pts[-1][0]:.1f} {ly(lo):.1f} L{pts[0][0]:.1f} {ly(lo):.1f} Z"
lgrid = "".join(f'<line x1="{LX0}" x2="{LW - 24}" y1="{ly(g):.1f}" y2="{ly(g):.1f}" class="gl"/><text class="gy" x="{LX0 - 10}" y="{ly(g) + 4:.1f}">{g}</text>' for g in (40, 60, 80, 100))
lx = "".join(f'<text class="bd" x="{x:.1f}" y="{LY0 + LPH + 20}">{i + 1}</text>' for i, (x, y) in enumerate(pts) if i % 2 == 0 or i == len(pts) - 1)
dots_svg = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{5.5 if i == len(pts) - 1 else 3.2}" class="{"pt pt--last" if i == len(pts) - 1 else "pt"}"/>' for i, (x, y) in enumerate(pts))
lbl = "".join(f'<text class="bv" x="{pts[i][0]:.1f}" y="{pts[i][1] - 12:.1f}">{MOCKS[i]}</text>' for i in (0, 9, len(MOCKS) - 1))
line_chart = (f'<svg viewBox="0 0 {LW} {LH}" class="lines"><defs><linearGradient id="ar" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5b1fd6" stop-opacity=".22"/><stop offset="1" stop-color="#5b1fd6" stop-opacity="0"/></linearGradient></defs>'
              f'{lgrid}<line x1="{LX0}" x2="{LW - 24}" y1="{ly(GOAL):.1f}" y2="{ly(GOAL):.1f}" class="thr"/>'
              f'<path d="{area}" fill="url(#ar)"/><path d="{path}" class="ln"/>{dots_svg}{lbl}{lx}'
              f'<text class="gx" x="{(LX0 + LW - 24) / 2:.1f}" y="{LY0 + LPH + 44}">номер пробника</text></svg>')
last5 = round(sum(MOCKS[-5:]) / 5)
g = MOCKS[-1] / 100
arc_len = math.pi * 150
p5 = f'''
<div class="page">{head(5, "04 · Экзамен", "Пробники ЕГЭ")}
  <div class="mk">
    <div class="card gauge">
      <svg viewBox="0 0 360 200"><path d="M30 180 A150 150 0 0 1 330 180" class="g-bg"/><path d="M30 180 A150 150 0 0 1 330 180" class="g-fg" stroke-dasharray="{arc_len * g:.1f} {arc_len:.1f}"/>
      <text x="180" y="160" class="g-n">{MOCKS[-1]}</text><text x="180" y="190" class="g-s">из 100 тестовых · пробник №{len(MOCKS)}</text></svg>
      <div class="g-row"><div><b>{LAST_PRIMARY}</b><span>из 45 первичных</span></div><div><b>+{MOCKS[-1] - MOCKS[0]}</b><span>с пробника №1</span></div><div><b>{last5}</b><span>в среднем за 5 последних</span></div></div>
    </div>
    <div class="card linecard"><div class="lc-h"><b>Тестовые баллы по пробникам</b><span class="thr__tag thr__tag--in">цель · {GOAL}</span></div>{line_chart}</div>
  </div>
</div>'''

# ── Страница 6: пробники — задания по номерам ──
def lvl(p):
    return "h-bad" if p < 50 else "h-mid" if p < 70 else "h-ok" if p < 90 else "h-top"
hexes = "".join(f'<div class="hex {lvl(p)}"><b>{n}</b><span>{t}</span><em>{p}%</em></div>' for n, t, p in TASKS)
weak = sorted(TASKS, key=lambda t: t[2])[:3]
p6 = f'''
<div class="page">{head(6, "05 · Экзамен", "Задания по номерам")}
  <p class="lead6">Доля баллов по каждому заданию КИМ за все {len(MOCKS)} пробников. Чем темнее ячейка, тем хуже получается задание.</p>
  <div class="hexes">{hexes}</div>
  <div class="hx-foot">
    <div class="legend"><span><i class="lg h-top"></i>90% и выше</span><span><i class="lg h-ok"></i>70–89%</span><span><i class="lg h-mid"></i>50–69%</span><span><i class="lg h-bad"></i>ниже 50%</span></div>
    <div class="focus"><b>В фокусе апреля:</b> {", ".join(f"№{n} ({(t[0].lower() + t[1:] if not t[:3].isupper() else t).replace('&shy;', '')})" for n, t, p in weak)}</div>
  </div>
</div>'''

# ── Страница 7: комментарий ──
p7 = f'''
<div class="page">{head(7, "06 · Итог", "Комментарий преподавателя")}
  <div class="quote"><span class="q">“</span><p>Март прошёл ровно: домашние задания по электростатике и постоянному току сданы в срок, работа над ошибками по правилам Кирхгофа и силе Лоренца выполнена. Пробники стабильно держатся выше 80 баллов. Главный резерв — задачи второй части: №24–26. В апреле разбираем их на каждом занятии и добавляем по одной такой задаче в каждое домашнее задание.</p></div>
  <div class="gloss"><div><b>РНО</b><span>работа над ошибками: обязательна, если за домашнее задание меньше {THRESHOLD}%, срок — три дня.</span></div>
  <div><b>Первичный балл</b><span>сумма баллов за задания пробника; тестовый — перевод по шкале ЕГЭ в 100.</span></div>
  <div><b>Уверенность</b><span>ученик сам оценивает после урока, насколько готов решать задачи по теме.</span></div></div>
</div>'''

CSS = open(os.path.join(HERE, "sample.css"), encoding="utf-8").read()
html = f"<!doctype html><html lang=ru><head><meta charset=utf-8><style>{font_faces()}\n{CSS}</style></head><body>{p1}{p2}{p3}{p4}{p5}{p6}{p7}</body></html>"
open(os.path.join(HERE, "sample.html"), "w", encoding="utf-8").write(html)

if "--render" in sys.argv:
    from playwright.sync_api import sync_playwright
    from PIL import Image
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1123, "height": 794}, device_scale_factor=2)
        pg.goto("file://" + os.path.join(HERE, "sample.html"))
        pg.wait_for_timeout(800)
        for i, el in enumerate(pg.locator(".page").all(), 1):
            png = os.path.join(HERE, f"s-{i}.png")
            el.screenshot(path=png)
            im = Image.open(png).convert("RGB")
            if "--publish" in sys.argv:
                im.resize((1600, round(1600 * im.height / im.width)), Image.LANCZOS).save(f"{OUT}/report-{i}.webp", quality=82, method=6)
                if True:
                    im.resize((720, round(720 * im.height / im.width)), Image.LANCZOS).save(f"{OUT}/report-{i}-s.webp", quality=80, method=6)
        b.close()
    print("rendered")
