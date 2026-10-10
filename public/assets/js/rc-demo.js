/* Зарядка конденсатора через резистор — живая схема и графики q(t), I(t).
   Перенесено из урока «Конденсатор в электрических цепях», раздел 4. */
(function () {
  'use strict';
  var cv = document.getElementById('rc');
  if (!cv) return;
  var $ = function (id) { return document.getElementById(id); };
  var clamp = function (v, a, b) { return Math.max(a, Math.min(b, v)); };
  var f = function (x, n) { var s = x.toFixed(n == null ? 1 : n); if (/^-0(\.0*)?$/.test(s)) s = s.slice(1); return s.replace('.', ',').replace('-', '−'); };
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* палитра сайта */
  var cs = getComputedStyle(document.documentElement);
  var P = {};
  ['ink', 'muted', 'line', 'paper', 'violet', 'magenta', 'blue', 'red', 'green', 'amber'].forEach(function (k) {
    P[k] = cs.getPropertyValue('--' + k).trim() || { red: '#d92b2b', green: '#0e8a5f', amber: '#b7791f' }[k] || '#888888';
  });
  if (!cs.getPropertyValue('--red').trim()) P.red = '#d92b2b';
  if (!cs.getPropertyValue('--green').trim()) P.green = '#0e8a5f';
  if (!cs.getPropertyValue('--amber').trim()) P.amber = '#b7791f';
  function rgb(c) { c = c.trim(); if (c[0] === '#') { var h = c.slice(1); if (h.length === 3) h = h.split('').map(function (x) { return x + x; }).join(''); return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)]; } var m = c.match(/[\d.]+/g) || [128, 128, 128]; return [+m[0], +m[1], +m[2]]; }
  var RP = rgb(P.red), RM = rgb(P.blue);
  function al(c, a) { var v = rgb(c); return 'rgba(' + v[0] + ',' + v[1] + ',' + v[2] + ',' + a + ')'; }
  function pot(fr) { fr = clamp(fr, 0, 1); return 'rgb(' + Math.round(RM[0] + (RP[0] - RM[0]) * fr) + ',' + Math.round(RM[1] + (RP[1] - RM[1]) * fr) + ',' + Math.round(RM[2] + (RP[2] - RM[2]) * fr) + ')'; }

  /* примитивы в логических координатах */
  var FS = 1;
  function line(ctx, pts, color, w, dash) { ctx.strokeStyle = color; ctx.lineWidth = w || 2.4; ctx.lineCap = 'round'; ctx.lineJoin = 'round'; if (dash) ctx.setLineDash(dash); ctx.beginPath(); ctx.moveTo(pts[0][0], pts[0][1]); for (var i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]); ctx.stroke(); if (dash) ctx.setLineDash([]); }
  function txt(ctx, s, x, y, color, size, align, weight) { ctx.font = (weight || 600) + ' ' + ((size || 12) * FS) + "px 'JetBrains Mono', ui-monospace, Menlo, monospace"; ctx.fillStyle = color; ctx.textAlign = align || 'left'; ctx.textBaseline = 'middle'; ctx.fillText(s, x, y); }
  function sub(ctx, a, b, x, y, color, size, align) { /* буква с индексом, без юникод-индексов */
    size = size || 12; ctx.font = '700 ' + (size * FS) + "px 'JetBrains Mono', ui-monospace, Menlo, monospace";
    var wa = ctx.measureText(a).width; ctx.font = '700 ' + (size * 0.72 * FS) + "px 'JetBrains Mono', ui-monospace, Menlo, monospace";
    var wb = ctx.measureText(b).width, x0 = align === 'center' ? x - (wa + wb) / 2 : x;
    txt(ctx, a, x0, y, color, size, 'left', 700); txt(ctx, b, x0 + wa, y + size * 0.3 * FS, color, size * 0.72, 'left', 700);
  }
  function arrow(ctx, x1, y1, x2, y2, color, w, head) { var dx = x2 - x1, dy = y2 - y1, L = Math.hypot(dx, dy); if (L < 2) return; var ux = dx / L, uy = dy / L, h = Math.min(head || 9, L * 0.45); ctx.strokeStyle = color; ctx.lineWidth = w || 2; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2 - ux * h * 0.7, y2 - uy * h * 0.7); ctx.stroke(); ctx.fillStyle = color; ctx.beginPath(); ctx.moveTo(x2, y2); ctx.lineTo(x2 - ux * h - uy * h * 0.45, y2 - uy * h + ux * h * 0.45); ctx.lineTo(x2 - ux * h + uy * h * 0.45, y2 - uy * h - ux * h * 0.45); ctx.closePath(); ctx.fill(); }
  function dot(ctx, x, y, r, color) { ctx.fillStyle = color; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill(); }
  function rot(ctx, a, b, fn) { var dx = b[0] - a[0], dy = b[1] - a[1], L = Math.hypot(dx, dy); ctx.save(); ctx.translate(a[0], a[1]); ctx.rotate(Math.atan2(dy, dx)); fn(L); ctx.restore(); }
  function resistor(ctx, a, b, o) {
    var c1 = o.c1 || P.ink, c2 = o.c2 || c1, bl = 54, bw = 20;
    rot(ctx, a, b, function (L) {
      var m = L / 2; line(ctx, [[0, 0], [m - bl / 2, 0]], c1); line(ctx, [[m + bl / 2, 0], [L, 0]], c2);
      if (o.heat > 0.01) { ctx.fillStyle = al(P.amber, 0.55 * o.heat); ctx.fillRect(m - bl / 2 - 6, -bw / 2 - 6, bl + 12, bw + 12); }
      ctx.fillStyle = P.paper; ctx.fillRect(m - bl / 2, -bw / 2, bl, bw);
      var g = ctx.createLinearGradient(m - bl / 2, 0, m + bl / 2, 0); g.addColorStop(0, al(c1, 0.3)); g.addColorStop(1, al(c2, 0.3)); ctx.fillStyle = g; ctx.fillRect(m - bl / 2, -bw / 2, bl, bw);
      ctx.strokeStyle = P.ink; ctx.lineWidth = 1.8; ctx.strokeRect(m - bl / 2, -bw / 2, bl, bw);
    });
  }
  function battery(ctx, a, b, o) {
    var c1 = o.c1 || P.ink, c2 = o.c2 || c1;
    var dx = b[0] - a[0], dy = b[1] - a[1], L = Math.hypot(dx, dy), ux = dx / L, uy = dy / L, nx = -uy, ny = ux;
    rot(ctx, a, b, function (L) {
      var m = L / 2, g = 5; line(ctx, [[0, 0], [m - g, 0]], c1); line(ctx, [[m + g, 0], [L, 0]], c2);
      var xp = m + g, xn = m - g;
      ctx.strokeStyle = P.ink; ctx.lineCap = 'butt'; ctx.lineWidth = 2.2; ctx.beginPath(); ctx.moveTo(xp, -17); ctx.lineTo(xp, 17); ctx.stroke();
      ctx.lineWidth = 5.5; ctx.beginPath(); ctx.moveTo(xn, -9); ctx.lineTo(xn, 9); ctx.stroke(); ctx.lineCap = 'round';
    });
    var m = L / 2, off = o.side || -26;
    txt(ctx, '+', a[0] + ux * (m + 14) + nx * off, a[1] + uy * (m + 14) + ny * off, P.red, 13, 'center', 700);
    txt(ctx, '−', a[0] + ux * (m - 14) + nx * off, a[1] + uy * (m - 14) + ny * off, P.blue, 13, 'center', 700);
  }
  function key(ctx, a, b, closed, o) {
    var c1 = o.c1 || P.ink, c2 = o.c2 || c1;
    rot(ctx, a, b, function (L) {
      var m = L / 2, h = 17; line(ctx, [[0, 0], [m - h, 0]], c1); line(ctx, [[m + h, 0], [L, 0]], c2);
      ctx.strokeStyle = c1; ctx.lineWidth = 2.6; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(m - h, 0);
      if (closed) ctx.lineTo(m + h, 0); else ctx.lineTo(m - h + 2 * h * Math.cos(0.55), -2 * h * Math.sin(0.55));
      ctx.stroke(); dot(ctx, m - h, 0, 3.6, P.ink); dot(ctx, m + h, 0, 3.6, P.ink);
    });
  }
  function signsAlong(ctx, x0, y0, dx, dy, len, s, n) { if (!s || n < 1) return; n = Math.min(n, Math.max(1, Math.floor(len / 7))); var col = s === '+' ? P.red : P.blue; for (var i = 0; i < n; i++) { var t = (i + 0.5) / n; txt(ctx, s, x0 + dx * len * t, y0 + dy * len * t, col, 12, 'center', 700); } }
  function capH(ctx, x1, x2, y, o) {
    var m = (x1 + x2) / 2, g = 7, pl = 27;
    line(ctx, [[x1, y], [m - g, y]], o.c1 || P.ink); line(ctx, [[m + g, y], [x2, y]], o.c2 || o.c1 || P.ink);
    ctx.strokeStyle = P.ink; ctx.lineWidth = 3.6; ctx.lineCap = 'butt'; ctx.beginPath(); ctx.moveTo(m - g, y - pl); ctx.lineTo(m - g, y + pl); ctx.moveTo(m + g, y - pl); ctx.lineTo(m + g, y + pl); ctx.stroke(); ctx.lineCap = 'round';
    signsAlong(ctx, m - g - 9, y - pl, 0, 1, 2 * pl, o.sL, o.nL); signsAlong(ctx, m + g + 9, y - pl, 0, 1, 2 * pl, o.sR, o.nR);
  }
  function flow(ctx, pts, phase, alpha) {
    var gap = 26; if (alpha < 0.03) return; var seg = [], L = 0, i;
    for (i = 1; i < pts.length; i++) { var l = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); seg.push(l); L += l; }
    ctx.fillStyle = al(P.ink, alpha);
    for (var s = ((phase % gap) + gap) % gap; s < L; s += gap) { var r = s; i = 0; while (i < seg.length - 1 && r > seg[i]) { r -= seg[i]; i++; } var t = seg[i] ? r / seg[i] : 0; ctx.beginPath(); ctx.arc(pts[i][0] + (pts[i + 1][0] - pts[i][0]) * t, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * t, 3.3, 0, Math.PI * 2); ctx.fill(); }
  }
  function graph(ctx, b, o) {
    var X = function (v) { return b.l + (v - o.x0) / (o.x1 - o.x0) * (b.r - b.l); }, Y = function (v) { return b.b - (v - o.y0) / (o.y1 - o.y0) * (b.b - b.t); };
    ctx.strokeStyle = P.line; ctx.lineWidth = 1;
    o.xt.forEach(function (t) { if (t[0] === o.x0) return; ctx.beginPath(); ctx.moveTo(X(t[0]), b.t); ctx.lineTo(X(t[0]), b.b); ctx.stroke(); });
    o.yt.forEach(function (t) { if (t[0] === o.y0) return; ctx.beginPath(); ctx.moveTo(b.l, Y(t[0])); ctx.lineTo(b.r, Y(t[0])); ctx.stroke(); });
    arrow(ctx, b.l, b.b, b.r + 12, b.b, P.muted, 1.4, 7); arrow(ctx, b.l, b.b, b.l, b.t - 12, P.muted, 1.4, 7);
    o.xt.forEach(function (t) { if (t[1]) txt(ctx, t[1], X(t[0]), b.b + 14, P.muted, 11, 'center'); });
    o.yt.forEach(function (t) { if (t[1]) txt(ctx, t[1], b.l - 7, Y(t[0]), P.muted, 11, 'right'); });
    txt(ctx, o.xl, b.r + 12, b.b - 13, P.muted, 11, 'right'); txt(ctx, o.yl, b.l + 8, b.t - 9, P.muted, 11, 'left');
    if (o.title) txt(ctx, o.title, b.r, b.t - 9, P.muted, 11, 'right');
    return { X: X, Y: Y };
  }
  function curve(ctx, fn, x0, x1, G, color, w) { if (x1 <= x0) return; ctx.strokeStyle = color; ctx.lineWidth = w || 2.6; ctx.beginPath(); for (var i = 0; i <= 140; i++) { var x = x0 + (x1 - x0) * i / 140, px = G.X(x), py = G.Y(fn(x)); if (i) ctx.lineTo(px, py); else ctx.moveTo(px, py); } ctx.stroke(); }
  function hbar(ctx, x, y, w, h, parts) { var cx = x; ctx.fillStyle = P.line; ctx.fillRect(x, y, w, h); parts.forEach(function (p) { var ww = w * clamp(p[0], 0, 1); ctx.fillStyle = p[1]; ctx.fillRect(cx, y, ww, h); cx += ww; }); }

  /* часы: пауза перед замыканием → рост → удержание → заново */
  var K = { tn: 1, phase: 'run', timer: 0, run: !reduce, speed: 5 / 8, end: 5.3, pre: 0.9, hold: 1.4 };
  function tick(dt) {
    if (!K.run) return;
    if (K.phase === 'pre') { K.timer += dt; if (K.timer >= K.pre) { K.phase = 'run'; K.tn = 0; K.timer = 0; } }
    else if (K.phase === 'run') { K.tn += dt * K.speed; if (K.tn >= K.end) { K.tn = K.end; K.phase = 'hold'; K.timer = 0; } }
    else { K.timer += dt; if (K.timer >= K.hold) { K.phase = 'pre'; K.tn = 0; K.timer = 0; } }
  }
  var D = { E: 9, R: 4, C: 500, ph: 0 };
  function slider(id, outId, set) { var s = $(id), o = $(outId); function u() { var v = +s.value; set(v); o.textContent = f(v, Number.isInteger(v) ? 0 : 1); } s.addEventListener('input', u); u(); }
  slider('rcE', 'rcEo', function (v) { D.E = v; });
  slider('rcR', 'rcRo', function (v) { D.R = v; });
  slider('rcC', 'rcCo', function (v) { D.C = v; });
  var pp = $('rcPP');
  function ppText() { pp.textContent = K.run ? 'Пауза' : 'Продолжить'; }
  pp.addEventListener('click', function () { K.run = !K.run; ppText(); start(); }); ppText();
  $('rcRe').addEventListener('click', function () { K.phase = 'pre'; K.tn = 0; K.timer = 0; K.run = true; ppText(); start(); });
  function setText(id, s) { var e = $(id); if (e && e.textContent !== s) e.textContent = s; }

  function graphs(ctx, tn, closed) {
    var xt = [[0, '0'], [1, 'τ'], [2, '2τ'], [3, '3τ'], [4, '4τ'], [5, '5τ']];
    var qf = function (x) { return 1 - Math.exp(-x); }, If = function (x) { return Math.exp(-x); };
    var Gq = graph(ctx, { l: 500, r: 860, t: 45, b: 185 }, { x0: 0, x1: 5.3, y0: 0, y1: 1.12, xt: xt, yt: [[0, '0'], [0.632, '0,63'], [1, '1']], xl: 't', yl: 'q', title: 'доля от Cε' });
    line(ctx, [[Gq.X(0), Gq.Y(1)], [Gq.X(5.3), Gq.Y(1)]], al(P.violet, 0.45), 1.2, [5, 5]);
    line(ctx, [[Gq.X(0), Gq.Y(0)], [Gq.X(1), Gq.Y(1)]], P.muted, 1.3, [3, 4]);
    curve(ctx, qf, 0, 5.3, Gq, al(P.violet, 0.22), 2);
    if (closed) { curve(ctx, qf, 0, tn, Gq, P.violet, 2.8); dot(ctx, Gq.X(tn), Gq.Y(qf(tn)), 5.5, P.violet); }
    var Gi = graph(ctx, { l: 500, r: 860, t: 255, b: 395 }, { x0: 0, x1: 5.3, y0: 0, y1: 1.12, xt: xt, yt: [[0, '0'], [0.368, '0,37'], [1, '1']], xl: 't', yl: 'I', title: 'доля от ε/R' });
    line(ctx, [[Gi.X(0), Gi.Y(1)], [Gi.X(1), Gi.Y(0)]], P.muted, 1.3, [3, 4]);
    curve(ctx, If, 0, 5.3, Gi, al(P.red, 0.22), 2);
    if (closed) { curve(ctx, If, 0, tn, Gi, P.red, 2.8); dot(ctx, Gi.X(tn), Gi.Y(If(tn)), 5.5, P.red); }
  }

  function draw() {
    var w = cv.clientWidth; if (!w) return;
    var narrow = w < 560, LW = narrow ? 460 : 900, LH = narrow ? 820 : 430;
    var dpr = Math.min(2, window.devicePixelRatio || 1), W = Math.round(w * dpr), H = Math.round(w * LH / LW * dpr);
    if (cv.width !== W || cv.height !== H) { cv.width = W; cv.height = H; cv.style.height = Math.round(w * LH / LW) + 'px'; }
    var ctx = cv.getContext('2d'); ctx.setTransform(W / LW, 0, 0, W / LW, 0, 0); ctx.clearRect(0, 0, LW, LH);
    FS = clamp(0.62 * LW / w, 1, 1.7);

    var closed = K.phase !== 'pre', tn = closed ? K.tn : 0, e = Math.exp(-tn), qf = closed ? 1 - e : 0, If = closed ? e : 0;
    var c0 = pot(0), cE = pot(1), cB = pot(If), cBR = closed ? cE : c0, n = Math.round(qf * 8);
    line(ctx, [[70, 125], [70, 70], [205, 70]], c0); battery(ctx, [205, 70], [255, 70], { c1: c0, c2: cE, side: -24 }); line(ctx, [[255, 70], [390, 70], [390, 125]], cE);
    key(ctx, [390, 125], [390, 195], closed, { c1: cE, c2: cBR }); line(ctx, [[390, 195], [390, 250], [270, 250]], cBR);
    capH(ctx, 190, 270, 250, { c1: cB, c2: cBR, sL: '−', nL: n, sR: '+', nR: n });
    line(ctx, [[190, 250], [70, 250], [70, 195]], cB); resistor(ctx, [70, 195], [70, 125], { c1: cB, c2: c0, heat: If * If });
    flow(ctx, [[223, 250], [70, 250], [70, 70], [390, 70], [390, 250], [237, 250]], D.ph, closed && If > 0.004 ? 0.85 : 0);
    txt(ctx, 'ε', 230, 36, P.ink, 16, 'center', 700); txt(ctx, 'R', 40, 160, P.ink, 15, 'center', 700); txt(ctx, 'C', 230, 296, P.ink, 15, 'center', 700); txt(ctx, 'K', 418, 160, P.ink, 15, 'center', 700);
    txt(ctx, 'ε делится между C и R', 70, 338, P.muted, 12);
    hbar(ctx, 70, 352, 320, 22, [[qf, al(P.green, 0.85)], [If, al(P.amber, 0.85)]]);
    if (qf > 0.14) sub(ctx, 'U', 'C', 70 + 320 * qf / 2, 362, P.paper, 12, 'center');
    if (If > 0.14) sub(ctx, 'U', 'R', 70 + 320 * (qf + If / 2), 362, P.paper, 12, 'center');
    txt(ctx, f(D.E * qf, 1) + ' + ' + f(D.E * If, 1) + ' = ' + f(closed ? D.E : 0, 1) + ' В', 390, 392, P.ink, 12, 'right');

    if (narrow) { ctx.save(); ctx.translate(-460, 410); graphs(ctx, tn, closed); ctx.restore(); }
    else graphs(ctx, tn, closed);

    var tau = D.R * D.C / 1000;
    setText('rcT', f(tn * tau, 2) + ' с');
    setText('rcQ', f(D.C * D.E * qf / 1000, 2));
    setText('rcI', f(D.E / D.R * If, 2));
    setText('rcTau', f(tau, 2));
    var st = !closed ? 'Ключ разомкнут: тока нет, конденсатор пуст'
      : tn < 0.2 ? 'Только замкнули: пустой конденсатор ведёт себя как провод, ток максимален I = ε/R'
      : tn > 4 ? 'Почти установилось: q ≈ Cε, ток почти ноль — конденсатор стал разрывом'
      : 'Напряжение на C растёт, на резистор остаётся меньше — ток падает';
    setText('rcSt', st);
  }

  var raf = 0, last = 0, visible = true;
  function loop(now) {
    raf = 0; if (!visible || document.hidden) return;
    var dt = Math.min(0.05, (now - last) / 1000 || 0); last = now;
    tick(dt); if (K.run && K.phase !== 'pre') D.ph += dt * 150 * Math.exp(-K.tn);
    draw();
    if (K.run) raf = requestAnimationFrame(loop);
  }
  function start() { if (!raf && visible && K.run) { last = performance.now(); raf = requestAnimationFrame(loop); } else draw(); }
  ['rcE', 'rcR', 'rcC'].forEach(function (id) { $(id).addEventListener('input', draw); });
  window.addEventListener('resize', draw);
  if ('IntersectionObserver' in window) new IntersectionObserver(function (es) { visible = es[0].isIntersecting; start(); }).observe(cv);
  document.addEventListener('visibilitychange', start);
  if (reduce) { K.tn = 1.2; K.phase = 'run'; }
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { draw(); start(); }); else start();
})();
