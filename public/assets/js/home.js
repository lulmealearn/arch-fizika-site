/* Главная: точки-индикатор для отзывов, которые на телефоне листаются вбок. */
/* Отзывы на телефоне листаются вбок: точки показывают, какой открыт, и переключают по нажатию. */
(function () {
  'use strict';
  var list = document.getElementById('reviews-list'), dots = document.querySelector('.reviews-dots');
  if (!list || !dots) return;
  var cards = Array.prototype.slice.call(list.querySelectorAll('.review')), btns = [];
  cards.forEach(function (c, i) {
    var b = document.createElement('button'); b.type = 'button'; b.tabIndex = -1;
    b.addEventListener('click', function () { list.scrollTo({ left: c.offsetLeft - list.offsetLeft - parseFloat(getComputedStyle(list).paddingLeft || 0), behavior: 'smooth' }); });
    dots.appendChild(b); btns.push(b);
  });
  var raf = 0;
  function mark() {
    raf = 0;
    var x = list.scrollLeft, best = 0, d = Infinity;
    cards.forEach(function (c, i) { var dd = Math.abs(c.offsetLeft - list.offsetLeft - x); if (dd < d) { d = dd; best = i; } });
    if (list.scrollLeft + list.clientWidth >= list.scrollWidth - 4) best = cards.length - 1;
    btns.forEach(function (b, i) { b.setAttribute('aria-current', i === best ? 'true' : 'false'); });
  }
  list.addEventListener('scroll', function () { if (!raf) raf = requestAnimationFrame(mark); }, { passive: true });
  mark();
})();

/* Длинные отзывы обрезаны на одной высоте; кнопка показывается, только если текст действительно не влез. */
(function () {
  'use strict';
  var cards = document.querySelectorAll('.review--long');
  function check() {
    cards.forEach(function (c) {
      var p = c.querySelector('p'), b = c.querySelector('.review__more');
      if (!p || !b || c.classList.contains('is-open')) return;
      b.hidden = p.scrollHeight <= p.clientHeight + 2;
    });
  }
  cards.forEach(function (c) {
    var b = c.querySelector('.review__more');
    if (!b) return;
    b.setAttribute('aria-expanded', 'false');
    b.addEventListener('click', function () {
      var open = c.classList.toggle('is-open');
      b.textContent = open ? 'Свернуть' : 'Читать полностью';
      b.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  });
  check();
  window.addEventListener('resize', check);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(check);
})();
