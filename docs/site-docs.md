# The website

`site/` holds the GitHub Pages site: a static landing page for
easy-math-lang. Plain HTML, CSS and JavaScript — no framework, no build
step, no external resources.

```
site/
├── index.html          the page
├── .nojekyll           keeps GitHub Pages from running Jekyll
├── assets/css/style.css
├── assets/js/main.js   theme toggle, EN/VI switch, OS detection
├── assets/img/         screenshots + compiled example output
│   └── manifest.json   what each image is and how it was produced
└── i18n/en.json, vi.json
```

The page is deployed by `.github/workflows/pages.yml`. One manual step is
needed once: **Settings → Pages → Build and deployment → Source: GitHub
Actions**.

## Regenerating the images

Every image under `site/assets/img/` is produced by the project itself —
editor screenshots come from the real editor rendered offscreen, the
example images come from the project compiler. Nothing is drawn by hand.

```
QT_QPA_PLATFORM=offscreen python3 scripts/make_site_screenshots.py
```

The script

- opens the real editor (`MainWindow`, like the offscreen GUI tests do)
  with `examples/example_2.ezmath` loaded and grabs it in English and
  Vietnamese, light and dark, plus the welcome banner and the `*draw`
  gallery;
- compiles the four built-in examples of `src/editor/help_dialogs.py`
  (basic math, fraction/equation, vector, simple `*draw`) to SVG with
  `compiler.pipeline.compile_ezmath` and crops the page to its content;
- writes `site/assets/img/manifest.json` with the SHA-256, the size and
  the way each image was produced.

The output is deterministic: fixed window size, fixed theme, fixed
example, an isolated settings file and no timestamps. Re-running the
script on the same machine reproduces the same bytes.

## Checking the site

```
python3 scripts/check_site.py
```

It fails when a relative link or image does not resolve, when a
`data-i18n` key is missing from `en.json` or `vi.json`, when an external
http(s) resource would be loaded, when an image is not in the manifest
(or does not match its SHA-256, or is too small to be a real image), or
when the site grows past 3 MB. The same checks run as part of the test
suite (`tests/test_site.py`).

## Translations

`site/i18n/en.json` and `site/i18n/vi.json` hold the same keys. The
English text is also in `index.html`, so the page stays readable when
JavaScript is off. The Vietnamese strings reuse the wording of the
editor's own catalog (`src/editor/locales/vi.json`).
