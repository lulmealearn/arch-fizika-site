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

  /* ── Материалы ── */
  function plural(n, one, few, many) {
    var a = n % 10, b = n % 100;
    if (a === 1 && b !== 11) return one;
    if (a >= 2 && a <= 4 && (b < 12 || b > 14)) return few;
    return many;
  }

  function row(href, kind, num, title, go, external, icon) {
    var li = el('li');
    var a = el('a', 'mat');
    a.href = href;
    if (external) { a.target = '_blank'; a.rel = 'noopener'; }
    var badge = el('span', 'mat__num' + (icon ? ' mat__num--icon' : ''));
    if (icon) {
      /* иконка визуализации, как в хранилище: своя → иконка раздела */
      var img = el('img'); img.alt = ''; img.loading = 'lazy';
      var tries = icon.slice();
      img.onerror = function () { tries.shift(); if (tries.length) img.src = tries[0]; else img.remove(); };
      img.src = tries[0];
      badge.appendChild(img);
    } else {
      badge.appendChild(el('span', 'mat__kind', kind));
      if (num != null) badge.appendChild(el('b', null, String(num)));
    }
    a.appendChild(badge);
    a.appendChild(el('span', 'mat__title', title));
    var g = el('span', 'mat__go', go); g.setAttribute('aria-hidden', 'true');
    a.appendChild(g);
    li.appendChild(a);
    return li;
  }

  function fill(listId, countId, items, make, emptyText) {
    var list = $(listId); list.textContent = '';
    $(countId).textContent = items.length ? String(items.length) : '';
    if (!items.length) { list.appendChild(el('li', 'mats__empty', emptyText)); return; }
    items.forEach(function (it) { list.appendChild(make(it)); });
  }

  function loadDash() {
    return api('GET', '/api/me/materials').then(function (d) {
      $('acc-eyebrow').textContent = 'Личный кабинет · ' + d.user.nickname;
      $('acc-title').textContent = 'Мои материалы';
      /* вошли: подсказка «войдите, чтобы открыть» больше не нужна, адрес чистим */
      if (params.get('locked') !== '1' && $('acc-note').dataset.kind === 'next') note('');
      if (location.search) { try { history.replaceState(null, '', location.pathname); } catch (e) { /* без истории */ } }
      fill('list-hw', 'n-hw', d.homeworks, function (h) {
        return row(h.url, 'ДЗ', h.number, h.title || 'Домашнее задание № ' + h.number, 'PDF →', true);
      }, 'Домашних заданий пока нет. Я открою их после занятия.');
      fill('list-lessons', 'n-lessons', d.lessons, function (l) {
        return row(l.url, 'Урок', l.number, l.title || 'Запись урока № ' + l.number, 'Смотреть →', true);
      }, 'Записей пока нет.');
      fill('list-viz', 'n-viz', d.viz, function (v) {
        var icon = v.cover ? ['../' + v.cover] : ['../assets/icons/viz/' + v.id + '.svg', '../assets/icons/viz/_' + v.section + '.svg'];
        return row('../viz/' + v.file, 'Визуализация', null, v.title, '→', false, icon);
      }, 'Закрытых визуализаций вам пока не открыто. Бесплатные доступны всем по ссылке ниже.');
      show('dash');
    }).catch(function (e) {
      if (e.status === 401) { toAuth(); return; }
      note(e.message); show('auth');
    });
  }

  /* ── ДЗ по номеру ── */
  $('f-jump').addEventListener('input', function () {
    var v = this.value.replace(/\D/g, '');
    if (v !== this.value) this.value = v;
  });
  $('jump-form').addEventListener('submit', function (e) {
    e.preventDefault();
    var n = $('f-jump').value.trim();
    if (!/^\d{1,6}$/.test(n) || n === '0') { $('f-jump').focus(); return showError('jump-error', 'Введите номер задания, например 42.'); }
    showError('jump-error', '');
    location.href = '/hw/' + Number(n);
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
    if (d.user) loadDash(); else toAuth();
  }).catch(function (e) { toAuth(); showError('auth-error', e.message); });
})();
