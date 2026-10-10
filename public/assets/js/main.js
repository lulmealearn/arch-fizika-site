/* Общие скрипты: боковая панель и появление блоков при скролле. Без зависимостей. */
(function () {
  'use strict';

  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ── Боковая панель ── */
  var drawer = document.getElementById('drawer');
  var openers = document.querySelectorAll('[data-open-drawer]');
  var lastFocus = null;

  function openDrawer() {
    if (!drawer) return;
    lastFocus = document.activeElement;
    drawer.classList.add('is-open');
    drawer.setAttribute('aria-hidden', 'false');
    document.body.classList.add('no-scroll');
    openers.forEach(function (b) { b.setAttribute('aria-expanded', 'true'); });
    var first = drawer.querySelector('.nav a');
    if (first) setTimeout(function () { first.focus({ preventScroll: true }); }, 60);
  }
  function closeDrawer() {
    if (!drawer || !drawer.classList.contains('is-open')) return;
    drawer.classList.remove('is-open');
    drawer.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('no-scroll');
    openers.forEach(function (b) { b.setAttribute('aria-expanded', 'false'); });
    if (lastFocus && lastFocus.focus) lastFocus.focus({ preventScroll: true });
  }
  openers.forEach(function (b) { b.addEventListener('click', openDrawer); });
  if (drawer) {
    drawer.querySelectorAll('[data-close-drawer]').forEach(function (b) { b.addEventListener('click', closeDrawer); });
    /* ссылка на раздел этой же страницы (#prices, #contacts): закрыть панель, браузер сам прокрутит */
    drawer.querySelectorAll('.nav a[href^="#"]').forEach(function (a) { a.addEventListener('click', closeDrawer); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeDrawer();
      if (e.key === 'Tab' && drawer.classList.contains('is-open')) {
        var f = drawer.querySelectorAll('a[href], button:not([disabled])');
        var list = Array.prototype.filter.call(f, function (el) { return el.offsetParent !== null; });
        if (!list.length) return;
        var a = list[0], z = list[list.length - 1];
        if (e.shiftKey && document.activeElement === a) { e.preventDefault(); z.focus(); }
        else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a.focus(); }
      }
    });
    /* свайп влево закрывает панель на телефоне */
    var panel = drawer.querySelector('.drawer__panel');
    var x0 = null;
    panel.addEventListener('touchstart', function (e) { x0 = e.touches[0].clientX; }, { passive: true });
    panel.addEventListener('touchend', function (e) {
      if (x0 !== null && x0 - e.changedTouches[0].clientX > 60) closeDrawer();
      x0 = null;
    }, { passive: true });
  }

  /* ── Появление блоков ── */
  window.revealOnScroll = function (root) {
    if (reduceMotion || !('IntersectionObserver' in window)) return;
    var els = (root || document).querySelectorAll('[data-reveal]:not(.reveal-in)');
    var vh = window.innerHeight || 800;
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        var el = en.target;
        var delay = parseInt(el.getAttribute('data-reveal') || '0', 10) || 0;
        setTimeout(function () { el.classList.add('reveal-in'); el.classList.remove('reveal-pending'); }, delay);
        io.unobserve(el);
      });
    }, { rootMargin: '0px 0px -8% 0px' });
    els.forEach(function (el) {
      /* то, что уже на первом экране, не прячем */
      if (el.getBoundingClientRect().top < vh * 0.92) return;
      el.classList.add('reveal-pending');
      io.observe(el);
    });
  };
  window.revealOnScroll();

  /* ── Число визуализаций в меню и на главной берём с сервера ── */
  var counters = document.querySelectorAll('[data-viz-count]');
  if (counters.length && window.fetch) {
    fetch('/api/visualizations').then(function (r) { return r.ok ? r.json() : null; }).then(function (d) {
      if (!d) return;
      counters.forEach(function (el) { el.textContent = String(d.items.length); });
    }).catch(function () { /* оставляем число из разметки */ });
  }
})();

/* Плавающая кнопка записи (только телефон, см. .float-cta в main.css):
   появляется после первого экрана и прячется, пока на экране блок, где кнопка записи уже есть ([data-float-hide]). */
(function () {
  'use strict';
  var cta = document.querySelector('.float-cta');
  if (!cta || !('IntersectionObserver' in window)) return;
  var visible = new Set(), ticking = false;
  function update() {
    ticking = false;
    var drawerOpen = document.body.classList.contains('no-scroll');
    var show = window.scrollY > window.innerHeight * 0.7 && visible.size === 0 && !drawerOpen;
    cta.classList.toggle('is-on', show);
    cta.setAttribute('aria-hidden', show ? 'false' : 'true');
    cta.tabIndex = show ? 0 : -1;
  }
  function queue() { if (!ticking) { ticking = true; requestAnimationFrame(update); } }
  var io = new IntersectionObserver(function (es) {
    es.forEach(function (e) { if (e.isIntersecting) visible.add(e.target); else visible.delete(e.target); });
    queue();
  }, { threshold: 0.05 });
  document.querySelectorAll('[data-float-hide]').forEach(function (el) { io.observe(el); });
  window.addEventListener('scroll', queue, { passive: true });
  new MutationObserver(queue).observe(document.body, { attributes: true, attributeFilter: ['class'] });
})();

/* Липкая шапка (по желанию владельца): при прокрутке вниз держится сверху, при прокрутке вверх уезжает.
   В самом верху страницы, при открытом меню и при фокусе с клавиатуры она видна всегда. */
(function () {
  'use strict';
  var bar = document.querySelector('.topbar');
  if (!bar) return;
  var root = document.documentElement, lastY = window.scrollY, ticking = false, upRun = 0;
  function sbw() { root.style.setProperty('--sbw', Math.max(0, window.innerWidth - root.clientWidth) + 'px'); }
  sbw(); window.addEventListener('resize', sbw);
  var HIDE_AFTER = 150; /* столько пикселей прокрутки вверх подряд, прежде чем шапка уедет */
  function setHidden(h) { bar.classList.toggle('is-hidden', h); root.classList.toggle('topbar-hidden', h); }
  function upd() {
    ticking = false;
    var y = window.scrollY, dy = y - lastY;
    bar.classList.toggle('is-stuck', y > 6);
    if (y < 80 || document.body.classList.contains('no-scroll') || bar.contains(document.activeElement)) { upRun = 0; setHidden(false); }
    else if (dy > 4) { upRun = 0; setHidden(false); }
    else if (dy < -4) { upRun += -dy; if (upRun > HIDE_AFTER) setHidden(true); }
    if (Math.abs(dy) > 4) lastY = y;
  }
  window.addEventListener('scroll', function () { if (!ticking) { ticking = true; requestAnimationFrame(upd); } }, { passive: true });
  bar.addEventListener('focusin', function () { setHidden(false); });
  upd();
})();
