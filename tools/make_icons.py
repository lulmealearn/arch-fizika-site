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

# ── Векторы и проекции: сложение по правилу параллелограмма и проекция на ось ──
O, A, Bv = (36, 80), (96, 66), (58, 30)
C = (A[0] + Bv[0] - O[0], A[1] + Bv[1] - O[1])
para = f'<path d="{poly([O, A, C, Bv])}Z"/>'
I['vektory-i-proekcii-pravila-slozheniya-vektorov'] = svg(
    shade(para, 4, 3) + f'<path d="{poly([O, A, C, Bv])}Z" fill="{L}" stroke="none"/>' +
    '<path d="M22 90H146" stroke-width="2.2" opacity=".55"/>' +
    f'<path d="M{A[0]} {A[1]}L{C[0]} {C[1]}M{Bv[0]} {Bv[1]}L{C[0]} {C[1]}" stroke-width="2.2" stroke-dasharray="4 5"/>' +
    f'<path d="M{C[0]} {C[1]}V90" stroke-width="2.2" stroke-dasharray="3 5"/>' +
    f'<path d="M{O[0]} 90H{C[0]}" stroke-width="5"/>' +
    arrow(*O, *A, 8, 2.8) + arrow(*O, *Bv, 8, 2.8) + arrow(*O, *C, 10) + dot(*O, 4))

# ── Статика: рычаг на опоре, грузы на разных плечах ──
fulcrum = '<path d="M80 58L94 84H66Z"/>'
w_big = '<rect x="32" y="62" width="22" height="18" rx="3"/>'
w_small = '<rect x="118" y="62" width="14" height="12" rx="2"/>'
I['statika'] = svg(
    '<path d="M18 86H142" stroke-width="2.6"/>' +
    shade(fulcrum) + f'<path d="M80 58L94 84H66Z" fill="{L}"/>' +
    '<path d="M24 54H136" stroke-width="5"/>' + dot(80, 56, 3.4, L) +
    '<path d="M43 54V62M125 54V62" stroke-width="2.4"/>' +
    shade(w_big, 3, 3) + w_big + shade(w_small, 3, 3) + w_small +
    '<g stroke-width="2.2" opacity=".7"><path d="M43 30H80M80 22V38M43 24V36"/><path d="M80 40H125M125 34V46"/></g>')

# ── Закон изменения энергии в цепях: лампочка, энергия уходит в свет и тепло ──
bulb = '<path d="M80 12C62 12 52 26 52 40C52 52 60 58 64 66V72H96V66C100 58 108 52 108 40C108 26 98 12 80 12Z"/>'
I['zakon-izmeneniya-energii-v-cepyah'] = svg(
    shade(bulb) + f'<path d="M80 12C62 12 52 26 52 40C52 52 60 58 64 66V72H96V66C100 58 108 52 108 40C108 26 98 12 80 12Z" fill="{L}"/>' +
    '<path d="M72 60V48M88 60V48" stroke-width="2.4"/>' +
    '<path d="M72 48C72 40 77 40 77 46C77 52 83 52 83 46C83 40 88 40 88 48" stroke-width="2.6"/>' +
    f'<rect x="66" y="72" width="28" height="14" rx="4" fill="{M}"/>' + '<path d="M66 79H94" stroke-width="2.2"/>' +
    '<path d="M74 92H86" stroke-width="3.4"/>' +
    '<g stroke-width="2.6"><path d="M36 22L28 16M32 40H22M36 58L28 64M124 22L132 16M128 40H138M124 58L132 64"/></g>')

# ── Напряжённость и потенциал: заряд, силовые линии и эквипотенциали ──
qx, qy = 80, 50
rays = ''.join(arrow(qx + 16 * math.cos(a), qy + 16 * math.sin(a), qx + 44 * math.cos(a), qy + 44 * math.sin(a), 7, 2.6)
               for a in [math.radians(d) for d in (0, 60, 120, 180, 240, 300)])
I['napryazhennost-i-potencial-polya-interaktivnyj-razbor'] = svg(
    f'<circle cx="{qx}" cy="{qy}" r="28" stroke-width="2" stroke-dasharray="3 5" opacity=".7"/>' +
    f'<circle cx="{qx}" cy="{qy}" r="40" stroke-width="2" stroke-dasharray="3 5" opacity=".5"/>' +
    rays +
    shade(f'<circle cx="{qx}" cy="{qy}" r="12"/>', 3, 3) + f'<circle cx="{qx}" cy="{qy}" r="12" fill="{L}"/>' +
    f'<path d="M{qx - 6} {qy}H{qx + 6}M{qx} {qy - 6}V{qy + 6}" stroke-width="3"/>')

# ── Внутренняя энергия и работа газа: цилиндр с поршнем над огнём ──
cyl = '<path d="M50 20V78H110V20"/>'
gas = ''.join(dot(x, y, 3, M) for x, y in [(62, 66), (78, 58), (96, 68), (70, 50), (90, 48), (100, 56), (60, 54), (84, 70)])
I['vnutrennyaya-energiya-rabota-gaza-i-pervoe-nachalo-termodina'] = svg(
    '<g transform="translate(0 -10)">' +
    shade('<rect x="50" y="36" width="60" height="42"/>', 4, 3, L) + gas + cyl +
    f'<rect x="52" y="30" width="56" height="9" rx="2" fill="{M}"/>' + '<path d="M80 30V14" stroke-width="3"/>' +
    arrow(124, 44, 124, 18, 8, 2.8) + '</g>' +
    f'<path d="M80 96C70 96 66 88 72 82C72 88 76 88 76 84C76 80 80 78 80 74C84 78 90 82 88 88C87 93 84 96 80 96Z" fill="{L}" stroke-width="2.6"/>')

# ── Проводники и диэлектрики: пластина во внешнем поле, заряды на гранях ──
plate = '<rect x="62" y="20" width="36" height="60" rx="5"/>'
I['provodniki-i-dielektriki-v-elektricheskom-pole'] = svg(
    ''.join(arrow(14, y, 56, y, 7, 2.6) + arrow(104, y, 146, y, 7, 2.6) for y in (30, 50, 70)) +
    shade(plate) + f'<rect x="62" y="20" width="36" height="60" rx="5" fill="{L}"/>' +
    ''.join(f'<path d="M66 {y}H72" stroke-width="2.8"/>' for y in (32, 50, 68)) +
    ''.join(f'<path d="M88 {y}H94M91 {y - 3}V{y + 3}" stroke-width="2.6"/>' for y in (32, 50, 68)))

# ── Относительность движения: тележка-платформа и шарик на ней, у каждого своя скорость ──
plat = '<rect x="36" y="52" width="88" height="18" rx="4"/>'
I['otnositelnost-dvizheniya'] = svg(
    '<path d="M14 90H146" stroke-width="2.6"/>' +
    shade(plat) + f'<rect x="36" y="52" width="88" height="18" rx="4" fill="{L}"/>' +
    f'<circle cx="54" cy="79" r="8" fill="{L}"/><circle cx="106" cy="79" r="8" fill="{L}"/>' + dot(54, 79, 2.4) + dot(106, 79, 2.4) +
    shade('<circle cx="72" cy="40" r="10"/>', 3, 2) + f'<circle cx="72" cy="40" r="10"/>' +
    arrow(86, 40, 112, 40, 8, 2.8) + arrow(40, 24, 120, 24, 9))

# ── Закон сохранения импульса: два шара летят навстречу ──
I['zakon-sohraneniya-impulsa'] = svg(
    '<path d="M14 84H146" stroke-width="2.2" opacity=".55"/>' +
    shade('<circle cx="48" cy="56" r="20"/>') + f'<circle cx="48" cy="56" r="20" fill="{L}"/>' +
    shade('<circle cx="112" cy="62" r="14"/>', 3, 3) + f'<circle cx="112" cy="62" r="14"/>' +
    arrow(30, 24, 66, 24, 9) + arrow(130, 34, 100, 34, 8, 2.8) +
    '<path d="M76 46l6 6M84 40v8M88 50l6-4" stroke-width="2.4"/>')

# ── Работа, энергия, мощность: брусок, сила и перемещение ──
blk = '<rect x="46" y="44" width="40" height="32" rx="4"/>'
I['rabota-energiya-moschnost'] = svg(
    '<path d="M14 76H146" stroke-width="2.6"/>' + '<g stroke-width="2" opacity=".6"><path d="M24 76l-6 8M40 76l-6 8M56 76l-6 8M72 76l-6 8M88 76l-6 8M104 76l-6 8M120 76l-6 8M136 76l-6 8"/></g>' +
    shade(blk) + f'<rect x="46" y="44" width="40" height="32" rx="4" fill="{L}"/>' +
    arrow(86, 60, 134, 40, 9) +
    '<path d="M46 26H112" stroke-width="2.4" stroke-dasharray="4 5"/>' + arrow(100, 26, 116, 26, 7, 2.4))

# ── МКТ идеального газа: сосуд с молекулами и их скоростями ──
box = '<rect x="38" y="16" width="84" height="70" rx="6"/>'
mol = [(58, 38, 18, -10), (92, 32, -14, 12), (74, 62, 16, 8), (104, 68, -10, -14), (54, 70, 12, -12)]
I['mkt-idealnogo-gaza'] = svg(
    shade(box) + f'<rect x="38" y="16" width="84" height="70" rx="6" fill="{L}"/>' +
    ''.join(arrow(x, y, x + dx, y + dy, 6, 2.2) for x, y, dx, dy in mol) +
    ''.join(dot(x, y, 5, V) for x, y, _, _ in mol))

# ── Тепловые машины: нагреватель → рабочее тело → холодильник, работа в сторону ──
I['teplovye-mashiny-shema-znaki-q-rabota-cikla-cikl-karno'] = svg(
    shade('<rect x="40" y="6" width="80" height="18" rx="5"/>', 3, 2) + f'<rect x="40" y="6" width="80" height="18" rx="5" fill="{M}"/>' +
    f'<rect x="40" y="78" width="80" height="18" rx="5" fill="{L}"/>' +
    shade('<circle cx="80" cy="51" r="14"/>', 3, 3) + f'<circle cx="80" cy="51" r="14" fill="{L}"/>' +
    arrow(80, 25, 80, 36, 7, 2.8) + arrow(80, 66, 80, 77, 7, 2.8) + arrow(95, 51, 132, 51, 8, 2.8) +
    '<path d="M50 15h6M104 15h6" stroke-width="2.6"/><path d="M50 87h6M104 87h6" stroke-width="2.6"/>')

# ── Тепловой баланс: калориметр — стакан с водой, кубик льда и термометр ──
cup = '<path d="M42 30L48 88H104L110 30"/>'
I['teplovoj-balans-tverdoe-telo-zhidkost-gaz'] = svg(
    shade('<path d="M42 30L48 88H104L110 30Z"/>') +
    f'<path d="M45 52L48 88H104L107 52Z" fill="{L}" stroke="none"/>' + cup + '<path d="M45 52H107" stroke-width="2.2"/>' +
    f'<rect x="58" y="42" width="18" height="18" rx="3" fill="#fff" transform="rotate(-12 67 51)"/>' +
    f'<rect x="88" y="10" width="10" height="56" rx="5" fill="#fff"/>' + f'<circle cx="93" cy="70" r="8" fill="{M}"/>' +
    '<path d="M93 30V66" stroke-width="3.4"/>')

# ── Испарение и кипение: колба с пузырьками, пар над ней, огонь снизу ──
flask = '<path d="M68 14V36L44 76A8 8 0 0 0 51 88H109A8 8 0 0 0 116 76L92 36V14"/>'
I['isparenie-nasyschennyj-par-kipenie'] = svg(
    shade('<path d="M68 14V36L44 76A8 8 0 0 0 51 88H109A8 8 0 0 0 116 76L92 36V14Z"/>', 4, 2, L) +
    f'<path d="M55 58H105L116 76A8 8 0 0 1 109 88H51A8 8 0 0 1 44 76Z" fill="{M}" stroke="none"/>' + flask +
    '<path d="M64 14H96" stroke-width="3"/>' +
    ''.join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#fff" stroke-width="2"/>' for x, y, r in [(66, 76, 4), (84, 70, 5), (98, 79, 3.5), (76, 64, 3)]) +
    '<path d="M124 30c-6-5 6-9 0-14M136 34c-6-5 6-9 0-14" stroke-width="2.4"/>')

# ── Конденсатор как электростатическая система: пластины, заряды и поле между ними ──
I['kondensator-kak-elektrostaticheskaya-sistema'] = svg(
    shade('<rect x="40" y="14" width="12" height="72" rx="3"/><rect x="108" y="14" width="12" height="72" rx="3"/>', 3, 2) +
    f'<rect x="40" y="14" width="12" height="72" rx="3" fill="{L}"/><rect x="108" y="14" width="12" height="72" rx="3" fill="{L}"/>' +
    ''.join(arrow(56, y, 102, y, 7, 2.4) for y in (28, 50, 72)) +
    '<path d="M22 44v12M16 50h12" stroke-width="3"/><path d="M132 50h12" stroke-width="3"/>')

# ── Теорема Гаусса: замкнутая сфера вокруг заряда, поток наружу ──
I['teorema-gaussa'] = svg(
    shade('<circle cx="80" cy="50" r="30"/>', 4, 3, L) + '<circle cx="80" cy="50" r="30"/>' +
    '<ellipse cx="80" cy="50" rx="30" ry="9" stroke-width="2" stroke-dasharray="4 5"/>' +
    ''.join(arrow(80 + 12 * math.cos(a), 50 + 12 * math.sin(a), 80 + 46 * math.cos(a), 50 + 46 * math.sin(a), 7, 2.4)
            for a in [math.radians(d) for d in (-30, 30, 150, 210, 90, 270)]) +
    f'<circle cx="80" cy="50" r="9" fill="#fff"/>' + '<path d="M75 50H85M80 45V55" stroke-width="2.8"/>')

# ── Законы постоянного тока: замкнутая цепь — источник, резистор, ток ──
I['zakony-postoyannogo-toka'] = svg(
    '<path d="M30 44V20H130V80H30V56" stroke-width="3"/>' +
    f'<rect x="62" y="12" width="36" height="16" rx="3" fill="{L}"/>' +
    '<path d="M20 44H40" stroke-width="3.4"/><path d="M25 56H35" stroke-width="5"/>' +
    shade('<circle cx="130" cy="50" r="12"/>', 3, 2) + f'<circle cx="130" cy="50" r="12" fill="#fff"/>' + '<path d="M125 55L130 44L135 55M127 51H133" stroke-width="2.4"/>' +
    arrow(66, 80, 96, 80, 8, 2.8))

# ── Метод узловых потенциалов: узлы, ветви с резисторами, заземление ──
nodes = [(34, 30), (126, 30), (80, 78)]
def zig(x1, y1, x2, y2):
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    dx, dy = x2 - x1, y2 - y1
    ln = math.hypot(dx, dy); ux, uy = dx / ln, dy / ln; px, py = -uy, ux
    pts = [(x1, y1), (mx - 14 * ux, my - 14 * uy)]
    for k in range(-2, 3):
        t = k * 6
        pts.append((mx + t * ux + (5 if k % 2 else -5) * px, my + t * uy + (5 if k % 2 else -5) * py))
    pts += [(mx + 14 * ux, my + 14 * uy), (x2, y2)]
    return f'<path d="{poly(pts)}" stroke-width="2.6"/>'
I['metod-uzlovyh-potencialov'] = svg(
    zig(*nodes[0], *nodes[1]) + zig(*nodes[0], *nodes[2]) + zig(*nodes[1], *nodes[2]) +
    '<path d="M80 78V90M70 90H90M74 95H86" stroke-width="2.6"/>' +
    ''.join(shade(f'<circle cx="{x}" cy="{y}" r="8"/>', 2, 2) + f'<circle cx="{x}" cy="{y}" r="8" fill="{L}"/>' for x, y in nodes))

# ── Закон Джоуля — Ленца: резистор греется ──
res = '<rect x="50" y="52" width="60" height="22" rx="4"/>'
I['zakon-dzhoulya-lenca-i-kpd-cepi'] = svg(
    '<path d="M14 63H50M110 63H146" stroke-width="3"/>' +
    shade(res) + f'<rect x="50" y="52" width="60" height="22" rx="4" fill="{M}"/>' +
    '<g stroke-width="2.6"><path d="M62 42c-6-6 6-10 0-16s6-10 0-16"/><path d="M80 42c-6-6 6-10 0-16s6-10 0-16"/><path d="M98 42c-6-6 6-10 0-16s6-10 0-16"/></g>' +
    arrow(22, 82, 42, 82, 7, 2.6))

# ── Нелинейные элементы: вольт-амперная характеристика и диод ──
I['nelinejnye-elementy-v-cepyah-postoyannogo-toka'] = svg(
    axes(30, 86, 140, 10) +
    f'<path d="{poly([(30 + x, 86 - 0.45 * math.exp(x / 18.0)) for x in range(0, 96, 2)])}"/>' +
    shade('<path d="M48 26L48 50L68 38Z"/>', 3, 2) + f'<path d="M48 26L48 50L68 38Z" fill="{L}"/>' +
    '<path d="M68 26V50M38 38H48M68 38H78" stroke-width="2.8"/>')

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
