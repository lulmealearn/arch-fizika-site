/* Админка: вкладки, ученики и их доступы, домашние задания (PDF) и уроки (ссылки).
   Визуализациями занимается admin.js; отсюда он берёт список учеников и «пикер» для поля «Кому открыта». */
(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var data = { users: [], hw: [], lessons: [], viz: [] };
  var started = false;

  /* ── Общее ── */
  function api(method, url, body) {
    var opts = { method: method, credentials: 'same-origin', headers: {} };
    if (body instanceof FormData) opts.body = body;
    else if (body !== undefined) { opts.body = JSON.stringify(body); opts.headers['Content-Type'] = 'application/json'; }
    return fetch(url, opts).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (d) {
        if (!r.ok) {
          var e = new Error(typeof d.detail === 'string' ? d.detail : 'Сервер ответил ошибкой ' + r.status + '.');
          e.status = r.status; throw e;
        }
        return d;
      });
    }, function () { throw new Error('Нет связи с сервером. Он запущен?'); });
  }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function plural(n, one, few, many) {
    var a = n % 10, b = n % 100;
    if (a === 1 && b !== 11) return one;
    if (a >= 2 && a <= 4 && (b < 12 || b > 14)) return few;
    return many;
  }
  var toastTimer = null;
  function toast(text, isError) {
    var t = $('toast');
    t.textContent = text; t.classList.toggle('is-error', !!isError); t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.hidden = true; }, isError ? 5000 : 2600);
  }
  function showError(msg) { var n = $('editor2-error'); n.textContent = msg || ''; n.hidden = !msg; }
  function date(iso) {
    if (!iso) return '—';
    var d = new Date(iso);
    return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' });
  }
  function armDelete(btn, run) {
    if (btn.classList.contains('is-armed')) { btn.disabled = true; run().catch(function (e) { toast(e.message, true); btn.disabled = false; }); return; }
    var label = btn.textContent;
    btn.classList.add('is-armed'); btn.textContent = 'Точно удалить?';
    setTimeout(function () { if (btn.isConnected) { btn.classList.remove('is-armed'); btn.textContent = label; } }, 3500);
  }
  function nick(id) {
    for (var i = 0; i < data.users.length; i++) if (data.users[i].id === id) return data.users[i].nickname;
    return '?';
  }
  function whoLine(ids) {
    if (!ids || !ids.length) return 'никому не открыто';
    var names = ids.map(nick);
    return 'открыто: ' + (names.length > 4 ? names.slice(0, 4).join(', ') + ' и ещё ' + (names.length - 4) : names.join(', '));
  }

  /* ── Пикер: список с галочками, поиск, «все / никто» ──
     items: [{id, label, sub}], selected: [id]. Возвращает функцию, отдающую выбранные id. */
  function picker(box, items, selected, emptyText) {
    box.textContent = '';
    var chosen = {};
    (selected || []).forEach(function (id) { chosen[id] = true; });
    if (!items.length) { box.appendChild(el('p', 'picker__empty', emptyText || 'Пусто.')); return function () { return []; }; }

    var bar = el('div', 'picker__bar');
    var search = null;
    if (items.length > 8) {
      search = el('input', 'input picker__search'); search.type = 'search'; search.placeholder = 'Поиск'; search.setAttribute('aria-label', 'Поиск по списку');
      bar.appendChild(search);
    }
    var all = el('button', 'btn btn--small picker__btn', 'Все'); all.type = 'button';
    var none = el('button', 'btn btn--small picker__btn', 'Никто'); none.type = 'button';
    var count = el('span', 'picker__count');
    bar.appendChild(all); bar.appendChild(none); bar.appendChild(count);
    box.appendChild(bar);

    var list = el('div', 'picker__list');
    var rows = items.map(function (it) {
      var lab = el('label', 'pick');
      var cb = el('input'); cb.type = 'checkbox'; cb.checked = !!chosen[it.id];
      cb.addEventListener('change', function () { chosen[it.id] = cb.checked; upd(); });
      var txt = el('span', 'pick__text');
      txt.appendChild(el('span', 'pick__label', it.label));
      if (it.sub) txt.appendChild(el('span', 'pick__sub', it.sub));
      lab.appendChild(cb); lab.appendChild(txt);
      list.appendChild(lab);
      return { it: it, lab: lab, cb: cb };
    });
    box.appendChild(list);

    function visible() { return rows.filter(function (r) { return !r.lab.hidden; }); }
    function upd() {
      var n = rows.filter(function (r) { return r.cb.checked; }).length;
      count.textContent = 'выбрано ' + n + ' из ' + rows.length;
    }
    all.addEventListener('click', function () { visible().forEach(function (r) { r.cb.checked = true; chosen[r.it.id] = true; }); upd(); });
    none.addEventListener('click', function () { visible().forEach(function (r) { r.cb.checked = false; chosen[r.it.id] = false; }); upd(); });
    if (search) search.addEventListener('input', function () {
      var q = search.value.trim().toLowerCase();
      rows.forEach(function (r) { r.lab.hidden = q && (r.it.label + ' ' + (r.it.sub || '')).toLowerCase().indexOf(q) < 0; });
    });
    upd();
    return function () { return rows.filter(function (r) { return r.cb.checked; }).map(function (r) { return r.it.id; }); };
  }
  function userItems() {
    return data.users.map(function (u) { return { id: u.id, label: u.nickname, sub: 'с ' + date(u.created_at) }; });
  }

  /* ── Вкладки ── */
  var TABS = ['viz', 'hw', 'lessons', 'users'];
  function setTab(name, push) {
    if (TABS.indexOf(name) < 0) name = 'viz';
    document.querySelectorAll('.tabs__btn').forEach(function (b) { b.setAttribute('aria-selected', String(b.dataset.tab === name)); });
    TABS.forEach(function (t) { $('panel-' + t).hidden = t !== name; });
    if (push) { try { history.replaceState(null, '', name === 'viz' ? location.pathname : '#' + name); } catch (e) { /* без истории */ } }
  }
  document.querySelectorAll('.tabs__btn').forEach(function (b) {
    b.addEventListener('click', function () { setTab(b.dataset.tab, true); });
  });

  /* ── Загрузка ── */
  function loadAll() {
    return Promise.all([
      api('GET', '/api/admin/users'), api('GET', '/api/admin/homeworks'), api('GET', '/api/admin/lessons'),
    ]).then(function (r) {
      data.users = r[0].users; data.hw = r[1].items; data.lessons = r[2].items;
      renderUsers(); renderHw(); renderLessons(); counts();
    }).catch(function (e) { toast(e.message, true); });
  }
  function counts() {
    $('tn-hw').textContent = data.hw.length || '';
    $('tn-lessons').textContent = data.lessons.length || '';
    $('tn-users').textContent = data.users.length || '';
  }

  /* ── Домашки ── */
  function renderHw() {
    var list = $('hw-list'); list.textContent = '';
    $('hw-summary').textContent = data.hw.length + ' ' + plural(data.hw.length, 'задание', 'задания', 'заданий');
    if (!data.hw.length) { list.appendChild(el('li', 'empty-list', 'Пока пусто. Нажми «Добавить ДЗ» и загрузи PDF.')); return; }
    data.hw.forEach(function (h) {
      var li = el('li', 'adm-row adm-row--plain');
      var num = el('span', 'numbadge'); num.appendChild(el('span', null, 'ДЗ')); num.appendChild(el('b', null, String(h.number)));
      var text = el('div', 'adm-row__text');
      text.appendChild(el('h2', 'adm-row__title', h.title || 'Домашнее задание № ' + h.number));
      text.appendChild(el('span', 'adm-row__meta', '/hw/' + h.number + '  ·  ' + whoLine(h.user_ids)));
      var actions = el('div', 'row-actions');
      var open = el('a', 'btn btn--small', 'PDF'); open.href = h.url; open.target = '_blank'; open.rel = 'noopener';
      var edit = el('button', 'btn btn--small', 'Изменить'); edit.type = 'button';
      edit.addEventListener('click', function () { editHw(h); });
      var del = el('button', 'btn btn--small btn--danger', 'Удалить'); del.type = 'button';
      del.addEventListener('click', function () {
        armDelete(del, function () { return api('DELETE', '/api/admin/homeworks/' + h.pk).then(function () { toast('ДЗ № ' + h.number + ' удалено'); return loadAll(); }); });
      });
      actions.appendChild(open); actions.appendChild(edit); actions.appendChild(del);
      li.appendChild(num); li.appendChild(text); li.appendChild(actions);
      list.appendChild(li);
    });
  }

  function nextNumber(items) {
    return items.reduce(function (m, x) { return Math.max(m, x.number); }, 0) + 1;
  }

  function editHw(h) {
    openEditor2(h ? 'ДЗ № ' + h.number : 'Новое ДЗ', function (body) {
      body.appendChild(field('Номер *', numberInput('e-number', h ? h.number : nextNumber(data.hw))));
      body.appendChild(field('Название', textInput('e-title', h ? h.title : '', 'Например: Кинематика, равноускоренное движение')));
      var drop = el('label', 'drop');
      var inp = el('input', 'drop__input'); inp.type = 'file'; inp.id = 'e-pdf'; inp.accept = 'application/pdf,.pdf';
      var t = el('span', 'drop__text', h ? 'Сейчас загружен PDF. Перетащи новый, чтобы заменить' : 'Перетащи PDF сюда или нажми, чтобы выбрать');
      drop.appendChild(inp); drop.appendChild(t);
      inp.addEventListener('change', function () {
        var f = inp.files[0]; if (!f) return;
        drop.classList.add('has-file'); t.textContent = f.name + ' · ' + Math.max(1, Math.round(f.size / 1024)) + ' КБ';
        var m = f.name.match(/(\d+)/);
        if (!h && m && !$('e-number').dataset.touched) $('e-number').value = m[1];
      });
      body.appendChild(field(h ? 'Заменить PDF (необязательно)' : 'PDF *', drop));
      var box = el('div', 'picker');
      var get = picker(box, userItems(), h ? h.user_ids : [], 'Учеников пока нет: они появятся после регистрации в личном кабинете.');
      body.appendChild(field('Кому открыто', box));
      return function () {
        var fd = new FormData();
        var pdf = inp.files[0];
        if (!h && !pdf) throw new Error('Выбери PDF-файл.');
        if (pdf && !/\.pdf$/i.test(pdf.name)) throw new Error('Нужен файл .pdf.');
        fd.append('number', $('e-number').value.trim());
        fd.append('title', $('e-title').value.trim());
        fd.append('user_ids', JSON.stringify(get()));
        if (pdf) fd.append('pdf', pdf);
        return (h ? api('PATCH', '/api/admin/homeworks/' + h.pk, fd) : api('POST', '/api/admin/homeworks', fd))
          .then(function (r) { toast((h ? 'Сохранено: ДЗ № ' : 'Добавлено: ДЗ № ') + r.number); });
      };
    });
  }

  /* ── Уроки ── */
  function renderLessons() {
    var list = $('lessons-list'); list.textContent = '';
    $('lessons-summary').textContent = data.lessons.length + ' ' + plural(data.lessons.length, 'урок', 'урока', 'уроков');
    if (!data.lessons.length) { list.appendChild(el('li', 'empty-list', 'Пока пусто. Нажми «Добавить урок» и вставь ссылку на запись.')); return; }
    data.lessons.forEach(function (l) {
      var li = el('li', 'adm-row adm-row--plain');
      var num = el('span', 'numbadge'); num.appendChild(el('span', null, 'Урок')); num.appendChild(el('b', null, String(l.number)));
      var text = el('div', 'adm-row__text');
      text.appendChild(el('h2', 'adm-row__title', l.title || 'Запись урока № ' + l.number));
      text.appendChild(el('span', 'adm-row__meta', whoLine(l.user_ids)));
      var actions = el('div', 'row-actions');
      var open = el('a', 'btn btn--small', 'Ссылка'); open.href = l.url; open.target = '_blank'; open.rel = 'noopener noreferrer';
      var edit = el('button', 'btn btn--small', 'Изменить'); edit.type = 'button';
      edit.addEventListener('click', function () { editLesson(l); });
      var del = el('button', 'btn btn--small btn--danger', 'Удалить'); del.type = 'button';
      del.addEventListener('click', function () {
        armDelete(del, function () { return api('DELETE', '/api/admin/lessons/' + l.pk).then(function () { toast('Урок № ' + l.number + ' удалён'); return loadAll(); }); });
      });
      actions.appendChild(open); actions.appendChild(edit); actions.appendChild(del);
      li.appendChild(num); li.appendChild(text); li.appendChild(actions);
      list.appendChild(li);
    });
  }

  function editLesson(l) {
    openEditor2(l ? 'Урок № ' + l.number : 'Новый урок', function (body) {
      body.appendChild(field('Номер *', numberInput('e-number', l ? l.number : nextNumber(data.lessons))));
      body.appendChild(field('Название', textInput('e-title', l ? l.title : '', 'Например: Законы Ньютона')));
      var url = textInput('e-url', l ? l.url : '', 'https://…'); url.type = 'url'; url.inputMode = 'url'; url.spellcheck = false;
      body.appendChild(field('Ссылка на запись *', url));
      var box = el('div', 'picker');
      var get = picker(box, userItems(), l ? l.user_ids : [], 'Учеников пока нет: они появятся после регистрации в личном кабинете.');
      body.appendChild(field('Кому открыт', box));
      return function () {
        var u = $('e-url').value.trim();
        if (!/^https?:\/\/\S+$/i.test(u)) throw new Error('Ссылка должна начинаться с https://');
        var payload = { number: Number($('e-number').value), title: $('e-title').value.trim(), url: u, user_ids: get() };
        return (l ? api('PATCH', '/api/admin/lessons/' + l.pk, payload) : api('POST', '/api/admin/lessons', payload))
          .then(function (r) { toast((l ? 'Сохранено: урок № ' : 'Добавлено: урок № ') + r.number); });
      };
    });
  }

  /* ── Ученики ── */
  function renderUsers() {
    var list = $('users-list'); list.textContent = '';
    var q = $('users-search').value.trim().toLowerCase();
    $('users-summary').textContent = data.users.length + ' ' + plural(data.users.length, 'ученик', 'ученика', 'учеников');
    $('users-search').hidden = data.users.length < 6;
    if (!data.users.length) { list.appendChild(el('li', 'empty-list', 'Пока никто не зарегистрировался. Отправь ученику ссылку на личный кабинет: /account/')); return; }
    data.users.filter(function (u) { return !q || u.nickname.toLowerCase().indexOf(q) >= 0; }).forEach(function (u) {
      var li = el('li', 'adm-row adm-row--plain');
      var av = el('span', 'avatar', u.nickname.charAt(0).toUpperCase()); av.setAttribute('aria-hidden', 'true');
      var text = el('div', 'adm-row__text');
      text.appendChild(el('h2', 'adm-row__title', u.nickname));
      var g = u.grants;
      text.appendChild(el('span', 'adm-row__meta',
        'ДЗ: ' + g.hw.length + '  ·  уроки: ' + g.lesson.length + '  ·  визуализации: ' + g.viz.length +
        '  ·  с ' + date(u.created_at) + (u.last_login_at ? ', заходил ' + date(u.last_login_at) : '')));
      var actions = el('div', 'row-actions');
      var acc = el('button', 'btn btn--small btn--solid', 'Доступ'); acc.type = 'button';
      acc.addEventListener('click', function () { editUserAccess(u); });
      var pw = el('button', 'btn btn--small', 'Пароль'); pw.type = 'button';
      pw.addEventListener('click', function () { editUserPassword(u); });
      var del = el('button', 'btn btn--small btn--danger', 'Удалить'); del.type = 'button';
      del.addEventListener('click', function () {
        armDelete(del, function () { return api('DELETE', '/api/admin/users/' + u.id).then(function () { toast('Ученик ' + u.nickname + ' удалён'); return loadAll(); }); });
      });
      actions.appendChild(acc); actions.appendChild(pw); actions.appendChild(del);
      li.appendChild(av); li.appendChild(text); li.appendChild(actions);
      list.appendChild(li);
    });
  }
  $('users-search').addEventListener('input', renderUsers);

  function editUserAccess(u) {
    /* закрытые визуализации берём свежими: их могли только что закрыть на соседней вкладке */
    api('GET', '/api/admin/visualizations').then(function (d) {
      var priv = d.items.filter(function (v) { return v.access === 'private'; });
      openEditor2('Доступ: ' + u.nickname, function (body) {
        body.appendChild(el('p', 'hint', 'Отметь, что открыть ученику. Изменения появятся у него в личном кабинете сразу после сохранения.'));
        var boxHw = el('div', 'picker'), boxL = el('div', 'picker'), boxV = el('div', 'picker');
        var getHw = picker(boxHw, data.hw.map(function (h) { return { id: h.pk, label: 'ДЗ № ' + h.number, sub: h.title }; }), u.grants.hw, 'Домашек пока нет.');
        var getL = picker(boxL, data.lessons.map(function (l) { return { id: l.pk, label: 'Урок № ' + l.number, sub: l.title }; }), u.grants.lesson, 'Уроков пока нет.');
        var getV = picker(boxV, priv.map(function (v) { return { id: v.pk, label: v.title, sub: v.parts }; }), u.grants.viz,
          'Закрытых визуализаций нет: все открыты всем. Закрыть можно на вкладке «Визуализации».');
        body.appendChild(field('Домашки', boxHw));
        body.appendChild(field('Уроки', boxL));
        body.appendChild(field('Визуализации (только закрытые)', boxV));
        return function () {
          return api('PUT', '/api/admin/users/' + u.id + '/grants', { hw: getHw(), lesson: getL(), viz: getV() })
            .then(function () { toast('Доступ сохранён: ' + u.nickname); });
        };
      });
    }).catch(function (e) { toast(e.message, true); });
  }

  function editUserPassword(u) {
    openEditor2('Новый пароль: ' + u.nickname, function (body) {
      body.appendChild(el('p', 'hint', 'Восстановления по почте нет, поэтому новый пароль задаёшь ты и передаёшь ученику. Старые входы ученика сбросятся.'));
      var inp = textInput('e-pass', randomPassword(), ''); inp.autocomplete = 'off'; inp.spellcheck = false; inp.classList.add('mono');
      body.appendChild(field('Пароль (не короче 6 символов)', inp));
      return function () {
        var pw = $('e-pass').value;
        if (pw.length < 6) throw new Error('Пароль не короче 6 символов.');
        return api('POST', '/api/admin/users/' + u.id + '/password', { password: pw })
          .then(function () { toast('Пароль ' + u.nickname + ' изменён: ' + pw); });
      };
    });
  }
  function randomPassword() {
    var abc = 'abcdefghijkmnpqrstuvwxyz23456789', out = '';
    var buf = new Uint32Array(8);
    (window.crypto || window.msCrypto).getRandomValues(buf);
    for (var i = 0; i < 8; i++) out += abc[buf[i] % abc.length];
    return out;
  }

  /* ── Второй редактор (ДЗ, урок, доступ, пароль) ── */
  var ed = $('editor2'), submitFn = null, lastFocus = null;
  function field(label, control) {
    var f = el('div', 'field');
    f.appendChild(el('span', 'field__label', label));
    f.appendChild(control);
    return f;
  }
  function textInput(id, value, placeholder) {
    var i = el('input', 'input'); i.type = 'text'; i.id = id; i.value = value || ''; if (placeholder) i.placeholder = placeholder; i.maxLength = id === 'e-url' ? 1000 : 200;
    return i;
  }
  function numberInput(id, value) {
    var i = el('input', 'input input--num'); i.type = 'text'; i.inputMode = 'numeric'; i.id = id; i.value = value; i.maxLength = 6;
    i.addEventListener('input', function () { i.dataset.touched = '1'; var v = i.value.replace(/\D/g, ''); if (v !== i.value) i.value = v; });
    return i;
  }
  function openEditor2(title, build) {
    $('editor2-title').textContent = title;
    showError('');
    var body = $('editor2-body'); body.textContent = '';
    submitFn = build(body);
    lastFocus = document.activeElement;
    ed.classList.add('is-open'); ed.setAttribute('aria-hidden', 'false');
    document.body.classList.add('no-scroll');
    $('editor2-form').scrollTop = 0;
    setTimeout(function () { var f = body.querySelector('input'); if (f) f.focus({ preventScroll: true }); }, 80);
  }
  function closeEditor2() {
    ed.classList.remove('is-open'); ed.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('no-scroll');
    if (lastFocus && lastFocus.focus) lastFocus.focus({ preventScroll: true });
  }
  ed.querySelectorAll('[data-close-editor2]').forEach(function (b) { b.addEventListener('click', closeEditor2); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && ed.classList.contains('is-open')) closeEditor2(); });
  $('editor2-form').addEventListener('submit', function (e) {
    e.preventDefault();
    if (!submitFn) return;
    var btn = $('editor2-save'), p;
    try { p = submitFn(); } catch (err) { showError(err.message); $('editor2-form').scrollTop = 0; return; }
    showError(''); btn.disabled = true; btn.textContent = 'Сохраняю…';
    p.then(function () { closeEditor2(); return loadAll(); })
      .catch(function (err) { showError(err.message); $('editor2-form').scrollTop = 0; })
      .then(function () { btn.disabled = false; btn.textContent = 'Сохранить'; });
  });

  $('hw-add').addEventListener('click', function () { editHw(null); });
  $('lesson-add').addEventListener('click', function () { editLesson(null); });

  /* ── Для admin.js ── */
  window.AdminAccess = {
    /* вызывается после входа: подгрузить учеников, ДЗ и уроки, открыть вкладку из адреса */
    start: function () {
      if (!started) { started = true; setTab((location.hash || '').replace('#', ''), false); }
      return loadAll();
    },
    users: function () { return data.users; },
    reloadUsers: function () { return api('GET', '/api/admin/users').then(function (d) { data.users = d.users; renderUsers(); counts(); }); },
    picker: picker,
    userItems: userItems,
    whoLine: whoLine,
  };
})();
