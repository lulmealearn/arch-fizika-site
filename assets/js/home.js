/* Главная: живой бросок в рамке под фото и мини-визуализация в карточке «Метод». */
(function () {
  'use strict';
  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var css = getComputedStyle(document.documentElement);
  function tok(name, fallback) { var v = css.getPropertyValue(name).trim(); return v || fallback; }
  var C = {
    ink: tok('--ink', '#181820'), muted: tok('--muted', '#6c6a78'), line: tok('--line', '#e2dfd6'),
    violet: tok('--violet', '#6d28d9'), magenta: tok('--magenta', '#d61f69'), blue: tok('--blue', '#1d4ed8')
  };
  var MONO = "11px 'JetBrains Mono', Menlo, monospace";
  var SERIF_I = "italic 16px 'PT Serif', Georgia, serif";

  function setupCanvas(cv) {
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var r = cv.getBoundingClientRect();
    cv.width = Math.max(1, Math.round(r.width * dpr));
    cv.height = Math.max(1, Math.round(r.height * dpr));
    var ctx = cv.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { ctx: ctx, w: r.width, h: r.height };
  }

  function arrow(ctx, x0, y0, x1, y1, color, width) {
    var a = Math.atan2(y1 - y0, x1 - x0), L = Math.hypot(x1 - x0, y1 - y0);
    if (L < 2) return;
    var head = Math.min(9, L * 0.45);
    ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = width || 2; ctx.lineCap = 'round';
    ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1 - head * 0.6 * Math.cos(a), y1 - head * 0.6 * Math.sin(a)); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(x1, y1);
    ctx.lineTo(x1 - head * Math.cos(a - 0.42), y1 - head * Math.sin(a - 0.42));
    ctx.lineTo(x1 - head * Math.cos(a + 0.42), y1 - head * Math.sin(a + 0.42));
    ctx.closePath(); ctx.fill();
  }
  /* буква-вектор: стрелка над буквой рисуется линией, а не символом U+20D7 */
  function vecLabel(ctx, txt, x, y, color) {
    ctx.font = SERIF_I; ctx.fillStyle = color; ctx.textBaseline = 'alphabetic';
    ctx.fillText(txt, x, y);
    var w = ctx.measureText(txt).width;
    var yy = y - 15;
    ctx.strokeStyle = color; ctx.lineWidth = 1.2;
    ctx.beginPath(); ctx.moveTo(x, yy); ctx.lineTo(x + w + 2, yy); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(x + w + 2, yy); ctx.lineTo(x + w - 2, yy - 3); ctx.moveTo(x + w + 2, yy); ctx.lineTo(x + w - 2, yy + 3); ctx.stroke();
  }

  function whenVisible(el, onChange) {
    if (!('IntersectionObserver' in window)) { onChange(true); return; }
    new IntersectionObserver(function (es) { onChange(es[0].isIntersecting); }).observe(el);
  }

  /* ── Бросок под углом в рамке ── */
  function ballistics(cv, hint) {
    var S, theta = 66 * Math.PI / 180, aim = theta;
    var t = 0, T = 2.2, g, v, K, pause = 0, running = false, last = 0, visible = true, raf = 0;
    var trails = [];

    function plan() {
      var x0 = 26, y0 = S.h - 54;
      var s2 = Math.sin(2 * theta), s1 = Math.sin(theta);
      /* дальность влезает по ширине, высота подъёма — по высоте рамки */
      K = Math.min(0.9 * (S.w - 52) / Math.max(s2, 0.05), 1.5 * (y0 - 40) / (s1 * s1));
      g = K * Math.pow(2 * s1 / T, 2);
      v = Math.sqrt(g * K);
      return { x0: x0, y0: y0 };
    }
    var P;
    function pos(tt) {
      return { x: P.x0 + v * Math.cos(theta) * tt, y: P.y0 - v * Math.sin(theta) * tt + g * tt * tt / 2 };
    }
    function resize() { S = setupCanvas(cv); P = plan(); draw(); }

    function draw() {
      var ctx = S.ctx;
      ctx.clearRect(0, 0, S.w, S.h);
      /* земля */
      ctx.strokeStyle = C.ink; ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.moveTo(12, P.y0 + 0.5); ctx.lineTo(S.w - 12, P.y0 + 0.5); ctx.stroke();
      ctx.strokeStyle = C.muted; ctx.lineWidth = 1;
      for (var hx = 16; hx < S.w - 12; hx += 10) { ctx.beginPath(); ctx.moveTo(hx, P.y0 + 1); ctx.lineTo(hx - 6, P.y0 + 7); ctx.stroke(); }

      /* старые траектории тают */
      trails.forEach(function (tr) {
        ctx.globalAlpha = tr.a; ctx.strokeStyle = C.violet; ctx.lineWidth = 1.5;
        ctx.beginPath(); tr.pts.forEach(function (p, i) { i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y); }); ctx.stroke();
      });
      ctx.globalAlpha = 1;

      /* полная траектория пунктиром */
      ctx.setLineDash([4, 6]); ctx.strokeStyle = C.muted; ctx.lineWidth = 1.2;
      ctx.beginPath();
      for (var i = 0; i <= 60; i++) { var q = pos(T * i / 60); i ? ctx.lineTo(q.x, q.y) : ctx.moveTo(q.x, q.y); }
      ctx.stroke(); ctx.setLineDash([]);

      /* пройденная часть */
      ctx.strokeStyle = C.violet; ctx.lineWidth = 2.5; ctx.beginPath();
      var n = Math.max(1, Math.round(60 * t / T));
      for (var j = 0; j <= n; j++) { var r = pos(t * j / n); j ? ctx.lineTo(r.x, r.y) : ctx.moveTo(r.x, r.y); }
      ctx.stroke();

      /* угол броска */
      ctx.strokeStyle = C.ink; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.arc(P.x0, P.y0, 26, -theta, 0); ctx.stroke();
      ctx.font = MONO; ctx.fillStyle = C.ink;
      ctx.fillText(Math.round(theta * 180 / Math.PI) + '°', P.x0 + 30, P.y0 - 8);

      /* тело и векторы */
      var b = pos(t);
      var vx = v * Math.cos(theta), vy = -v * Math.sin(theta) + g * t;
      var sc = 46 / v;
      arrow(ctx, b.x, b.y, b.x + vx * sc, b.y + vy * sc, C.ink, 2);
      vecLabel(ctx, 'v', b.x + vx * sc + 6, b.y + vy * sc - 2, C.ink);
      arrow(ctx, b.x, b.y, b.x, b.y + 34, C.magenta, 2);
      vecLabel(ctx, 'g', b.x + 7, b.y + 40, C.magenta);
      ctx.fillStyle = C.violet; ctx.beginPath(); ctx.arc(b.x, b.y, 7, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = '#ffffff'; ctx.beginPath(); ctx.arc(b.x - 2, b.y - 2, 2, 0, Math.PI * 2); ctx.fill();
    }

    function relaunch() {
      var pts = []; for (var i = 0; i <= 40; i++) pts.push(pos(T * i / 40));
      trails.unshift({ pts: pts, a: 0.35 }); trails = trails.slice(0, 3);
      theta = aim; P = plan(); t = 0;
      if (hint) hint.textContent = 'θ = ' + Math.round(theta * 180 / Math.PI) + '° · веди пальцем по рамке';
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
      var px = e.clientX - r.left, py = e.clientY - r.top;
      var a = Math.atan2(P.y0 - py, px - P.x0);
      aim = Math.max(15, Math.min(82, a * 180 / Math.PI)) * Math.PI / 180;
      if (hint) hint.textContent = 'θ = ' + Math.round(aim * 180 / Math.PI) + '° · следующий бросок';
    }
    cv.addEventListener('pointermove', aimAt);
    cv.addEventListener('pointerdown', function (e) { aimAt(e); if (!reduceMotion) { pause = 0; relaunch(); } else { theta = aim; P = plan(); draw(); } });

    resize();
    window.addEventListener('resize', resize);
    if (reduceMotion) { t = T * 0.55; draw(); return; }
    running = true;
    whenVisible(cv, function (on) { visible = on; start(); });
    document.addEventListener('visibilitychange', start);
    start();
  }

  /* ── Мини-визуализация: x(t) и касательная ── */
  function miniPlot(cv, input, out) {
    var S, a = parseFloat(input.value), phase = 0, raf = 0, visible = true, last = 0;
    function x(t) { return 0.6 * t + a * t * t / 2; }
    function dx(t) { return 0.6 + a * t; }
    function draw() {
      var ctx = S.ctx, W = S.w, H = S.h, L = 22, B = H - 16, R = W - 10, Tt = 10;
      ctx.clearRect(0, 0, W, H);
      var tMax = 4, xs = [];
      for (var i = 0; i <= 80; i++) xs.push(x(tMax * i / 80));
      var lo = Math.min(0, Math.min.apply(null, xs)), hi = Math.max(1, Math.max.apply(null, xs));
      function X(t) { return L + (R - L) * t / tMax; }
      function Y(v) { return B - (B - Tt) * (v - lo) / (hi - lo); }
      ctx.strokeStyle = C.ink; ctx.lineWidth = 1.2;
      ctx.beginPath(); ctx.moveTo(L, Tt - 4); ctx.lineTo(L, B); ctx.lineTo(R, B); ctx.stroke();
      ctx.font = MONO; ctx.fillStyle = C.muted; ctx.fillText('t', R - 8, H - 2); ctx.fillText('x', 6, Tt + 6);
      if (lo < 0) { ctx.strokeStyle = C.line; ctx.beginPath(); ctx.moveTo(L, Y(0)); ctx.lineTo(R, Y(0)); ctx.stroke(); }
      ctx.strokeStyle = C.blue; ctx.lineWidth = 2.5; ctx.beginPath();
      xs.forEach(function (v, k) { var px = X(tMax * k / 80), py = Y(v); k ? ctx.lineTo(px, py) : ctx.moveTo(px, py); });
      ctx.stroke();
      var tp = 0.5 + 3 * (0.5 - 0.5 * Math.cos(phase));
      var k = dx(tp), x0 = X(tp), y0 = Y(x(tp)), span = 0.9;
      ctx.setLineDash([4, 4]); ctx.strokeStyle = C.magenta; ctx.lineWidth = 1.6; ctx.beginPath();
      ctx.moveTo(X(tp - span), Y(x(tp) - k * span)); ctx.lineTo(X(tp + span), Y(x(tp) + k * span)); ctx.stroke(); ctx.setLineDash([]);
      ctx.fillStyle = C.magenta; ctx.beginPath(); ctx.arc(x0, y0, 4.5, 0, Math.PI * 2); ctx.fill();
    }
    function loop(now) {
      raf = 0; if (!visible || document.hidden) return;
      var dt = Math.min(0.05, (now - last) / 1000 || 0); last = now;
      phase += dt * 0.9; draw(); raf = requestAnimationFrame(loop);
    }
    function start() { if (!raf && visible && !reduceMotion) { last = performance.now(); raf = requestAnimationFrame(loop); } }
    function sync() {
      a = parseFloat(input.value);
      out.textContent = 'a = ' + a.toFixed(1).replace('.', ',').replace('-', '−') + ' м/с²';
      draw();
    }
    S = setupCanvas(cv);
    input.addEventListener('input', sync);
    window.addEventListener('resize', function () { S = setupCanvas(cv); draw(); });
    sync();
    whenVisible(cv, function (on) { visible = on; start(); });
    document.addEventListener('visibilitychange', start);
    start();
  }

  function boot() {
    var cv = document.getElementById('throw');
    if (cv) ballistics(cv, document.getElementById('throw-hint'));
    var mc = document.getElementById('mini-plot');
    if (mc) miniPlot(mc, document.getElementById('mini-a'), document.getElementById('mini-a-out'));
  }
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(boot); else boot();
})();
