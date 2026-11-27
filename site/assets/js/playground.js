/* Easy Math Lang — in-browser playground
   Lazy-loads Pyodide on first Run; keeps working (with a message) if it fails. */
(function () {
  'use strict';

  var PYODIDE_VERSION = '0.26.4';
  var PYODIDE_INDEX = 'https://cdn.jsdelivr.net/pyodide/v' + PYODIDE_VERSION + '/full/';
  var WHEEL_BASE = (new URL('assets/playground/', window.location.href)).href;

  var pyodide = null;
  var loadingPromise = null;

  var inputEl = document.getElementById('pg-input');
  var outputEl = document.getElementById('pg-output');
  var errorEl = document.getElementById('pg-error');
  var loadingEl = document.getElementById('pg-loading');
  var fallbackEl = document.getElementById('pg-fallback');
  var exampleSelect = document.getElementById('pg-example');

  var DEFAULT_EXAMPLES = [
    { name: 'Basic math', code: '<width> = 5\n<area> = calc(<width> * 2)\n\nArea: <area>\n' },
    { name: 'Fraction and equation', code: '*frac(2 ; 3)\n\n*frac(x + 1 ; x - 1)\n\nSolve: *frac(x ; 2) + *frac(1 ; 3) = *frac(5 ; 6)\n' },
    { name: 'Vector', code: 'Vector: *vec(3 ; 4)\n\nLength: *root(2 ; *pow(3 ; 2) + *pow(4 ; 2))\n' },
    { name: 'Simple *draw', code: '*draw(\n    *point(A = 0, 0)\n    *point(B = 3, 0)\n    *point(C = 0, 4)\n    *triangle(A ; B ; C)\n)\n' }
  ];

  function showError(msg) {
    errorEl.hidden = false;
    errorEl.textContent = msg;
  }
  function clearError() {
    errorEl.hidden = true;
    errorEl.textContent = '';
  }

  async function loadExamples() {
    try {
      var res = await fetch('assets/data/examples.json', { cache: 'no-cache' });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      var data = await res.json();
      if (Array.isArray(data) && data.length) {
        populateExamples(data);
        return;
      }
    } catch (e) { /* fall back */ }
    populateExamples(DEFAULT_EXAMPLES);
  }

  function populateExamples(list) {
    exampleSelect.innerHTML = '';
    list.forEach(function (ex, idx) {
      var opt = document.createElement('option');
      opt.value = String(idx);
      opt.textContent = ex.name || ('Example ' + (idx + 1));
      opt.dataset.code = ex.code || '';
      exampleSelect.appendChild(opt);
    });
    if (list.length) {
      inputEl.value = list[0].code || '';
    }
  }

  exampleSelect.addEventListener('change', function () {
    var opt = exampleSelect.options[exampleSelect.selectedIndex];
    if (opt && opt.dataset.code) inputEl.value = opt.dataset.code;
  });

  async function loadPyodideOnce() {
    if (pyodide) return pyodide;
    if (loadingPromise) return loadingPromise;
    loadingEl.hidden = false;
    loadingPromise = (async function () {
      if (!window.loadPyodide) {
        await new Promise(function (resolve, reject) {
          var s = document.createElement('script');
          s.src = PYODIDE_INDEX + 'pyodide.js';
          s.onload = resolve;
          s.onerror = reject;
          document.head.appendChild(s);
        });
      }
      var py = await window.loadPyodide({ indexURL: PYODIDE_INDEX });
      await py.loadPackage('micropip');
      var wr = await fetch(WHEEL_BASE + 'wheel.json', { cache: 'no-cache' });
      var wj = await wr.json();
      var micropip = py.pyimport('micropip');
      await micropip.install(WHEEL_BASE + wj.file);
      pyodide = py;
      loadingEl.hidden = true;
      return py;
    })();
    try {
      return await loadingPromise;
    } catch (e) {
      loadingPromise = null;
      loadingEl.hidden = true;
      fallbackEl.hidden = false;
      throw e;
    }
  }

  async function run() {
    clearError();
    outputEl.textContent = '';
    var code = inputEl.value;
    try {
      var py = await loadPyodideOnce();
      var python = [
        'import io, sys, os',
        'from compiler.pipeline import compile_ezmath',
        'src_path = "/tmp/case.ezmath"',
        'out_path = "/tmp/case.typ"',
        'with open(src_path, "w", encoding="utf-8") as _f:',
        '    _f.write(' + JSON.stringify(code) + ')',
        'buf = io.StringIO()',
        'old = sys.stderr',
        'sys.stderr = buf',
        'try:',
        '    ok = compile_ezmath(src_path, out_path, format="typ")',
        'finally:',
        '    sys.stderr = old',
        'err_text = buf.getvalue()',
        'try:',
        '    with open(out_path, "r", encoding="utf-8") as _f:',
        '        out_text = _f.read()',
        'except FileNotFoundError:',
        '    out_text = ""',
        'ezmath_result = out_text',
        'ezmath_stderr = err_text',
      ].join('\n');
      await py.runPythonAsync(python);
      var outText = py.globals.get('ezmath_result');
      var errText = py.globals.get('ezmath_stderr');
      outputEl.textContent = (outText === undefined || outText === null) ? '' : String(outText);
      if (errText && String(errText).trim()) showError(String(errText).trim());
    } catch (e) {
      fallbackEl.hidden = false;
      showError((e && e.message) ? e.message : String(e));
    }
  }

  document.getElementById('pg-run').addEventListener('click', run);

  document.getElementById('pg-copy').addEventListener('click', function () {
    var text = outputEl.textContent;
    if (navigator.clipboard) navigator.clipboard.writeText(text);
  });

  document.getElementById('pg-share').addEventListener('click', async function () {
    var compressed = await compress(inputEl.value);
    var url = window.location.origin + window.location.pathname + '#code=' + compressed;
    if (navigator.clipboard) navigator.clipboard.writeText(url);
    window.location.hash = 'code=' + compressed;
  });

  async function compress(text) {
    if (window.CompressionStream) {
      try {
        var cs = new CompressionStream('deflate-raw');
        var w = cs.writable.getWriter();
        w.write(new TextEncoder().encode(text));
        w.close();
        var buf = await new Response(cs.readable).arrayBuffer();
        return b64url(new Uint8Array(buf));
      } catch (e) { /* fall through */ }
    }
    return b64url(new TextEncoder().encode(text));
  }

  async function decompress(hash) {
    var raw = fromB64url(hash);
    if (window.DecompressionStream) {
      try {
        var ds = new DecompressionStream('deflate-raw');
        var w = ds.writable.getWriter();
        w.write(raw);
        w.close();
        var buf = await new Response(ds.readable).arrayBuffer();
        return new TextDecoder().decode(buf);
      } catch (e) { /* fall through */ }
    }
    try { return new TextDecoder().decode(raw); } catch (e) { return null; }
  }

  function b64url(bytes) {
    var bin = '';
    for (var i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
    return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
  }
  function fromB64url(s) {
    s = s.replace(/-/g, '+').replace(/_/g, '/');
    while (s.length % 4) s += '=';
    var bin = atob(s);
    var bytes = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return bytes;
  }

  // Load from hash on page load.
  (async function init() {
    await loadExamples();
    var m = (window.location.hash || '').match(/code=(.+)/);
    if (m) {
      var code = await decompress(m[1]);
      if (code !== null) inputEl.value = code;
    }
  })();
})();
