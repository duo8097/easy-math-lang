/* Easy Math Lang — landing page behaviour
   ------------------------------------------------------------------
   Three small jobs, no framework:
     1. language toggle (EN/VI) driven by site/i18n/*.json
     2. light/dark theme with a manual toggle
     3. detect the visitor's OS and highlight the matching download

   The page is fully readable in English with JavaScript disabled: the
   English text lives in the HTML and the JSON files only add the
   translation. Every storage access is wrapped in try/catch because
   localStorage throws in private mode and in some file:// contexts. */

(function () {
  'use strict';

  var STORAGE_LANG = 'ezmath-lang';
  var STORAGE_THEME = 'ezmath-theme';
  var DEFAULT_LANG = 'en';
  var SUPPORTED = ['en', 'vi'];

  var currentLang = DEFAULT_LANG;
  var strings = {};

  /* ---------------------------------------------------------- helpers */

  function readStorage(key) {
    try {
      return window.localStorage.getItem(key);
    } catch (err) {
      return null;
    }
  }

  function writeStorage(key, value) {
    try {
      window.localStorage.setItem(key, value);
    } catch (err) {
      /* storage unavailable — the choice simply is not remembered */
    }
  }

  function detectLanguage() {
    /* ?lang=vi shares the page in one language; it wins over the
       stored choice. */
    try {
      var requested = (new URLSearchParams(window.location.search)
        .get('lang') || '').toLowerCase();
      if (SUPPORTED.indexOf(requested) !== -1) {
        return requested;
      }
    } catch (err) {
      /* no URLSearchParams — fall through */
    }
    var saved = readStorage(STORAGE_LANG);
    if (saved && SUPPORTED.indexOf(saved) !== -1) {
      return saved;
    }
    var nav = (navigator.language || navigator.userLanguage || '').toLowerCase();
    if (nav.indexOf('vi') === 0) {
      return 'vi';
    }
    return DEFAULT_LANG;
  }

  function lookup(key) {
    if (!key) { return null; }
    var parts = key.split('.');
    var node = strings;
    for (var i = 0; i < parts.length; i += 1) {
      if (node === null || typeof node !== 'object') { return null; }
      node = node[parts[i]];
    }
    return typeof node === 'string' ? node : null;
  }

  /* --------------------------------------------------------- rendering */

  function applyString(element, text) {
    /* Only plain text is replaced — the English source may contain
       inline markup (<code>…</code>), which is kept as-is. */
    if (text.indexOf('<') === -1) {
      element.textContent = text;
      return;
    }
    var holder = document.createElement('div');
    holder.innerHTML = text;
    element.textContent = '';
    while (holder.firstChild) {
      element.appendChild(holder.firstChild);
    }
  }

  function translate() {
    var nodes = document.querySelectorAll('[data-i18n]');
    for (var i = 0; i < nodes.length; i += 1) {
      var text = lookup(nodes[i].getAttribute('data-i18n'));
      if (text !== null) { applyString(nodes[i], text); }
    }

    var attrs = document.querySelectorAll('[data-i18n-attr-aria-label]');
    for (var j = 0; j < attrs.length; j += 1) {
      var label = lookup(attrs[j].getAttribute('data-i18n-attr-aria-label'));
      if (label !== null) { attrs[j].setAttribute('aria-label', label); }
    }

    var meta = lookup('meta.title');
    if (meta) { document.title = meta; }
    var description = lookup('meta.description');
    if (description) {
      var tag = document.querySelector('meta[name="description"]');
      if (tag) { tag.setAttribute('content', description); }
    }

    document.documentElement.lang = currentLang;
    var buttons = document.querySelectorAll('.lang-btn');
    for (var k = 0; k < buttons.length; k += 1) {
      var pressed = buttons[k].getAttribute('data-lang') === currentLang;
      buttons[k].setAttribute('aria-pressed', pressed ? 'true' : 'false');
    }
  }

  function loadLanguage(lang) {
    currentLang = lang;
    if (lang === DEFAULT_LANG) {
      /* English is already in the markup — nothing to download. */
      translate();
      return;
    }
    fetch('i18n/' + lang + '.json', { cache: 'no-cache' })
      .then(function (response) {
        if (!response.ok) { throw new Error('HTTP ' + response.status); }
        return response.json();
      })
      .then(function (data) {
        strings = data || {};
        translate();
      })
      .catch(function () {
        /* Keep the English text (and the English lang attribute). */
        document.documentElement.lang = DEFAULT_LANG;
        var buttons = document.querySelectorAll('.lang-btn');
        for (var i = 0; i < buttons.length; i += 1) {
          buttons[i].setAttribute('aria-pressed', buttons[i].getAttribute('data-lang') === DEFAULT_LANG ? 'true' : 'false');
        }
      });
  }

  function setLanguage(lang) {
    if (SUPPORTED.indexOf(lang) === -1) { return; }
    writeStorage(STORAGE_LANG, lang);
    loadLanguage(lang);
  }

  /* ------------------------------------------------------------ theme */

  function prefersDark() {
    return !!(window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
  }

  function applyTheme(theme) {
    document.body.classList.toggle('dark', theme === 'dark');
  }

  function setTheme(theme, remember) {
    applyTheme(theme);
    if (remember) { writeStorage(STORAGE_THEME, theme); }
  }

  function initTheme() {
    var saved = readStorage(STORAGE_THEME);
    if (saved === 'dark' || saved === 'light') {
      setTheme(saved, false);
    } else {
      setTheme(prefersDark() ? 'dark' : 'light', false);
    }
    var toggle = document.getElementById('theme-toggle');
    if (!toggle) { return; }
    toggle.addEventListener('click', function () {
      setTheme(document.body.classList.contains('dark') ? 'light' : 'dark', true);
    });
  }

  /* ------------------------------------------------------ OS detection */

  function detectOS() {
    var agent = navigator.userAgent || '';
    var platform = '';
    if (/Windows/i.test(agent)) {
      platform = 'windows';
    } else if (/Mac OS X|Macintosh/i.test(agent)) {
      platform = 'macos';
    } else if (/Linux|X11|Android/i.test(agent)) {
      platform = 'linux';
    }
    var links = document.querySelectorAll('[data-platform]');
    var names = { windows: 'Windows', macos: 'macOS', linux: 'Linux' };
    for (var i = 0; i < links.length; i += 1) {
      var match = links[i].getAttribute('data-platform') === platform;
      links[i].parentNode.classList.toggle('is-detected', match);
    }
    var hint = document.getElementById('os-hint');
    if (!hint) { return; }
    if (!platform) { return; }
    var text = lookup('download.hint');
    if (text) { text = text.replace('{os}', names[platform]); }
    else { text = 'Your system looks like ' + names[platform] + '.'; }
    hint.textContent = text;
    hint.hidden = false;
  }

  /* ------------------------------------------------------------- init */

  function init() {
    initTheme();
    var lang = detectLanguage();
    loadLanguage(lang);
    detectOS();

    var buttons = document.querySelectorAll('.lang-btn');
    for (var i = 0; i < buttons.length; i += 1) {
      buttons[i].addEventListener('click', function (event) {
        setLanguage(event.currentTarget.getAttribute('data-lang'));
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
