/* Личный кабинет: вход и регистрация (ник + пароль), затем открытые ученику ДЗ, записи уроков и визуализации. */
(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var params = new URLSearchParams(location.search);
  var mode = 'login';

  /* Вернуться можно только на страницу этого же сайта */
  function safeNext() {
    var n = params.get('next') || '';
    return /^\/(?![\/\\])/.test(n) ? n : '';
  }
  var next = safeNext();

  function api(method, url, body) {
    var opts = { method: method, credentials: 'same-origin', headers: {} };
    if (body !== undefined) { opts.body = JSON.stringify(body); opts.headers['Content-Type'] = 'application/json'; }
    return fetch(url, opts).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (d) {
        if (!r.ok) {
          var e = new Error(typeof d.detail === 'string' ? d.detail : 'Сервер ответил ошибкой ' + r.status + '.');
          e.status = r.status; throw e;
        }
        return d;
      });
    }, function () { throw new Error('Нет связи с сервером. Проверьте интернет и попробуйте ещё раз.'); });
  }

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function showError(id, msg) { var n = $(id); n.textContent = msg || ''; n.hidden = !msg; }
  function note(text) { var n = $('acc-note'); n.textContent = text || ''; n.hidden = !text; n.dataset.kind = ''; }

  function show(view) {
    ['loading', 'auth', 'dash'].forEach(function (v) { $('view-' + v).hidden = v !== view; });
    $('logout').hidden = view !== 'dash';
  }

  /* ── Вход / регистрация ── */
  function setMode(m) {
    mode = m;
    var reg = m === 'register';
    $('tab-login').setAttribute('aria-selected', String(!reg));
    $('tab-register').setAttribute('aria-selected', String(reg));
    $('row-pass2').hidden = !reg;
    $('nick-hint').hidden = !reg;
    $('pass-hint').hidden = !reg;
    $('f-pass').setAttribute('autocomplete', reg ? 'new-password' : 'current-password');
    $('auth-submit').textContent = reg ? 'Зарегистрироваться' : 'Войти';
    $('acc-title').textContent = reg ? 'Регистрация' : 'Вход';
    showError('auth-error', '');
  }
  $('tab-login').addEventListener('click', function () { setMode('login'); });
  $('tab-register').addEventListener('click', function () { setMode('register'); });

  document.querySelectorAll('[data-toggle-pw]').forEach(function (b) {
    b.addEventListener('click', function () {
      var on = $('f-pass').type === 'password';
      $('f-pass').type = on ? 'text' : 'password';
      $('f-pass2').type = on ? 'text' : 'password';
      b.textContent = on ? 'Скрыть' : 'Показать';
      b.setAttribute('aria-label', on ? 'Скрыть пароль' : 'Показать пароль');
    });
  });

  $('auth-form').addEventListener('submit', function (e) {
    e.preventDefault();
    var nick = $('f-nick').value.trim(), pw = $('f-pass').value;
    if (!nick) { $('f-nick').focus(); return showError('auth-error', 'Введите ник.'); }
    if (!pw) { $('f-pass').focus(); return showError('auth-error', 'Введите пароль.'); }
    if (mode === 'register') {
      if (!/^[A-Za-zА-Яа-яЁё0-9_.\-]{3,32}$/.test(nick)) { $('f-nick').focus(); return showError('auth-error', 'Ник: от 3 до 32 символов — буквы, цифры, точка, дефис или подчёркивание, без пробелов.'); }
      if (pw.length < 6) { $('f-pass').focus(); return showError('auth-error', 'Пароль должен быть не короче 6 символов.'); }
      if (pw !== $('f-pass2').value) { $('f-pass2').focus(); return showError('auth-error', 'Пароли не совпадают.'); }
    }
    showError('auth-error', '');
    var btn = $('auth-submit'); btn.disabled = true;
    api('POST', '/api/auth/' + mode, { nickname: nick, password: pw }).then(function (d) {
      $('f-pass').value = ''; $('f-pass2').value = '';
      if (next && mode === 'login') { location.replace(next); return; }
      if (mode === 'register') note('Готово, вы зарегистрированы как «' + d.user.nickname + '». Напишите этот ник мне в Telegram, и я открою вам материалы.');
      else note('');
      loadDash();
    }).catch(function (err) { showError('auth-error', err.message); })
      .then(function () { btn.disabled = false; });
  });

  $('logout').addEventListener('click', function () {
    api('POST', '/api/auth/logout').then(function () { note(''); mode = 'login'; toAuth(); });
  });

  function toAuth() {
    setMode(mode);
    show('auth');
    $('acc-eyebrow').textContent = 'Личный кабинет';
  }

  /* ── Занятия: папки ── */
  var lessons = [], mocks = [], sections = [], secFilter = 'all', filter = 'all', current = null, currentKind = 'lesson';

  function plural(n, one, few, many) {
    var a = n % 10, b = n % 100;
    if (a === 1 && b !== 11) return one;
    if (a >= 2 && a <= 4 && (b < 12 || b > 14)) return few;
    return many;
  }
  function vizIcon(v) {
    return v.cover ? ['../' + v.cover] : ['../assets/icons/viz/' + v.id + '.svg', '../assets/icons/viz/_' + v.section + '.svg'];
  }
  function iconImg(tries) {
    var img = el('img'); img.alt = ''; img.loading = 'lazy';
    tries = tries.slice();
    img.onerror = function () { tries.shift(); if (tries.length) img.src = tries[0]; else img.remove(); };
    img.src = tries[0];
    return img;
  }
  var ICONS = {
    video: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="3"/><path d="M10 9.2v5.6l4.8-2.8z" fill="currentColor"/></svg>',
    notes: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h9l4 4v14H6z"/><path d="M15 3v4h4M9 12h7M9 16h5"/></svg>',
    pdf: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h9l4 4v14H6z"/><path d="M15 3v4h4M9 13h6M9 17h6M9 9h2"/></svg>',
    hw: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 4h14v17H5z"/><path d="M9 4V2.8h6V4M8.5 11l2 2 4-4M8.5 17h7"/></svg>'
  };

  /* что лежит в папке — коротко, для карточки */
  function contents(l) {
    /* inside — что лежит в папке, даже пока материалы закрыты до «Начать» */
    var i = l.inside || { video: !!l.url, notes: !!l.notes_url, hw: !!l.hw_url, viz: l.viz.length };
    var parts = [];
    if (i.video) parts.push('запись');
    if (i.notes) parts.push('конспект');
    if (i.hw) parts.push('ДЗ');
    if (i.viz) parts.push(i.viz + ' ' + plural(i.viz, 'визуализация', 'визуализации', 'визуализаций'));
    return parts.length ? parts.join(' · ') : 'материалы скоро появятся';
  }
  function lessonTitle(l) { return l.title || 'Занятие № ' + l.number; }

  /* ── Срок на ДЗ: «Не начато» → «Начать» (идёт срок) → «Сдал». Истёк без сдачи — снова «Не начато», просрочка в счётчике ── */
  var STATE_TEXT = { todo: 'не начато', active: 'в работе', done: 'сдано' };
  function dlState(l) { return (l.deadline && l.deadline.state) || 'todo'; }
  function daysWord(n) { return n + ' ' + plural(n, 'день', 'дня', 'дней'); }
  function timeLeft(iso) {
    var ms = new Date(iso).getTime() - Date.now();
    if (ms <= 0) return 'срок истёк';
    var min = Math.ceil(ms / 60000), d = Math.floor(min / 1440), h = Math.floor((min % 1440) / 60), m = min % 60;
    if (d) return d + ' ' + plural(d, 'день', 'дня', 'дней') + (h ? ' ' + h + ' ' + plural(h, 'час', 'часа', 'часов') : '');
    if (h) return h + ' ' + plural(h, 'час', 'часа', 'часов') + (m ? ' ' + m + ' мин' : '');
    return m + ' мин';
  }
  function when(iso) {
    var d = new Date(iso);
    return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' }) + ', ' +
      d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
  }
  function stateLine(l) {
    var st = dlState(l), dl = l.deadline || {};
    if (st === 'active') return 'осталось ' + timeLeft(dl.due_at);
    return STATE_TEXT[st];
  }

  function folderCard(l) {
    var li = el('li');
    var st0 = dlState(l);
    var b = el('button', 'folder folder--' + st0);
    b.type = 'button';
    b.setAttribute('aria-label', 'Занятие № ' + l.number + ': ' + lessonTitle(l) + '. ' + stateLine(l));
    var tab = el('span', 'folder__tab');
    tab.appendChild(el('span', null, 'Занятие'));
    tab.appendChild(el('b', null, '№ ' + l.number));
    var body = el('span', 'folder__body');
    body.appendChild(el('span', 'folder__title', lessonTitle(l)));
    var sec = sectionOf(l);
    if (sec) {
      var tag = el('span', 'folder__sec');
      var dot = el('span', 'folder__secdot'); dot.style.background = sec.color;
      tag.appendChild(dot); tag.appendChild(document.createTextNode(sec.label));
      body.appendChild(tag);
    }
    body.appendChild(el('span', 'folder__what', contents(l)));
    var foot = el('span', 'folder__foot');
    var st = el('span', 'folder__state', stateLine(l));
    if (st0 === 'active') st.dataset.due = l.deadline.due_at;
    foot.appendChild(st);
    var over = (l.deadline && l.deadline.overdue) || 0;
    if (over) foot.appendChild(el('span', 'folder__late', 'просрочено' + (over > 1 ? ' × ' + over : '')));
    body.appendChild(foot);
    b.appendChild(tab); b.appendChild(body);
    b.addEventListener('click', function () { openLesson(l); });
    li.appendChild(b);
    return li;
  }

  /* Пробник — такая же карточка-папка: красная, пока не решён, зелёная — решён */
  function mockTitle(m) { return m.title || 'Пробник № ' + m.number; }
  function mockCard(m) {
    var li = el('li');
    var b = el('button', 'folder folder--mock folder--' + (m.done ? 'done' : 'todo'));
    b.type = 'button';
    b.setAttribute('aria-label', 'Пробник № ' + m.number + ': ' + mockTitle(m) + '. ' + (m.done ? 'Решён' : 'Не решён'));
    var tab = el('span', 'folder__tab');
    tab.appendChild(el('span', null, 'Пробник'));
    tab.appendChild(el('b', null, '№ ' + m.number));
    var body = el('span', 'folder__body');
    body.appendChild(el('span', 'folder__title', mockTitle(m)));
    body.appendChild(el('span', 'folder__what', m.result ? 'первая часть: ' + m.result.score + ' из ' + m.result.max + ' ' + plural(m.result.max, 'балла', 'баллов', 'баллов')
      : m.tasks && m.tasks.length ? 'вариант · бланк ответов' : 'вариант в формате ЕГЭ'));
    body.appendChild(el('span', 'folder__state', m.done ? 'решён' : 'не решён'));
    b.appendChild(tab); b.appendChild(body);
    b.addEventListener('click', function () { openMock(m); });
    li.appendChild(b);
    return li;
  }
  function renderMocks() {
    var list = $('mocks'); list.textContent = '';
    if (!mocks.length) list.appendChild(el('li', 'folders__empty', 'Пробников пока нет.'));
    mocks.forEach(function (m) { list.appendChild(mockCard(m)); });
    $('kt-mocks').textContent = mocks.length || '';
  }
  function renderReports(reports) {
    var list = $('reports'); list.textContent = '';
    if (!reports.length) list.appendChild(el('li', 'folders__empty', 'Отчётов пока нет. Первый появится в конце месяца.'));
    reports.forEach(function (r) {
      var d = r.created_at ? new Date(r.created_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' }) : '';
      list.appendChild(item(r.url, ICONS.pdf, 'Отчёт' + (d ? ' · ' + d : ''), r.title, 'PDF →', true));
    });
    $('kt-reports').textContent = reports.length || '';
  }

  /* ── Вкладки кабинета ── */
  var KTABS = { lessons: '', mocks: '#probniki', reports: '#otchety' };
  function setKtab(name, push) {
    if (!KTABS.hasOwnProperty(name)) name = 'lessons';
    document.querySelectorAll('.ktabs__btn').forEach(function (b) { b.setAttribute('aria-selected', String(b.dataset.ktab === name)); });
    Object.keys(KTABS).forEach(function (k) { $('kpanel-' + k).hidden = k !== name; });
    if (push) { try { history.replaceState(null, '', location.pathname + KTABS[name]); } catch (e) { /* без истории */ } }
  }
  document.querySelectorAll('.ktabs__btn').forEach(function (b) {
    b.addEventListener('click', function () { setKtab(b.dataset.ktab, true); });
  });

  function matches(l, q) {
    if (!q) return true;
    if (/^\d+$/.test(q)) return String(l.number) === q || String(l.number).indexOf(q) === 0;
    var sec = sectionOf(l);
    var hay = (lessonTitle(l) + ' ' + (sec ? sec.label : '') + ' ' + l.viz.map(function (v) { return v.title; }).join(' ')).toLowerCase();
    return q.toLowerCase().split(/\s+/).every(function (w) { return hay.indexOf(w) >= 0; });
  }

  /* ── Разделы физики: Все · Механика · МКТ и термодинамика · … (только те, где есть занятия) ── */
  function sectionOf(l) {
    for (var i = 0; i < sections.length; i++) if (sections[i].id === l.section) return sections[i];
    return null;
  }
  function inSection(l) { return secFilter === 'all' || (secFilter === 'none' ? !l.section : l.section === secFilter); }
  function renderSecChips() {
    var box = $('sec-chips'); box.textContent = '';
    var counts = {}, none = 0;
    lessons.forEach(function (l) { if (l.section) counts[l.section] = (counts[l.section] || 0) + 1; else none++; });
    var used = sections.filter(function (s) { return counts[s.id]; });
    box.hidden = !used.length;
    if (box.hidden) { secFilter = 'all'; return; }
    if (secFilter !== 'all' && secFilter !== 'none' && !counts[secFilter]) secFilter = 'all';
    function chip(id, label, n, color) {
      var b = el('button', 'fchip fchip--sec'); b.type = 'button';
      b.setAttribute('aria-pressed', String(secFilter === id));
      if (color) { var d = el('span', 'fchip__dot'); d.style.background = color; b.appendChild(d); }
      b.appendChild(document.createTextNode(label + ' '));
      b.appendChild(el('span', null, String(n)));
      b.addEventListener('click', function () { secFilter = id; renderSecChips(); renderFolders(); });
      box.appendChild(b);
    }
    chip('all', 'Все', lessons.length);
    used.forEach(function (s) { chip(s.id, s.label, counts[s.id], s.color); });
    if (none) chip('none', 'Без раздела', none);
  }

  function renderFolders() {
    var q = $('f-find').value.trim();
    var list = $('folders'); list.textContent = '';
    var pool = lessons.filter(inSection);
    var cnt = { todo: 0, active: 0, done: 0 };
    pool.forEach(function (l) { cnt[dlState(l)]++; });
    $('c-todo').textContent = cnt.todo; $('c-active').textContent = cnt.active; $('c-done').textContent = cnt.done;
    var shown = pool.filter(function (l) {
      return matches(l, q) && (filter === 'all' || dlState(l) === filter);
    });
    shown.forEach(function (l) { list.appendChild(folderCard(l)); });
    var hint = $('finder-hint');
    if (!lessons.length) {
      list.appendChild(el('li', 'folders__empty', 'Занятий пока нет. Я открою их после первого урока.'));
      hint.hidden = true;
    } else if (!shown.length) {
      list.appendChild(el('li', 'folders__empty', q ? 'Ничего не нашлось. Попробуйте номер занятия или другое слово.' : 'Здесь пока пусто.'));
      hint.hidden = true;
    } else {
      hint.hidden = !q;
      hint.textContent = 'Найдено: ' + shown.length + ' из ' + lessons.length;
    }
  }

  $('f-find').addEventListener('input', renderFolders);
  /* «Не начаты» / «В работе» / «Сданы» — переключатели: повторное нажатие снимает фильтр */
  document.querySelectorAll('.fchip[data-filter]').forEach(function (b) {
    b.addEventListener('click', function () {
      filter = filter === b.dataset.filter ? 'all' : b.dataset.filter;
      document.querySelectorAll('.fchip[data-filter]').forEach(function (x) { x.setAttribute('aria-pressed', String(x.dataset.filter === filter)); });
      renderFolders();
    });
  });
  /* Enter / «Открыть»: точный номер или единственная найденная папка — сразу открываем */
  $('finder').addEventListener('submit', function (e) {
    e.preventDefault();
    var q = $('f-find').value.trim();
    if (!q) { $('f-find').focus(); return; }
    var exact = lessons.filter(function (l) { return String(l.number) === q; });
    var found = exact.length ? exact : lessons.filter(function (l) { return matches(l, q); });
    var hint = $('finder-hint');
    if (found.length === 1) { openLesson(found[0]); return; }
    hint.hidden = false;
    hint.textContent = found.length ? 'Нашлось несколько занятий — выберите нужное ниже.' :
      (/^\d+$/.test(q) ? 'Занятие № ' + q + ' вам пока не открыто.' : 'Ничего не нашлось.');
  });

  /* ── Открытая папка ── */
  var dlg = $('lesson');
  function item(href, icon, kind, title, go, external) {
    var li = el('li');
    var a = el('a', 'litem');
    a.href = href;
    if (external) { a.target = '_blank'; a.rel = 'noopener'; }
    var ic = el('span', 'litem__ic');
    if (typeof icon === 'string') ic.innerHTML = icon; else { ic.classList.add('litem__ic--img'); ic.appendChild(icon); }
    var txt = el('span', 'litem__text');
    txt.appendChild(el('span', 'litem__kind', kind));
    txt.appendChild(el('span', 'litem__title', title));
    a.appendChild(ic); a.appendChild(txt);
    var g = el('span', 'litem__go', go); g.setAttribute('aria-hidden', 'true'); a.appendChild(g);
    li.appendChild(a);
    return li;
  }
  function paintDone(l) {
    var mock = currentKind === 'mock';
    $('lesson-mark').hidden = !mock;
    $('lesson-dl').hidden = mock;
    dlg.classList.remove('is-active');
    if (!mock) return renderDeadline(l);
    dlg.classList.toggle('is-done', l.done);
    $('lesson-done').checked = l.done;
    $('lesson-done-label').textContent = l.done ? 'Решён' : 'Не решён';
    $('lesson-done-hint').textContent = 'Отметьте, когда решите вариант';
  }
  /* Панель срока в окне занятия */
  function confirmButton(text, armedText, cls, onGo) {
    var btn = el('button', 'btn ' + cls, text); btn.type = 'button';
    var armed = false;
    btn.addEventListener('click', function () {
      if (!armed) {
        armed = true; btn.textContent = armedText; btn.classList.add('is-armed');
        setTimeout(function () { if (btn.isConnected && armed) { armed = false; btn.textContent = text; btn.classList.remove('is-armed'); } }, 5000);
        return;
      }
      btn.disabled = true;
      onGo(function () { btn.disabled = false; armed = false; btn.textContent = text; btn.classList.remove('is-armed'); });
    });
    return btn;
  }
  function dlAction(l, action) {
    return function (restore) {
      api('POST', '/api/me/lessons/' + l.pk + '/' + action).then(function (r) {
        l.deadline = r.deadline; l.done = r.deadline.state === 'done';
        paintDone(l);
        if (l.locked) reloadLessons();  // после первого «Начать» сервер открыл материалы — подтягиваем ссылки
      }).catch(function (e) {
        restore();
        var err = $('lesson-dl').querySelector('.form-error');
        if (err) { err.textContent = e.message; err.hidden = false; }
        reloadLessons();  // срок мог истечь — подтянуть свежее состояние
      });
    };
  }
  function renderDeadline(l) {
    var box = $('lesson-dl'); box.textContent = '';
    var st = dlState(l), dl = l.deadline || {}, days = dl.days || 3, over = dl.overdue || 0;
    dlg.classList.toggle('is-done', st === 'done');
    dlg.classList.toggle('is-active', st === 'active');
    box.className = 'dl dl--' + st;
    var head = el('div', 'dl__head');
    head.appendChild(el('span', 'dl__label', 'Домашнее задание'));
    head.appendChild(el('span', 'dl__state', STATE_TEXT[st]));
    box.appendChild(head);
    var err = el('p', 'form-error'); err.hidden = true;
    if (st === 'todo') {
      box.appendChild(el('p', 'dl__text', over
        ? 'Срок истёк' + (over > 1 ? ' уже ' + over + ' ' + plural(over, 'раз', 'раза', 'раз') : '') + ', а задание не отмечено сданным. Возьмите новый срок и сдайте задание — просрочка останется в истории.'
        : 'Материалы занятия откроются, когда вы нажмёте «Начать». С этого момента у вас ' + daysWord(days) + ' на домашнее задание — начинайте, когда будете готовы.'));
      box.appendChild(confirmButton(over ? 'Взять новый срок · ' + daysWord(days) : 'Начать · срок ' + daysWord(days),
        'Подтвердите: срок пойдёт сразу', 'btn--solid dl__btn', dlAction(l, 'start')));
    } else if (st === 'active') {
      var big = el('b', 'dl__left', timeLeft(dl.due_at)); big.dataset.due = dl.due_at;
      box.appendChild(el('span', 'dl__kicker', 'Осталось'));
      box.appendChild(big);
      box.appendChild(el('p', 'dl__text', 'Сдать до ' + when(dl.due_at) + '. Когда отправите решение, нажмите «Сдал».'));
      var total = new Date(dl.due_at) - new Date(dl.started_at), passed = Date.now() - new Date(dl.started_at);
      var bar = el('span', 'dl__bar'); var fill = el('i');
      fill.style.width = Math.max(2, Math.min(100, 100 * passed / total)) + '%';
      fill.dataset.from = dl.started_at; fill.dataset.to = dl.due_at;
      bar.appendChild(fill); box.appendChild(bar);
      box.appendChild(confirmButton('Сдал', 'Точно сдали? Отменить будет нельзя', 'btn--solid dl__btn', dlAction(l, 'submit')));
    } else {
      box.appendChild(el('p', 'dl__text', 'Сдано ' + when(dl.submitted_at) + '.' +
        (over ? ' Срок был просрочен ' + over + ' ' + plural(over, 'раз', 'раза', 'раз') + '.' : '')));
    }
    box.appendChild(err);
  }

  function showDialog() {
    if (dlg.showModal) dlg.showModal(); else dlg.setAttribute('open', '');
    document.documentElement.classList.add('pop-lock');
  }
  function openMock(m) {
    current = m; currentKind = 'mock';
    $('lesson-tab').textContent = 'Пробник № ' + m.number;
    $('lesson-title').textContent = mockTitle(m);
    var list = $('lesson-items'); list.textContent = '';
    list.appendChild(item(m.url, ICONS.pdf, 'Вариант', 'Пробник № ' + m.number, 'Открыть →', false));
    renderSheet(m);
    paintDone(m);
    showDialog();
  }

  /* ── Бланк ответов первой части: проверяет сервер, попытка одна ── */
  var NOTE_PART1 = 'Это баллы только за первую часть. Вторая часть в этот результат не входит.';
  function draftKey(m) { return 'mock-draft-' + m.pk; }
  function loadDraft(m) { try { return JSON.parse(localStorage.getItem(draftKey(m)) || '{}'); } catch (e) { return {}; } }
  function saveDraft(m, d) { try { localStorage.setItem(draftKey(m), JSON.stringify(d)); } catch (e) { /* без хранилища тоже работает */ } }
  function dropDraft(m) { try { localStorage.removeItem(draftKey(m)); } catch (e) { /* не важно */ } }

  function renderSheet(m) {
    var box = $('lesson-sheet'); box.textContent = '';
    box.hidden = !(m.tasks && m.tasks.length);
    if (box.hidden) return;
    if (m.result) return renderResult(box, m.result);

    box.appendChild(el('h3', 'bsheet__h', 'Бланк ответов · первая часть'));
    box.appendChild(el('p', 'bsheet__hint', 'Решите вариант и впишите ответы. Дробные числа — через запятую, ответы из нескольких цифр — без пробелов. Отправить можно один раз; до отправки ответы сохраняются на этом устройстве.'));
    var draft = loadDraft(m);
    var grid = el('div', 'bsheet__grid');
    m.tasks.forEach(function (n) {
      var lab = el('label', 'cell');
      lab.appendChild(el('span', 'cell__n', String(n)));
      var inp = el('input', 'cell__in'); inp.type = 'text'; inp.maxLength = 20; inp.autocomplete = 'off'; inp.spellcheck = false;
      inp.inputMode = 'decimal'; inp.dataset.n = n; inp.value = draft[n] || '';
      inp.setAttribute('aria-label', 'Ответ на задание ' + n);
      inp.addEventListener('input', function () { draft[n] = inp.value; saveDraft(m, draft); count(); });
      lab.appendChild(inp);
      grid.appendChild(lab);
    });
    box.appendChild(grid);
    var foot = el('div', 'bsheet__foot');
    var filled = el('span', 'bsheet__count');
    var btn = el('button', 'btn btn--solid', 'Отправить ответы'); btn.type = 'button';
    var err = el('p', 'form-error'); err.hidden = true;
    foot.appendChild(filled); foot.appendChild(btn);
    box.appendChild(foot); box.appendChild(err);
    function count() {
      var n = m.tasks.filter(function (t) { return (draft[t] || '').trim(); }).length;
      filled.textContent = 'заполнено ' + n + ' из ' + m.tasks.length;
    }
    count();
    var armed = false;
    btn.addEventListener('click', function () {
      if (!armed) {
        armed = true; btn.textContent = 'Точно отправить? Изменить будет нельзя';
        btn.classList.add('is-armed');
        setTimeout(function () { if (btn.isConnected && armed) { armed = false; btn.textContent = 'Отправить ответы'; btn.classList.remove('is-armed'); } }, 4000);
        return;
      }
      btn.disabled = true; err.hidden = true;
      var answers = {};
      m.tasks.forEach(function (t) { answers[t] = (draft[t] || '').trim(); });
      api('POST', '/api/me/mocks/' + m.pk + '/answers', { answers: answers }).then(function (r) {
        m.result = r; m.done = true; dropDraft(m);
        renderSheet(m); paintDone(m);
      }).catch(function (e) { err.textContent = e.message; err.hidden = false; btn.disabled = false; armed = false; btn.textContent = 'Отправить ответы'; btn.classList.remove('is-armed'); });
    });
  }

  function renderResult(box, r) {
    var head = el('div', 'res');
    head.appendChild(el('span', 'res__label', 'Первая часть'));
    var big = el('b', 'res__score'); big.textContent = r.score + ' из ' + r.max;
    head.appendChild(big);
    head.appendChild(el('span', 'res__unit', plural(r.max, 'первичного балла', 'первичных баллов', 'первичных баллов')));
    box.appendChild(head);
    box.appendChild(el('p', 'bsheet__hint', NOTE_PART1));
    var table = el('div', 'rtable');
    var hdr = el('div', 'rrow rrow--head');
    ['№', 'Ваш ответ', 'Правильный', 'Баллы'].forEach(function (t) { hdr.appendChild(el('span', null, t)); });
    table.appendChild(hdr);
    r.details.forEach(function (d) {
      var row = el('div', 'rrow ' + (d.points === d.max ? 'rrow--ok' : d.points ? 'rrow--half' : 'rrow--bad'));
      row.appendChild(el('span', 'rrow__n', String(d.n)));
      row.appendChild(el('span', null, d.given || '—'));
      row.appendChild(el('span', null, d.correct));
      row.appendChild(el('span', 'rrow__pts', d.points + ' / ' + d.max));
      table.appendChild(row);
    });
    box.appendChild(table);
  }
  /* Содержимое папки. До первого «Начать» материалы закрыты (их не отдаёт и сервер) — показываем только, что внутри */
  function fillLesson(l) {
    var list = $('lesson-items'); list.textContent = '';
    if (l.locked) {
      var what = contents(l);
      var li = el('li', 'lesson__locked');
      li.appendChild(el('b', null, 'Материалы откроются после «Начать»'));
      li.appendChild(el('span', null, what === 'материалы скоро появятся' ? 'Материалы этого занятия скоро появятся.' : 'В папке: ' + what + '.'));
      list.appendChild(li);
    } else {
      if (l.url) list.appendChild(item(l.url, ICONS.video, 'Запись', 'Смотреть запись занятия', 'Смотреть →', true));
      if (l.notes_url) list.appendChild(item(l.notes_url, ICONS.notes, 'Конспект', 'Конспект занятия', 'PDF →', true));
      if (l.hw_url) list.appendChild(item(l.hw_url, ICONS.hw, 'Домашнее задание', 'ДЗ к занятию № ' + l.number, 'PDF →', true));
      l.viz.forEach(function (v) { list.appendChild(item('../viz/' + v.file, iconImg(vizIcon(v)), 'Визуализация', v.title, '→', false)); });
      if (!list.children.length) list.appendChild(el('li', 'lesson__empty', 'Материалы этого занятия скоро появятся.'));
    }
    paintDone(l);
  }
  function openLesson(l) {
    current = l; currentKind = 'lesson';
    $('lesson-sheet').hidden = true;
    $('lesson-tab').textContent = 'Занятие № ' + l.number;
    $('lesson-title').textContent = lessonTitle(l);
    fillLesson(l);
    try { history.replaceState(null, '', '#z' + l.number); } catch (e) { /* без истории */ }
    showDialog();
  }
  function closeLesson() {
    if (dlg.open) { if (dlg.close) dlg.close(); else dlg.removeAttribute('open'); }
  }
  dlg.addEventListener('close', function () {
    document.documentElement.classList.remove('pop-lock');
    var wasMock = currentKind === 'mock';
    current = null;
    try { history.replaceState(null, '', location.pathname + (wasMock ? KTABS.mocks : '')); } catch (e) { /* без истории */ }
    renderFolders(); renderMocks();
  });
  dlg.querySelectorAll('[data-close-lesson]').forEach(function (b) { b.addEventListener('click', closeLesson); });
  dlg.addEventListener('click', function (e) { if (e.target === dlg) closeLesson(); });

  /* переключатель «решён» — только у пробников; у занятий вместо него срок на ДЗ */
  $('lesson-done').addEventListener('change', function () {
    var l = current, want = this.checked, box = this;
    if (!l || currentKind !== 'mock') return;
    l.done = want; paintDone(l);
    box.disabled = true;
    api('PUT', '/api/me/mock-progress/' + l.pk, { done: want }).catch(function (e) {
      l.done = !want; paintDone(l); note(e.message);
    }).then(function () { box.disabled = false; });
  });

  function loadDash() {
    return api('GET', '/api/me/materials').then(function (d) {
      $('acc-eyebrow').textContent = 'Личный кабинет · ' + d.user.nickname;
      $('acc-title').textContent = 'Мои материалы';
      /* вошли: подсказка «войдите, чтобы открыть» больше не нужна */
      if (params.get('locked') !== '1' && $('acc-note').dataset.kind === 'next') note('');
      var hash = location.hash;
      if (location.search) { try { history.replaceState(null, '', location.pathname + hash); } catch (e) { /* без истории */ } }
      lessons = d.lessons;
      sections = d.sections || [];
      renderSecChips();
      mocks = d.mocks || [];
      renderFolders(); renderMocks(); renderReports(d.reports || []);
      $('kt-lessons').textContent = lessons.length || '';
      setKtab(hash === KTABS.mocks ? 'mocks' : hash === KTABS.reports ? 'reports' : 'lessons', false);
      var extra = $('list-viz'); extra.textContent = '';
      d.viz.forEach(function (v) {
        extra.appendChild(item('../viz/' + v.file, iconImg(vizIcon(v)), 'Визуализация', v.title, '→', false));
      });
      $('extra-viz').hidden = !d.viz.length;
      /* в кабинете только последние 3; остальные — в хранилище, там они без замка */
      var more = (d.viz_total || 0) - d.viz.length;
      $('extra-more').hidden = more <= 0;
      $('extra-more').textContent = more > 0 ? 'Ещё ' + more + ' ' + plural(more, 'визуализация открыта', 'визуализации открыты', 'визуализаций открыто') +
        ' вам — они в общем списке визуализаций с пометкой «открыто вам».' : '';
      show('dash');
      /* ссылка вида /account/#z12 сразу открывает папку */
      openFromHash(hash);
    }).catch(function (e) {
      if (e.status === 401) { toAuth(); return; }
      note(e.message); show('auth');
    });
  }

  function openFromHash(hash) {
    if (hash === KTABS.mocks) { setKtab('mocks', false); return; }
    if (hash === KTABS.reports) { setKtab('reports', false); return; }
    var m = /^#z(\d+)$/.exec(hash || '');
    if (!m || dlg.open) return;
    setKtab('lessons', false);
    lessons.forEach(function (l) { if (String(l.number) === m[1]) openLesson(l); });
  }
  window.addEventListener('hashchange', function () { openFromHash(location.hash); });

  /* Свежие состояния сроков без перерисовки всего кабинета */
  function reloadLessons() {
    return api('GET', '/api/me/materials').then(function (d) {
      var byPk = {};
      d.lessons.forEach(function (x) { byPk[x.pk] = x; });
      lessons.forEach(function (l) {
        var x = byPk[l.pk];
        if (x) Object.keys(x).forEach(function (k) { l[k] = x[k]; });  // тот же объект: окно и папки ссылаются на него
      });
      if (current && currentKind === 'lesson') fillLesson(current);
      if (!dlg.open) renderFolders();
    }).catch(function () { /* не важно */ });
  }
  /* Таймеры: раз в 30 секунд обновляем «осталось …»; истёк срок — берём состояние с сервера */
  setInterval(function () {
    if ($('view-dash').hidden) return;
    var expired = false;
    document.querySelectorAll('[data-due]').forEach(function (n) {
      if (new Date(n.dataset.due).getTime() <= Date.now()) expired = true;
      n.textContent = (n.classList.contains('folder__state') ? 'осталось ' : '') + timeLeft(n.dataset.due);
    });
    document.querySelectorAll('.dl__bar i[data-from]').forEach(function (i) {
      var a = new Date(i.dataset.from).getTime(), b = new Date(i.dataset.to).getTime();
      i.style.width = Math.max(2, Math.min(100, 100 * (Date.now() - a) / (b - a))) + '%';
    });
    if (expired) reloadLessons();
  }, 30000);

  /* Пока кабинет открыт и виден на экране, раз в минуту продлеваем сеанс (для статистики в админке) */
  setInterval(function () {
    if (document.visibilityState !== 'visible' || $('view-dash').hidden) return;
    fetch('/api/me/ping', { method: 'POST', credentials: 'same-origin' }).catch(function () { /* не важно */ });
  }, 60000);

  /* ── Админка в этом же браузере ── */
  $('admin-logout').addEventListener('click', function () {
    api('POST', '/api/admin/logout').then(function () { $('admin-note').hidden = true; });
  });

  /* ── Старт ── */
  if (params.get('locked') === '1') {
    note('Этот материал вам пока не открыт. Если вы занимаетесь у меня, напишите мне свой ник — я открою доступ.');
  } else if (next) {
    note('Этот материал доступен ученикам. Войдите в личный кабинет, чтобы открыть его.');
    $('acc-note').dataset.kind = 'next';
  }
  setMode(params.get('mode') === 'register' ? 'register' : 'login');

  api('GET', '/api/auth/me').then(function (d) {
    $('admin-note').hidden = !d.admin;
    if (d.user) loadDash(); else toAuth();
  }).catch(function (e) { toAuth(); showError('auth-error', e.message); });
})();
