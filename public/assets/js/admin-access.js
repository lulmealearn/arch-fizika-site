/* Админка: вкладки, ученики и их доступы, занятия (запись, конспект, ДЗ и визуализации в одной папке).
   Визуализациями занимается admin.js; отсюда он берёт список учеников и «пикер» для поля «Кому открыта». */
(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var data = { users: [], lessons: [], viz: [], mocks: [], sections: [] };
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
  /* «2 ч назад», «вчера», «5 дн. назад» */
  function ago(iso) {
    if (!iso) return 'ещё не заходил';
    var m = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
    if (m < 2) return 'только что';
    if (m < 60) return m + ' мин назад';
    var h = Math.round(m / 60);
    if (h < 24) return h + ' ч назад';
    var d = Math.round(h / 24);
    if (d === 1) return 'вчера';
    return d + ' ' + plural(d, 'день', 'дня', 'дней') + ' назад';
  }
  function dateTime(iso) {
    if (!iso) return '—';
    var d = new Date(iso);
    return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }) + ', ' + d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
  }
  function timeOnly(iso) { return iso ? new Date(iso).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }) : ''; }
  function duration(min) {
    if (min < 60) return min + ' мин';
    var h = Math.floor(min / 60), m = min % 60;
    return h + ' ч' + (m ? ' ' + m + ' мин' : '');
  }
  /* полоска «сделано из открытого» */
  function meter(label, done, total) {
    var w = el('span', 'meter' + (total && done === total ? ' meter--full' : ''));
    w.appendChild(el('span', 'meter__label', label));
    var bar = el('span', 'meter__bar'); var fill = el('span', 'meter__fill');
    fill.style.transform = 'scaleX(' + (total ? done / total : 0) + ')';
    bar.appendChild(fill); w.appendChild(bar);
    w.appendChild(el('span', 'meter__num', total ? done + ' / ' + total : '—'));
    return w;
  }

  function armDelete(btn, run, armedText) {
    if (btn.classList.contains('is-armed')) { btn.disabled = true; run().catch(function (e) { toast(e.message, true); btn.disabled = false; }); return; }
    var label = btn.textContent;
    btn.classList.add('is-armed'); btn.textContent = armedText || 'Точно удалить?';
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
  /* Список с галочками. opts.onChange — после каждой отметки; у возвращённой функции есть .cover(ids):
     спрятать строки (например, визуализации, которые уже открыты через отмеченные занятия) — их отметка не теряется. */
  function picker(box, items, selected, emptyText, opts) {
    opts = opts || {};
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
      cb.addEventListener('change', function () { chosen[it.id] = cb.checked; upd(); if (opts.onChange) opts.onChange(); });
      var txt = el('span', 'pick__text');
      txt.appendChild(el('span', 'pick__label', it.label));
      if (it.sub) txt.appendChild(el('span', 'pick__sub', it.sub));
      lab.appendChild(cb); lab.appendChild(txt);
      list.appendChild(lab);
      return { it: it, lab: lab, cb: cb };
    });
    box.appendChild(list);

    var covered = {}, q = '';
    var coverNote = el('p', 'picker__empty');
    coverNote.hidden = true;
    box.appendChild(coverNote);
    function apply() {
      rows.forEach(function (r) {
        r.lab.hidden = !!covered[r.it.id] || (!!q && (r.it.label + ' ' + (r.it.sub || '')).toLowerCase().indexOf(q) < 0);
      });
      var n = rows.filter(function (r) { return covered[r.it.id]; }).length;
      coverNote.hidden = !n || !opts.coverText;
      if (opts.coverText) coverNote.textContent = opts.coverText(n);
    }
    function visible() { return rows.filter(function (r) { return !r.lab.hidden; }); }
    function upd() {
      var shown = rows.filter(function (r) { return !covered[r.it.id]; });
      var n = shown.filter(function (r) { return r.cb.checked; }).length;
      count.textContent = 'выбрано ' + n + ' из ' + shown.length;
    }
    all.addEventListener('click', function () { visible().forEach(function (r) { r.cb.checked = true; chosen[r.it.id] = true; }); upd(); if (opts.onChange) opts.onChange(); });
    none.addEventListener('click', function () { visible().forEach(function (r) { r.cb.checked = false; chosen[r.it.id] = false; }); upd(); if (opts.onChange) opts.onChange(); });
    if (search) search.addEventListener('input', function () { q = search.value.trim().toLowerCase(); apply(); });
    upd();
    var get = function () { return rows.filter(function (r) { return r.cb.checked; }).map(function (r) { return r.it.id; }); };
    get.cover = function (ids) {
      covered = {};
      (ids || []).forEach(function (id) { covered[id] = true; });
      apply(); upd();
    };
    return get;
  }
  function userItems() {
    return data.users.map(function (u) { return { id: u.id, label: u.nickname, sub: 'с ' + date(u.created_at) }; });
  }

  /* ── Вкладки ── */
  var TABS = ['viz', 'lessons', 'mocks', 'users'];
  function setTab(name, push) {
    if (name === 'hw') name = 'lessons';  /* старая вкладка «Домашки» */
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
      api('GET', '/api/admin/users'), api('GET', '/api/admin/lessons'), api('GET', '/api/admin/visualizations'), api('GET', '/api/admin/mocks'),
    ]).then(function (r) {
      data.users = r[0].users; data.lessons = r[1].items; data.viz = r[2].items; data.sections = r[2].sections || []; data.mocks = r[3].items;
      renderUsers(); renderLessons(); renderMocks(); counts();
      loadAuto();
    }).catch(function (e) { toast(e.message, true); });
  }
  function counts() {
    $('tn-lessons').textContent = data.lessons.length || '';
    $('tn-mocks').textContent = data.mocks.length || '';
    $('tn-users').textContent = data.users.length || '';
  }

  function nextNumber(items) {
    return items.reduce(function (m, x) { return Math.max(m, x.number); }, 0) + 1;
  }

  /* ── Занятия ── */
  function vizTitle(id) {
    for (var i = 0; i < data.viz.length; i++) if (data.viz[i].pk === id) return data.viz[i].title;
    return '?';
  }
  function lessonContents(l) {
    var parts = [];
    if (l.url) parts.push('запись');
    if (l.notes_url) parts.push('конспект');
    if (l.hw_url) parts.push('ДЗ');
    if (l.viz_ids.length) parts.push(l.viz_ids.length + ' ' + plural(l.viz_ids.length, 'визуализация', 'визуализации', 'визуализаций'));
    return parts.length ? parts.join(' · ') : 'пока пусто';
  }
  function renderLessons() {
    var list = $('lessons-list'); list.textContent = '';
    $('lessons-summary').textContent = data.lessons.length + ' ' + plural(data.lessons.length, 'занятие', 'занятия', 'занятий');
    if (!data.lessons.length) { list.appendChild(el('li', 'empty-list', 'Пока пусто. Нажми «Добавить занятие»: запись, конспект, ДЗ и визуализации — в одной папке.')); return; }
    data.lessons.forEach(function (l) {
      var li = el('li', 'adm-row adm-row--plain');
      var num = el('span', 'numbadge'); num.appendChild(el('span', null, 'Занятие')); num.appendChild(el('b', null, String(l.number)));
      var text = el('div', 'adm-row__text');
      text.appendChild(el('h2', 'adm-row__title', l.title || 'Занятие № ' + l.number));
      var sec = data.sections.filter(function (x) { return x.id === l.section; })[0];
      text.appendChild(el('span', 'adm-row__meta', (sec ? sec.label + '  ·  ' : 'без раздела  ·  ') + lessonContents(l) + (l.deadline_days && l.deadline_days !== 3 ? '  ·  срок на ДЗ ' + l.deadline_days + ' ' + plural(l.deadline_days, 'день', 'дня', 'дней') : '') + '  ·  ' + whoLine(l.user_ids)));
      var actions = el('div', 'row-actions');
      var edit = el('button', 'btn btn--small', 'Изменить'); edit.type = 'button';
      edit.addEventListener('click', function () { editLesson(l); });
      var del = el('button', 'btn btn--small btn--danger', 'Удалить'); del.type = 'button';
      del.addEventListener('click', function () {
        armDelete(del, function () { return api('DELETE', '/api/admin/lessons/' + l.pk).then(function () { toast('Занятие № ' + l.number + ' удалено'); return loadAll(); }); });
      });
      actions.appendChild(edit); actions.appendChild(del);
      li.appendChild(num); li.appendChild(text); li.appendChild(actions);
      list.appendChild(li);
    });
  }

  /* Поле для PDF: выбрать, заменить или убрать. Возвращает {box, file(), remove()} */
  function pdfField(id, currentUrl, emptyText, accept) {
    var wrap = el('div', 'pdf-field');
    var drop = el('label', 'drop' + (currentUrl ? ' has-file' : ''));
    var inp = el('input', 'drop__input'); inp.type = 'file'; inp.id = id; inp.accept = accept || 'application/pdf,.pdf';
    var t = el('span', 'drop__text', currentUrl ? 'Загружен. Перетащи новый файл, чтобы заменить' : emptyText);
    drop.appendChild(inp); drop.appendChild(t);
    wrap.appendChild(drop);
    var removed = false;
    var tools = el('div', 'pdf-field__tools');
    if (currentUrl) {
      var open = el('a', 'btn btn--small', 'Открыть'); open.href = currentUrl; open.target = '_blank'; open.rel = 'noopener';
      var rm = el('button', 'btn btn--small btn--danger', 'Убрать'); rm.type = 'button';
      rm.addEventListener('click', function () {
        removed = !removed; inp.value = '';
        rm.textContent = removed ? 'Вернуть' : 'Убрать';
        t.textContent = removed ? 'Файл будет убран после сохранения' : 'Загружен. Перетащи новый файл, чтобы заменить';
        drop.classList.toggle('has-file', !removed);
      });
      tools.appendChild(open); tools.appendChild(rm);
      wrap.appendChild(tools);
    }
    inp.addEventListener('change', function () {
      var f = inp.files[0]; if (!f) return;
      removed = false;
      drop.classList.add('has-file'); t.textContent = f.name + ' · ' + Math.max(1, Math.round(f.size / 1024)) + ' КБ';
      /* номер из имени файла (dz-12.pdf → 12); год вроде 2027 номером не считаем */
      var m = (f.name.match(/\d+/g) || []).filter(function (x) { return x.length <= 3; }).map(function (x) { return [x, x]; })[0];
      var numEl = $('e-number');
      if (m && numEl && !numEl.dataset.touched && numEl.dataset.fresh === '1') numEl.value = m[1];
    });
    return { box: wrap, file: function () { return inp.files[0] || null; }, remove: function () { return removed; } };
  }

  function editLesson(l) {
    openEditor2(l ? 'Занятие № ' + l.number : 'Новое занятие', function (body) {
      var num = numberInput('e-number', l ? l.number : nextNumber(data.lessons));
      if (!l) num.dataset.fresh = '1';  /* номер нового занятия подставляется из имени PDF, например dz-12.pdf */
      body.appendChild(field('Номер *', num));
      body.appendChild(field('Тема', textInput('e-title', l ? l.title : '', 'Например: Законы Ньютона')));
      var sel = el('select', 'input'); sel.id = 'e-section';
      [['auto', 'Как у первой визуализации в папке'], ['none', 'Без раздела']].concat(
        data.sections.map(function (x) { return [x.id, x.label]; })).forEach(function (o) {
        var opt = el('option', null, o[1]); opt.value = o[0]; sel.appendChild(opt);
      });
      sel.value = l ? (l.section || 'none') : 'auto';
      body.appendChild(field('Раздел (фильтр в кабинете ученика)', sel));
      var dd = numberInput('e-deadline', l ? l.deadline_days : 3); dd.maxLength = 2;
      body.appendChild(field('Срок на ДЗ, дней (считается с момента, когда ученик нажал «Начать»)', dd));
      var url = textInput('e-url', l ? l.url : '', 'https://… (можно добавить позже)'); url.type = 'url'; url.inputMode = 'url'; url.spellcheck = false;
      body.appendChild(field('Ссылка на запись', url));
      var notes = pdfField('e-notes', l && l.notes_url, 'Перетащи PDF конспекта или нажми, чтобы выбрать');
      body.appendChild(field('Конспект (PDF)', notes.box));
      var hw = pdfField('e-hw', l && l.hw_url, 'Перетащи PDF домашнего задания или нажми, чтобы выбрать');
      body.appendChild(field('Домашнее задание (PDF)', hw.box));
      var boxV = el('div', 'picker');
      var getV = picker(boxV, data.viz.map(function (v) {
        return { id: v.pk, label: v.title, sub: (v.access === 'private' ? 'закрытая' : 'открыта всем') + (v.parts ? ' · ' + v.parts : '') };
      }), l ? l.viz_ids : [], 'Визуализаций пока нет.');
      body.appendChild(field('Визуализации в папке', boxV));
      var boxU = el('div', 'picker');
      var getU = picker(boxU, userItems(), l ? l.user_ids : [], 'Учеников пока нет: они появятся после регистрации в личном кабинете.');
      body.appendChild(field('Кому открыто', boxU));
      return function () {
        var u = $('e-url').value.trim();
        if (u && !/^https?:\/\/\S+$/i.test(u)) throw new Error('Ссылка на запись должна начинаться с https://');
        [notes.file(), hw.file()].forEach(function (f) { if (f && !/\.pdf$/i.test(f.name)) throw new Error('Конспект и ДЗ — файлы .pdf.'); });
        var fd = new FormData();
        fd.append('number', $('e-number').value.trim());
        fd.append('title', $('e-title').value.trim());
        fd.append('url', u);
        fd.append('section', $('e-section').value);
        var ddv = $('e-deadline').value.trim();
        if (ddv && !(+ddv >= 1 && +ddv <= 60)) throw new Error('Срок на ДЗ — от 1 до 60 дней.');
        fd.append('deadline_days', ddv);
        fd.append('viz_ids', JSON.stringify(getV()));
        fd.append('user_ids', JSON.stringify(getU()));
        if (notes.file()) fd.append('notes', notes.file()); else if (notes.remove()) fd.append('remove_notes', 'true');
        if (hw.file()) fd.append('hw', hw.file()); else if (hw.remove()) fd.append('remove_hw', 'true');
        return (l ? api('PATCH', '/api/admin/lessons/' + l.pk, fd) : api('POST', '/api/admin/lessons', fd))
          .then(function (r) { toast((l ? 'Сохранено: занятие № ' : 'Добавлено: занятие № ') + r.number); });
      };
    });
  }

  /* ── Пробники ── */
  function renderMocks() {
    var list = $('mocks-list'); list.textContent = '';
    $('mocks-summary').textContent = data.mocks.length + ' ' + plural(data.mocks.length, 'пробник', 'пробника', 'пробников');
    if (!data.mocks.length) { list.appendChild(el('li', 'empty-list', 'Пока пусто. Нажми «Добавить пробник» и загрузи HTML или PDF варианта.')); return; }
    data.mocks.forEach(function (m) {
      var li = el('li', 'adm-row adm-row--plain');
      var num = el('span', 'numbadge'); num.appendChild(el('span', null, 'Пробник')); num.appendChild(el('b', null, String(m.number)));
      var text = el('div', 'adm-row__text');
      text.appendChild(el('h2', 'adm-row__title', m.title || 'Пробник № ' + m.number));
      text.appendChild(el('span', 'adm-row__meta',
        (m.tasks && m.tasks.length ? 'автопроверка: ' + m.tasks.length + ' ' + plural(m.tasks.length, 'задание', 'задания', 'заданий') + ', ' + m.key_points + ' б.' : 'без автопроверки') +
        (m.deadline_days && m.deadline_days !== 7 ? '  ·  срок ' + m.deadline_days + ' ' + plural(m.deadline_days, 'день', 'дня', 'дней') : '') +
        '  ·  ' + whoLine(m.user_ids)));
      var actions = el('div', 'row-actions');
      var open = el('a', 'btn btn--small', 'Открыть'); open.href = m.url; open.target = '_blank'; open.rel = 'noopener';
      var edit = el('button', 'btn btn--small', 'Изменить'); edit.type = 'button';
      edit.addEventListener('click', function () { editMock(m); });
      var del = el('button', 'btn btn--small btn--danger', 'Удалить'); del.type = 'button';
      del.addEventListener('click', function () {
        armDelete(del, function () { return api('DELETE', '/api/admin/mocks/' + m.pk).then(function () { toast('Пробник № ' + m.number + ' удалён'); return loadAll(); }); });
      });
      actions.appendChild(open); actions.appendChild(edit); actions.appendChild(del);
      li.appendChild(num); li.appendChild(text); li.appendChild(actions);
      list.appendChild(li);
    });
  }

  function editMock(m) {
    openEditor2(m ? 'Пробник № ' + m.number : 'Новый пробник', function (body) {
      var num = numberInput('e-number', m ? m.number : nextNumber(data.mocks));
      if (!m) num.dataset.fresh = '1';
      body.appendChild(field('Номер *', num));
      body.appendChild(field('Название', textInput('e-title', m ? m.title : '', 'Например: Вариант в формате ЕГЭ 2027')));
      var ACCEPT = '.html,.htm,text/html,application/pdf,.pdf';
      var pdf = pdfField('e-mock', m && m.url, 'Перетащи HTML (или PDF) варианта или нажми, чтобы выбрать', ACCEPT);
      body.appendChild(field(m ? 'Вариант (HTML или PDF)' : 'Вариант (HTML или PDF) *', pdf.box));
      var key = el('textarea', 'input input--key'); key.id = 'e-key'; key.rows = 8; key.spellcheck = false;
      key.value = m ? (m.key_text || '') : '';
      key.placeholder = '1: 2,5\n2: -3 | -3,0\n5: 24 (2, любой порядок)\n7: 31 (2)';
      body.appendChild(field('Ключ первой части (автопроверка)', key));
      body.appendChild(el('p', 'hint', 'По строке на задание: «номер: ответ». Несколько допустимых ответов — через «|». В скобках: 2 — задание на 2 балла (одна ошибка — 1 балл), «любой порядок» — цифры можно писать в любом порядке. Если ключ вписан в HTML пробника (<script id="answer-key">), он подставится сам при загрузке. Пусто — без автопроверки. Если ученики уже сдали ответы, после изменения ключа их баллы пересчитаются.'));
      var md = numberInput('e-deadline', m ? m.deadline_days : 7); md.maxLength = 2;
      body.appendChild(field('Срок, дней (считается с момента, когда ученик нажал «Начать»)', md));
      var boxU = el('div', 'picker');
      var getU = picker(boxU, userItems(), m ? m.user_ids : [], 'Учеников пока нет: они появятся после регистрации в личном кабинете.');
      body.appendChild(field('Кому открыт', boxU));
      return function () {
        if (!m && !pdf.file()) throw new Error('Выбери файл варианта (HTML или PDF).');
        if (m && pdf.remove()) throw new Error('Вариант нельзя убрать — можно заменить другим PDF или удалить пробник.');
        [pdf.file()].forEach(function (f) { if (f && !/\.(pdf|html?)$/i.test(f.name)) throw new Error('Нужен файл .html или .pdf.'); });
        var fd = new FormData();
        fd.append('number', $('e-number').value.trim());
        fd.append('title', $('e-title').value.trim());
        fd.append('user_ids', JSON.stringify(getU()));
        var mdv = $('e-deadline').value.trim();
        if (mdv && !(+mdv >= 1 && +mdv <= 60)) throw new Error('Срок — от 1 до 60 дней.');
        fd.append('deadline_days', mdv);
        if (pdf.file()) fd.append('pdf', pdf.file());
        var keyText = $('e-key').value.trim();
        if (keyText) fd.append('answer_key', keyText);
        else if (m && m.key_text) fd.append('clear_key', 'true');
        return (m ? api('PATCH', '/api/admin/mocks/' + m.pk, fd) : api('POST', '/api/admin/mocks', fd))
          .then(function (r) {
            toast((m ? 'Сохранено: пробник № ' : 'Добавлено: пробник № ') + r.number +
              (r.tasks.length ? ' · автопроверка: ' + r.tasks.length + ' ' + plural(r.tasks.length, 'задание', 'задания', 'заданий') : ''));
          });
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
      var st = u.stats || {};
      var head = el('div', 'urow__head');
      head.appendChild(el('h2', 'adm-row__title', u.nickname));
      if (u.role === 'curator') head.appendChild(el('span', 'urow__role', 'куратор' + (u.tg_chat_id ? '' : ' · без Telegram')));
      else if (u.tg_chat_id) head.appendChild(el('span', 'urow__role urow__role--tg', 'Telegram'));
      var seen = el('span', 'urow__seen' + (st.last_seen_at && Date.now() - new Date(st.last_seen_at) < 864e5 ? ' is-fresh' : ''), ago(st.last_seen_at));
      seen.title = st.last_seen_at ? 'Последняя активность: ' + dateTime(st.last_seen_at) : '';
      head.appendChild(seen);
      text.appendChild(head);
      var facts = el('div', 'urow__facts');
      facts.appendChild(el('span', null, 'сеансов за 30 дней: ' + (st.visits_30d || 0)));
      var dev = el('span', st.devices_30d >= 3 ? 'urow__warn' : null, 'устройств: ' + (st.devices_30d || 0));
      if (st.devices_30d >= 3) dev.title = 'Заходили с трёх и более устройств за месяц — возможно, аккаунтом пользуются несколько человек';
      facts.appendChild(dev);
      var drafts = (u.reports || []).filter(function (r) { return r.status === 'draft'; }).length;
      facts.appendChild(el('span', null, 'отчётов: ' + (u.reports || []).length));
      if (drafts) facts.appendChild(el('span', 'urow__warn', 'черновик отчёта ждёт проверки'));
      if (st.lessons_active) facts.appendChild(el('span', null, 'ДЗ в работе: ' + st.lessons_active));
      if (st.mocks_active) facts.appendChild(el('span', null, 'пробников в работе: ' + st.mocks_active));
      if (st.next_due) {
        var soon = new Date(st.next_due.due_at) - Date.now() < 864e5;
        var nd = el('span', soon ? 'urow__warn' : null, 'ближайший срок: ' + st.next_due.label + ' — ' + timeLeft(st.next_due.due_at));
        nd.title = 'Сдать до ' + dateTime(st.next_due.due_at);
        facts.appendChild(nd);
      }
      var over = (st.lessons_overdue || 0) + (st.mocks_overdue || 0);
      if (over) {
        var ov = el('span', 'urow__warn', 'просрочек: ' + over);
        ov.title = 'ДЗ: ' + (st.lessons_overdue || 0) + ', пробники: ' + (st.mocks_overdue || 0);
        facts.appendChild(ov);
      }
      text.appendChild(facts);
      var meters = el('div', 'urow__meters');
      meters.appendChild(meter('ДЗ сданы', st.lessons_done || 0, st.lessons_total || 0));
      meters.appendChild(meter('Пробники сданы', st.mocks_done || 0, st.mocks_total || 0));
      text.appendChild(meters);
      var actions = el('div', 'row-actions');
      var more = el('button', 'btn btn--small', 'Подробнее'); more.type = 'button';
      more.addEventListener('click', function () { showActivity(u); });
      actions.appendChild(more);
      var acc = el('button', 'btn btn--small btn--solid', 'Доступ'); acc.type = 'button';
      acc.addEventListener('click', function () { editUserAccess(u); });
      var rep = el('button', 'btn btn--small', 'Отчёты'); rep.type = 'button';
      rep.addEventListener('click', function () { editUserReports(u); });
      var cur = el('button', 'btn btn--small', 'Telegram'); cur.type = 'button';
      cur.addEventListener('click', function () { editUserRole(u); });
      var pw = el('button', 'btn btn--small', 'Пароль'); pw.type = 'button';
      pw.addEventListener('click', function () { editUserPassword(u); });
      var del = el('button', 'btn btn--small btn--danger', 'Удалить'); del.type = 'button';
      del.addEventListener('click', function () {
        armDelete(del, function () { return api('DELETE', '/api/admin/users/' + u.id).then(function () { toast('Ученик ' + u.nickname + ' удалён'); return loadAll(); }); });
      });
      actions.appendChild(acc); actions.appendChild(rep); actions.appendChild(cur); actions.appendChild(pw); actions.appendChild(del);
      li.appendChild(av); li.appendChild(text); li.appendChild(actions);
      list.appendChild(li);
    });
  }
  $('users-search').addEventListener('input', renderUsers);

  /* ── Подробно об ученике: только просмотр ── */
  var KIND = { video: 'Запись', notes: 'Конспект', hw: 'ДЗ', viz: 'Визуализация', mock: 'Пробник', report: 'Отчёт' };
  function viewLabel(w) {
    if (w.kind === 'viz' || w.kind === 'report') return KIND[w.kind] + ' · ' + (w.title || w.ref);
    if (w.kind === 'mock') return 'Пробник № ' + w.ref + (w.title ? ' · ' + w.title : '');
    return KIND[w.kind] + ' · занятие № ' + w.ref + (w.title ? ' · ' + w.title : '');
  }
  function showActivity(u) {
    openEditor2(u.nickname, function (body) {
      body.appendChild(el('p', 'hint', 'Загружаю…'));
      api('GET', '/api/admin/users/' + u.id + '/activity').then(function (a) {
        body.textContent = '';
        var s = a.summary;
        var tiles = el('div', 'tiles');
        function tile(label, value, sub, warn) {
          var t = el('div', 'tile' + (warn ? ' tile--warn' : ''));
          t.appendChild(el('span', 'tile__label', label));
          t.appendChild(el('b', 'tile__value', value));
          if (sub) t.appendChild(el('span', 'tile__sub', sub));
          tiles.appendChild(t);
        }
        var lastV = a.visits[0];
        tile('Последний заход', lastV ? ago(lastV.last_seen_at) : 'не заходил', lastV ? dateTime(lastV.last_seen_at) : '');
        tile('Сеансов за 30 дней', String(s.visits_30d), s.visits_30d ? 'в сумме ≈ ' + duration(s.minutes_30d) : '');
        tile('Открыл материалов', String(s.views_30d), 'за 30 дней');
        tile('Устройства', String(s.devices_30d.length), s.devices_30d.join(', ') || '—', s.devices_30d.length >= 3);
        body.appendChild(tiles);
        if (s.devices_30d.length >= 3) body.appendChild(el('p', 'act-warn', 'За месяц заходили с ' + s.devices_30d.length + ' разных устройств. Это бывает у одного ученика (телефон, ноутбук, школьный компьютер), но может значить, что аккаунтом пользуются несколько человек.'));

        /* Дедлайны ученика — то же, что он видит в панели «Дедлайны» */
        var dls = a.deadlines || [];
        var dlBox = el('ul', 'plist dlist');
        if (!dls.length) dlBox.appendChild(el('li', 'picker__empty', 'Сейчас ничего не начато и не просрочено.'));
        dls.forEach(function (x) {
          var active = x.state === 'active', soon = active && new Date(x.due_at) - Date.now() < 864e5;
          var li = el('li', 'prow dlrow prow--' + (active ? 'active' : 'todo') + (soon ? ' is-soon' : ''));
          li.appendChild(el('span', 'prow__dot'));
          var t = el('span', 'prow__text');
          t.appendChild(el('b', null, x.label + (x.title ? ' · ' + x.title : '')));
          if (active) {
            t.appendChild(el('span', 'dlrow__left', 'осталось ' + timeLeft(x.due_at)));
            t.appendChild(el('span', null, 'начал ' + dateTime(x.started_at) + '  ·  сдать до ' + dateTime(x.due_at) + '  ·  срок ' + x.days + ' ' + plural(x.days, 'день', 'дня', 'дней')));
            var bar = el('span', 'dlrow__bar'), fill = el('i');
            fill.style.width = Math.max(3, Math.min(100, 100 * (Date.now() - new Date(x.started_at)) / (new Date(x.due_at) - new Date(x.started_at)))) + '%';
            bar.appendChild(fill); t.appendChild(bar);
          } else {
            t.appendChild(el('span', 'dlrow__left dlrow__left--late', 'срок истёк ' + dateTime(x.last_overdue_at)));
            t.appendChild(el('span', null, 'ждёт, пока ученик возьмёт новый срок (' + x.days + ' ' + plural(x.days, 'день', 'дня', 'дней') + ')'));
          }
          if (x.overdue) t.appendChild(el('span', 'prow__res urow__warn', 'Просрочено ' + x.overdue + ' ' + plural(x.overdue, 'раз', 'раза', 'раз')));
          li.appendChild(t);
          dlBox.appendChild(li);
        });
        var nActive = dls.filter(function (x) { return x.state === 'active'; }).length, nLate = dls.length - nActive;
        body.appendChild(field('Дедлайны: в работе ' + nActive + (nLate ? ', срок истёк ' + nLate : ''), dlBox));

        function progressList(items, kind) {
          var mock = kind === 'mock', what = mock ? 'Пробник' : 'ДЗ';
          var ul = el('ul', 'plist');
          if (!items.length) ul.appendChild(el('li', 'picker__empty', mock ? 'Пробники не открыты.' : 'Занятия не открыты.'));
          items.forEach(function (it) {
            var dl = it.deadline || { state: it.done ? 'done' : 'todo', overdue: 0, days: mock ? 7 : 3 };
            var li = el('li', 'prow prow--' + dl.state);
            li.appendChild(el('span', 'prow__dot'));
            var t = el('span', 'prow__text');
            t.appendChild(el('b', null, (mock ? 'Пробник № ' : 'Занятие № ') + it.number + (it.title ? ' · ' + it.title : '')));
            var stText = dl.state === 'done' ? what + ' ' + (mock ? 'сдан ' : 'сдано ') + dateTime(dl.submitted_at || it.marked_at)
              : dl.state === 'active' ? what + ' в работе, срок до ' + dateTime(dl.due_at)
              : what + (mock ? ' не начат' : ' не начато');
            t.appendChild(el('span', null, stText + '  ·  ' + (it.opened_at ? 'открывал ' + dateTime(it.opened_at) : 'не открывал')));
            if (dl.overdue || dl.first_started_at) {
              var info = el('span', 'prow__res');
              if (dl.overdue) info.appendChild(el('b', 'urow__warn', 'Просрочено ' + dl.overdue + ' ' + plural(dl.overdue, 'раз', 'раза', 'раз')));
              if (dl.first_started_at) info.appendChild(document.createTextNode((dl.overdue ? '  ·  ' : '') + 'впервые начал ' + dateTime(dl.first_started_at) + '  ·  срок ' + dl.days + ' ' + plural(dl.days, 'день', 'дня', 'дней')));
              t.appendChild(info);
            }
            if (it.submission) {
              var sb = it.submission, sres = el('span', 'prow__res');
              var link = el('a', null, sb.files.length + ' ' + plural(sb.files.length, 'файл', 'файла', 'файлов'));
              link.href = '/check/#s' + sb.id; link.target = '_blank'; link.rel = 'noopener';
              if (sb.status === 'checked') sres.appendChild(el('b', null, mock
                ? '2 часть: ' + sb.score + ' из ' + sb.max + ' первичных' + (it.total ? ' · итого ' + it.total.primary + ' из ' + it.total.max + (it.total.test != null ? ' → ' + it.total.test + ' тестовых' : '') : '') + '  ·  '
                : 'Проверено: ' + sb.score + ' из ' + sb.max + ' (' + Math.round(100 * sb.score / sb.max) + '%)  ·  '));
              else sres.appendChild(el('b', null, 'Ждёт проверки  ·  '));
              sres.appendChild(link);
              t.appendChild(sres);
            }
            if (mock && it.result) {
              var r = it.result;
              var res = el('span', 'prow__res');
              res.appendChild(el('b', null, 'Первая часть: ' + r.score + ' из ' + r.max));
              res.appendChild(document.createTextNode(r.wrong.length ? '  ·  ошибки в заданиях ' + r.wrong.join(', ') : '  ·  без ошибок'));
              res.appendChild(document.createTextNode('  ·  ответы ' + dateTime(r.submitted_at)));
              t.appendChild(res);
            } else if (mock && it.has_key) {
              t.appendChild(el('span', 'prow__res', 'Ответы на первую часть ещё не отправлены'));
            }
            li.appendChild(t);
            var btns = el('span', 'prow__btns');
            function resetBtn(label, title, url, msg) {
              var b = el('button', 'btn btn--small btn--danger prow__reset', label); b.type = 'button'; b.title = title;
              b.addEventListener('click', function () {
                armDelete(b, function () { return api('DELETE', url).then(function () { toast(msg); showActivity(u); }); }, 'Точно сбросить?');
              });
              btns.appendChild(b);
            }
            if (mock && it.result) {
              resetBtn('Сбросить ответы', 'Ответы стираются, пробник снова «Не начат», вариант остаётся открытым — ученик берёт новый срок и сдаёт заново',
                '/api/admin/mocks/' + it.pk + '/attempts/' + u.id, 'Ответы сброшены: ' + u.nickname + ' может сдать пробник № ' + it.number + ' заново');
            }
            if (dl.state !== 'todo' || dl.overdue || dl.first_started_at) {
              resetBtn('Сбросить срок', 'Снова «Не начато», материалы закрыты до «Начать», просрочек нет' + (mock ? ', ответы стираются' : ''),
                '/api/admin/users/' + u.id + '/' + (mock ? 'mocks/' : 'lessons/') + it.pk + '/deadline',
                'Срок сброшен: ' + (mock ? 'пробник № ' : 'занятие № ') + it.number + ' у ' + u.nickname + ' снова «Не начато»');
            }
            if (btns.children.length) li.appendChild(btns);
            ul.appendChild(li);
          });
          return ul;
        }
        var ld = a.lessons.filter(function (x) { return x.done; }).length, md = a.mocks.filter(function (x) { return x.done; }).length;
        body.appendChild(field('Занятия: ДЗ сдано ' + ld + ' из ' + a.lessons.length, progressList(a.lessons, 'lesson')));
        body.appendChild(field('Пробники: сдано ' + md + ' из ' + a.mocks.length, progressList(a.mocks, 'mock')));

        var sess = el('ul', 'slist');
        if (!a.visits.length) sess.appendChild(el('li', 'picker__empty', 'Сеансов пока нет.'));
        a.visits.slice(0, 30).forEach(function (v) {
          var li = el('li', 'srow');
          li.appendChild(el('b', null, dateTime(v.started_at) + '–' + timeOnly(v.last_seen_at)));
          li.appendChild(el('span', null, '≈ ' + duration(v.minutes)));
          li.appendChild(el('span', null, v.device));
          li.appendChild(el('span', null, v.opened ? 'открыл ' + v.opened : 'только кабинет'));
          sess.appendChild(li);
        });
        body.appendChild(field('Сеансы (последние)', sess));

        var vl = el('ul', 'slist');
        if (!a.views.length) vl.appendChild(el('li', 'picker__empty', 'Пока ничего не открывал.'));
        a.views.slice(0, 40).forEach(function (w) {
          var li = el('li', 'srow srow--view');
          li.appendChild(el('b', null, viewLabel(w)));
          li.appendChild(el('span', null, dateTime(w.at)));
          vl.appendChild(li);
        });
        body.appendChild(field('Что открывал', vl));
        body.appendChild(el('p', 'hint', 'Сеанс — заходы без перерыва дольше 30 минут; длительность приблизительная. Записи на Телебоссе учитываются как открытые, но сколько из них досмотрено, сайт не знает. Дата регистрации: ' + date(a.user.created_at)));
      }).catch(function (e) { body.textContent = ''; body.appendChild(el('p', 'form-error', e.message)); });
      return null;  /* только просмотр: без кнопки «Сохранить» */
    });
  }

  function editUserAccess(u) {
    if (u.role === 'curator') {
      openEditor2('Доступ: ' + u.nickname, function (body) {
        body.appendChild(el('p', 'hint', 'Куратору открыто всё сразу: все занятия с материалами, визуализации и пробники — без «Начать», без сроков и без сдачи. Отдельно открывать ничего не нужно.'));
        return null;
      });
      return;
    }
    openEditor2('Доступ: ' + u.nickname, function (body) {
      body.appendChild(el('p', 'hint', 'Отметь занятия, которые открыть ученику: вместе с ними откроется всё, что лежит в их папках, включая закрытые визуализации (после того как ученик нажмёт «Начать»). Ниже — визуализации, которые можно открыть отдельно, без занятия: то, что уже лежит в отмеченных занятиях, из этого списка пропадает.'));
      var boxL = el('div', 'picker'), boxV = el('div', 'picker'), boxM = el('div', 'picker');
      var lessonViz = {};
      data.lessons.forEach(function (l) { lessonViz[l.pk] = l.viz_ids || []; });
      var getV = null;
      function cover() {
        if (!getV) return;
        var ids = [];
        getL().forEach(function (pk) { ids = ids.concat(lessonViz[pk] || []); });
        getV.cover(ids);
      }
      var getM = picker(boxM, data.mocks.map(function (m) { return { id: m.pk, label: 'Пробник № ' + m.number, sub: m.title }; }), u.grants.mock, 'Пробников пока нет.');
      var getL = picker(boxL, data.lessons.map(function (l) { return { id: l.pk, label: 'Занятие № ' + l.number, sub: [l.title, lessonContents(l)].filter(Boolean).join(' · ') }; }), u.grants.lesson, 'Занятий пока нет.', { onChange: cover });
      /* сначала закрытые (их и нужно открывать), потом открытые всем — отметка пригодится, если визуализацию позже закроют */
      var vizItems = data.viz.slice().sort(function (a, b) {
        return (a.access === 'private' ? 0 : 1) - (b.access === 'private' ? 0 : 1) || a.position - b.position;
      }).map(function (v) {
        return { id: v.pk, label: v.title, sub: (v.access === 'private' ? 'закрытая' : 'открыта всем') + (v.parts ? ' · ' + v.parts : '') };
      });
      getV = picker(boxV, vizItems, u.grants.viz, 'Визуализаций пока нет.', {
        coverText: function (n) { return 'Ещё ' + n + ' ' + plural(n, 'визуализация открыта', 'визуализации открыты', 'визуализаций открыто') + ' через отмеченные занятия — в списке их нет.'; }
      });
      cover();
      body.appendChild(field('Занятия', boxL));
      body.appendChild(field('Пробники', boxM));
      body.appendChild(field('Отдельные визуализации', boxV));
      return function () {
        return api('PUT', '/api/admin/users/' + u.id + '/grants', { lesson: getL(), mock: getM(), viz: getV() })
          .then(function () { toast('Доступ сохранён: ' + u.nickname); });
      };
    });
  }

  /* Отчёты для родителей. Из Google-таблицы сайт сам собирает черновик раз в месяц (решение владельца):
     открыть, дописать комментарий, опубликовать — ученик увидит его в кабинете. Можно и загрузить готовый PDF. */
  function monthTitle() {
    var d = new Date(); d.setDate(1); d.setMonth(d.getMonth() - (new Date().getDate() < 15 ? 1 : 0));
    var t = d.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' }).replace(' г.', '');
    return t.charAt(0).toUpperCase() + t.slice(1);
  }
  function ymd(d) { return d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2); }
  function prevMonth() {
    var now = new Date(), first = new Date(now.getFullYear(), now.getMonth() - 1, 1), last = new Date(now.getFullYear(), now.getMonth(), 0);
    return [ymd(first), ymd(last)];
  }
  function reloadUsers() {
    return api('GET', '/api/admin/users').then(function (d) { data.users = d.users; renderUsers(); return d.users; });
  }
  function reportRow(u, r, redraw) {
    var li = el('li', 'rep' + (r.kind === 'auto' ? ' rep--auto' : ''));
    var top = el('div', 'rep__top');
    var a = el('a', 'rep__title', r.title); a.href = r.url; a.target = '_blank'; a.rel = 'noopener';
    top.appendChild(a);
    top.appendChild(el('span', 'rep__badge' + (r.status === 'draft' ? ' rep__badge--draft' : ''), r.status === 'draft' ? 'черновик' : 'опубликован'));
    top.appendChild(el('span', 'rep__date', r.kind === 'auto' ? 'из таблицы · ' + date(r.collected_at) : 'PDF · ' + date(r.created_at)));
    li.appendChild(top);
    var acts = el('div', 'rep__acts');
    function busy(btn, p, done) {
      btn.disabled = true;
      return p.then(function (x) { if (done) done(x); }).catch(function (e) { toast(e.message, true); }).then(function () { btn.disabled = false; });
    }
    if (r.kind === 'auto') {
      li.appendChild(el('p', 'rep__meta', 'Вкладка «' + (r.tab || '?') + '» · занятий: ' + r.lessons + ' · пробников: ' + r.mocks +
        (r.notify_error ? ' · ' + r.notify_error : '')));
      var ta = el('textarea', 'input rep__comment'); ta.rows = 4; ta.maxLength = 5000; ta.value = r.comment || '';
      ta.placeholder = 'Комментарий преподавателя: как прошёл месяц, что получается, над чем работаем дальше. Пустая строка — новый абзац.';
      ta.setAttribute('aria-label', 'Комментарий преподавателя');
      li.appendChild(ta);
      var save = el('button', 'btn btn--small', 'Сохранить комментарий'); save.type = 'button';
      save.addEventListener('click', function () {
        busy(save, api('PUT', '/api/admin/reports/' + r.pk, { comment: ta.value }), function (x) { r.comment = x.comment; toast('Комментарий сохранён'); });
      });
      var ref = el('button', 'btn btn--small', 'Обновить из таблицы'); ref.type = 'button';
      ref.title = 'Заново взять цифры из таблицы, если там что-то поправили. Комментарий останется.';
      ref.addEventListener('click', function () {
        busy(ref, api('POST', '/api/admin/reports/' + r.pk + '/refresh'), function (x) { Object.assign(r, x); toast('Цифры обновлены'); redraw(); });
      });
      var pub = el('button', 'btn btn--small ' + (r.status === 'draft' ? 'btn--solid' : ''), r.status === 'draft' ? 'Опубликовать' : 'Снять с публикации'); pub.type = 'button';
      pub.addEventListener('click', function () {
        var go = r.status === 'draft'
          ? api('PUT', '/api/admin/reports/' + r.pk, { comment: ta.value }).then(function () { return api('POST', '/api/admin/reports/' + r.pk + '/publish'); })
          : api('POST', '/api/admin/reports/' + r.pk + '/unpublish');
        busy(pub, go, function (x) {
          Object.assign(r, x);
          toast(x.status === 'published' ? 'Опубликован: ученик видит отчёт в кабинете' : 'Снят с публикации');
          redraw(); reloadUsers(); loadAuto();
        });
      });
      acts.appendChild(save); acts.appendChild(ref); acts.appendChild(pub);
    }
    var del = el('button', 'btn btn--small btn--danger', 'Удалить'); del.type = 'button';
    del.addEventListener('click', function () {
      armDelete(del, function () {
        return api('DELETE', '/api/admin/reports/' + r.pk).then(function () {
          toast('Отчёт удалён: ' + r.title);
          u.reports = (u.reports || []).filter(function (x) { return x.pk !== r.pk; });
          redraw(); reloadUsers(); loadAuto();
        });
      });
    });
    acts.appendChild(del);
    li.appendChild(acts);
    return li;
  }
  function editUserReports(u) {
    openEditor2('Отчёты: ' + u.nickname, function (body) {
      body.appendChild(el('p', 'hint', 'Отчёт видит только этот ученик (и родители — через его аккаунт) на вкладке «Отчёты», после публикации. Черновики сайт собирает сам из таблицы 1-го числа за прошлый месяц: откройте, допишите комментарий и опубликуйте — бот пришлёт ученику ссылку.'));
      var list = el('ul', 'rep-list');
      function redraw() {
        list.textContent = '';
        (u.reports || []).forEach(function (r) { list.appendChild(reportRow(u, r, redraw)); });
        if (!(u.reports || []).length) list.appendChild(el('li', 'picker__empty', 'Отчётов пока нет.'));
      }
      redraw();
      body.appendChild(field('Отчёты', list));

      var pm = prevMonth();
      var box = el('div', 'rep-make');
      var f1 = el('input', 'input'); f1.type = 'date'; f1.id = 'e-from'; f1.value = pm[0]; f1.setAttribute('aria-label', 'Начало периода');
      var f2 = el('input', 'input'); f2.type = 'date'; f2.id = 'e-to'; f2.value = pm[1]; f2.setAttribute('aria-label', 'Конец периода');
      var mk = el('button', 'btn btn--small btn--solid', 'Собрать черновик'); mk.type = 'button';
      box.appendChild(f1); box.appendChild(el('span', null, '—')); box.appendChild(f2); box.appendChild(mk);
      body.appendChild(field('Собрать из Google-таблицы за период', box));
      mk.addEventListener('click', function () {
        mk.disabled = true; mk.textContent = 'Собираю…';
        api('POST', '/api/admin/users/' + u.id + '/reports/auto', { period_from: f1.value, period_to: f2.value })
          .then(function (r) { u.reports = [r].concat(u.reports || []); redraw(); reloadUsers(); toast('Черновик готов: ' + r.title); })
          .catch(function (e) { toast(e.message, true); })
          .then(function () { mk.disabled = false; mk.textContent = 'Собрать черновик'; });
      });

      body.appendChild(field('Или загрузить готовый PDF — период *', textInput('e-title', monthTitle(), 'Например: Октябрь 2026')));
      var pdf = pdfField('e-report', null, 'Перетащи PDF отчёта или нажми, чтобы выбрать');
      body.appendChild(field('PDF отчёта (публикуется сразу)', pdf.box));
      return function () {
        var f = pdf.file();
        if (!f) { closeEditor2(); return Promise.resolve(); }
        if (!/\.pdf$/i.test(f.name)) throw new Error('Нужен файл .pdf.');
        if (!$('e-title').value.trim()) throw new Error('Укажи период, например «Октябрь 2026».');
        var fd = new FormData(); fd.append('title', $('e-title').value.trim()); fd.append('pdf', f);
        return api('POST', '/api/admin/users/' + u.id + '/reports', fd).then(function (r) { toast('Отчёт загружен: ' + r.title); });
      };
    });
  }

  /* Черновики отчётов за прошлый месяц: сайт собирает их сам при первом открытии админки после 1-го числа */
  var autoTimer = null;
  function loadAuto() {
    var bar = $('reports-auto');
    clearTimeout(autoTimer);
    api('GET', '/api/admin/reports/auto').then(function (s) {
      bar.textContent = '';
      if (!s.enabled) { bar.hidden = true; return; }
      bar.hidden = false;
      if (s.running) {
        bar.appendChild(el('p', null, 'Собираю из таблицы черновики отчётов за ' + s.label + '…'));
        autoTimer = setTimeout(function () { reloadUsers().then(loadAuto); }, 5000);
        return;
      }
      if (s.drafts.length) {
        bar.appendChild(el('p', null, 'Черновики отчётов за ' + s.label + ' ждут проверки — откройте, допишите комментарий и опубликуйте:'));
        var names = el('div', 'auto-bar__names');
        s.drafts.forEach(function (d) {
          var b = el('button', 'btn btn--small', d.nickname); b.type = 'button';
          b.addEventListener('click', function () {
            var u = data.users.filter(function (x) { return x.id === d.user_id; })[0];
            if (u) editUserReports(u);
          });
          names.appendChild(b);
        });
        bar.appendChild(names);
      } else if (!s.linked) {
        bar.appendChild(el('p', null, 'Отчёты за ' + s.label + ': пока не из чего собирать — ни один ученик не привязан к таблице. Впишите ученикам chat id (кнопка «Telegram») и проверьте привязку кнопкой «Таблица».'));
      } else if (s.made.length) {
        bar.appendChild(el('p', null, 'Отчёты за ' + s.label + ': все черновики проверены и опубликованы.'));
      } else {
        bar.appendChild(el('p', null, 'Отчёты за ' + s.label + ': черновиков нет — у привязанных учеников' + (s.skipped.length ? ' (' + s.skipped.join(', ') + ')' : '') + ' в таблице нет занятий за этот месяц.'));
      }
      if (s.errors.length) {
        var er = el('p', 'auto-bar__err', 'Не собрались: ' + s.errors.join('; '));
        bar.appendChild(er);
      }
      var again = el('button', 'btn btn--small', 'Собрать недостающие'); again.type = 'button';
      again.title = 'Собрать черновики за ' + s.label + ' тем, у кого их ещё нет: например, после того как ученика привязали к таблице';
      again.addEventListener('click', function () {
        again.disabled = true;
        api('POST', '/api/admin/reports/auto/run').then(loadAuto).catch(function (e) { toast(e.message, true); again.disabled = false; });
      });
      bar.appendChild(again);
    }).catch(function () { bar.hidden = true; });
  }

  /* Связь с Google-таблицей: какие вкладки учеников видит сайт и кто к какой привязан */
  function showSheet() {
    openEditor2('Google-таблица', function (body) {
      body.appendChild(el('p', 'hint', 'Проверяю связь…'));
      api('GET', '/api/admin/sheet').then(function (s) {
        body.textContent = '';
        if (!s.enabled) {
          body.appendChild(el('p', 'hint', 'Таблица не подключена. Как подключить: tools/sheets/README.md — вставить скрипт в Apps Script, развернуть как веб-приложение, затем остановить сайт и выполнить «python run.py set-sheet».'));
          return;
        }
        if (!s.ok) { body.appendChild(el('p', 'form-error', s.error)); return; }
        body.appendChild(el('p', 'hint', 'Связь есть: «' + s.title + '». Сайт пишет туда сданные и проверенные ДЗ (по теме урока) и пробники (в столбец с номером пробника), а оттуда берёт цифры для отчётов. Ученик находится по chat id в первой строке его вкладки; если там его нет — укажите вкладку вручную (кнопка «Telegram» у ученика).'));
        var tl = el('ul', 'slist');
        s.tabs.slice().sort(function (a, b) {
          function w(t) { return t.users.length ? 0 : t.chat_ids.length ? 1 : 2; }
          return w(a) - w(b);
        }).forEach(function (t) {
          var li = el('li', 'srow');
          li.appendChild(el('b', null, t.name));
          li.appendChild(el('span', null, t.chat_ids.length ? 'chat id ' + t.chat_ids.join(', ') : 'chat id не указан'));
          li.appendChild(el('span', null, t.mock_tab ? 'пробники: ' + t.mock_tab : 'без вкладки пробников'));
          li.appendChild(el('span', t.users.length ? null : 'urow__warn', t.users.length ? 'на сайте: ' + t.users.join(', ') : 'на сайте никто не привязан'));
          tl.appendChild(li);
        });
        body.appendChild(field('Вкладки учеников', tl));
        var lost = s.users.filter(function (x) { return !x.tab; });
        if (lost.length) {
          var ul = el('ul', 'slist');
          lost.forEach(function (x) {
            var li = el('li', 'srow');
            li.appendChild(el('b', null, x.nickname));
            li.appendChild(el('span', 'urow__warn', x.manual ? 'указанной вкладки нет в таблице' : x.chat ? 'chat id нет ни на одной вкладке' : 'нет chat id'));
            ul.appendChild(li);
          });
          body.appendChild(field('Ученики сайта без вкладки', ul));
        }
      }).catch(function (e) { body.textContent = ''; body.appendChild(el('p', 'form-error', e.message)); });
      return null;
    });
  }
  $('users-sheet').addEventListener('click', showSheet);

  /* Куратор: проверяет сданные ДЗ на /check/, бот присылает ему новые работы */
  function editUserRole(u) {
    openEditor2('Telegram и роль: ' + u.nickname, function (body) {
      body.appendChild(el('p', 'hint', 'Chat id ученика — бот присылает ему результаты проверки ДЗ и пробников одновременно с сайтом. Если отметить «Куратор», человек проверяет работы на странице «Проверка работ», а бот присылает ему новые сданные работы.'));
      var lab = el('label', 'check-row');
      var cb = el('input'); cb.type = 'checkbox'; cb.id = 'e-curator'; cb.checked = u.role === 'curator';
      lab.appendChild(cb); lab.appendChild(el('span', null, 'Куратор — проверяет домашние задания'));
      body.appendChild(lab);
      var chat = textInput('e-chat', u.tg_chat_id || '', 'например 123456789'); chat.inputMode = 'numeric'; chat.classList.add('mono');
      body.appendChild(field('Telegram chat id — ученику: результаты, куратору: новые работы', chat));
      var tab = textInput('e-tab', u.sheet_tab || '', 'пусто — найти по chat id');
      body.appendChild(field('Вкладка в Google-таблице (если chat id в ней не записан)', tab));
      var bot = el('p', 'hint', 'Проверяю бота…');
      body.appendChild(bot);
      api('GET', '/api/admin/telegram').then(function (t) {
        bot.textContent = t.enabled
          ? 'Бот подключён. Chat id человек узнаёт у @userinfobot (или он уже есть в вашем боте); он должен хотя бы раз нажать /start у @Arch_Tutor_Bot — иначе Telegram не даст боту ему написать. Ссылки в сообщениях ведут на ' + t.site_url + '.'
          : 'Бот ещё не подключён: остановите сайт и выполните «python run.py set-bot» — он попросит токен бота и адрес сайта. Пока работы ждут на странице проверки без уведомлений.';
      }).catch(function () { bot.textContent = ''; });
      var test = el('button', 'btn btn--small', 'Отправить пробное сообщение'); test.type = 'button';
      test.addEventListener('click', function () {
        test.disabled = true;
        api('PUT', '/api/admin/users/' + u.id + '/role', { curator: $('e-curator').checked, tg_chat_id: $('e-chat').value.trim(), sheet_tab: $('e-tab').value.trim() })
          .then(function () { return api('POST', '/api/admin/users/' + u.id + '/tg-test'); })
          .then(function () { toast('Сообщение отправлено — проверьте Telegram'); })
          .catch(function (e) { toast(e.message, true); })
          .then(function () { test.disabled = false; });
      });
      body.appendChild(test);
      return function () {
        var c = $('e-chat').value.trim();
        if (c && !/^-?\d{3,20}$/.test(c)) throw new Error('Chat id — это число, например 123456789.');
        return api('PUT', '/api/admin/users/' + u.id + '/role', { curator: $('e-curator').checked, tg_chat_id: c, sheet_tab: $('e-tab').value.trim() })
          .then(function (r) { toast(u.nickname + (r.role === 'curator' ? ' — куратор' : ' — ученик') + (r.tg_chat_id ? ', Telegram подключён' : ', без Telegram')); });
      };
    });
  }

  function timeLeft(iso) {
    var ms = new Date(iso).getTime() - Date.now();
    if (ms <= 0) return 'срок истёк';
    var min = Math.ceil(ms / 60000), d = Math.floor(min / 1440), h = Math.floor((min % 1440) / 60), m = min % 60;
    if (d) return d + ' ' + plural(d, 'день', 'дня', 'дней') + (h ? ' ' + h + ' ' + plural(h, 'час', 'часа', 'часов') : '');
    if (h) return h + ' ' + plural(h, 'час', 'часа', 'часов') + (m ? ' ' + m + ' мин' : '');
    return m + ' мин';
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
    /* окно только для просмотра — без «Сохранить», «Отмена» становится «Закрыть» */
    $('editor2-save').hidden = !submitFn;
    ed.querySelector('.editor__foot [data-close-editor2]').textContent = submitFn ? 'Отмена' : 'Закрыть';
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

  $('lesson-add').addEventListener('click', function () { editLesson(null); });
  $('mock-add').addEventListener('click', function () { editMock(null); });
  $('scale-edit').addEventListener('click', editScale);

  /* Шкала перевода первичных баллов ЕГЭ в тестовые: её утверждают каждый год, поэтому она редактируется */
  function editScale() {
    openEditor2('Задания и шкала перевода', function (body) {
      body.appendChild(el('p', 'hint', 'Загружаю…'));
      api('GET', '/api/admin/scale').then(function (sc) {
        body.textContent = '';
        body.appendChild(el('p', 'hint', 'Задания 21–26 — вторая часть: куратор ставит баллы по каждому, сумма считается сама. Темы видит ученик в разборе. Шкала переводит итог из 45 первичных в тестовые; её утверждают каждый год (обычно в апреле) — тогда впишите новые числа.'));
        var tasks = el('textarea', 'input input--key'); tasks.id = 'e-tasks'; tasks.rows = 10; tasks.spellcheck = false;
        tasks.value = sc.tasks.map(function (t) { return t.n + ': ' + t.max + ': ' + t.theme; }).join('\n');
        body.appendChild(field('Задания КИМ — «номер: максимум: тема»', tasks));
        body.appendChild(field('Год шкалы', textInput('e-year', sc.year, '2026')));
        var ta = el('textarea', 'input input--key'); ta.id = 'e-scale'; ta.rows = 10; ta.spellcheck = false;
        ta.value = sc.scale.map(function (t, i) { return i + ': ' + t; }).join('\n');
        body.appendChild(field('Шкала: первичные → тестовые, 46 строк (0–45)', ta));
      });
      return function () {
        var lines = $('e-scale').value.split(/\n+/).map(function (x) { return x.trim(); }).filter(Boolean);
        var scale = lines.map(function (x) {
          var m = /^(\d+)\s*[:=\-–—\s]\s*(\d+)$/.exec(x) || /^(\d+)$/.exec(x);
          if (!m) throw new Error('Шкала: не понял строку «' + x + '». Нужно «первичные: тестовые», например «28: 70».');
          return +(m[2] || m[1]);
        });
        return api('PUT', '/api/admin/scale', { scale: scale, year: $('e-year').value.trim(), tasks: $('e-tasks').value })
          .then(function () { toast('Задания и шкала сохранены'); });
      };
    });
  }


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
