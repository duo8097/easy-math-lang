(function () {
  'use strict';
  var el = document.getElementById('changelog-list');
  fetch('https://api.github.com/repos/duo8097/easy-math-lang/releases', { headers: { 'Accept': 'application/vnd.github+json' } })
    .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(function (data) {
      if (!Array.isArray(data) || !data.length) { el.textContent = 'No releases found.'; return; }
      el.innerHTML = data.map(function (rel) {
        return '<section class="sample"><h2>' + (rel.tag_name || '') + '</h2>' +
          '<p class="muted">' + (rel.published_at ? new Date(rel.published_at).toLocaleDateString() : '') + '</p>' +
          '<div>' + (rel.body ? rel.body.replace(/\n/g, '<br>') : '') + '</div></section>';
      }).join('');
    })
    .catch(function (e) {
      el.innerHTML = '<p>Could not load releases. <a href="https://github.com/duo8097/easy-math-lang/releases">View on GitHub</a>.</p>';
    });
})();
