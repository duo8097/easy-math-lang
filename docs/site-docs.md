# GitHub Pages Site Documentation

This document explains how the Easy Math Lang GitHub Pages site is structured and how to regenerate the screenshots.

## Site Structure

The site is built as a static HTML/CSS/JS site with no framework or bundlers:

```
site/
├── index.html                    # Main landing page
├── assets/
│   ├── css/
│   │   └── style.css            # Main stylesheet
│   ├── js/
│   │   └── main.js              # JavaScript for translations, theme toggle, and OS detection
│   └── img/
│       ├── *.png                # Screenshot images from the editor
│       └── ezmath-icon.png       # App icon (from repo/icons/ezmath-icon.png)
├── i18n/
│   ├── en.json                  # English translations
│   └── vi.json                  # Vietnamese translations
├── .nojekyll                     # Prevents Jekyll from processing the site
```

## Screenshots Generation

The site includes screenshots from the Easy Math Editor showing the interface with Vietnamese UI support. Screenshots are generated using the `scripts/make_site_screenshots.py` script.

### Prerequisites

1. Build the Easy Math Editor first:
   ```bash
   uv sync
   uv run easy-math-editor --help
   ```

2. Install required Python packages (if not already installed):
   ```bash
   pip install PySide6
   ```

### Running the Screenshot Script

Set the QT_QPA_PLATFORM environment variable to "offscreen" and run the script:

```bash
QT_QPA_PLATFORM=offscreen python3 scripts/make_site_screenshots.py
```

### Generated Screenshots

The script generates the following screenshots:

- `editor-screenshot-english-light-*.png`: English theme, light mode
- `editor-screenshot-english-dark-*.png`: English theme, dark mode
- `editor-screenshot-vietnamese-light-*.png`: Vietnamese theme, light mode
- `editor-screenshot-vietnamese-dark-*.png`: Vietnamese theme, dark mode
- `editor-screenshot-welcome-light.png`: Welcome panel (English, light theme)
- `editor-screenshot-draw-gallery-light.png`: *draw gallery (English, light theme)

Each screenshot shows a real example from the `examples/` directory (example.ezmath or draw_test.ezmath) compiled in the actual Easy Math Editor.

### Screenshot Quality

- Fixed window size and position
- Fixed theme (light/dark) as specified
- Fixed example file
- No timestamps or variable content
- HiDPI-friendly (device pixel ratio 2)
- PNG format, optimized under 300 KB per image

### Notes on Screenshot Generation

- The Vietnamese UI screenshots require fcitx5 input method configuration on Linux. If the editor fails to render properly, the script will report the issue instead of faking the screenshot.
- The welcome panel and *draw gallery screenshots require triggering specific UI states that may not render properly offscreen. If they don't render, the script will report the issue.

## Translation System

The site supports English and Vietnamese via the `data-i18n` attribute system. Strings are loaded from JSON files in `site/i18n/`.

### Adding New Translations

1. Add the key to both `site/i18n/en.json` and `site/i18n/vi.json`
2. Add a `data-i18n="your.key"` attribute to the element in HTML
3. Run the quality check script to verify both languages have the same keys

### Translation Keys

Keys follow a dot notation hierarchy:
- `hero.title`: Hero section title
- `hero.subtitle`: Hero section subtitle
- `hero.buttons.download`: Download button text
- `hero.buttons.github`: GitHub button text
- `hero.buttons.docs`: Docs button text
- `code_result.title`: Code → Result section title
- `code_result.description`: Code → Result section description
- `editor.title`: Editor Screenshots section title
- `editor.description`: Editor Screenshots section description
- `features.title`: Features section title
- `features.items.[feature-name].title`: Feature title
- `features.items.[feature-name].desc`: Feature description
- `download.title`: Download section title
- `download.description`: Download section description
- `download.detect_os`: OS detection message
- `download.windows`: Windows platform name
- `download.macos`: macOS platform name
- `download.linux`: Linux platform name
- `docs.title`: Documentation section title
- `docs.description`: Documentation section description
- `footer.license`: Footer license text
- `footer.github`: Footer GitHub link text

## Quality Checks

The `scripts/check_site.py` script verifies:

1. **Links and Images**: All relative links and images resolve correctly
2. **i18n Parity**: Every `data-i18n` key exists in both en.json and vi.json
3. **External Resources**: No external http(s) resources are loaded
4. **Site Size**: Total site size stays under 3 MB

Run the quality check:

```bash
python3 scripts/check_site.py
```

## Deployment

The site is deployed using GitHub Actions. The workflow is defined in `.github/workflows/pages.yml`.

### Manual Deployment Steps

If the automated deployment doesn't work, you can manually deploy the site:

1. Go to your repository's Settings → Pages
2. Under "Build and deployment", set "Source" to "GitHub Actions"
3. Click "Run workflow" to trigger a manual deployment

The site is deployed from the `site/` directory as a static site.

## Local Development

To test the site locally:

1. Start a local web server in the site directory:
   ```bash
   python3 -m http.server 8000
   ```

2. Open `http://localhost:8000` in your browser

3. The theme toggle and language switch will work locally

## Contributing

- All code and documentation should be in English
- Vietnamese strings are allowed ONLY in `site/i18n/vi.json`
- No framework, bundler, or npm dependencies
- All URLs are relative (the site lives under `/easy-math-lang/`)
- No external CDNs or trackers

## License

MIT License - See LICENSE file for details.