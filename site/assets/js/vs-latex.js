(function () {
  'use strict';
  var el = document.getElementById('vs-list');
  fetch('assets/data/comparison.json', { cache: 'no-cache' })
    .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(function (data) {
      el.innerHTML = data.map(function (p) {
        var tryUrl = 'playground.html#code=' + btoa(unescape(encodeURIComponent(p.ezmath))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
        return '<section class="vs-row">' +
          '<div class="vs-col"><h3>' + p.title + ' — LaTeX</h3><pre>' + escapeHtml(p.latex) + '</pre><p class="vs-meta">' + p.latex_chars + ' chars, ' + p.latex_lines + ' lines</p></div>' +
          '<div class="vs-col"><h3>' + p.title + ' — ezmath</h3><pre>' + escapeHtml(p.ezmath) + '</pre><p class="vs-meta">' + p.ezmath_chars + ' chars, ' + p.ezmath_lines + ' lines</p>' +
          '<a class="btn" href="' + tryUrl + '">Try in playground</a></div></section>';
      }).join('');
    })
    .catch(function () { el.textContent = 'Could not load comparison data.'; });

  function escapeHtml(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
})();
