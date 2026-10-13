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

/* Графики с [data-draw] прорисовываются один раз, когда попадают на экран (даже на первом экране). */
(function () {
  'use strict';
  var els = document.querySelectorAll('[data-draw]');
  if (!els.length || !('IntersectionObserver' in window)) return;
  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  var io = new IntersectionObserver(function (es) {
    es.forEach(function (e) {
      if (!e.isIntersecting) return;
      io.unobserve(e.target);
      requestAnimationFrame(function () { requestAnimationFrame(function () { e.target.classList.add('is-drawn'); }); });
    });
  }, { threshold: 0.35 });
  els.forEach(function (el) { el.classList.add('is-armed'); io.observe(el); });
})();

/* Кнопка «Дедлайны» для вошедших учеников (решение владельца): вместо «Бесплатный урок» в шапке —
   огонёк, открывает панель справа: что начато и сколько осталось до сдачи. Плавающая кнопка записи тоже прячется. */
(function () {
  'use strict';
  var bar = document.querySelector('.topbar');
  if (!bar || !window.fetch) return;
  var root = document.documentElement, KEY = 'signed-in';
  /* чтобы «Бесплатный урок» не мелькал у тех, кто уже входил, класс ставим сразу и снимаем, если вход истёк */
  try { if (localStorage.getItem(KEY) === '1') root.classList.add('is-student'); } catch (e) { /* без хранилища */ }

  var FLAME = '<svg class="flame" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round" aria-hidden="true">' +
    '<path class="flame__outer" d="M12 21.2c-3.9 0-6.6-2.7-6.6-6.3 0-2.7 1.5-4.7 3.2-6.4.3 1.6 1.1 2.7 2.2 3.2.1-3.3 1.6-6.1 4.2-8.4.2 3.1 1.6 4.9 2.9 6.7 1 1.4 1.5 2.9 1.5 4.7 0 3.6-3.1 6.5-7.4 6.5z"/>' +
    '<path class="flame__inner" d="M12 21.2c-1.8 0-3-1.2-3-2.9 0-1.5 1-2.7 2.3-3.7.2 1 .7 1.5 1.3 1.7.3-1.1.9-1.9 1.8-2.5.4 1.7 1.6 2.5 1.6 4.3 0 1.8-1.7 3.1-4 3.1z" fill="currentColor" stroke="none"/></svg>';

  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function plural(n, one, few, many) { var a = Math.abs(n) % 100, b = a % 10; if (a > 10 && a < 20) return many; if (b > 1 && b < 5) return few; return b === 1 ? one : many; }
  function left(iso) {
    var ms = new Date(iso).getTime() - Date.now();
    if (ms <= 0) return 'срок истёк';
    var min = Math.ceil(ms / 60000), d = Math.floor(min / 1440), h = Math.floor((min % 1440) / 60), m = min % 60;
    if (d) return d + ' ' + plural(d, 'день', 'дня', 'дней') + (h ? ' ' + h + ' ' + plural(h, 'час', 'часа', 'часов') : '');
    if (h) return h + ' ' + plural(h, 'час', 'часа', 'часов') + (m ? ' ' + m + ' мин' : '');
    return m + ' мин';
  }
  function when(iso) {
    var d = new Date(iso);
    return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' }) + ', ' + d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
  }

  /* кнопка в шапке */
  var btn = el('button', 'dl-btn');
  btn.type = 'button';
  btn.setAttribute('aria-controls', 'dlp'); btn.setAttribute('aria-expanded', 'false');
  btn.innerHTML = FLAME + '<span class="dl-btn__txt">Дедлайны</span><span class="dl-btn__n" hidden></span>';
  var cta = bar.querySelector('.cta-text');
  bar.insertBefore(btn, cta || null);

  /* панель справа */
  var panel = el('div', 'dlp'); panel.id = 'dlp'; panel.setAttribute('aria-hidden', 'true');
  panel.innerHTML = '<button class="dlp__scrim" type="button" tabindex="-1" aria-label="Закрыть"></button>' +
    '<section class="dlp__panel" role="dialog" aria-modal="true" aria-labelledby="dlp-h">' +
    '<div class="dlp__head"><h2 class="dlp__h" id="dlp-h">' + FLAME + 'Дедлайны</h2>' +
    '<button class="icon-btn dlp__close" type="button" aria-label="Закрыть"><svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M3 3l12 12M15 3L3 15"/></svg></button></div>' +
    '<div class="dlp__body"></div>' +
    '<div class="dlp__foot"><a class="btn btn--solid" href="/account/">Личный кабинет <span aria-hidden="true">→</span></a></div></section>';
  document.body.appendChild(panel);
  var body = panel.querySelector('.dlp__body'), data = null, lastFocus = null;

  function render() {
    body.textContent = '';
    var items = (data && data.items) || [];
    var active = items.filter(function (x) { return x.state === 'active'; });
    var late = items.filter(function (x) { return x.state !== 'active'; });
    if (!items.length) {
      body.appendChild(el('p', 'dlp__empty', 'Сейчас ничего не начато. Когда откроете занятие или пробник в кабинете и нажмёте «Начать», срок появится здесь.'));
    }
    function group(title, list, cls) {
      if (!list.length) return;
      body.appendChild(el('h3', 'dlp__group', title));
      var ul = el('ul', 'dlp__list');
      list.forEach(function (x) {
        var li = el('li');
        var a = el('a', 'dlp__item ' + cls); a.href = x.url;
        var top = el('span', 'dlp__top');
        top.appendChild(el('span', 'dlp__kind', x.label));
        if (x.overdue) top.appendChild(el('span', 'dlp__late', 'просрочено' + (x.overdue > 1 ? ' × ' + x.overdue : '')));
        a.appendChild(top);
        if (x.title) a.appendChild(el('span', 'dlp__title', x.title));
        if (x.state === 'active') {
          var urgent = new Date(x.due_at) - Date.now() < 864e5;
          if (urgent) a.classList.add('is-urgent');
          var big = el('b', 'dlp__left', left(x.due_at)); big.dataset.due = x.due_at;
          a.appendChild(big);
          a.appendChild(el('span', 'dlp__meta', 'начато ' + when(x.started_at) + ' · сдать до ' + when(x.due_at)));
          var total = new Date(x.due_at) - new Date(x.started_at), passed = Date.now() - new Date(x.started_at);
          var barEl = el('span', 'dlp__bar'), fill = el('i');
          fill.style.width = Math.max(3, Math.min(100, 100 * passed / total)) + '%';
          barEl.appendChild(fill); a.appendChild(barEl);
        } else {
          a.appendChild(el('span', 'dlp__meta', 'Срок истёк' + (x.last_overdue_at ? ' ' + when(x.last_overdue_at) : '') + '. Откройте и возьмите новый срок — ' + x.days + ' ' + plural(x.days, 'день', 'дня', 'дней') + '.'));
        }
        li.appendChild(a); ul.appendChild(li);
      });
      body.appendChild(ul);
    }
    group('В работе', active, 'dlp__item--active');
    group('Срок истёк', late, 'dlp__item--late');
    if (data && data.user && data.user.curator) {
      var c = el('a', 'dlp__curator', 'Проверка работ →'); c.href = '/check/'; body.appendChild(c);
    }
    /* на кнопке — сколько сейчас в работе; горит сильнее, если до сдачи меньше суток */
    var n = btn.querySelector('.dl-btn__n');
    n.hidden = !active.length; n.textContent = active.length;
    btn.classList.toggle('is-urgent', active.some(function (x) { return new Date(x.due_at) - Date.now() < 864e5; }));
    btn.setAttribute('aria-label', 'Дедлайны' + (active.length ? ': в работе ' + active.length : ''));
  }

  function open() {
    lastFocus = document.activeElement;
    panel.classList.add('is-open'); panel.setAttribute('aria-hidden', 'false');
    btn.setAttribute('aria-expanded', 'true');
    document.body.classList.add('no-scroll');
    load();
    setTimeout(function () { panel.querySelector('.dlp__close').focus({ preventScroll: true }); }, 60);
  }
  function close() {
    if (!panel.classList.contains('is-open')) return;
    panel.classList.remove('is-open'); panel.setAttribute('aria-hidden', 'true');
    btn.setAttribute('aria-expanded', 'false');
    document.body.classList.remove('no-scroll');
    if (lastFocus && lastFocus.focus) lastFocus.focus({ preventScroll: true });
  }
  btn.addEventListener('click', open);
  panel.querySelector('.dlp__scrim').addEventListener('click', close);
  panel.querySelector('.dlp__close').addEventListener('click', close);
  panel.querySelectorAll('.dlp__body, .dlp__foot').forEach(function (n) {
    n.addEventListener('click', function (e) { var a = e.target.closest('a'); if (a && a.pathname === location.pathname) close(); });
  });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });
  var x0 = null, sheet = panel.querySelector('.dlp__panel');
  sheet.addEventListener('touchstart', function (e) { x0 = e.touches[0].clientX; }, { passive: true });
  sheet.addEventListener('touchend', function (e) { if (x0 !== null && e.changedTouches[0].clientX - x0 > 60) close(); x0 = null; }, { passive: true });

  function load() {
    return fetch('/api/me/deadlines', { credentials: 'same-origin' }).then(function (r) {
      if (r.status === 401) {
        root.classList.remove('is-student');
        try { localStorage.removeItem(KEY); } catch (e) { /* без хранилища */ }
        close();
        return null;
      }
      return r.ok ? r.json() : null;
    }).then(function (d) {
      if (!d) return;
      data = d;
      root.classList.add('is-student');
      try { localStorage.setItem(KEY, '1'); } catch (e) { /* без хранилища */ }
      render();
    }).catch(function () { /* без сети оставляем как есть */ });
  }
  load();
  /* таймеры в открытой панели и состояние кнопки — раз в минуту; после действий в кабинете — при возврате на вкладку */
  setInterval(function () {
    panel.querySelectorAll('[data-due]').forEach(function (b) { b.textContent = left(b.dataset.due); });
  }, 30000);
  document.addEventListener('visibilitychange', function () { if (document.visibilityState === 'visible' && root.classList.contains('is-student')) load(); });
  window.refreshDeadlines = load;  /* кабинет зовёт после «Начать» / сдачи */
})();
