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
      text.appendChild(el('span', 'adm-row__meta', (sec ? sec.label + '  ·  ' : 'без раздела  ·  ') + lessonContents(l) + '  ·  ' + whoLine(l.user_ids)));
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
      var seen = el('span', 'urow__seen' + (st.last_seen_at && Date.now() - new Date(st.last_seen_at) < 864e5 ? ' is-fresh' : ''), ago(st.last_seen_at));
      seen.title = st.last_seen_at ? 'Последняя активность: ' + dateTime(st.last_seen_at) : '';
      head.appendChild(seen);
      text.appendChild(head);
      var facts = el('div', 'urow__facts');
      facts.appendChild(el('span', null, 'сеансов за 30 дней: ' + (st.visits_30d || 0)));
      var dev = el('span', st.devices_30d >= 3 ? 'urow__warn' : null, 'устройств: ' + (st.devices_30d || 0));
      if (st.devices_30d >= 3) dev.title = 'Заходили с трёх и более устройств за месяц — возможно, аккаунтом пользуются несколько человек';
      facts.appendChild(dev);
      facts.appendChild(el('span', null, 'отчётов: ' + (u.reports || []).length));
      text.appendChild(facts);
      var meters = el('div', 'urow__meters');
      meters.appendChild(meter('Занятия просмотрены', st.lessons_done || 0, st.lessons_total || 0));
      meters.appendChild(meter('Пробники решены', st.mocks_done || 0, st.mocks_total || 0));
      text.appendChild(meters);
      var actions = el('div', 'row-actions');
      var more = el('button', 'btn btn--small', 'Подробнее'); more.type = 'button';
      more.addEventListener('click', function () { showActivity(u); });
      actions.appendChild(more);
      var acc = el('button', 'btn btn--small btn--solid', 'Доступ'); acc.type = 'button';
      acc.addEventListener('click', function () { editUserAccess(u); });
      var rep = el('button', 'btn btn--small', 'Отчёты'); rep.type = 'button';
      rep.addEventListener('click', function () { editUserReports(u); });
      var pw = el('button', 'btn btn--small', 'Пароль'); pw.type = 'button';
      pw.addEventListener('click', function () { editUserPassword(u); });
      var del = el('button', 'btn btn--small btn--danger', 'Удалить'); del.type = 'button';
      del.addEventListener('click', function () {
        armDelete(del, function () { return api('DELETE', '/api/admin/users/' + u.id).then(function () { toast('Ученик ' + u.nickname + ' удалён'); return loadAll(); }); });
      });
      actions.appendChild(acc); actions.appendChild(rep); actions.appendChild(pw); actions.appendChild(del);
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

        function progressList(items, kind) {
          var ul = el('ul', 'plist');
          if (!items.length) ul.appendChild(el('li', 'picker__empty', kind === 'mock' ? 'Пробники не открыты.' : 'Занятия не открыты.'));
          items.forEach(function (it) {
            var li = el('li', 'prow prow--' + (it.done ? 'done' : 'todo'));
            li.appendChild(el('span', 'prow__dot'));
            var t = el('span', 'prow__text');
            t.appendChild(el('b', null, (kind === 'mock' ? 'Пробник № ' : 'Занятие № ') + it.number + (it.title ? ' · ' + it.title : '')));
            t.appendChild(el('span', null,
              (it.done ? (kind === 'mock' ? 'решён ' : 'просмотрено ') + dateTime(it.marked_at) : 'не отмечено') +
              '  ·  ' + (it.opened_at ? 'открывал ' + dateTime(it.opened_at) : 'не открывал')));
            if (kind === 'mock' && it.result) {
              var r = it.result;
              var res = el('span', 'prow__res');
              res.appendChild(el('b', null, 'Первая часть: ' + r.score + ' из ' + r.max));
              res.appendChild(document.createTextNode(r.wrong.length ? '  ·  ошибки в заданиях ' + r.wrong.join(', ') : '  ·  без ошибок'));
              res.appendChild(document.createTextNode('  ·  сдано ' + dateTime(r.submitted_at)));
              t.appendChild(res);
              var reset = el('button', 'btn btn--small btn--danger prow__reset', 'Сбросить ответы'); reset.type = 'button';
              reset.title = 'Ученик сможет отправить ответы заново';
              reset.addEventListener('click', function () {
                armDelete(reset, function () {
                  return api('DELETE', '/api/admin/mocks/' + it.pk + '/attempts/' + u.id).then(function () {
                    toast('Ответы сброшены: ' + u.nickname + ' может сдать пробник № ' + it.number + ' заново'); showActivity(u);
                  });
                });
              });
              li.appendChild(t); li.appendChild(reset); ul.appendChild(li);
              return;
            } else if (kind === 'mock' && it.has_key) {
              t.appendChild(el('span', 'prow__res', 'Ответы на первую часть ещё не отправлены'));
            }
            li.appendChild(t);
            ul.appendChild(li);
          });
          return ul;
        }
        var ld = a.lessons.filter(function (x) { return x.done; }).length, md = a.mocks.filter(function (x) { return x.done; }).length;
        body.appendChild(field('Занятия: просмотрено ' + ld + ' из ' + a.lessons.length, progressList(a.lessons, 'lesson')));
        body.appendChild(field('Пробники: решено ' + md + ' из ' + a.mocks.length, progressList(a.mocks, 'mock')));

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
    var priv = data.viz.filter(function (v) { return v.access === 'private'; });
    openEditor2('Доступ: ' + u.nickname, function (body) {
      body.appendChild(el('p', 'hint', 'Отметь занятия, которые открыть ученику: вместе с ними откроется всё, что лежит в их папках, включая закрытые визуализации. Ниже — закрытые визуализации, которые можно открыть отдельно, без занятия.'));
      var boxL = el('div', 'picker'), boxV = el('div', 'picker'), boxM = el('div', 'picker');
      var getM = picker(boxM, data.mocks.map(function (m) { return { id: m.pk, label: 'Пробник № ' + m.number, sub: m.title }; }), u.grants.mock, 'Пробников пока нет.');
      var getL = picker(boxL, data.lessons.map(function (l) { return { id: l.pk, label: 'Занятие № ' + l.number, sub: [l.title, lessonContents(l)].filter(Boolean).join(' · ') }; }), u.grants.lesson, 'Занятий пока нет.');
      var getV = picker(boxV, priv.map(function (v) { return { id: v.pk, label: v.title, sub: v.parts }; }), u.grants.viz,
        'Закрытых визуализаций нет: все открыты всем. Закрыть можно на вкладке «Визуализации».');
      body.appendChild(field('Занятия', boxL));
      body.appendChild(field('Пробники', boxM));
      body.appendChild(field('Отдельные визуализации (только закрытые)', boxV));
      return function () {
        return api('PUT', '/api/admin/users/' + u.id + '/grants', { lesson: getL(), mock: getM(), viz: getV() })
          .then(function () { toast('Доступ сохранён: ' + u.nickname); });
      };
    });
  }

  /* Отчёты для родителей: личные PDF ученика, раз в месяц */
  function monthTitle() {
    var d = new Date(); d.setDate(1); d.setMonth(d.getMonth() - (new Date().getDate() < 15 ? 1 : 0));
    var t = d.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' }).replace(' г.', '');
    return t.charAt(0).toUpperCase() + t.slice(1);
  }
  function editUserReports(u) {
    openEditor2('Отчёты: ' + u.nickname, function (body) {
      body.appendChild(el('p', 'hint', 'Отчёт видит только этот ученик — в кабинете на вкладке «Отчёты». Новые показываются сверху.'));
      var list = el('ul', 'rep-list');
      (u.reports || []).forEach(function (r) {
        var li = el('li', 'rep');
        var a = el('a', 'rep__title', r.title); a.href = r.url; a.target = '_blank'; a.rel = 'noopener';
        li.appendChild(a);
        li.appendChild(el('span', 'rep__date', date(r.created_at)));
        var del = el('button', 'btn btn--small btn--danger', 'Удалить'); del.type = 'button';
        del.addEventListener('click', function () {
          armDelete(del, function () {
            return api('DELETE', '/api/admin/reports/' + r.pk).then(function () {
              li.remove(); toast('Отчёт удалён: ' + r.title);
              return api('GET', '/api/admin/users').then(function (d) { data.users = d.users; renderUsers(); });
            });
          });
        });
        li.appendChild(del);
        list.appendChild(li);
      });
      if (!(u.reports || []).length) list.appendChild(el('li', 'picker__empty', 'Отчётов пока нет.'));
      body.appendChild(field('Загружено', list));
      body.appendChild(field('Период *', textInput('e-title', monthTitle(), 'Например: Октябрь 2026')));
      var pdf = pdfField('e-report', null, 'Перетащи PDF отчёта или нажми, чтобы выбрать');
      body.appendChild(field('Новый отчёт (PDF)', pdf.box));
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
