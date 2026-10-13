/* Проверка работ кураторами: очередь сданных ДЗ, фото и PDF, «верно из всего» и комментарий. */
(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var status = 'new', items = [], target = null, part2Max = 17, part2 = [];

  function api(method, url, body) {
    var opts = { method: method, credentials: 'same-origin', headers: {} };
    if (body !== undefined) { opts.body = JSON.stringify(body); opts.headers['Content-Type'] = 'application/json'; }
    return fetch(url, opts).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (d) {
        if (!r.ok) { var e = new Error(typeof d.detail === 'string' ? d.detail : 'Сервер ответил ошибкой ' + r.status + '.'); e.status = r.status; throw e; }
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
  function plural(n, one, few, many) {
    var a = Math.abs(n) % 100, b = a % 10;
    if (a > 10 && a < 20) return many;
    if (b > 1 && b < 5) return few;
    return b === 1 ? one : many;
  }
  function when(iso) {
    if (!iso) return '';
    var d = new Date(iso);
    return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' }) + ', ' + d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
  }
  function msg(text, html) { var m = $('msg'); if (html) m.innerHTML = html; else m.textContent = text || ''; m.hidden = !(text || html); }

  /* ── Просмотр фото ── */
  var view = $('view'), photos = [], at = 0;
  function show(i) {
    at = (i + photos.length) % photos.length;
    $('view-img').src = photos[at].url;
    $('view-img').alt = 'Фото ' + (at + 1) + ' из ' + photos.length;
    $('view-open').href = photos[at].url;
    $('view-count').textContent = (at + 1) + ' / ' + photos.length;
    $('view-prev').hidden = $('view-next').hidden = photos.length < 2;
    view.querySelector('.ck-view__stage').scrollTop = 0;
  }
  function openView(list, i) {
    photos = list; show(i);
    if (view.showModal) view.showModal(); else view.setAttribute('open', '');
  }
  $('view-prev').addEventListener('click', function () { show(at - 1); });
  $('view-next').addEventListener('click', function () { show(at + 1); });
  $('view-close').addEventListener('click', function () { view.close(); });
  view.addEventListener('keydown', function (e) {
    if (e.key === 'ArrowLeft') show(at - 1);
    if (e.key === 'ArrowRight') show(at + 1);
  });

  /* ── Карточка работы ── */
  function card(s) {
    var li = el('li', 'ck-card'); li.id = 's' + s.id;
    if (target === s.id) li.classList.add('is-target');
    var head = el('div', 'ck-card__head');
    var who = el('h2', 'ck-card__who', s.student + ' ');
    var what = s.kind === 'mock'
      ? (s.mock ? 'пробник № ' + s.mock.number + (s.mock.title ? ' · ' + s.mock.title : '') : 'пробник удалён')
      : (s.lesson ? 'занятие № ' + s.lesson.number + (s.lesson.title ? ' · ' + s.lesson.title : '') : 'занятие удалено');
    who.appendChild(el('span', null, '· ' + what));
    head.appendChild(who);
    var meta = el('div', 'ck-card__meta');
    meta.appendChild(el('span', null, 'сдано ' + when(s.created_at)));
    if (s.overdue) meta.appendChild(el('span', 'ck-late', 'срок до сдачи истекал ' + s.overdue + ' ' + plural(s.overdue, 'раз', 'раза', 'раз')));
    if (s.lesson && s.lesson.hw_url) { var a = el('a', null, 'условие ДЗ (PDF)'); a.href = s.lesson.hw_url; a.target = '_blank'; a.rel = 'noopener'; meta.appendChild(a); }
    if (s.mock) { var mv = el('a', null, 'вариант'); mv.href = s.mock.url; mv.target = '_blank'; mv.rel = 'noopener'; meta.appendChild(mv); }
    head.appendChild(meta);
    li.appendChild(head);
    if (s.part1) li.appendChild(el('p', 'ck-part1', 'Первая часть (автопроверка): ' + s.part1.score + ' из ' + s.part1.max + ' первичных' +
      (s.part1.wrong.length ? ' · ошибки в заданиях ' + s.part1.wrong.join(', ') : ' · без ошибок')));
    if (s.purged) li.appendChild(el('p', 'ck-purged', 'Файлы удалены с сайта по сроку хранения; копия — в Telegram.'));
    if (s.notify_error) li.appendChild(el('p', 'ck-warn', 'Бот не смог прислать работу: ' + s.notify_error));

    var grid = el('div', 'ck-files');
    var imgs = s.files.filter(function (f) { return f.type.indexOf('image/') === 0; });
    s.files.forEach(function (f, i) {
      if (f.type.indexOf('image/') === 0) {
        var b = el('button', 'ck-file'); b.type = 'button';
        b.setAttribute('aria-label', 'Открыть фото ' + (imgs.indexOf(f) + 1) + ' крупно');
        var im = el('img'); im.src = f.url; im.alt = ''; im.loading = 'lazy'; b.appendChild(im);
        b.addEventListener('click', function () { openView(imgs, imgs.indexOf(f)); });
        grid.appendChild(b);
      } else {
        var p = el('a', 'ck-file ck-file--pdf'); p.href = f.url; p.target = '_blank'; p.rel = 'noopener';
        p.appendChild(document.createTextNode('PDF')); p.appendChild(el('small', null, f.name || 'файл ' + (i + 1)));
        grid.appendChild(p);
      }
    });
    li.appendChild(grid);
    li.appendChild(s.status === 'checked' && !s.editing ? resultBlock(s) : form(s));
    return li;
  }
  function resultBlock(s) {
    var box = el('div', 'ck-result');
    if (s.kind === 'mock') {
      box.appendChild(el('b', null, '2 часть: ' + s.score + ' из ' + s.max + ' первичных'));
      if (s.task_scores) box.appendChild(el('span', null, Object.keys(s.task_scores).sort(function (x, y) { return x - y; }).map(function (n) { return '№' + n + ': ' + s.task_scores[n]; }).join(' · ')));
      if (s.total) box.appendChild(el('b', 'ck-total', 'итого ' + s.total.primary + ' из ' + s.total.max + ' первичных' + (s.total.test != null ? ' → ' + s.total.test + ' тестовых' : '')));
    } else {
      box.appendChild(el('b', null, s.score + ' из ' + s.max + ' · ' + Math.round(100 * s.score / s.max) + '%'));
    }
    box.appendChild(el('span', null, 'проверил ' + (s.checked_by || '—') + ', ' + when(s.checked_at)));
    var edit = el('button', 'btn btn--small', 'Изменить'); edit.type = 'button';
    edit.addEventListener('click', function () { s.editing = true; render(); });
    box.appendChild(edit);
    if (s.comment) box.appendChild(el('p', null, s.comment));
    if (s.student_notified_at) box.appendChild(el('span', 'ck-sent', 'результат отправлен ученику в Telegram ' + when(s.student_notified_at)));
    else if (s.student_notify_error) box.appendChild(el('span', 'ck-sent ck-sent--no', s.student_notify_error));
    var sh = sheetLine(s);
    if (sh) box.appendChild(sh);
    return box;
  }
  /* Google-таблица: результат записывается фоном; если не вышло — видно здесь, можно повторить */
  var sheetRefresh = null;
  function sheetLine(s) {
    if (!s.sheet) return null;
    var wrap = el('span', 'ck-sent ck-sheet');
    var fresh = s.sheet.synced_at && (!s.checked_at || new Date(s.sheet.synced_at) >= new Date(s.checked_at));
    if (fresh && !s.sheet.error) {
      wrap.textContent = 'записано в таблицу: ' + s.sheet.place;
      return wrap;
    }
    if (s.sheet.error) { wrap.classList.add('ck-sent--no'); wrap.textContent = 'в таблицу не записано: ' + s.sheet.error + ' '; }
    else {
      wrap.textContent = 'записываю в таблицу… ';
      if (!sheetRefresh) sheetRefresh = setTimeout(function () { sheetRefresh = null; load(); }, 6000);
    }
    var again = el('button', 'btn btn--small', 'Записать ещё раз'); again.type = 'button';
    again.addEventListener('click', function () {
      again.disabled = true; again.textContent = 'Записываю…';
      api('POST', '/api/check/submissions/' + s.id + '/sheet').then(function (r) {
        Object.keys(r).forEach(function (k) { s[k] = r[k]; }); render();
      }).catch(function (e) { again.disabled = false; again.textContent = 'Записать ещё раз'; wrap.firstChild.textContent = e.message + ' '; });
    });
    wrap.appendChild(again);
    return wrap;
  }
  function form(s) {
    var f = el('form', 'ck-form'); f.noValidate = true;
    function num(label, value, id) {
      var lab = el('label', null, label);
      var inp = el('input', 'ck-num'); inp.type = 'text'; inp.inputMode = 'numeric'; inp.maxLength = 3; inp.id = id; inp.value = value == null ? '' : value;
      inp.addEventListener('input', function () { var v = inp.value.replace(/\D/g, ''); if (v !== inp.value) inp.value = v; });
      lab.appendChild(inp);
      return [lab, inp];
    }
    var mock = s.kind === 'mock', a = null, b = null, cells = {};
    if (mock) {
      /* вторая часть — по заданиям, как в таблице: сумма считается сама */
      var grid = el('div', 'ck-tasks');
      var sumEl = el('b', 'ck-tasks__sum');
      part2.forEach(function (t) {
        var lab = el('label', 'ck-task');
        var top = el('span', 'ck-task__n', '№ ' + t.n);
        lab.appendChild(top);
        lab.appendChild(el('span', 'ck-task__th', t.theme));
        var row = el('span', 'ck-task__row');
        var inp = el('input', 'ck-num ck-num--s'); inp.type = 'text'; inp.inputMode = 'numeric'; inp.maxLength = 2;
        inp.setAttribute('aria-label', 'Баллы за задание ' + t.n + ' из ' + t.max);
        var v = s.task_scores && s.task_scores[String(t.n)];
        inp.value = v == null ? '' : v;
        inp.addEventListener('input', function () { var x = inp.value.replace(/\D/g, ''); if (x !== inp.value) inp.value = x; total(); });
        row.appendChild(inp); row.appendChild(el('span', 'ck-of', 'из ' + t.max));
        lab.appendChild(row);
        cells[t.n] = { inp: inp, max: t.max };
        grid.appendChild(lab);
      });
      f.appendChild(grid);
      var sumWrap = el('p', 'ck-tasks__total');
      sumWrap.appendChild(document.createTextNode('Вторая часть: ')); sumWrap.appendChild(sumEl);
      f.appendChild(sumWrap);
      var total = function () {
        var sum = 0; Object.keys(cells).forEach(function (n) { sum += +cells[n].inp.value || 0; });
        sumEl.textContent = sum + ' из ' + part2Max + ' первичных' + (s.part1 ? ' · итого с первой частью ' + (sum + s.part1.score) + ' из ' + (part2Max + s.part1.max) : '');
      };
      total();
    } else {
      a = num('Верно', s.score, 'sc-' + s.id); b = num('Всего задач', s.max, 'mx-' + s.id);
      f.appendChild(a[0]); f.appendChild(el('span', 'ck-of', 'из')); f.appendChild(b[0]);
    }
    var cl = el('label', 'ck-comment', 'Комментарий для ученика');
    var ta = el('textarea'); ta.maxLength = 3000; ta.value = s.comment || ''; ta.placeholder = 'Например: №4 — cos 60° = 1/2, а не √3/2';
    cl.appendChild(ta); f.appendChild(cl);
    var save = el('button', 'btn btn--solid', s.status === 'checked' ? 'Сохранить' : 'Проверено'); save.type = 'submit';
    f.appendChild(save);
    if (s.editing) {
      var cancel = el('button', 'btn', 'Отмена'); cancel.type = 'button';
      cancel.addEventListener('click', function () { s.editing = false; render(); });
      f.appendChild(cancel);
    }
    var err = el('p', 'form-error'); err.hidden = true; f.appendChild(err);
    f.addEventListener('submit', function (e) {
      e.preventDefault();
      var payload = { comment: ta.value.trim() };
      if (mock) {
        var ts = {}, bad = null;
        Object.keys(cells).forEach(function (n) {
          var v = cells[n].inp.value.trim();
          if (v === '' || +v > cells[n].max) bad = bad || n;
          ts[n] = +v;
        });
        if (bad) { err.textContent = 'Задание ' + bad + ': впишите баллы от 0 до ' + cells[bad].max + '.'; err.hidden = false; cells[bad].inp.focus(); return; }
        payload.task_scores = ts;
      } else {
        var sc = a[1].value.trim(), mx = b[1].value.trim();
        if (!sc || !mx) { err.textContent = 'Впишите, сколько верно и из скольких.'; err.hidden = false; return; }
        if (+sc > +mx) { err.textContent = '«Верно» не может быть больше, чем всего задач.'; err.hidden = false; return; }
        payload.score = +sc; payload.max_score = +mx;
      }
      save.disabled = true; err.hidden = true;
      api('PUT', '/api/check/submissions/' + s.id, payload).then(function (r) {
        var wasNew = s.status === 'new';
        Object.keys(r).forEach(function (k) { s[k] = r[k]; }); s.editing = false;
        if (wasNew && status === 'new') { counts.new--; counts.checked++; items = items.filter(function (x) { return x.id !== s.id; }); }
        render();
      }).catch(function (e2) { err.textContent = e2.message; err.hidden = false; save.disabled = false; });
    });
    return f;
  }

  var counts = { new: 0, checked: 0 };
  function render() {
    $('c-new').textContent = counts.new; $('c-checked').textContent = counts.checked;
    var list = $('list'); list.textContent = '';
    if (!items.length) list.appendChild(el('li', 'ck-empty', status === 'new' ? 'Новых работ нет. Когда ученик сдаст ДЗ, оно появится здесь, а бот пришлёт его вам.' : 'Проверенных работ пока нет.'));
    items.forEach(function (s) { list.appendChild(card(s)); });
  }
  function load() {
    return api('GET', '/api/check/submissions?status=' + status).then(function (d) {
      items = d.items; counts = d.counts; part2Max = d.part2_max || 17; part2 = d.part2 || []; render();
      if (target) {
        var n = $('s' + target);
        if (n) n.scrollIntoView({ block: 'start' });
      }
    });
  }
  function setTab(st) {
    status = st;
    document.querySelectorAll('.ck-tabs__btn').forEach(function (b) { b.setAttribute('aria-selected', String(b.dataset.status === st)); });
    return load();
  }
  document.querySelectorAll('.ck-tabs__btn').forEach(function (b) {
    b.addEventListener('click', function () { target = null; setTab(b.dataset.status); });
  });

  /* ── Старт: ссылка из бота вида /check/#s15 ведёт к нужной работе ── */
  var m = /^#s(\d+)$/.exec(location.hash || '');
  if (m) target = +m[1];
  api('GET', '/api/check/me').then(function (me) {
    $('who').textContent = me.name;
    $('body').hidden = false;
    return setTab('new').then(function () {
      if (target && !$('s' + target)) return setTab('checked');
    });
  }).catch(function (e) {
    if (e.status === 401) msg(null, 'Эта страница — для кураторов. <a href="/account/?next=/check/">Войдите в личный кабинет</a> под аккаунтом куратора. Если вы куратор, а страница не открывается, попросите Артура отметить ваш аккаунт.');
    else msg(e.message);
  });
})();
