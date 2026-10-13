/**
 * Связь сайта с таблицей «Ученики — учёт занятий».
 *
 * Это ОТДЕЛЬНЫЙ проект Apps Script (не тот, где живёт бот): у веб-приложения своя функция doPost,
 * и она не должна мешать боту. Как установить — tools/sheets/README.md.
 *
 * Что умеет (сайт присылает POST с JSON и секретом):
 *   ping    — проверить связь;
 *   tabs    — список вкладок учеников с их chat_id;
 *   find    — какая вкладка у ученика (по chat_id или имени вкладки);
 *   hw      — отметить сданное ДЗ (а после проверки — верных, всего, комментарий) в строке с той же темой урока;
 *   mock    — записать баллы пробника по заданиям в столбец с номером пробника на вкладке «П-…»;
 *   report  — отдать занятия и пробники ученика для ежемесячного отчёта.
 *
 * Сайт ничего не удаляет и не трогает формулы: пишет только «ДЗ сдал», «Дата сдачи», «Верных», «Всего»,
 * «Комментарий к ДЗ» и баллы пробника.
 */

// ▼▼▼ Две строки, которые нужно заполнить ▼▼▼
const SHEET_ID = '1wbCshRz43Jh08ujqmZDFCEQDI_xsMtjT8VXNqMvgsIs'; // id таблицы — из её адреса
const SECRET = 'ВСТАВЬТЕ_СЕКРЕТ_ИЗ_run.py_set-sheet';            // тот же секрет, что в .env сайта
// ▲▲▲

const SERVICE_TABS = /^(_|П-|Сводка$|Шаблон)/; // не вкладки учеников
const COL = { // заголовки столбцов на вкладке ученика (ищем по названию — раскладка может меняться)
  date: 'Дата занятия', topic: 'Тема урока', conf: 'Уверенность (1–5)', hinder: 'Что мешало',
  hw: '№ ДЗ', done: 'ДЗ сдал', submitted: 'Дата сдачи', correct: 'Верных', total: 'Всего',
  rno: 'РНО сделан', comment: 'Комментарий к ДЗ'
};
const MOCK_FIRST_COL = 4;  // столбец D — пробник № 1
const MOCK_COUNT = 40;
const MOCK_DATE_ROW = 2;
const MOCK_TASK_ROW = 6;   // строка задания № 1
const MOCK_TASK_ROWS = 30; // строки 6–35

function doPost(e) {
  let body;
  try {
    body = JSON.parse((e && e.postData && e.postData.contents) || '{}');
  } catch (err) {
    return out_({ ok: false, error: 'Сайт прислал не JSON.' });
  }
  if (!SECRET || SECRET.indexOf('ВСТАВЬТЕ') === 0) return out_({ ok: false, error: 'В скрипте не вписан SECRET.' });
  if (body.secret !== SECRET) return out_({ ok: false, error: 'Неверный секрет: сравните SECRET в скрипте и SHEETS_SECRET в .env сайта.' });
  try {
    const ss = SpreadsheetApp.openById(SHEET_ID);
    const actions = { ping: ping_, tabs: tabs_, find: find_, hw: hw_, mock: mock_, report: report_ };
    const fn = actions[body.action];
    if (!fn) return out_({ ok: false, error: 'Неизвестное действие: ' + body.action });
    if (body.action === 'hw' || body.action === 'mock') {
      const lock = LockService.getScriptLock();
      lock.waitLock(20000);
      try { return out_(fn(ss, body)); } finally { lock.releaseLock(); }
    }
    return out_(fn(ss, body));
  } catch (err) {
    return out_({ ok: false, error: String(err && err.message || err) });
  }
}

function doGet() {
  return out_({ ok: true, hint: 'Это адрес для сайта. Открывать его в браузере не нужно.' });
}

function out_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

// ── Вкладки ──
function ping_(ss) {
  return { ok: true, title: ss.getName() };
}

function studentTabs_(ss) {
  return ss.getSheets().filter(function (sh) { return !SERVICE_TABS.test(sh.getName()); });
}

/** chat_id, записанные на вкладке ученика: справа от подписи «chat_id:» в первой строке. */
function chatIds_(sh) {
  const last = sh.getLastColumn();
  if (last < 2) return [];
  const row = sh.getRange(1, 1, 1, last).getValues()[0];
  const ids = [];
  for (let i = 0; i < row.length - 1; i++) {
    if (String(row[i]).trim().toLowerCase() === 'chat_id:' && row[i + 1] !== '' && row[i + 1] !== null) {
      const id = idStr_(row[i + 1]);
      if (id && ids.indexOf(id) < 0) ids.push(id);
    }
  }
  return ids;
}

function idStr_(v) {
  if (typeof v === 'number') return String(Math.round(v));
  return String(v).trim().replace(/\.0+$/, '');
}

function tabs_(ss) {
  return {
    ok: true,
    tabs: studentTabs_(ss).map(function (sh) {
      const m = mockTab_(ss, sh);
      return { name: sh.getName(), chat_ids: chatIds_(sh), mock_tab: m ? m.getName() : null };
    })
  };
}

function studentTab_(ss, body) {
  if (body.tab) {
    const sh = ss.getSheetByName(String(body.tab));
    if (!sh) throw new Error('Нет вкладки «' + body.tab + '».');
    return sh;
  }
  const id = body.chat_id ? idStr_(body.chat_id) : '';
  if (!id) throw new Error('У ученика на сайте не указан ни chat id, ни вкладка в таблице.');
  const found = studentTabs_(ss).filter(function (sh) { return chatIds_(sh).indexOf(id) >= 0; });
  if (!found.length) throw new Error('Ни на одной вкладке нет chat_id ' + id + '. Впишите его в первую строку вкладки ученика или укажите вкладку на сайте.');
  if (found.length > 1) throw new Error('chat_id ' + id + ' есть на нескольких вкладках: ' + found.map(function (s) { return s.getName(); }).join(', ') + '. Укажите вкладку на сайте.');
  return found[0];
}

/** «3 (Егор)» → «П-3 (Егор)» или «П-3»; «Тест» → «П-Тест». */
function mockTab_(ss, sh) {
  const name = sh.getName();
  const exact = ss.getSheetByName('П-' + name);
  if (exact) return exact;
  const num = /^(\d+)/.exec(name);
  if (!num) return null;
  const re = new RegExp('^П-' + num[1] + '(\\D|$)');
  const all = ss.getSheets().filter(function (s) { return re.test(s.getName()); });
  return all.length ? all[0] : null;
}

function find_(ss, body) {
  const sh = studentTab_(ss, body);
  const m = mockTab_(ss, sh);
  return { ok: true, tab: sh.getName(), mock_tab: m ? m.getName() : null, chat_ids: chatIds_(sh) };
}

// ── Занятия и ДЗ ──
function columns_(sh) {
  const head = sh.getRange(1, 1, 1, sh.getLastColumn()).getValues()[0].map(function (h) { return String(h).trim(); });
  const cols = {};
  Object.keys(COL).forEach(function (k) {
    const i = head.indexOf(COL[k]);
    cols[k] = i >= 0 ? i + 1 : 0;
  });
  if (!cols.topic || !cols.hw) throw new Error('На вкладке «' + sh.getName() + '» нет столбцов «Тема урока» и «№ ДЗ».');
  return cols;
}

function norm_(s) {
  return String(s == null ? '' : s).toLowerCase().replace(/ё/g, 'е').replace(/[«»"'.,:;!?()\[\]–—-]/g, ' ').replace(/\s+/g, ' ').trim();
}

function lessonRows_(sh, cols) {
  const n = sh.getLastRow() - 1;
  if (n < 1) return [];
  const values = sh.getRange(2, 1, n, sh.getLastColumn()).getValues();
  const rows = [];
  values.forEach(function (r, i) {
    const get = function (k) { return cols[k] ? r[cols[k] - 1] : ''; };
    if (get('date') === '' && get('topic') === '' && get('hw') === '') return;
    rows.push({
      row: i + 2, date: get('date') instanceof Date ? get('date').toISOString() : (get('date') || null),
      topic: String(get('topic') || ''), conf: num_(get('conf')), hinder: String(get('hinder') || ''),
      hw: num_(get('hw')), done: get('done') === true || String(get('done')).toUpperCase() === 'TRUE',
      submitted: get('submitted') instanceof Date ? get('submitted').toISOString() : null,
      correct: num_(get('correct')), total: num_(get('total')),
      rno: get('rno') === true || String(get('rno')).toUpperCase() === 'TRUE',
      comment: String(get('comment') || '')
    });
  });
  return rows;
}

function num_(v) {
  if (v === '' || v === null || v === undefined || typeof v === 'boolean') return null;
  const x = Number(String(v).replace(',', '.'));
  return isFinite(x) ? x : null;
}

/** Строка с той же темой: сначала точное совпадение, потом «одна тема содержит другую». Если строк несколько —
 *  та, что прислал сайт в прошлый раз (row), иначе первая ещё не проверенная, иначе последняя. */
function matchRow_(rows, topic, hint) {
  const t = norm_(topic);
  if (!t) return { error: 'У занятия на сайте нет темы.' };
  let found = rows.filter(function (r) { return norm_(r.topic) === t; });
  if (!found.length) {
    found = rows.filter(function (r) {
      const x = norm_(r.topic);
      return x && (x.indexOf(t) >= 0 || t.indexOf(x) >= 0);
    });
  }
  if (!found.length) return { error: 'нет строки с темой «' + topic + '»' };
  if (hint) {
    const same = found.filter(function (r) { return r.row === hint; });
    if (same.length) return { row: same[0] };
  }
  const open = found.filter(function (r) { return r.correct === null; });
  return { row: open.length ? open[0] : found[found.length - 1] };
}

function hw_(ss, body) {
  const sh = studentTab_(ss, body);
  const cols = columns_(sh);
  const m = matchRow_(lessonRows_(sh, cols), body.topic, body.row);
  if (m.error) return { ok: false, tab: sh.getName(), error: 'На вкладке «' + sh.getName() + '» ' + m.error + '. Поправьте тему в таблице или в занятии на сайте.' };
  const r = m.row.row;
  const set = function (k, v) { if (cols[k]) sh.getRange(r, cols[k]).setValue(v); };
  set('done', true);
  if (body.submitted_at) set('submitted', new Date(body.submitted_at));
  if (body.correct !== undefined && body.correct !== null) {  // работа проверена; до проверки — только «сдал» и дата
    set('correct', Number(body.correct));
    set('total', Number(body.total));
    set('comment', String(body.comment || ''));
  }
  return { ok: true, tab: sh.getName(), row: r, hw: m.row.hw };
}

// ── Пробники ──
function mockLayout_(mt) {
  const rows = mt.getRange(MOCK_TASK_ROW, 1, MOCK_TASK_ROWS, 3).getValues();
  const tasks = [];
  rows.forEach(function (r, i) {
    const n = num_(r[0]);
    if (n !== null && (num_(r[2]) !== null || String(r[1]).trim())) tasks.push({ n: n, theme: String(r[1] || ''), max: num_(r[2]), row: MOCK_TASK_ROW + i });
  });
  return tasks;
}

function mock_(ss, body) {
  const sh = studentTab_(ss, body);
  const mt = mockTab_(ss, sh);
  if (!mt) return { ok: false, tab: sh.getName(), error: 'Для вкладки «' + sh.getName() + '» нет вкладки пробников «П-…».' };
  const n = Number(body.number);
  if (!(n >= 1 && n <= MOCK_COUNT)) return { ok: false, tab: mt.getName(), error: 'На вкладке «' + mt.getName() + '» столбцы только для пробников 1–' + MOCK_COUNT + ', а пришёл № ' + body.number + '.' };
  const col = MOCK_FIRST_COL + n - 1;
  const head = num_(mt.getRange(1, col).getValue());
  if (head !== null && head !== n) return { ok: false, tab: mt.getName(), error: 'На вкладке «' + mt.getName() + '» над столбцом ' + col + ' стоит № ' + head + ', а не ' + n + '.' };
  const tasks = mockLayout_(mt);
  const scores = body.scores || {};
  let written = 0;
  tasks.forEach(function (t) {
    const v = scores[String(t.n)];
    if (v === undefined || v === null || v === '') return;
    mt.getRange(t.row, col).setValue(Number(v));
    written++;
  });
  if (body.date) mt.getRange(MOCK_DATE_ROW, col).setValue(new Date(body.date));
  return { ok: true, tab: mt.getName(), column: col, written: written };
}

// ── Отчёт ──
function report_(ss, body) {
  const sh = studentTab_(ss, body);
  const cols = columns_(sh);
  const out = { ok: true, tab: sh.getName(), lessons: lessonRows_(sh, cols), mocks: [], tasks: [], mock_tab: null };
  const mt = mockTab_(ss, sh);
  if (mt) {
    out.mock_tab = mt.getName();
    const tasks = mockLayout_(mt);
    out.tasks = tasks.map(function (t) { return { n: t.n, theme: t.theme, max: t.max }; });
    const width = MOCK_COUNT;
    const head = mt.getRange(1, MOCK_FIRST_COL, MOCK_DATE_ROW, width).getValues();
    const grid = mt.getRange(MOCK_TASK_ROW, MOCK_FIRST_COL, MOCK_TASK_ROWS, width).getValues();
    for (let c = 0; c < width; c++) {
      const scores = {};
      let any = false;
      tasks.forEach(function (t) {
        const v = num_(grid[t.row - MOCK_TASK_ROW][c]);
        if (v !== null) { scores[String(t.n)] = v; any = true; }
      });
      if (!any) continue;
      const d = head[MOCK_DATE_ROW - 1][c];
      out.mocks.push({ n: num_(head[0][c]) || c + 1, date: d instanceof Date ? d.toISOString() : null, scores: scores });
    }
  }
  return out;
}

/** Запустите вручную из редактора (▶ testAccess), чтобы Google спросил разрешение на доступ к таблице. */
function testAccess() {
  const ss = SpreadsheetApp.openById(SHEET_ID);
  Logger.log('Таблица: ' + ss.getName() + ', вкладок учеников: ' + studentTabs_(ss).length);
}
