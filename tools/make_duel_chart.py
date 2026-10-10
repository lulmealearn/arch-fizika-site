"""График «дуэли» на странице цен: самостоятельно (хаотичные всплески, неизвестный итог) против занятий
(рост с небольшими колебаниями до «ЕГЭ 90+»). Перезаписывает оба SVG (широкий и для телефона) в public/prices/index.html.
Запуск: python tools/make_duel_chart.py"""
import math
import random
import re

PAGE = 'public/prices/index.html'
V, G, INK = '#6d28d9', '#9b98a6', '#181820'


def smooth(p):
    """Catmull-Rom → кубические Безье: плавная линия через все точки."""
    d = f"M{p[0][0]:.1f} {p[0][1]:.1f}"
    for i in range(len(p) - 1):
        p0 = p[i - 1] if i > 0 else p[i]
        p1, p2 = p[i], p[i + 1]
        p3 = p[i + 2] if i + 2 < len(p) else p[i + 1]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f"C{c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {p2[0]:.1f} {p2[1]:.1f}"
    return d


def me_points(x0, x1, y0, y1, n, amp, seed):
    """Рост по баллам: S-образный тренд + мелкие колебания вверх-вниз."""
    rnd = random.Random(seed)
    pts = []
    for i in range(n):
        t = i / (n - 1)
        s = 1 / (1 + math.exp(-5.5 * (t - 0.48)))
        s0, s1 = 1 / (1 + math.exp(5.5 * 0.48)), 1 / (1 + math.exp(-5.5 * 0.52))
        trend = y0 + (y1 - y0) * (s - s0) / (s1 - s0)
        wob = 0 if i in (0, n - 1) else (-1) ** i * amp * rnd.uniform(0.45, 1.0)
        pts.append((x0 + (x1 - x0) * t, trend + wob))
    return pts


def chip(x, y, text, fs):
    h, pad = fs * 1.9, fs * 0.7
    w = len(text) * fs * 0.56 + pad * 2
    yy = y - h - fs * 0.95
    return (f'<rect x="{x - w / 2:.1f}" y="{yy:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{h / 2:.1f}" fill="#fff" stroke="{V}" stroke-width="1.6"/>'
            f'<text x="{x:.1f}" y="{yy + h / 2 + fs * 0.33:.1f}" text-anchor="middle" font-family="Jura, sans-serif" font-weight="700" font-size="{fs:.1f}" fill="{V}">{text}</text>')


def chart(W, H, base, x0, x1, fs, me, chips, solo, fan, cls, uid):
    ex, ey = me[-1]
    path = smooth(me)
    sx, sy = solo[-1]
    grid = ''.join(f'<path d="M{x0} {base - (base - 30) * k / 3:.0f}H{x1}"/>' for k in (1, 2, 3))
    out = [f'<svg class="duel__chart {cls}" viewBox="0 0 {W} {H}" fill="none" role="img" aria-label="График: самостоятельно результат скачет вверх и вниз и итог непредсказуем; на занятиях баллы растут с небольшими колебаниями до 90+">',
           f'<defs><linearGradient id="dg{uid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{V}" stop-opacity=".28"/><stop offset="1" stop-color="{V}" stop-opacity="0"/></linearGradient><clipPath id="dc{uid}"><rect class="duel__clip" x="0" y="-30" width="{W}" height="{base + 28}"/></clipPath></defs>',
           '__SOLO__',
           '<g class="duel__me">',
           f'<path d="{path}L{ex:.1f} {base}L{me[0][0]:.1f} {base}Z" fill="url(#dg{uid})"/>',
           f'<path d="{path}" stroke="{V}" stroke-width="{fs * 0.3:.1f}" stroke-linecap="round" stroke-linejoin="round"/>']
    for i, label in chips:
        x, y = me[i]
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{fs * 0.36:.1f}" fill="{V}" stroke="#fff" stroke-width="2.5"/>')
        out.append(chip(x, y, label, fs * 0.9))
    pill_w = fs * 6.2
    out.append(f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="{fs * 1.05:.1f}" fill="{V}" fill-opacity=".18"/><circle cx="{ex:.1f}" cy="{ey:.1f}" r="{fs * 0.55:.1f}" fill="{V}"/>')
    out.append(f'<g transform="rotate(-4 {ex:.1f} {ey:.1f})"><rect x="{ex - pill_w + fs * 0.6:.1f}" y="{ey - fs * 3.3:.1f}" width="{pill_w:.1f}" height="{fs * 2.1:.1f}" rx="{fs * 1.05:.1f}" fill="{INK}"/>'
               f'<text x="{ex - pill_w / 2 + fs * 0.6:.1f}" y="{ey - fs * 3.3 + fs * 1.42:.1f}" text-anchor="middle" font-family="Jura, sans-serif" font-weight="700" font-size="{fs * 1.1:.1f}" fill="#fff">ЕГЭ 90+</text></g>')
    out.append('</g>')
    out.append('</g>')  # конец обрезки-проявления
    solo_parts = [f'<g stroke="{V}" stroke-opacity=".14" stroke-width="1.2" stroke-dasharray="3 6">{grid}</g>',
                  f'<path d="{smooth(solo)}" stroke="{G}" stroke-width="{fs * 0.24:.1f}" stroke-linecap="round" stroke-linejoin="round"/>']
    for fy in fan:
        solo_parts.append(f'<path d="M{sx:.1f} {sy:.1f}Q{(sx + x1) / 2:.1f} {sy:.1f} {x1 - fs * 1.2:.1f} {fy:.1f}" stroke="{G}" stroke-width="{fs * 0.14:.1f}" stroke-dasharray="2 5" stroke-linecap="round"/>'
                          f'<circle cx="{x1 - fs * 1.2:.1f}" cy="{fy:.1f}" r="{fs * 0.26:.1f}" fill="{G}" fill-opacity=".6"/>')
    fm = sorted(fan)[len(fan) // 2]
    solo_parts.append(f'<g transform="rotate(6 {x1 - fs * 1.2:.1f} {fm:.1f})"><rect x="{x1 - fs * 2.6:.1f}" y="{fm - fs * 3.4:.1f}" width="{fs * 2.6:.1f}" height="{fs * 2:.1f}" rx="{fs:.1f}" fill="#e4e1d8"/>'
                      f'<text x="{x1 - fs * 1.3:.1f}" y="{fm - fs * 3.4 + fs * 1.45:.1f}" text-anchor="middle" font-family="Jura, sans-serif" font-weight="700" font-size="{fs * 1.2:.1f}" fill="#6c6a78">?</text></g>')
    k = out.index('__SOLO__')
    out[k:k + 1] = [f'<g clip-path="url(#dc{uid})">'] + solo_parts
    # проявление обеих линий слева направо — через clipPath (.duel__clip), клетка фона остаётся видна
    out.append(f'<circle cx="{solo[0][0]:.1f}" cy="{solo[0][1]:.1f}" r="{fs * 0.42:.1f}" fill="#fff" stroke="{V}" stroke-width="3"/>')
    out.append(f'<path d="M{x0} {base}H{x1 + 10}" stroke="{INK}" stroke-opacity=".35" stroke-width="1.6"/>')
    out.append(f'<text x="{x0}" y="{base + fs * 1.6:.1f}" font-family="JetBrains Mono, monospace" font-size="{fs * 0.85:.1f}" fill="#6c6a78">старт</text>')
    out.append(f'<text x="{x1}" y="{base + fs * 1.6:.1f}" text-anchor="end" font-family="JetBrains Mono, monospace" font-size="{fs * 0.85:.1f}" fill="#6c6a78">экзамен</text>')
    out.append('</svg>')
    return '\n            '.join(out)


# широкий график (компьютер)
me_w = me_points(48, 816, 236, 52, 24, 9, 3)
solo_w = [(48, 236), (92, 214), (128, 172), (156, 226), (196, 244), (238, 150), (270, 104), (304, 214), (346, 240),
          (392, 196), (430, 232), (468, 132), (500, 186), (540, 246), (590, 214), (628, 120), (664, 226), (706, 192), (744, 168)]
wide = chart(900, 300, 258, 40, 860, 15, me_w, [(8, 'план подготовки'), (13, 'разбор ошибок'), (18, 'пробные варианты')],
             solo_w, [96, 168, 238], 'duel__chart--wide', 'w')
# узкий график (телефон)
me_n = me_points(26, 318, 240, 72, 14, 6, 7)
solo_n = [(26, 240), (52, 196), (70, 236), (96, 136), (118, 226), (146, 246), (168, 168), (190, 222), (214, 120), (238, 214), (262, 186)]
narrow = chart(360, 300, 262, 20, 346, 14, me_n, [(5, 'план'), (10, 'пробники')], solo_n, [112, 178, 244], 'duel__chart--narrow', 'n')

s = open(PAGE, encoding='utf-8').read()
s, n1 = re.subn(r'<svg class="duel__chart duel__chart--wide".*?</svg>', lambda m: wide, s, count=1, flags=re.S)
s, n2 = re.subn(r'<svg class="duel__chart duel__chart--narrow".*?</svg>', lambda m: narrow, s, count=1, flags=re.S)
assert n1 == 1 and n2 == 1, 'не нашёл графики дуэли на странице цен'
open(PAGE, 'w', encoding='utf-8').write(s)
print('ok')
