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


def label(x, y, text, fs, color, anchor='start', weight=700, family='Jura, sans-serif'):
    return (f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" font-family="{family}" font-weight="{weight}" '
            f'font-size="{fs:.1f}" fill="{color}" stroke="#fff" stroke-width="{fs * 0.32:.1f}" stroke-linejoin="round" paint-order="stroke">{text}</text>')


def chart(W, H, base, x0, xe, top, fs, me, solo, fan, notes, months, cls, uid):
    """Понятный график: оси подписаны (баллы ↑, месяцы →), вертикаль «ЕГЭ», подписи линий справа у их концов,
    пометки «загорелся / забросил» на серой линии."""
    ex, ey = me[-1]
    path = smooth(me)
    sx, sy = solo[-1]
    M = '#6c6a78'
    lx = xe + fs * 1.1  # колонка подписей справа
    out = [f'<svg class="duel__chart {cls}" viewBox="0 0 {W} {H}" fill="none" role="img" aria-label="График за учебный год: самостоятельно баллы то растут, то падают, и итог непредсказуем; на занятиях баллы стабильно растут до 90+ к ЕГЭ">',
           f'<defs><linearGradient id="dg{uid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{V}" stop-opacity=".25"/><stop offset="1" stop-color="{V}" stop-opacity="0"/></linearGradient>'
           f'<clipPath id="dc{uid}"><rect class="duel__clip" x="0" y="-40" width="{W}" height="{base + 38}"/></clipPath></defs>']
    out.append(f'<g stroke="{INK}" stroke-opacity=".12" stroke-width="1" stroke-dasharray="3 6">' +
               ''.join(f'<path d="M{x0} {base - (base - top) * k / 4:.0f}H{xe}"/>' for k in (1, 2, 3, 4)) + '</g>')
    out.append(f'<path d="M{x0} {base}V{top - fs * 1.2:.0f}" stroke="{INK}" stroke-opacity=".45" stroke-width="1.6"/>'
               f'<path d="M{x0 - fs * .35:.1f} {top - fs * .6:.1f}L{x0} {top - fs * 1.3:.1f}L{x0 + fs * .35:.1f} {top - fs * .6:.1f}" stroke="{INK}" stroke-opacity=".45" stroke-width="1.6"/>')
    out.append(f'<text x="{x0 + fs * .6:.1f}" y="{top - fs * .55:.1f}" font-family="JetBrains Mono, monospace" font-size="{fs * .85:.1f}" fill="{M}">баллы</text>')
    out.append(f'<path d="M{x0} {base}H{xe}" stroke="{INK}" stroke-opacity=".45" stroke-width="1.6"/>')
    # вертикаль «ЕГЭ» — финиш, где сравниваются результаты
    out.append(f'<path d="M{xe} {base}V{top - fs * .4:.0f}" stroke="{INK}" stroke-opacity=".35" stroke-width="1.4" stroke-dasharray="4 4"/>')
    for x, t, a in months:
        out.append(f'<text x="{x:.1f}" y="{base + fs * 1.55:.1f}" text-anchor="{a}" font-family="JetBrains Mono, monospace" font-size="{fs * .85:.1f}" fill="{M}">{t}</text>')
    out.append(f'<text x="{xe:.1f}" y="{base + fs * 1.55:.1f}" text-anchor="middle" font-family="Jura, sans-serif" font-weight="700" font-size="{fs:.1f}" fill="{INK}">ЕГЭ</text>')
    out.append(f'<g clip-path="url(#dc{uid})">')
    out.append(f'<path d="{smooth(solo)}" stroke="{G}" stroke-width="{fs * 0.24:.1f}" stroke-linecap="round" stroke-linejoin="round"/>')
    for fy in fan:
        out.append(f'<path d="M{sx:.1f} {sy:.1f}Q{(sx + xe) / 2:.1f} {sy:.1f} {xe:.1f} {fy:.1f}" stroke="{G}" stroke-width="{fs * 0.14:.1f}" stroke-dasharray="2 5" stroke-linecap="round"/>'
                   f'<circle cx="{xe:.1f}" cy="{fy:.1f}" r="{fs * 0.28:.1f}" fill="{G}"/>')
    for (nx, ny, txt, up) in notes:
        ty = ny - fs * 1.0 if up else ny + fs * 1.75
        out.append(f'<circle cx="{nx:.1f}" cy="{ny:.1f}" r="{fs * .3:.1f}" fill="{G}"/>' + label(nx, ty, txt, fs * .85, M, 'middle', 600, 'JetBrains Mono, monospace'))
    out.append(f'<path d="{path}L{ex:.1f} {base}L{me[0][0]:.1f} {base}Z" fill="url(#dg{uid})"/>')
    out.append(f'<path d="{path}" stroke="{V}" stroke-width="{fs * 0.3:.1f}" stroke-linecap="round" stroke-linejoin="round"/>')
    out.append(f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="{fs * 1.05:.1f}" fill="{V}" fill-opacity=".18"/><circle cx="{ex:.1f}" cy="{ey:.1f}" r="{fs * 0.55:.1f}" fill="{V}"/>')
    # подписи справа: со мной → ЕГЭ 90+; самостоятельно → итог непредсказуем
    out.append(f'<text x="{lx:.1f}" y="{ey - fs * .5:.1f}" font-family="Jura, sans-serif" font-weight="700" font-size="{fs * 1.1:.1f}" fill="{V}">со мной</text>')
    pw = fs * 5.6
    out.append(f'<rect x="{lx:.1f}" y="{ey + fs * .2:.1f}" width="{pw:.1f}" height="{fs * 1.9:.1f}" rx="{fs * .95:.1f}" fill="{INK}"/>'
               f'<text x="{lx + pw / 2:.1f}" y="{ey + fs * .2 + fs * 1.32:.1f}" text-anchor="middle" font-family="Jura, sans-serif" font-weight="700" font-size="{fs:.1f}" fill="#fff">ЕГЭ 90+</text>')
    fm = sorted(fan)[1]
    out.append(f'<text x="{lx:.1f}" y="{fm - fs * .35:.1f}" font-family="Jura, sans-serif" font-weight="700" font-size="{fs * 1.1:.1f}" fill="{M}">самостоятельно</text>')
    out.append(f'<text x="{lx:.1f}" y="{fm + fs * 1.0:.1f}" font-family="JetBrains Mono, monospace" font-size="{fs * .85:.1f}" fill="{M}">итог — лотерея</text>')
    out.append('</g>')
    out.append(f'<circle cx="{solo[0][0]:.1f}" cy="{solo[0][1]:.1f}" r="{fs * 0.42:.1f}" fill="#fff" stroke="{INK}" stroke-opacity=".6" stroke-width="2.5"/>')
    out.append('</svg>')
    return '\n            '.join(out)


# широкий график (компьютер): справа колонка подписей
me_w = me_points(80, 780, 270, 84, 22, 8, 3)
solo_w = [(80, 270), (118, 250), (150, 208), (180, 258), (214, 276), (254, 190), (286, 146), (320, 246), (360, 274),
          (404, 232), (440, 262), (476, 170), (508, 214), (546, 252), (590, 228), (626, 160), (660, 252), (696, 222), (730, 206)]
wide = chart(1000, 330, 286, 66, 780, 52, 15, me_w, solo_w, [126, 206, 262],
             [(286, 146, 'загорелся', True), (546, 252, 'забросил', False)],
             [(80, 'сентябрь', 'start'), (430, 'январь', 'middle'), (690, 'май', 'middle')], 'duel__chart--wide', 'w')
# узкий график (телефон)
me_n = me_points(40, 232, 266, 92, 12, 5, 7)
solo_n = [(40, 266), (58, 230), (74, 262), (94, 170), (114, 250), (134, 270), (154, 198), (174, 248), (192, 156), (210, 222)]
narrow = chart(400, 330, 282, 30, 232, 60, 15, me_n, solo_n, [130, 206, 268],
               [(94, 170, 'загорелся', True)],
               [(40, 'сент.', 'start'), (136, 'янв.', 'middle')], 'duel__chart--narrow', 'n')

s = open(PAGE, encoding='utf-8').read()
s, n1 = re.subn(r'<svg class="duel__chart duel__chart--wide".*?</svg>', lambda m: wide, s, count=1, flags=re.S)
s, n2 = re.subn(r'<svg class="duel__chart duel__chart--narrow".*?</svg>', lambda m: narrow, s, count=1, flags=re.S)
assert n1 == 1 and n2 == 1, 'не нашёл графики дуэли на странице цен'
open(PAGE, 'w', encoding='utf-8').write(s)
print('ok')
