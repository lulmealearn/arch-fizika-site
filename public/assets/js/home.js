/* Главная: игрушка «брось мяч» в блоке «Бесплатное занятие».
   Физика честная: скорость броска и g постоянны, меняется только угол,
   поэтому дальность L = v²·sin2θ / g максимальна при 45°, а 30° и 60° дают одинаковую дальность. */
(function () {
  'use strict';
  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var css = getComputedStyle(document.documentElement);
  function tok(name, fallback) { var v = css.getPropertyValue(name).trim(); return v || fallback; }
  var C = { ink: tok('--ink', '#181820'), muted: tok('--muted', '#6c6a78'), violet: tok('--violet', '#6d28d9'), magenta: tok('--magenta', '#d61f69') };
  var MONO = "12px 'JetBrains Mono', Menlo, monospace";
  var DEG = Math.PI / 180, MAX_ANGLE = 80, MIN_ANGLE = 10;

  function setupCanvas(cv) {
    var dpr = Math.min(window.devicePixelRatio || 1, 2), r = cv.getBoundingClientRect();
    cv.width = Math.max(1, Math.round(r.width * dpr)); cv.height = Math.max(1, Math.round(r.height * dpr));
    var ctx = cv.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    return { ctx: ctx, w: r.width, h: r.height };
  }
  function arrow(ctx, x0, y0, x1, y1, color, width) {
    var a = Math.atan2(y1 - y0, x1 - x0), L = Math.hypot(x1 - x0, y1 - y0); if (L < 3) return;
    var head = Math.min(9, L * 0.45);
    ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = width || 2; ctx.lineCap = 'round';
    ctx.beginPath(); ctx.moveTo(x0, y0); ctx.lineTo(x1 - head * 0.6 * Math.cos(a), y1 - head * 0.6 * Math.sin(a)); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x1 - head * Math.cos(a - 0.42), y1 - head * Math.sin(a - 0.42)); ctx.lineTo(x1 - head * Math.cos(a + 0.42), y1 - head * Math.sin(a + 0.42)); ctx.closePath(); ctx.fill();
  }
  /* буква-вектор: стрелка над буквой рисуется линией */
  function vec(ctx, ch, x, y, color) {
    ctx.font = "italic 16px 'PT Serif', Georgia, serif"; ctx.fillStyle = color; ctx.textBaseline = 'alphabetic';
    ctx.fillText(ch, x, y); var w = ctx.measureText(ch).width, yy = y - 15;
    ctx.strokeStyle = color; ctx.lineWidth = 1.2; ctx.beginPath(); ctx.moveTo(x, yy); ctx.lineTo(x + w + 2, yy);
    ctx.moveTo(x + w + 2, yy); ctx.lineTo(x + w - 2, yy - 3); ctx.moveTo(x + w + 2, yy); ctx.lineTo(x + w - 2, yy + 3); ctx.stroke();
  }

  function ballistics(cv, hint) {
    var S, P, theta = 52 * DEG, aim = theta, t = 0, pause = 0, running = false, last = 0, visible = true, raf = 0, trails = [];
    var v, g, R45;

    /* масштаб подбирается один раз под размер поля: самый дальний бросок (45°) и самый высокий (80°) помещаются */
    function scale() {
      var x0 = 22, y0 = S.h - 26;
      var byWidth = 0.92 * (S.w - x0 - 16);
      var byHeight = 2 * (y0 - 22) / Math.pow(Math.sin(MAX_ANGLE * DEG), 2);
      R45 = Math.min(byWidth, byHeight);
      var T45 = 1.7;                        /* полёт под 45° длится 1,7 с */
      g = 2 * R45 / (T45 * T45);
      v = Math.sqrt(g * R45);               /* R45 = v²/g */
      P = { x0: x0, y0: y0 };
    }
    function flight(th) { return 2 * v * Math.sin(th) / g; }
    function pos(tt, th) { return { x: P.x0 + v * Math.cos(th) * tt, y: P.y0 - v * Math.sin(th) * tt + g * tt * tt / 2 }; }
    function resize() { S = setupCanvas(cv); scale(); draw(); }

    function draw() {
      var ctx = S.ctx, T = flight(theta);
      ctx.clearRect(0, 0, S.w, S.h);
      ctx.strokeStyle = C.ink; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.moveTo(8, P.y0 + 0.5); ctx.lineTo(S.w - 8, P.y0 + 0.5); ctx.stroke();
      /* метка максимальной дальности (45°) */
      var xm = P.x0 + R45;
      ctx.setLineDash([2, 4]); ctx.strokeStyle = C.muted; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(xm, P.y0 - 14); ctx.lineTo(xm, P.y0 + 6); ctx.stroke(); ctx.setLineDash([]);
      ctx.font = "10px 'JetBrains Mono', Menlo, monospace"; ctx.fillStyle = C.muted; ctx.textAlign = 'right'; ctx.fillText('макс. при 45°', xm - 4, P.y0 - 18); ctx.textAlign = 'left';
      trails.forEach(function (tr) {
        ctx.globalAlpha = tr.a; ctx.strokeStyle = C.violet; ctx.lineWidth = 1.5;
        ctx.beginPath(); tr.pts.forEach(function (p, i) { if (i) ctx.lineTo(p.x, p.y); else ctx.moveTo(p.x, p.y); }); ctx.stroke();
      });
      ctx.globalAlpha = 1;
      ctx.setLineDash([4, 6]); ctx.strokeStyle = C.muted; ctx.lineWidth = 1.2; ctx.beginPath();
      for (var i = 0; i <= 50; i++) { var q = pos(T * i / 50, theta); if (i) ctx.lineTo(q.x, q.y); else ctx.moveTo(q.x, q.y); }
      ctx.stroke(); ctx.setLineDash([]);
      ctx.strokeStyle = C.violet; ctx.lineWidth = 2.5; ctx.beginPath();
      var n = Math.max(1, Math.round(50 * t / T));
      for (var j = 0; j <= n; j++) { var r = pos(t * j / n, theta); if (j) ctx.lineTo(r.x, r.y); else ctx.moveTo(r.x, r.y); }
      ctx.stroke();
      ctx.strokeStyle = C.ink; ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(P.x0, P.y0, 22, -theta, 0); ctx.stroke();
      ctx.font = MONO; ctx.fillStyle = C.ink; ctx.fillText(Math.round(theta / DEG) + '°', P.x0 + 26, P.y0 - 6);
      var b = pos(t, theta), vx = v * Math.cos(theta), vy = -v * Math.sin(theta) + g * t, sc = 38 / v;
      arrow(ctx, b.x, b.y, b.x + vx * sc, b.y + vy * sc, C.ink, 2); vec(ctx, 'v', b.x + vx * sc + 5, b.y + vy * sc - 2, C.ink);
      arrow(ctx, b.x, b.y, b.x, b.y + 28, C.magenta, 2); vec(ctx, 'g', b.x + 6, b.y + 34, C.magenta);
      ctx.fillStyle = C.violet; ctx.beginPath(); ctx.arc(b.x, b.y, 6.5, 0, Math.PI * 2); ctx.fill();
    }
    function describe(th) {
      var share = Math.round(Math.sin(2 * th) * 100);
      return 'Угол ' + Math.round(th / DEG) + '° — дальность ' + share + '% от максимальной. Тапни, чтобы бросить под другим углом';
    }
    function relaunch() {
      var T = flight(theta), pts = []; for (var i = 0; i <= 40; i++) pts.push(pos(T * i / 40, theta));
      trails.unshift({ pts: pts, a: 0.35 }); trails = trails.slice(0, 3);
      theta = aim; t = 0;
      if (hint) hint.textContent = describe(theta);
    }
    function frame(now) {
      raf = 0; if (!running || !visible || document.hidden) return;
      var dt = Math.min(0.05, (now - last) / 1000 || 0); last = now;
      trails.forEach(function (tr) { tr.a = Math.max(0, tr.a - dt * 0.12); });
      var T = flight(theta);
      if (pause > 0) { pause -= dt; if (pause <= 0) relaunch(); }
      else { t += dt; if (t >= T) { t = T; pause = 0.7; } }
      draw(); raf = requestAnimationFrame(frame);
    }
    function start() { if (!raf && running && visible) { last = performance.now(); raf = requestAnimationFrame(frame); } }
    function aimAt(e) {
      var r = cv.getBoundingClientRect();
      var a = Math.atan2(P.y0 - (e.clientY - r.top), (e.clientX - r.left) - P.x0) / DEG;
      aim = Math.max(MIN_ANGLE, Math.min(MAX_ANGLE, a)) * DEG;
    }
    cv.addEventListener('pointermove', function (e) { if (e.pointerType === 'mouse') { aimAt(e); if (hint) hint.textContent = 'Следующий бросок: ' + Math.round(aim / DEG) + '°, клик — бросить сейчас'; } });
    cv.addEventListener('pointerdown', function (e) { aimAt(e); if (!reduceMotion) { pause = 0; relaunch(); } else { theta = aim; t = flight(theta) * 0.5; draw(); if (hint) hint.textContent = describe(theta); } });

    resize();
    window.addEventListener('resize', resize);
    if (hint) hint.textContent = describe(theta);
    if (reduceMotion) { t = flight(theta) * 0.5; draw(); return; }
    running = true;
    if ('IntersectionObserver' in window) new IntersectionObserver(function (es) { visible = es[0].isIntersecting; start(); }).observe(cv);
    document.addEventListener('visibilitychange', start);
    start();
  }

  function boot() { var tc = document.getElementById('throw'); if (tc) ballistics(tc, document.getElementById('throw-hint')); }
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(boot); else boot();
})();
