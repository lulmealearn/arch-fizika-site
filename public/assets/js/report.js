// Отчёт: листы 1123 px уменьшаются под ширину окна; «Сохранить PDF» — печать браузера (листы A4 альбомом).
(function () {
  var root = document.documentElement;
  function fit() {
    var z = Math.min(1, (root.clientWidth - 16) / 1123);
    root.style.setProperty('--z', z.toFixed(4));
  }
  fit();
  window.addEventListener('resize', fit);
  window.addEventListener('beforeprint', function () { root.style.setProperty('--z', '1'); });
  window.addEventListener('afterprint', fit);
  var b = document.getElementById('rep-print');
  if (b) b.addEventListener('click', function () { window.print(); });
})();
