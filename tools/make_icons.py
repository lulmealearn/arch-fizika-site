"""Обложки-иконки визуализаций в манере «lineal color» (как на Flaticon), но в цвете сайта:
   толстый фиолетовый контур #6d28d9, плоская заливка двумя светлыми тонами, смещённая от контура.
   Запуск: python tools/make_icons.py public/assets/icons/viz
   Имя файла = slug визуализации; _<раздел>.svg — запасная иконка раздела."""
import math
import os
import sys

OUT = sys.argv[1] if len(sys.argv) > 1 else 'public/assets/icons/viz'
V = '#6d28d9'   # контур, акценты
M = '#c4b5fd'   # насыщенная заливка (смещённая «тень»)
L = '#ede9fe'   # светлая заливка
SW = 3.4        # основная толщина линии


def svg(body):
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 100" fill="none" stroke="%s" stroke-width="%s" '
            'stroke-linecap="round" stroke-linejoin="round">%s</svg>\n' % (V, SW, body))


def shade(shape, dx=4, dy=3, fill=M):
    """Фирменный приём lineal color: цветная заливка формы, сдвинутая от контура."""
    return f'<g transform="translate({dx} {dy})" fill="{fill}" stroke="none">{shape}</g>'


def arrow(x1, y1, x2, y2, h=8, w=None):
    a = math.atan2(y2 - y1, x2 - x1)
    p1 = (x2 - h * math.cos(a - .5), y2 - h * math.sin(a - .5))
    p2 = (x2 - h * math.cos(a + .5), y2 - h * math.sin(a + .5))
    sw = f' stroke-width="{w}"' if w else ''
    return (f'<path d="M{x1:.1f} {y1:.1f}L{x2:.1f} {y2:.1f}"{sw}/>'
            f'<path d="M{p1[0]:.1f} {p1[1]:.1f}L{x2:.1f} {y2:.1f}L{p2[0]:.1f} {p2[1]:.1f}Z" fill="{V}"{sw}/>')


def poly(pts):
    return 'M' + 'L'.join(f'{x:.1f} {y:.1f}' for x, y in pts)


def dot(x, y, r=4.5, fill=V):
    return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{fill}" stroke="none"/>'


def axes(x0=30, y0=86, x1=136, y1=10):
    return f'<g stroke-width="2.2" opacity=".55">{arrow(x0 - 4, y0, x1, y0, 7, 2.2)}{arrow(x0, y0 + 4, x0, y1, 7, 2.2)}</g>'


I = {}

# ── Тригонометрический круг ──
cx, cy, r, th = 80, 50, 34, math.radians(40)
px, py = cx + r * math.cos(th), cy - r * math.sin(th)
I['trigonometricheskij-krug'] = svg(
    shade(f'<circle cx="{cx}" cy="{cy}" r="{r}"/>') +
    f'<path d="M{cx} {cy}L{cx + r} {cy}A{r} {r} 0 0 0 {px:.1f} {py:.1f}Z" fill="{L}" stroke="none"/>' +
    f'<g stroke-width="2.2" opacity=".55"><path d="M38 {cy}H122M{cx} 8V92"/></g>' +
    f'<circle cx="{cx}" cy="{cy}" r="{r}"/>' +
    f'<path d="M{cx} {cy}L{px:.1f} {py:.1f}"/>' +
    f'<path d="M{px:.1f} {py:.1f}V{cy}" stroke-width="2.4" stroke-dasharray="3 5"/>' +
    f'<path d="M{cx + 12} {cy}A12 12 0 0 0 {cx + 12 * math.cos(th):.1f} {cy - 12 * math.sin(th):.1f}" stroke-width="2.4"/>' +
    dot(px, py, 5.5))

# ── Предел и производная: лупа над точкой кривой — вблизи кривая становится прямой ──
P = [(22, 76), (58, 74), (88, 52), (138, 12)]
def bez(t):
    return tuple((1 - t) ** 3 * P[0][i] + 3 * (1 - t) ** 2 * t * P[1][i] + 3 * (1 - t) * t * t * P[2][i] + t ** 3 * P[3][i] for i in (0, 1))
bx, by = bez(.5)
d = (3 * (.25 * (P[1][0] - P[0][0]) + .5 * (P[2][0] - P[1][0]) + .25 * (P[3][0] - P[2][0])),
     3 * (.25 * (P[1][1] - P[0][1]) + .5 * (P[2][1] - P[1][1]) + .25 * (P[3][1] - P[2][1])))
ln = math.hypot(*d); ux, uy = d[0] / ln, d[1] / ln
R = 19
I['predel-i-proizvodnaya'] = svg(
    shade(f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="{R}"/>', 4, 4) +
    f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="{R}" fill="{L}" stroke="none"/>' +
    f'<path d="M{P[0][0]} {P[0][1]}C{P[1][0]} {P[1][1]} {P[2][0]} {P[2][1]} {P[3][0]} {P[3][1]}"/>' +
    f'<path d="M{bx - 34 * ux:.1f} {by - 34 * uy:.1f}L{bx + 34 * ux:.1f} {by + 34 * uy:.1f}" stroke-width="2.2" stroke-dasharray="4 5"/>' +
    f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="{R}"/>' +
    f'<path d="M{bx + R * .72:.1f} {by + R * .72:.1f}L{bx + R * .72 + 16:.1f} {by + R * .72 + 16:.1f}" stroke-width="7"/>' +
    dot(bx, by, 4.5))

# ── Интеграл: столбики Римана под кривой ──
f = lambda x: 80 - 52 * math.exp(-((x - 84) / 32) ** 2)
bars = ''
for i, x in enumerate(range(40, 128, 14)):
    h = f(x + 7)
    bars += f'<rect x="{x}" y="{h:.1f}" width="14" height="{86 - h:.1f}" fill="{L if i % 2 else M}" stroke-width="2"/>'
I['integral'] = svg(axes() + bars + f'<path d="{poly([(x, f(x)) for x in range(34, 136)])}"/>')

# ── Равномерное и равнопеременное движение: тележка ──
cart = '<rect x="46" y="40" width="64" height="28" rx="6"/>'
I['ravnomernoe-i-ravnoperemennoe'] = svg(
    '<path d="M18 88H142" stroke-width="2.6"/>' +
    shade(cart) + cart +
    f'<circle cx="60" cy="76" r="9" fill="{L}"/><circle cx="96" cy="76" r="9" fill="{L}"/>' + dot(60, 76, 2.6) + dot(96, 76, 2.6) +
    '<path d="M22 46H36M14 54H34M22 62H36" stroke-width="2.6"/>' +
    arrow(58, 24, 118, 24, 9))

# ── Бросок под углом: пушка и траектория ──
b = (88 - 52 + 0.839 * 76) / 76 ** 2
traj = [(x, 52 - 0.839 * (x - 60) + b * (x - 60) ** 2) for x in range(60, 137)]
barrel = '<rect x="30" y="66" width="40" height="15" rx="5" transform="rotate(-40 34 74)"/>'
ballx = 110; bally = 52 - 0.839 * 50 + b * 2500
I['brosok-pod-uglom'] = svg(
    '<path d="M14 90H146" stroke-width="2.6"/>' +
    f'<path d="{poly(traj)}" stroke-width="2.4" stroke-dasharray="4 6"/>' +
    shade(barrel) + barrel +
    f'<circle cx="38" cy="80" r="10" fill="{L}"/>' + dot(38, 80, 2.8) +
    shade(f'<circle cx="{ballx}" cy="{bally:.1f}" r="7"/>', 3, 2) + f'<circle cx="{ballx}" cy="{bally:.1f}" r="7"/>')

# ── Движение по окружности: шарик на нити ──
cx, cy, r, an = 80, 52, 34, math.radians(30)
bx, by = cx + r * math.cos(an), cy - r * math.sin(an)
I['dvizhenie-po-okruzhnosti'] = svg(
    f'<circle cx="{cx}" cy="{cy}" r="{r}" stroke-width="2.4" stroke-dasharray="4 6"/>' +
    f'<path d="M{cx} {cy}L{bx:.1f} {by:.1f}" stroke-width="2.6"/>' + dot(cx, cy, 4) +
    arrow(bx, by, bx - 28 * math.sin(an), by - 28 * math.cos(an), 9) +
    shade(f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="9"/>', 3, 3) + f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="9" fill="{L}"/>')

# ── Нити и блоки ──
w1 = '<path d="M54 66H74L78 88H50Z"/>'
w2 = '<path d="M88 56H104L107 72H85Z"/>'
I['kinematicheskie-svyazi'] = svg(
    '<path d="M50 8H110"/><path d="M58 8l-6 7M70 8l-6 7M82 8l-6 7M94 8l-6 7M106 8l-6 7" stroke-width="2"/>' +
    '<path d="M80 8V20"/>' +
    '<path d="M64 36V66M96 36V56" stroke-width="2.6"/>' +
    shade('<circle cx="80" cy="36" r="16"/>') + f'<circle cx="80" cy="36" r="16"/>' +
    '<path d="M64 36A16 16 0 0 1 96 36" stroke-width="2.6"/>' + dot(80, 36, 4) +
    shade(w1) + w1 + shade(w2, 3, 2) + w2 +
    arrow(42, 70, 42, 90, 7, 2.6) + arrow(118, 74, 118, 54, 7, 2.6))

# ── Законы Ньютона: то самое яблоко ──
apple = ('<path d="M80 36C67 26 44 30 46 54C48 76 64 92 80 85C96 92 112 76 114 54C116 30 93 26 80 36Z"/>')
I['dinamika'] = svg(
    shade(apple) + apple +
    '<path d="M80 36C80 28 82 22 87 17"/>' +
    f'<path d="M86 22C93 11 106 13 109 17C103 25 92 27 86 22Z" fill="{L}"/>' +
    f'<path d="M58 50C58 44 62 40 67 38" stroke="{L}" stroke-width="4"/>' +
    arrow(132, 30, 132, 80, 9))

# ── Конденсатор (электролитический) ──
cap = '<rect x="60" y="14" width="40" height="54" rx="9"/>'
I['kondensator-v-cepyah'] = svg(
    shade(cap) + cap +
    f'<path d="M88 14.5H91A9 9 0 0 1 99.5 23V59A9 9 0 0 1 91 67.5H88Z" fill="{L}" stroke="none"/>' +
    '<path d="M88 16V66" stroke-width="2.4"/>' +
    '<path d="M91 30H97M91 41H97M91 52H97" stroke-width="2.6"/>' +
    '<path d="M72 68V92M90 68V86"/>' +
    '<path d="M46 76V86M41 81H51" stroke-width="2.8"/>')

# ── Запасные иконки разделов ──
sine = [(40 + i, 52 - 20 * math.sin(i / 80 * 2 * math.pi)) for i in range(0, 81)]
chart = '<rect x="28" y="14" width="104" height="74" rx="10"/>'
I['_matematika'] = svg(shade(chart) + f'<rect x="28" y="14" width="104" height="74" rx="10" fill="{L}"/>' +
                       '<g stroke-width="2.2" opacity=".55"><path d="M40 52H120M40 24V80"/></g>' + f'<path d="{poly(sine)}"/>')

bob = '<circle cx="104" cy="72" r="12"/>'
I['_mekhanika'] = svg('<path d="M46 10H114"/><path d="M80 10L104 72" stroke-width="2.6"/>' +
                      '<path d="M80 10L56 72" stroke-width="2" stroke-dasharray="3 6" opacity=".6"/>' +
                      '<path d="M50 80Q80 96 110 80" stroke-width="2.2" stroke-dasharray="3 6"/>' + dot(80, 10, 4) +
                      shade(bob, 3, 3) + f'<circle cx="104" cy="72" r="12" fill="{L}"/>')

tube = '<rect x="72" y="10" width="16" height="62" rx="8"/>'
I['_mkt-termodinamika'] = svg(shade('<circle cx="80" cy="78" r="14"/>' + tube) +
                              f'<rect x="72" y="10" width="16" height="62" rx="8" fill="{L}"/>' +
                              f'<circle cx="80" cy="78" r="14" fill="{M}"/>' + f'<rect x="77" y="36" width="6" height="40" rx="3" fill="{V}" stroke="none"/>' +
                              '<path d="M96 22H104M96 34H104M96 46H104M96 58H104" stroke-width="2.6"/>')

magnet = '<path d="M50 14H68V52A12 12 0 0 0 92 52V14H110V52A30 30 0 0 1 50 52Z"/>'
I['_elektrodinamika'] = svg(shade(magnet) + magnet +
                            f'<path d="M50 14H68V28H50Z" fill="{V}"/><path d="M92 14H110V28H92Z" fill="{L}"/>' +
                            '<path d="M38 22Q20 50 46 84M122 22Q140 50 114 84" stroke-width="2.4" stroke-dasharray="3 6"/>')

lens = '<path d="M80 10Q98 50 80 90Q62 50 80 10Z"/>'
I['_optika'] = svg('<path d="M18 30H80L130 50M18 50H130M18 70H80L130 50" stroke-width="2.6"/>' +
                   shade(lens, 3, 0) + f'<path d="M80 10Q98 50 80 90Q62 50 80 10Z" fill="{L}"/>' + dot(130, 50, 4.5) +
                   '<path d="M12 50H148" stroke-width="1.6" opacity=".45" stroke-dasharray="3 5"/>')

I['_kvanty'] = svg(f'<ellipse cx="80" cy="50" rx="46" ry="17" transform="rotate(-28 80 50)"/>'
                   f'<ellipse cx="80" cy="50" rx="46" ry="17" transform="rotate(28 80 50)"/>' +
                   shade('<circle cx="80" cy="50" r="11"/>', 3, 3) + f'<circle cx="80" cy="50" r="11" fill="{L}"/>' +
                   dot(120.6, 28.4, 5) + dot(39.4, 71.6, 5))

os.makedirs(OUT, exist_ok=True)
for k, v in I.items():
    with open(os.path.join(OUT, k + '.svg'), 'w', encoding='utf-8') as fh:
        fh.write(v)
print(len(I), 'icons ->', OUT)
