/* Всплывающие окна поверх страницы (<dialog class="pop">), открываются кнопками [data-pop="id"].
   Окно «вырастает» из нажатой кнопки; закрывается крестиком, Esc или тапом мимо окна.
   В окне с дипломами тап по диплому показывает его крупно, «← Все дипломы» возвращает к списку. */
(function () {
  'use strict';
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var opener = null;

  function lock(on) { document.documentElement.classList.toggle('is-pop-open', on); }

  function open(d, btn) {
    if (typeof d.showModal !== 'function') return;
    opener = btn;
    showAll(d);
    d.classList.remove('is-closing');
    d.showModal();
    lock(true);
    /* точка роста — центр кнопки в координатах окна (offset* не зависят от анимации масштаба) */
    var box = d.querySelector('.pop__box'), bb = btn.getBoundingClientRect();
    box.style.transformOrigin = (bb.left + bb.width / 2 - box.offsetLeft) + 'px ' + (bb.top + bb.height / 2 - box.offsetTop) + 'px';
    var c = d.querySelector('[data-pop-close]'); if (c) c.focus({ preventScroll: true });
  }

  function close(d) {
    if (!d.open || d.classList.contains('is-closing')) return;
    function done() { d.classList.remove('is-closing'); d.close(); }
    if (reduce) { done(); return; }
    d.classList.add('is-closing');
    setTimeout(done, 180);
  }

  function showAll(d) {
    var g = d.querySelector('.pop__gallery'); if (!g) return;
    g.classList.remove('is-single');
    Array.prototype.forEach.call(g.children, function (it) { it.classList.remove('is-on'); });
    var back = d.querySelector('[data-pop-back]'); if (back) back.hidden = true;
  }
  function showOne(d, item) {
    var g = d.querySelector('.pop__gallery');
    g.classList.add('is-single'); item.classList.add('is-on');
    var back = d.querySelector('[data-pop-back]'); if (back) { back.hidden = false; back.focus({ preventScroll: true }); }
    d.querySelector('.pop__box').scrollTop = 0;
  }

  document.querySelectorAll('dialog.pop').forEach(function (d) {
    d.addEventListener('click', function (e) {
      if (e.target === d) { close(d); return; }                       /* тап по затемнению */
      if (e.target.closest('[data-pop-close]')) { close(d); return; }
      if (e.target.closest('[data-pop-back]')) { showAll(d); return; }
      var shot = e.target.closest('.pop__shot');
      if (shot) {
        var item = shot.closest('.pop__item');
        if (item.classList.contains('is-on')) showAll(d); else showOne(d, item);
      }
    });
    d.addEventListener('cancel', function (e) { e.preventDefault(); close(d); });   /* Esc */
    d.addEventListener('close', function () { lock(false); if (opener) opener.focus({ preventScroll: true }); });
  });

  document.querySelectorAll('[data-pop]').forEach(function (btn) {
    var d = document.getElementById(btn.getAttribute('data-pop'));
    if (!d) return;
    btn.addEventListener('click', function () { open(d, btn); });
  });
})();
