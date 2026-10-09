/* Главная: живая система блоков в карточке «Визуализация» и бросок мяча в блоке «Бесплатное занятие». */
(function () {
  'use strict';
  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var css = getComputedStyle(document.documentElement);
  function tok(name, fallback) { var v = css.getPropertyValue(name).trim(); return v || fallback; }
  var C = {
    ink: tok('--ink', '#181820'), muted: tok('--muted', '#6c6a78'), line: tok('--line', '#e2dfd6'), paper: '#ffffff',
    violet: tok('--violet', '#6d28d9'), violetTint: tok('--violet-tint', '#ede7fb'),
    magenta: tok('--magenta', '#d61f69'), blue: tok('--blue', '#1d4ed8')
  };
  var MONO = "12px 'JetBrains Mono', Menlo, monospace";
  var G = 9.8;

  function setupCanvas(cv) {
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var r = cv.getBoundingClientRect();
    cv.width = Math.max(1, Math.round(r.width * dpr));
    cv.height = Math.max(1, Math.round(r.height * dpr));
    var ctx = cv.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { ctx: ctx, w: r.width, h: r.height };
  }
  function whenVisible(el, cb) {
    if (!('IntersectionObserver' in window)) { cb(true); return; }
    new IntersectionObserver(function (es) { cb(es[0].isIntersecting); }).observe(el);
  }
  function arrow(ctx, x0, y0, x1, y1, color, width) {
    var a = Math.atan2(y1 - y0, x1 - x0), L = Math.hypot(x1 - x0, y1 - y0);
    if (L < 3) return;
    var head = Math.min(10, L * 0.45);
    ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = width || 2.2; ctx.lineCap = 'round';
    ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1 - head * 0.6 * Math.cos(a), y1 - head * 0.6 * Math.sin(a)); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(x1, y1);
    ctx.lineTo(x1 - head * Math.cos(a - 0.42), y1 - head * Math.sin(a - 0.42));
    ctx.lineTo(x1 - head * Math.cos(a + 0.42), y1 - head * Math.sin(a + 0.42));
    ctx.closePath(); ctx.fill();
  }
  /* Буква с индексом и, по желанию, стрелкой-вектором сверху (линией, а не символом U+20D7) */
  function sym(ctx, base, sub, x, y, color, size, vec) {
    size = size || 17;
    ctx.fillStyle = color; ctx.textBaseline = 'alphabetic';
    ctx.font = "italic " + size + "px 'PT Serif', Georgia, serif";
    ctx.fillText(base, x, y);
    var w = ctx.measureText(base).width;
    if (sub) { ctx.font = Math.round(size * 0.62) + "px 'PT Serif', Georgia, serif"; ctx.fillText(sub, x + w + 1, y + size * 0.22); }
    if (vec) {
      var yy = y - size * 0.92, x2 = x + w + 2;
      ctx.strokeStyle = color; ctx.lineWidth = 1.3;
      ctx.beginPath(); ctx.moveTo(x, yy); ctx.lineTo(x2, yy); ctx.moveTo(x2, yy); ctx.lineTo(x2 - 4, yy - 3); ctx.moveTo(x2, yy); ctx.lineTo(x2 - 4, yy + 3); ctx.stroke();
    }
  }
  function hatch(ctx, x0, x1, y) {
    ctx.strokeStyle = C.ink; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(x0, y); ctx.lineTo(x1, y); ctx.stroke();
    ctx.lineWidth = 1; ctx.strokeStyle = C.muted;
    for (var x = x0 + 4; x < x1; x += 9) { ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + 7, y - 7); ctx.stroke(); }
  }
  function pulley(ctx, x, y, r, angle, color) {
    ctx.fillStyle = C.paper; ctx.strokeStyle = color; ctx.lineWidth = 2.4;
    ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    ctx.lineWidth = 1.2;
    for (var i = 0; i < 3; i++) {
      var a = angle + i * Math.PI / 3;
      ctx.beginPath(); ctx.moveTo(x - Math.cos(a) * (r - 4), y - Math.sin(a) * (r - 4)); ctx.lineTo(x + Math.cos(a) * (r - 4), y + Math.sin(a) * (r - 4)); ctx.stroke();
    }
    ctx.fillStyle = color; ctx.beginPath(); ctx.arc(x, y, 3.2, 0, Math.PI * 2); ctx.fill();
  }
  function box(ctx, cx, top, w, h, fill, stroke, label, sub) {
    ctx.fillStyle = fill; ctx.strokeStyle = stroke; ctx.lineWidth = 2;
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(cx - w / 2, top, w, h, 6); else ctx.rect(cx - w / 2, top, w, h);
    ctx.fill(); ctx.stroke();
    sym(ctx, label, sub, cx - 9, top + h / 2 + 6, stroke, 18);
  }
  function fmt(v, d) { return v.toFixed(d).replace('.', ',').replace('-', '−'); }
  /* Строка из кусков: обычный текст или {b: 'a', s: '2'} — буква с индексом, нарисованным вручную */
  function seq(ctx, parts, x, y, size, color, italic) {
    var cx = x;
    parts.forEach(function (p) {
      if (typeof p === 'string') {
        ctx.font = (italic ? 'italic ' : '') + size + "px 'PT Serif', Georgia, serif"; ctx.fillStyle = color;
        ctx.fillText(p, cx, y); cx += ctx.measureText(p).width;
      } else {
        sym(ctx, p.b, p.s, cx, y, color, size, false);
        ctx.font = 'italic ' + size + "px 'PT Serif', Georgia, serif"; var w = ctx.measureText(p.b).width;
        ctx.font = Math.round(size * 0.62) + "px 'PT Serif', Georgia, serif"; w += ctx.measureText(p.s).width + 2;
        cx += w;
      }
    });
    return cx;
  }

  /* ── Нити и блоки: неподвижный блок + подвижный блок, x₂ + 2x₁ = const ── */
  function pulleys(cv, input, out, readout) {
    var S, k = parseFloat(input.value), t = 0, pause = 0, raf = 0, visible = true, last = 0;
    var R = 20, PX = 150 / G; /* пикселей на (м/с²·с²): подобрано, чтобы движение было видно */

    function accel() { /* a₂ вниз (м/с²) для груза m₂ на свободном конце; a₁ = −a₂/2 для подвижного блока с m₁ */
      return 2 * G * (2 * k - 1) / (4 * k + 1);
    }
    function geom() {
      var W = S.w, H = S.h;
      var narrow = W < 460;
      var fx = narrow ? W * 0.5 : W * 0.38;          /* неподвижный блок */
      var mx = fx - 2 * R;                             /* подвижный: его правая касательная = левая касательная неподвижного */
      var ceil = 22, fy = ceil + 34;
      return { W: W, H: H, fx: fx, fy: fy, mx: mx, ceil: ceil, anchorX: mx - R, narrow: narrow,
               y1Mid: fy + 120, y2Mid: fy + 110, floor: H - 14 };
    }

    function draw() {
      var ctx = S.ctx, g = geom(), a2 = accel(), a1 = -a2 / 2;
      var s2 = a2 * t * t / 2 * PX;                    /* смещение m₂ вниз, px */
      var s1 = -s2 / 2;
      var y1 = g.y1Mid + s1;                          /* центр подвижного блока */
      var y2 = g.y2Mid + s2;                          /* верх груза m₂ */
      ctx.clearRect(0, 0, g.W, g.H);

      hatch(ctx, g.anchorX - 26, g.fx + 26, g.ceil);
      /* подвес неподвижного блока */
      ctx.strokeStyle = C.ink; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.moveTo(g.fx, g.ceil); ctx.lineTo(g.fx, g.fy); ctx.stroke();

      /* нить: потолок → вниз → под подвижным блоком → вверх → через неподвижный → вниз к m₂ */
      ctx.strokeStyle = C.ink; ctx.lineWidth = 1.8;
      ctx.beginPath();
      ctx.moveTo(g.anchorX, g.ceil); ctx.lineTo(g.anchorX, y1);
      ctx.arc(g.mx, y1, R, Math.PI, 0, true);
      ctx.lineTo(g.mx + R, g.fy);
      ctx.arc(g.fx, g.fy, R, Math.PI, 0, false);
      ctx.lineTo(g.fx + R, y2);
      ctx.stroke();

      var spin = s2 / R;
      pulley(ctx, g.fx, g.fy, R, spin, C.ink);
      pulley(ctx, g.mx, y1, R, spin / 2, C.violet);

      /* груз m₁ на подвижном блоке */
      ctx.strokeStyle = C.violet; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.moveTo(g.mx, y1); ctx.lineTo(g.mx, y1 + R + 14); ctx.stroke();
      var b1top = y1 + R + 14;
      box(ctx, g.mx, b1top, 54, 44, C.violetTint, C.violet, 'm', '1');
      /* груз m₂ */
      box(ctx, g.fx + R, y2, 46, 40, '#e2e8fa', C.blue, 'm', '2');

      /* векторы ускорений: длина пропорциональна модулю */
      var sc = 7;
      if (Math.abs(a2) > 0.05) {
        var ax2 = g.fx + R + 36, ay2 = y2 + 20;
        arrow(ctx, ax2, ay2, ax2, ay2 + a2 * sc, C.magenta, 2.4);
        sym(ctx, 'a', '2', ax2 + 8, ay2 + a2 * sc / 2 + 6, C.magenta, 17, true);
        var ax1 = g.mx - 44, ay1 = b1top + 22;
        arrow(ctx, ax1, ay1, ax1, ay1 + a1 * sc, C.magenta, 2.4);
        sym(ctx, 'a', '1', ax1 - 26, ay1 + a1 * sc / 2 + 6, C.magenta, 17, true);
      }

      /* табличка с числами */
      var px = g.narrow ? 14 : g.W * 0.64, py = g.narrow ? g.H - 64 : 70;
      ctx.textBaseline = 'alphabetic';
      var v2 = fmt(Math.abs(a2), 1) + ' м/с²', v1 = fmt(Math.abs(a1), 1) + ' м/с²';
      var state = Math.abs(a2) < 0.05 ? 'равновесие' : (a2 > 0 ? 'груз 2 опускается' : 'груз 2 поднимается');
      if (!g.narrow) {
        ctx.font = MONO; ctx.fillStyle = C.muted; ctx.fillText('СВЯЗЬ ДВИЖЕНИЙ', px, py);
        seq(ctx, [{ b: 'x', s: '2' }, ' + 2', { b: 'x', s: '1' }, ' = const'], px, py + 32, 20, C.ink, true);
        seq(ctx, [{ b: 'a', s: '2' }, ' = 2', { b: 'a', s: '1' }], px, py + 62, 20, C.ink, true);
        ctx.font = MONO; ctx.fillStyle = C.muted; ctx.fillText('СЕЙЧАС', px, py + 102);
        seq(ctx, [{ b: 'a', s: '2' }, ' = ' + v2], px, py + 128, 16, C.ink, false);
        seq(ctx, [{ b: 'a', s: '1' }, ' = ' + v1], px, py + 152, 16, C.ink, false);
        ctx.font = MONO; ctx.fillStyle = C.violet; ctx.fillText(state, px, py + 178);
      }
      /* на узком экране числа показываются под рисунком, в HTML */
      if (readout) {
        var html = '<i>a</i><sub>2</sub> = ' + v2 + ' · <i>a</i><sub>1</sub> = ' + v1 + '<br><span class="st">' + state + '</span> · <i>a</i><sub>2</sub> = 2<i>a</i><sub>1</sub>';
        if (readout.innerHTML !== html) readout.innerHTML = html;
      }

      return { y1: y1, y2: y2, b1bottom: b1top + 44, g: g };
    }

    function step(now) {
      raf = 0;
      if (!visible || document.hidden) return;
      var dt = Math.min(0.05, (now - last) / 1000 || 0); last = now;
      if (pause > 0) { pause -= dt; if (pause <= 0) { t = 0; draw(); } }
      else {
        t += dt * 0.9;
        var st = draw(), g = st.g;
        /* упор: груз 2 дошёл до пола или до блока, подвижный блок — до потолка или пола */
        if (st.y2 + 40 > g.floor || st.y2 < g.fy + R + 6 || st.y1 - R < g.ceil + 10 || st.b1bottom > g.floor || t > 3) pause = 0.9;
      }
      raf = requestAnimationFrame(step);
    }
    function start() { if (!raf && visible && !reduceMotion) { last = performance.now(); raf = requestAnimationFrame(step); } }
    function sync() {
      k = parseFloat(input.value);
      out.textContent = fmt(k, 2);
      t = 0; pause = 0;
      draw();
    }

    S = setupCanvas(cv);
    input.addEventListener('input', sync);
    window.addEventListener('resize', function () { S = setupCanvas(cv); draw(); });
    sync();
    if (reduceMotion) { t = 0.8; draw(); return; }
    whenVisible(cv, function (on) { visible = on; start(); });
    document.addEventListener('visibilitychange', start);
    start();
  }

  /* ── Бросок под углом: игрушка в блоке «Бесплатное занятие» ── */
  function ballistics(cv, hint) {
    var S, theta = 52 * Math.PI / 180, aim = theta;
    var t = 0, T = 1.8, g, v, pause = 0, running = false, last = 0, visible = true, raf = 0, trails = [], P;

    function plan() {
      var x0 = 22, y0 = S.h - 26;
      var s2 = Math.sin(2 * theta), s1 = Math.sin(theta);
      var K = Math.min(0.92 * (S.w - 44) / Math.max(s2, 0.05), 1.8 * (y0 - 30) / (s1 * s1));
      g = K * Math.pow(2 * s1 / T, 2);
      v = Math.sqrt(g * K);
      return { x0: x0, y0: y0 };
    }
    function pos(tt) { return { x: P.x0 + v * Math.cos(theta) * tt, y: P.y0 - v * Math.sin(theta) * tt + g * tt * tt / 2 }; }
    function resize() { S = setupCanvas(cv); P = plan(); draw(); }

    function draw() {
      var ctx = S.ctx;
      ctx.clearRect(0, 0, S.w, S.h);
      ctx.strokeStyle = C.ink; ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.moveTo(8, P.y0 + 0.5); ctx.lineTo(S.w - 8, P.y0 + 0.5); ctx.stroke();
      trails.forEach(function (tr) {
        ctx.globalAlpha = tr.a; ctx.strokeStyle = C.violet; ctx.lineWidth = 1.5;
        ctx.beginPath(); tr.pts.forEach(function (p, i) { i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y); }); ctx.stroke();
      });
      ctx.globalAlpha = 1;
      ctx.setLineDash([4, 6]); ctx.strokeStyle = C.muted; ctx.lineWidth = 1.2; ctx.beginPath();
      for (var i = 0; i <= 50; i++) { var q = pos(T * i / 50); i ? ctx.lineTo(q.x, q.y) : ctx.moveTo(q.x, q.y); }
      ctx.stroke(); ctx.setLineDash([]);
      ctx.strokeStyle = C.violet; ctx.lineWidth = 2.5; ctx.beginPath();
      var n = Math.max(1, Math.round(50 * t / T));
      for (var j = 0; j <= n; j++) { var r = pos(t * j / n); j ? ctx.lineTo(r.x, r.y) : ctx.moveTo(r.x, r.y); }
      ctx.stroke();
      ctx.strokeStyle = C.ink; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.arc(P.x0, P.y0, 22, -theta, 0); ctx.stroke();
      ctx.font = MONO; ctx.fillStyle = C.ink; ctx.fillText(Math.round(theta * 180 / Math.PI) + '°', P.x0 + 26, P.y0 - 6);
      var b = pos(t), vx = v * Math.cos(theta), vy = -v * Math.sin(theta) + g * t, sc = 38 / v;
      arrow(ctx, b.x, b.y, b.x + vx * sc, b.y + vy * sc, C.ink, 2);
      sym(ctx, 'v', '', b.x + vx * sc + 5, b.y + vy * sc - 2, C.ink, 16, true);
      arrow(ctx, b.x, b.y, b.x, b.y + 28, C.magenta, 2);
      sym(ctx, 'g', '', b.x + 6, b.y + 34, C.magenta, 16, true);
      ctx.fillStyle = C.violet; ctx.beginPath(); ctx.arc(b.x, b.y, 6.5, 0, Math.PI * 2); ctx.fill();
    }
    function relaunch() {
      var pts = []; for (var i = 0; i <= 40; i++) pts.push(pos(T * i / 40));
      trails.unshift({ pts: pts, a: 0.35 }); trails = trails.slice(0, 3);
      theta = aim; P = plan(); t = 0;
    }
    function frame(now) {
      raf = 0;
      if (!running || !visible || document.hidden) return;
      var dt = Math.min(0.05, (now - last) / 1000 || 0); last = now;
      trails.forEach(function (tr) { tr.a = Math.max(0, tr.a - dt * 0.12); });
      if (pause > 0) { pause -= dt; if (pause <= 0) relaunch(); }
      else { t += dt; if (t >= T) { t = T; pause = 0.7; } }
      draw();
      raf = requestAnimationFrame(frame);
    }
    function start() { if (!raf && running && visible) { last = performance.now(); raf = requestAnimationFrame(frame); } }
    function aimAt(e) {
      var r = cv.getBoundingClientRect();
      var a = Math.atan2(P.y0 - (e.clientY - r.top), (e.clientX - r.left) - P.x0);
      aim = Math.max(15, Math.min(80, a * 180 / Math.PI)) * Math.PI / 180;
      if (hint) hint.textContent = 'Угол ' + Math.round(aim * 180 / Math.PI) + '° — посмотри, где упадёт';
    }
    cv.addEventListener('pointermove', function (e) { if (e.pointerType === 'mouse') aimAt(e); });
    cv.addEventListener('pointerdown', function (e) { aimAt(e); if (!reduceMotion) { pause = 0; relaunch(); } else { theta = aim; P = plan(); draw(); } });

    resize();
    window.addEventListener('resize', resize);
    if (reduceMotion) { t = T * 0.5; draw(); return; }
    running = true;
    whenVisible(cv, function (on) { visible = on; start(); });
    document.addEventListener('visibilitychange', start);
    start();
  }

  function boot() {
    var pc = document.getElementById('pulleys');
    if (pc) pulleys(pc, document.getElementById('mass-ratio'), document.getElementById('mass-ratio-out'), document.getElementById('pulley-readout'));
    var tc = document.getElementById('throw');
    if (tc) ballistics(tc, document.getElementById('throw-hint'));
  }
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(boot); else boot();
})();
