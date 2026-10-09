/* Хранилище: берёт список с сервера (/api/visualizations), рисует папки, фильтрует по разделу и тегу. */
(function () {
  'use strict';
  var DATA_URL = '/api/visualizations';
  var listEl = document.getElementById('list');
  var secEl = document.getElementById('chips-sections');
  var shownEl = document.getElementById('shown');
  var totalEl = document.getElementById('total');
  var filtersEl = document.querySelector('.filters');
  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  var state = { section: 'all' };
  var data = null, sectionsById = {};

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function plural(n, one, few, many) {
    var m10 = n % 10, m100 = n % 100;
    if (m10 === 1 && m100 !== 11) return one;
    if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return few;
    return many;
  }

  function readHash() {
    var h = (location.hash || '').replace('#', '');
    if (h && sectionsById[h]) state.section = h;
  }
  function writeHash() {
    var h = state.section === 'all' ? '' : '#' + state.section;
    try { history.replaceState(null, '', location.pathname + location.search + h); } catch (e) { /* без истории тоже работает */ }
  }

  function renderChips() {
    var items = data.items;
    secEl.textContent = '';
    var counts = {};
    items.forEach(function (it) { counts[it.section] = (counts[it.section] || 0) + 1; });

    var defs = [{ id: 'all', label: 'Все', color: 'var(--ink)', n: items.length }].concat(
      data.sections.map(function (s) {
        return { id: s.id, label: s.label, color: s.color, n: counts[s.id] || 0 };
      })
    );
    defs.forEach(function (d) {
      var b = el('button', 'chip');
      b.type = 'button';
      if (!d.n) { b.disabled = true; b.title = 'Скоро'; }
      b.setAttribute('aria-pressed', String(state.section === d.id));
      if (d.id !== 'all') { var dot = el('span', 'dot'); dot.style.background = d.color; b.appendChild(dot); }
      b.appendChild(document.createTextNode(d.label + ' '));
      b.appendChild(el('span', 'count', String(d.n)));
      b.addEventListener('click', function () { state.section = d.id; writeHash(); render(true); });
      secEl.appendChild(b);
    });
  }

  function card(it, num, animate, delay) {
    var s = sectionsById[it.section] || { label: it.section, color: '#181820', tint: '#ece9e0', ink: '#181820' };
    var a = el('a', 'row');
    a.href = it.file;
    if (animate && !reduceMotion) { a.classList.add('enter'); a.style.animationDelay = delay + 'ms'; }

    var folder = el('div', 'folder');
    folder.setAttribute('aria-hidden', 'true');
    var tab = el('div', 'folder__tab', num); tab.style.background = s.color;
    var body = el('div', 'folder__body'); body.style.background = s.tint;
    var sheet = el('div', 'sheet');
    if (it.cover) { var img = el('img'); img.src = '../' + it.cover; img.alt = ''; img.loading = 'lazy'; sheet.appendChild(img); }
    else sheet.appendChild(el('span', 'ph', 'обложка'));
    folder.appendChild(tab); folder.appendChild(body); folder.appendChild(sheet);

    var text = el('div', 'row__text');
    text.appendChild(el('span', 'row__meta', num + ' · ' + s.label + ' · ' + it.parts));
    text.appendChild(el('h2', 'row__title', it.title));
    text.appendChild(el('p', 'row__desc', it.description));
    var tags = el('div', 'row__tags');
    var st = el('span', 'tag', s.label); st.style.background = s.tint; st.style.borderColor = s.tint; st.style.color = s.ink;
    tags.appendChild(st);
    it.tags.forEach(function (t) { tags.appendChild(el('span', 'tag', t)); });
    text.appendChild(tags);

    var go = el('span', 'go', '→'); go.setAttribute('aria-hidden', 'true');
    a.appendChild(folder); a.appendChild(text); a.appendChild(go);
    return a;
  }

  function render(animate) {
    renderChips();
    var all = data.items;
    var list = all.map(function (it, i) { return { it: it, num: pad(i + 1) }; }).filter(function (x) {
      return state.section === 'all' || x.it.section === state.section;
    });

    listEl.textContent = '';
    var prev = null;
    list.forEach(function (x, i) {
      var li = el('li');
      if (x.it.section !== prev) {
        var s = sectionsById[x.it.section] || { label: x.it.section, color: '#181820', ink: '#181820' };
        var d = el('div', 'divider');
        var sq = el('span', 'sq'); sq.style.background = s.color;
        var nm = el('span', 'name', s.label); nm.style.color = s.ink;
        d.appendChild(sq); d.appendChild(nm); d.appendChild(el('span', 'rule'));
        li.appendChild(d);
        prev = x.it.section;
      }
      li.appendChild(card(x.it, x.num, animate, Math.min(i, 8) * 45));
      listEl.appendChild(li);
    });

    if (!list.length) {
      var li = el('li', 'empty');
      li.appendChild(el('div', null, 'В этом разделе пока ничего нет.'));
      var reset = el('button', 'btn btn--small', 'Показать все'); reset.type = 'button';
      reset.addEventListener('click', function () { state.section = 'all'; writeHash(); render(true); });
      li.appendChild(reset);
      listEl.appendChild(li);
    }
    shownEl.textContent = 'показано ' + list.length + ' из ' + all.length;
  }

  function fail() {
    listEl.textContent = '';
    var li = el('li', 'empty');
    li.textContent = 'Не получилось загрузить список. Обнови страницу через минуту.';
    listEl.appendChild(li);
  }

  if (filtersEl && 'IntersectionObserver' in window) {
    var sentinel = document.createElement('div');
    filtersEl.parentNode.insertBefore(sentinel, filtersEl);
    new IntersectionObserver(function (es) { filtersEl.classList.toggle('is-stuck', !es[0].isIntersecting); }).observe(sentinel);
  }

  fetch(DATA_URL, { cache: 'no-cache' })
    .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(function (json) {
      data = json;
      data.sections.forEach(function (s) { sectionsById[s.id] = s; });
      var n = data.items.length;
      if (totalEl) totalEl.textContent = n + ' ' + plural(n, 'материал', 'материала', 'материалов');
      readHash();
      render(false);
      window.addEventListener('hashchange', function () { readHash(); render(true); });
    })
    .catch(fail);
})();
