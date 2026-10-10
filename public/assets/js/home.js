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
