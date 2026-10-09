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
})();
