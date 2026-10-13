/* Проверка работ кураторами: очередь сданных ДЗ, фото и PDF, «верно из всего» и комментарий. */
(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var status = 'new', items = [], target = null;

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
    who.appendChild(el('span', null, '· ' + (s.lesson ? 'занятие № ' + s.lesson.number + (s.lesson.title ? ' · ' + s.lesson.title : '') : 'занятие удалено')));
    head.appendChild(who);
    var meta = el('div', 'ck-card__meta');
    meta.appendChild(el('span', null, 'сдано ' + when(s.created_at)));
    if (s.overdue) meta.appendChild(el('span', 'ck-late', 'срок до сдачи истекал ' + s.overdue + ' ' + plural(s.overdue, 'раз', 'раза', 'раз')));
    if (s.lesson && s.lesson.hw_url) { var a = el('a', null, 'условие ДЗ (PDF)'); a.href = s.lesson.hw_url; a.target = '_blank'; a.rel = 'noopener'; meta.appendChild(a); }
    head.appendChild(meta);
    li.appendChild(head);
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
    box.appendChild(el('b', null, s.score + ' из ' + s.max + ' · ' + Math.round(100 * s.score / s.max) + '%'));
    box.appendChild(el('span', null, 'проверил ' + (s.checked_by || '—') + ', ' + when(s.checked_at)));
    var edit = el('button', 'btn btn--small', 'Изменить'); edit.type = 'button';
    edit.addEventListener('click', function () { s.editing = true; render(); });
    box.appendChild(edit);
    if (s.comment) box.appendChild(el('p', null, s.comment));
    return box;
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
    var a = num('Верно', s.score, 'sc-' + s.id), b = num('Всего задач', s.max, 'mx-' + s.id);
    f.appendChild(a[0]); f.appendChild(el('span', 'ck-of', 'из')); f.appendChild(b[0]);
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
      var sc = a[1].value.trim(), mx = b[1].value.trim();
      if (!sc || !mx) { err.textContent = 'Впишите, сколько верно и из скольких.'; err.hidden = false; return; }
      if (+sc > +mx) { err.textContent = '«Верно» не может быть больше, чем всего задач.'; err.hidden = false; return; }
      save.disabled = true; err.hidden = true;
      api('PUT', '/api/check/submissions/' + s.id, { score: +sc, max_score: +mx, comment: ta.value.trim() }).then(function (r) {
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
      items = d.items; counts = d.counts; render();
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
