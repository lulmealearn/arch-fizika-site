/* Увеличение: полноэкранный просмотр по клику или тапу (лупы при наведении нет — владелец её убрал).
   Разметка: <figure class="zoomable" data-zoom="img" data-full="большая.webp"> с <img> внутри
   или data-zoom="html" с блоком [data-zoom-content] — он клонируется в просмотр. */
(function () {
  'use strict';

  /* ── Масштаб «картинки» из HTML: вписать широкий блок в карточку ── */
  function fit(box) {
    var inner = box.firstElementChild;
    if (!inner) return;
    inner.style.transform = 'none';
    var natural = inner.scrollWidth, avail = box.clientWidth;
    var s = Math.min(1, avail / natural);
    inner.style.transform = 'scale(' + s + ')';
    box.style.height = Math.ceil(inner.offsetHeight * s) + 'px';
  }
  var fits = document.querySelectorAll('.fit');
  fits.forEach(fit);
  if ('ResizeObserver' in window) {
    var ro = new ResizeObserver(function (es) { es.forEach(function (e) { fit(e.target); }); });
    fits.forEach(function (b) { ro.observe(b); });
  } else {
    window.addEventListener('resize', function () { fits.forEach(fit); });
  }


  /* ── Просмотр на весь экран ── */
  var box = null, lastFocus = null;
  function ensureBox() {
    if (box) return box;
    box = document.createElement('div');
    box.className = 'lightbox';
    box.setAttribute('role', 'dialog');
    box.setAttribute('aria-modal', 'true');
    box.setAttribute('aria-label', 'Просмотр крупно');
    box.innerHTML =
      '<div class="lightbox__bar"><span class="lightbox__hint"></span>' +
      '<button class="lightbox__close" type="button" aria-label="Закрыть">' +
      '<svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M3 3l12 12M15 3L3 15"/></svg></button></div>' +
      '<div class="lightbox__stage"></div>';
    document.body.appendChild(box);
    box.querySelector('.lightbox__close').addEventListener('click', close);
    box.addEventListener('click', function (e) { if (e.target === box || e.target.classList.contains('lightbox__stage')) close(); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && box.classList.contains('is-open')) close(); });
    return box;
  }
  function open(fig) {
    var b = ensureBox(), stage = b.querySelector('.lightbox__stage'), hint = b.querySelector('.lightbox__hint');
    stage.textContent = '';
    stage.classList.remove('is-2x');
    if (fig.getAttribute('data-zoom') === 'img') {
      var src = fig.getAttribute('data-full') || fig.querySelector('img').src;
      var img = document.createElement('img');
      img.src = src; img.alt = fig.querySelector('img').alt;
      img.addEventListener('click', function (e) {
        e.stopPropagation();
        var rect = img.getBoundingClientRect();
        var fx = (e.clientX - rect.left) / rect.width, fy = (e.clientY - rect.top) / rect.height;
        stage.classList.toggle('is-2x');
        if (stage.classList.contains('is-2x')) {
          stage.scrollLeft = fx * stage.scrollWidth - stage.clientWidth / 2;
          stage.scrollTop = fy * stage.scrollHeight - stage.clientHeight / 2;
        }
      });
      stage.appendChild(img);
      hint.textContent = 'Нажми на картинку, чтобы приблизить ещё';
    } else {
      var src2 = fig.querySelector('[data-zoom-content]');
      var clone = src2.firstElementChild.cloneNode(true);
      clone.style.transform = 'none';
      var wrap = document.createElement('div'); wrap.className = 'lightbox__html';
      wrap.appendChild(clone); stage.appendChild(wrap);
      hint.textContent = 'Таблица листается вбок, если не влезает';
    }
    lastFocus = document.activeElement;
    b.classList.add('is-open');
    document.body.classList.add('no-scroll');
    setTimeout(function () { b.querySelector('.lightbox__close').focus({ preventScroll: true }); }, 30);
  }
  function close() {
    if (!box) return;
    box.classList.remove('is-open');
    document.body.classList.remove('no-scroll');
    if (lastFocus && lastFocus.focus) lastFocus.focus({ preventScroll: true });
  }

  document.querySelectorAll('.zoomable').forEach(function (fig) {
    fig.addEventListener('click', function () { open(fig); });
    fig.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(fig); } });
  });
})();
