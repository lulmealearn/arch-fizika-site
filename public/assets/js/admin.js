/* Админка: вход, список с перестановкой, форма загрузки и редактирования. Без зависимостей. */
(function () {
  'use strict';

  var $ = function (id) { return document.getElementById(id); };
  var views = ['loading', 'setup', 'login', 'list'];
  var state = { sections: [], items: [], editing: null, slugTouched: false, removeCover: false, coverUrl: null };

  /* ── Сервер ── */
  function api(method, url, body) {
    var opts = { method: method, credentials: 'same-origin', headers: {} };
    if (body instanceof FormData) opts.body = body;
    else if (body !== undefined) { opts.body = JSON.stringify(body); opts.headers['Content-Type'] = 'application/json'; }
    return fetch(url, opts).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (data) {
        if (r.status === 401 && url.indexOf('/login') < 0) { show('login'); }
        if (!r.ok) {
          var msg = typeof data.detail === 'string' ? data.detail : 'Сервер ответил ошибкой ' + r.status + '.';
          var err = new Error(msg); err.status = r.status; throw err;
        }
        return data;
      });
    }, function () { throw new Error('Нет связи с сервером. Он запущен?'); });
  }

  function show(name) {
    views.forEach(function (v) { $('view-' + v).hidden = v !== name; });
    $('logout').hidden = name !== 'list';
  }

  var toastTimer = null;
  function toast(text, isError) {
    var t = $('toast');
    t.textContent = text; t.classList.toggle('is-error', !!isError); t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.hidden = true; }, isError ? 5000 : 2600);
  }

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function plural(n, one, few, many) {
    var a = n % 10, b = n % 100;
    if (a === 1 && b !== 11) return one;
    if (a >= 2 && a <= 4 && (b < 12 || b > 14)) return few;
    return many;
  }
  var TR = { 'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'e','ж':'zh','з':'z','и':'i','й':'j','к':'k','л':'l','м':'m','н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u','ф':'f','х':'h','ц':'c','ч':'ch','ш':'sh','щ':'sch','ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya' };
  function slugify(s) {
    var out = s.toLowerCase().split('').map(function (c) { return TR[c] !== undefined ? TR[c] : c; }).join('');
    return out.replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 60).replace(/-+$/, '');
  }
  function sectionBy(id) {
    for (var i = 0; i < state.sections.length; i++) if (state.sections[i].id === id) return state.sections[i];
    return { id: id, label: id, color: '#181820', tint: '#ece9e0', ink: '#181820' };
  }

  /* ── Вход и выход ── */
  function boot() {
    api('GET', '/api/admin/me').then(function (me) {
      if (!me.configured) return show('setup');
      if (!me.authenticated) { show('login'); $('login-password').focus(); return; }
      loadList();
    }).catch(function (e) { show('login'); showError('login-error', e.message); });
  }

  function showError(id, msg) { var n = $(id); n.textContent = msg || ''; n.hidden = !msg; }

  $('login-form').addEventListener('submit', function (e) {
    e.preventDefault();
    var pw = $('login-password').value;
    if (!pw) return showError('login-error', 'Введи пароль.');
    showError('login-error', '');
    var btn = this.querySelector('button[type="submit"]'); btn.disabled = true;
    api('POST', '/api/admin/login', { password: pw }).then(function () {
      $('login-password').value = '';
      loadList();
    }).catch(function (err) { showError('login-error', err.message); })
      .then(function () { btn.disabled = false; });
  });

  $('logout').addEventListener('click', function () {
    api('POST', '/api/admin/logout').then(function () { show('login'); });
  });

  /* ── Список ── */
  function loadList() {
    return api('GET', '/api/admin/visualizations').then(function (d) {
      state.sections = d.sections; state.items = d.items;
      renderList(); show('list');
    }).catch(function (e) { toast(e.message, true); });
  }

  function renderList() {
    var list = $('adm-list');
    list.textContent = '';
    var pub = state.items.filter(function (i) { return i.is_published; }).length;
    var drafts = state.items.length - pub;
    $('list-summary').textContent = pub + ' ' + plural(pub, 'опубликована', 'опубликованы', 'опубликовано') +
      (drafts ? ' · ' + drafts + ' ' + plural(drafts, 'черновик', 'черновика', 'черновиков') : '');

    if (!state.items.length) {
      var li = el('li', 'empty-list', 'Пока пусто. Нажми «Добавить», чтобы загрузить первую визуализацию.');
      list.appendChild(li);
      return;
    }
    state.items.forEach(function (it, idx) { list.appendChild(row(it, idx)); });
  }

  function row(it, idx) {
    var s = sectionBy(it.section);
    var li = el('li', 'adm-row' + (it.is_published ? '' : ' is-draft'));
    li.dataset.pk = it.pk;

    var handle = el('button', 'handle', '⠿');
    handle.type = 'button'; handle.setAttribute('aria-label', 'Перетащить'); handle.tabIndex = -1;
    handle.addEventListener('mousedown', function () { li.draggable = true; });
    handle.addEventListener('mouseup', function () { li.draggable = false; });
    li.addEventListener('dragstart', function (e) {
      dragEl = li; startOrder = currentOrder();
      li.classList.add('is-dragging');
      e.dataTransfer.effectAllowed = 'move';
      try { e.dataTransfer.setData('text/plain', String(it.pk)); } catch (err) { /* старые браузеры */ }
    });
    li.addEventListener('dragend', finishDrag);

    var arrows = el('div', 'arrows');
    var up = el('button', null, '▲'); up.type = 'button'; up.setAttribute('aria-label', 'Выше: ' + it.title); up.disabled = idx === 0;
    var down = el('button', null, '▼'); down.type = 'button'; down.setAttribute('aria-label', 'Ниже: ' + it.title); down.disabled = idx === state.items.length - 1;
    up.addEventListener('click', function () { move(idx, -1); });
    down.addEventListener('click', function () { move(idx, 1); });
    arrows.appendChild(up); arrows.appendChild(down);

    var folder = el('div', 'mini-folder'); folder.setAttribute('aria-hidden', 'true');
    var tab = el('span', 'tab', pad(idx + 1)); tab.style.background = s.color;
    var body = el('span', 'body'); body.style.background = s.tint;
    var sheet = el('span', 'sheet');
    if (it.cover) { var img = el('img'); img.src = '/' + it.cover; img.alt = ''; sheet.appendChild(img); }
    else {  /* как в хранилище: иконка визуализации, иначе иконка раздела */
      var ic = el('img', 'sheet__icon'), tries = ['/assets/icons/viz/' + (it.slug || it.id) + '.svg', '/assets/icons/viz/_' + it.section + '.svg'];
      ic.alt = ''; ic.onerror = function () { tries.shift(); if (tries.length) ic.src = tries[0]; else ic.remove(); }; ic.src = tries[0]; sheet.appendChild(ic);
    }
    folder.appendChild(tab); folder.appendChild(body); folder.appendChild(sheet);

    var text = el('div', 'adm-row__text');
    text.appendChild(el('h2', 'adm-row__title', it.title));
    var meta = [s.label, it.parts].filter(Boolean).join(' · ');
    text.appendChild(el('span', 'adm-row__meta', meta + '  ·  /viz/' + it.file));

    var status = el('button', 'status ' + (it.is_published ? 'status--on' : 'status--off'), it.is_published ? 'На сайте' : 'Черновик');
    status.type = 'button';
    status.title = it.is_published ? 'Скрыть от учеников' : 'Опубликовать';
    status.addEventListener('click', function () { togglePublish(it, status); });

    var actions = el('div', 'row-actions');
    var open = el('a', 'btn btn--small', 'Открыть'); open.href = '/viz/' + it.file; open.target = '_blank'; open.rel = 'noopener';
    var edit = el('button', 'btn btn--small', 'Изменить'); edit.type = 'button';
    edit.addEventListener('click', function () { openEditor(it); });
    var del = el('button', 'btn btn--small btn--danger', 'Удалить'); del.type = 'button';
    del.addEventListener('click', function () { armDelete(del, it); });
    actions.appendChild(open); actions.appendChild(edit); actions.appendChild(del);

    li.appendChild(handle); li.appendChild(arrows); li.appendChild(folder); li.appendChild(text);
    li.appendChild(status); li.appendChild(actions);
    return li;
  }

  function togglePublish(it, btn) {
    btn.disabled = true;
    var fd = new FormData(); fd.append('is_published', it.is_published ? 'false' : 'true');
    api('PATCH', '/api/admin/visualizations/' + it.pk, fd).then(function (v) {
      toast(v.is_published ? 'Опубликовано: ученики видят' : 'Скрыто: теперь это черновик');
      return loadList();
    }).catch(function (e) { toast(e.message, true); btn.disabled = false; });
  }

  function armDelete(btn, it) {
    if (btn.classList.contains('is-armed')) {
      btn.disabled = true;
      api('DELETE', '/api/admin/visualizations/' + it.pk).then(function () {
        toast('Удалено: ' + it.title); return loadList();
      }).catch(function (e) { toast(e.message, true); btn.disabled = false; });
      return;
    }
    btn.classList.add('is-armed'); btn.textContent = 'Точно удалить?';
    setTimeout(function () { if (btn.isConnected) { btn.classList.remove('is-armed'); btn.textContent = 'Удалить'; } }, 3500);
  }

  /* ── Порядок ── */
  var dragEl = null, startOrder = null;
  function currentOrder() {
    return Array.prototype.map.call($('adm-list').children, function (li) { return Number(li.dataset.pk); }).filter(Boolean);
  }
  $('adm-list').addEventListener('dragover', function (e) {
    if (!dragEl) return;
    e.preventDefault();
    var target = e.target.closest ? e.target.closest('.adm-row') : null;
    if (!target || target === dragEl) return;
    var r = target.getBoundingClientRect();
    var after = e.clientY > r.top + r.height / 2;
    target.parentNode.insertBefore(dragEl, after ? target.nextSibling : target);
  });
  $('adm-list').addEventListener('drop', function (e) { e.preventDefault(); });
  function finishDrag() {
    if (!dragEl) return;
    dragEl.classList.remove('is-dragging'); dragEl.draggable = false;
    var order = currentOrder();
    dragEl = null;
    if (startOrder && order.join() !== startOrder.join()) saveOrder(order);
  }
  function move(idx, dir) {
    var j = idx + dir;
    if (j < 0 || j >= state.items.length) return;
    var ids = state.items.map(function (i) { return i.pk; });
    var t = ids[idx]; ids[idx] = ids[j]; ids[j] = t;
    saveOrder(ids);
  }
  function saveOrder(ids) {
    api('PUT', '/api/admin/order', { ids: ids }).then(function (d) {
      state.items = d.items; renderList(); toast('Порядок сохранён');
    }).catch(function (e) { toast(e.message, true); loadList(); });
  }

  /* ── Редактор ── */
  var editor = $('editor');
  var lastFocus = null;

  $('add-btn').addEventListener('click', function () { openEditor(null); });
  editor.querySelectorAll('[data-close-editor]').forEach(function (b) { b.addEventListener('click', closeEditor); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && editor.classList.contains('is-open')) closeEditor(); });

  function fillSections(selected) {
    var sel = $('f-section'); sel.textContent = '';
    state.sections.forEach(function (s) {
      var o = el('option', null, s.label); o.value = s.id; if (s.id === selected) o.selected = true; sel.appendChild(o);
    });
    paintSectionDot();
  }
  function paintSectionDot() { $('section-dot').style.background = sectionBy($('f-section').value).color; }
  $('f-section').addEventListener('change', paintSectionDot);

  function renderTagSuggest() {
    var box = $('tag-suggest'); box.textContent = '';
    var have = $('f-tags').value.split(',').map(function (t) { return t.trim().toLowerCase(); });
    var all = [];
    state.items.forEach(function (i) { (i.tags || []).forEach(function (t) { if (all.indexOf(t) < 0) all.push(t); }); });
    all.filter(function (t) { return have.indexOf(t.toLowerCase()) < 0; }).slice(0, 12).forEach(function (t) {
      var b = el('button', null, '+ ' + t); b.type = 'button';
      b.addEventListener('click', function () {
        var v = $('f-tags').value.trim();
        $('f-tags').value = v ? v.replace(/,\s*$/, '') + ', ' + t : t;
        renderTagSuggest();
      });
      box.appendChild(b);
    });
  }
  $('f-tags').addEventListener('input', renderTagSuggest);

  function setDescCounter() { $('desc-counter').textContent = $('f-description').value.length + ' / 600'; }
  $('f-description').addEventListener('input', setDescCounter);

  function setCoverPreview(src, label) {
    var img = $('cover-preview');
    if (src) { img.src = src; img.hidden = false; } else { img.removeAttribute('src'); img.hidden = true; }
    $('cover-text').textContent = label;
    $('cover-drop').classList.toggle('has-file', !!src);
    $('cover-remove').hidden = !src;
  }

  function openEditor(item) {
    state.editing = item; state.slugTouched = !!item; state.removeCover = false;
    $('editor-form').reset();
    showError('editor-error', '');
    $('editor-title').textContent = item ? 'Изменить визуализацию' : 'Новая визуализация';
    $('html-label').textContent = item ? 'Заменить HTML-файл (необязательно)' : 'HTML-файл визуализации *';
    $('html-drop-text').textContent = item ? 'Сейчас: /viz/' + item.file + '. Перетащи новый файл, чтобы заменить' : 'Перетащи .html сюда или нажми, чтобы выбрать';
    $('html-drop').classList.remove('has-file');
    fillSections(item ? item.section : (state.sections[0] && state.sections[0].id));
    $('f-title').value = item ? item.title : '';
    $('f-description').value = item ? item.description : '';
    $('f-parts').value = item ? item.parts : '';
    $('f-tags').value = item ? (item.tags || []).join(', ') : '';
    $('f-slug').value = item ? item.slug : '';
    $('f-published').checked = item ? item.is_published : true;
    $('slug-hint').textContent = item ? 'Если поменять адрес, старые ссылки у учеников перестанут работать.' : 'Подставится из названия. Латиница, цифры, дефисы.';
    $('slug-hint').classList.remove('warn');
    if (state.coverUrl) { URL.revokeObjectURL(state.coverUrl); state.coverUrl = null; }
    if (item && item.cover) setCoverPreview('/' + item.cover, 'Текущая обложка. Перетащи новую, чтобы заменить');
    else setCoverPreview(null, 'Нет обложки — будет заглушка. Перетащи картинку или нажми');
    setDescCounter(); renderTagSuggest();

    lastFocus = document.activeElement;
    editor.classList.add('is-open'); editor.setAttribute('aria-hidden', 'false');
    document.body.classList.add('no-scroll');
    $('editor-form').scrollTop = 0;
    setTimeout(function () { (item ? $('f-title') : $('f-html')).focus({ preventScroll: true }); }, 80);
  }

  function closeEditor() {
    editor.classList.remove('is-open'); editor.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('no-scroll');
    if (lastFocus && lastFocus.focus) lastFocus.focus({ preventScroll: true });
  }

  $('f-title').addEventListener('input', function () {
    if (!state.slugTouched) $('f-slug').value = slugify(this.value);
  });
  $('f-slug').addEventListener('input', function () {
    state.slugTouched = true;
    var clean = this.value.toLowerCase().replace(/[^a-z0-9-]/g, '');
    if (clean !== this.value) this.value = clean;
    if (state.editing) $('slug-hint').classList.toggle('warn', this.value !== state.editing.slug);
  });

  /* Перетаскивание файлов: поле input лежит поверх зоны, браузер сам примет файл */
  ['html-drop', 'cover-drop'].forEach(function (id) {
    var zone = $(id);
    zone.addEventListener('dragenter', function () { zone.classList.add('is-over'); });
    zone.addEventListener('dragleave', function () { zone.classList.remove('is-over'); });
    zone.addEventListener('drop', function () { zone.classList.remove('is-over'); });
  });

  $('f-html').addEventListener('change', function () {
    var f = this.files[0];
    if (!f) return;
    $('html-drop').classList.add('has-file');
    $('html-drop-text').textContent = f.name + ' · ' + Math.max(1, Math.round(f.size / 1024)) + ' КБ';
    f.text().then(function (html) {
      var m = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
      if (m && !$('f-title').value.trim()) {
        $('f-title').value = m[1].replace(/\s+/g, ' ').trim();
        $('f-title').dispatchEvent(new Event('input'));
      }
      if (!$('f-parts').value.trim()) {
        var chips = html.match(/data-go="s\d+"/g);
        var n = chips ? chips.length : (html.match(/<h2[\s>]/gi) || []).length;
        if (n > 1) $('f-parts').value = n + ' ' + plural(n, 'раздел', 'раздела', 'разделов');
      }
    }).catch(function () { /* не смогли прочитать — не страшно */ });
  });

  $('f-cover').addEventListener('change', function () {
    var f = this.files[0];
    if (!f) return;
    if (state.coverUrl) URL.revokeObjectURL(state.coverUrl);
    state.coverUrl = URL.createObjectURL(f);
    state.removeCover = false;
    setCoverPreview(state.coverUrl, f.name);
  });
  $('cover-remove').addEventListener('click', function () {
    $('f-cover').value = '';
    if (state.coverUrl) { URL.revokeObjectURL(state.coverUrl); state.coverUrl = null; }
    state.removeCover = !!(state.editing && state.editing.cover);
    setCoverPreview(null, 'Обложки не будет — будет заглушка');
  });

  $('editor-form').addEventListener('submit', function (e) {
    e.preventDefault();
    var item = state.editing;
    var html = $('f-html').files[0];
    var title = $('f-title').value.trim();
    if (!item && !html) return showError('editor-error', 'Выбери HTML-файл визуализации.');
    if (!title) { $('f-title').focus(); return showError('editor-error', 'Впиши название.'); }
    if (html && !/\.html?$/i.test(html.name)) return showError('editor-error', 'Нужен файл с расширением .html.');
    showError('editor-error', '');

    var fd = new FormData();
    if (html) fd.append('html', html);
    fd.append('title', title);
    fd.append('description', $('f-description').value.trim());
    fd.append('section', $('f-section').value);
    fd.append('tags', $('f-tags').value);
    fd.append('parts', $('f-parts').value.trim());
    fd.append('slug', $('f-slug').value.trim());
    fd.append('is_published', $('f-published').checked ? 'true' : 'false');
    var cover = $('f-cover').files[0];
    if (cover) fd.append('cover', cover);
    else if (state.removeCover) fd.append('remove_cover', 'true');

    var btn = $('save-btn'); btn.disabled = true; btn.textContent = 'Сохраняю…';
    var req = item ? api('PATCH', '/api/admin/visualizations/' + item.pk, fd) : api('POST', '/api/admin/visualizations', fd);
    req.then(function (v) {
      closeEditor();
      toast((item ? 'Сохранено: ' : 'Добавлено: ') + v.title + (v.is_published ? '' : ' (черновик)'));
      return loadList();
    }).catch(function (err) {
      showError('editor-error', err.message);
      $('editor-form').scrollTop = 0;
    }).then(function () { btn.disabled = false; btn.textContent = 'Сохранить'; });
  });

  boot();
})();
