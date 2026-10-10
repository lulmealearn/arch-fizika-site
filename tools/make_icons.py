"""Обложки-иконки визуализаций: линия цвета сайта #6d28d9, заливка — светлый тон того же цвета.
   Запуск: python tools/make_icons.py public/assets/icons/viz  (имя файла = slug визуализации, _<раздел>.svg — запасная иконка раздела)."""
import math, os, sys
OUT = sys.argv[1]
V, T = '#6d28d9', '#ede9fe'
def svg(body):
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 100" fill="none" stroke="%s" stroke-width="2.6" '
            'stroke-linecap="round" stroke-linejoin="round">%s</svg>\n' % (V, body))
def arrow(x1, y1, x2, y2, h=7, w=None):
    a = math.atan2(y2 - y1, x2 - x1)
    p1 = (x2 - h * math.cos(a - .45), y2 - h * math.sin(a - .45)); p2 = (x2 - h * math.cos(a + .45), y2 - h * math.sin(a + .45))
    sw = f' stroke-width="{w}"' if w else ''
    return f'<path d="M{x1:.1f} {y1:.1f}L{x2:.1f} {y2:.1f}M{p1[0]:.1f} {p1[1]:.1f}L{x2:.1f} {y2:.1f}L{p2[0]:.1f} {p2[1]:.1f}"{sw}/>'
def poly(pts): return 'M' + 'L'.join(f'{x:.1f} {y:.1f}' for x, y in pts)
def axes(x0=32, y0=86, x1=134, y1=12): return f'<g stroke-width="1.6" opacity=".5">{arrow(x0-4, y0, x1, y0, 6)}{arrow(x0, y0+4, x0, y1, 6)}</g>'
dot = lambda x, y, r=4.2: f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{V}" stroke="none"/>'
I = {}

# Тригонометрический круг
cx, cy, r, th = 80, 52, 36, math.radians(40)
px, py = cx + r * math.cos(th), cy - r * math.sin(th)
I['trigonometricheskij-krug'] = svg(
    f'<path d="M{cx} {cy}L{cx+r} {cy}A{r} {r} 0 0 0 {px:.1f} {py:.1f}Z" fill="{T}" stroke="none"/>'
    f'<g stroke-width="1.6" opacity=".5"><path d="M36 {cy}H124M{cx} 10V94"/></g>'
    f'<circle cx="{cx}" cy="{cy}" r="{r}"/><path d="M{cx} {cy}L{px:.1f} {py:.1f}"/>'
    f'<path d="M{px:.1f} {py:.1f}V{cy}M{px:.1f} {py:.1f}H{cx}" stroke-width="1.8" stroke-dasharray="3 4"/>'
    f'<path d="M{cx} {cy}H{px:.1f}" stroke-width="4.5"/>' + dot(px, py))

# Предел и производная: кривая, касательная, треугольник приращений
P = [(38, 82), (70, 80), (92, 60), (128, 16)]
def bez(t): return tuple((1-t)**3*P[0][i] + 3*(1-t)**2*t*P[1][i] + 3*(1-t)*t*t*P[2][i] + t**3*P[3][i] for i in (0, 1))
bx, by = bez(.5); dx, dy = 82.5, -60; L = math.hypot(dx, dy); ux, uy = dx / L, dy / L
k = dy / dx
I['predel-i-proizvodnaya'] = svg(axes() +
    f'<path d="M{P[0][0]} {P[0][1]}C{P[1][0]} {P[1][1]} {P[2][0]} {P[2][1]} {P[3][0]} {P[3][1]}"/>'
    f'<path d="M{bx-34*ux:.1f} {by-34*uy:.1f}L{bx+40*ux:.1f} {by+40*uy:.1f}" stroke-width="1.8" stroke-dasharray="4 4"/>'
    f'<path d="M{bx:.1f} {by:.1f}H{bx+20:.1f}V{by+20*k:.1f}Z" fill="{T}" stroke-width="1.8"/>' + dot(bx, by))

# Интеграл: площадь под графиком
f = lambda x: 80 - 52 * math.exp(-((x - 82) / 30) ** 2)
xs = [36 + i for i in range(0, 95)]
a, b = 58, 110
area = [(a, 86)] + [(x, f(x)) for x in range(a, b + 1)] + [(b, 86)]
I['integral'] = svg(f'<path d="{poly(area)}Z" fill="{T}" stroke="none"/>' + axes() +
    f'<path d="{poly([(x, f(x)) for x in xs])}"/>' +
    f'<path d="M{a} 86V{f(a):.1f}M{b} 86V{f(b):.1f}" stroke-width="1.8" stroke-dasharray="3 4"/>')

# Равномерное и равнопеременное: x(t) прямая и парабола
kk = 72 / 78 ** 2
par = [(34 + i, 86 - kk * i * i) for i in range(0, 79)]
I['ravnomernoe-i-ravnoperemennoe'] = svg(axes() +
    '<path d="M34 86L128 44" stroke-width="2" stroke-dasharray="5 5"/>' + f'<path d="{poly(par)}"/>' + dot(*par[-1]) + dot(128, 44, 3.4))

# Бросок под углом
traj = [(x, 86 - 62 * (1 - ((x - 80) / 48) ** 2)) for x in range(32, 129)]
bx, by = 100, 86 - 62 * (1 - (20 / 48) ** 2); sl = 124 * 20 / 48 ** 2; L = math.hypot(1, sl)
a0 = math.atan(124 * 48 / 48 ** 2)
I['brosok-pod-uglom'] = svg('<path d="M18 86H142" stroke-width="2"/>' +
    f'<path d="{poly(traj)}" stroke-width="2" stroke-dasharray="4 5"/>' +
    f'<path d="M46 86A14 14 0 0 0 {32+14*math.cos(a0):.1f} {86-14*math.sin(a0):.1f}" stroke-width="1.8"/>' +
    arrow(bx, by, bx + 24 / L, by + 24 * sl / L) + arrow(bx, by, bx, by + 24, 6, 2) + dot(bx, by, 5))

# Движение по окружности
cx, cy, r = 80, 54, 34; ang = math.radians(45)
bx, by = cx + r * math.cos(ang), cy - r * math.sin(ang)
I['dvizhenie-po-okruzhnosti'] = svg(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{T}" stroke-width="2" stroke-dasharray="4 5"/>' + dot(cx, cy, 2.6) +
    arrow(bx, by, bx - 28 * math.sin(ang), by - 28 * math.cos(ang)) + arrow(bx, by, bx - 18 * math.cos(ang), by + 18 * math.sin(ang), 6, 2) + dot(bx, by, 5))

# Нити и блоки
I['kinematicheskie-svyazi'] = svg('<path d="M52 12H108"/><path d="M58 12l-5 6M70 12l-5 6M82 12l-5 6M94 12l-5 6M106 12l-5 6" stroke-width="1.6" opacity=".5"/>'
    '<path d="M80 12V28"/>' f'<circle cx="80" cy="40" r="12" fill="{T}"/>' + dot(80, 40, 2.6) +
    '<path d="M68 40V68M92 40V56"/><path d="M68 40A12 12 0 0 1 92 40" stroke-width="2.6"/>'
    f'<rect x="57" y="68" width="22" height="20" rx="3" fill="{T}"/><rect x="84" y="56" width="16" height="14" rx="3" fill="{T}"/>' +
    arrow(48, 70, 48, 88, 6, 2) + arrow(110, 70, 110, 54, 6, 2))

# Законы Ньютона: брусок и силы
I['dinamika'] = svg('<path d="M22 74H138" stroke-width="2"/><path d="M30 74l-6 6M44 74l-6 6M58 74l-6 6M102 74l-6 6M116 74l-6 6M130 74l-6 6" stroke-width="1.6" opacity=".5"/>'
    f'<rect x="62" y="48" width="36" height="26" rx="3" fill="{T}"/>' +
    arrow(98, 61, 132, 61) + arrow(62, 70, 38, 70, 6, 2) + arrow(80, 48, 80, 16) + arrow(80, 61, 80, 94, 7, 2) + dot(80, 61, 2.6))

# Конденсатор: пластины, поле, заряды
I['kondensator-v-cepyah'] = svg(f'<rect x="66" y="22" width="28" height="56" fill="{T}" stroke="none"/>'
    '<path d="M22 50H66M94 50H138"/><path d="M66 20V80M94 20V80" stroke-width="4.5"/>' +
    ''.join(arrow(71, y, 89, y, 5, 1.6) for y in (32, 50, 68)) +
    '<path d="M52 26V36M47 31H57M103 31H113" stroke-width="2.2"/>' + dot(22, 50, 3.4) + dot(138, 50, 3.4))

# ── Запасные иконки разделов (для новых визуализаций без своей иконки) ──
sine = [(34 + i, 50 - 26 * math.sin(i / 96 * 2 * math.pi)) for i in range(0, 97)]
I['_matematika'] = svg(f'<g stroke-width="1.6" opacity=".5">{arrow(30, 50, 136, 50, 6)}{arrow(34, 90, 34, 10, 6)}</g><path d="{poly(sine)}"/>')
I['_mekhanika'] = svg('<path d="M22 80H138" stroke-width="2"/>' f'<circle cx="62" cy="62" r="18" fill="{T}"/>' + arrow(80, 62, 124, 62) + dot(62, 62, 2.6))
mol = [(56, 34), (88, 28), (108, 50), (70, 64), (98, 74), (50, 80)]
I['_mkt-termodinamika'] = svg(f'<rect x="36" y="16" width="88" height="74" rx="6" fill="{T}" stroke-width="2.2"/>' +
    ''.join(f'<circle cx="{x}" cy="{y}" r="5.5" fill="{V}" stroke="none"/>' for x, y in mol) +
    ''.join(f'<path d="M{x+7} {y-3}l8 -4" stroke-width="1.8"/>' for x, y in (mol[0], mol[1], mol[3])))
I['_elektrodinamika'] = svg('<path d="M74 78H40V22H120V78H86" stroke-width="2.4"/>'
    '<path d="M74 66V90" stroke-width="2.4"/><path d="M86 72V84" stroke-width="5"/>'
    f'<rect x="66" y="14" width="28" height="16" rx="2" fill="{T}"/>' + arrow(128, 40, 128, 62, 6, 2))
I['_optika'] = svg(f'<path d="M80 12Q96 50 80 88Q64 50 80 12Z" fill="{T}"/>'
    '<path d="M24 30H80L124 50M24 50H124M24 70H80L124 50" stroke-width="2"/>' + dot(124, 50, 3.6) +
    '<path d="M20 50H140" stroke-width="1.2" opacity=".4" stroke-dasharray="3 4"/>')
I['_kvanty'] = svg(f'<ellipse cx="80" cy="50" rx="44" ry="16" transform="rotate(-25 80 50)"/><ellipse cx="80" cy="50" rx="44" ry="16" transform="rotate(25 80 50)"/>'
    f'<circle cx="80" cy="50" r="9" fill="{T}"/>' + dot(80, 50, 3.2) + dot(119.9, 31.4, 4) + dot(44, 70, 4))

os.makedirs(OUT, exist_ok=True)
for k, v in I.items():
    open(os.path.join(OUT, k + '.svg'), 'w', encoding='utf-8').write(v)
print(len(I), 'icons')
