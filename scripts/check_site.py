#!/usr/bin/env python3
"""Quality check for the GitHub Pages site.

Verifies, and fails with a non-zero exit code when something is wrong:

1. every relative link and image in ``site/`` resolves to a real file;
2. every ``data-i18n`` key exists in both ``site/i18n/en.json`` and
   ``site/i18n/vi.json`` (and both catalogs have the same key set);
3. no external http(s) resource is *loaded* by the page (scripts,
   stylesheets, images, fonts, CSS ``url()``/``@import``, JS
   ``import``/``require``) — plain hyperlinks to GitHub are fine;
4. every image referenced by ``index.html`` is listed in
   ``site/assets/img/manifest.json``, is a real image (not a renamed
   text file) and still matches the SHA-256 recorded there;
5. every image in ``site/assets/img`` is listed in the manifest, so no
   placeholder or stale file can hide there;
6. the whole site stays below 3 MB.

Usage:
    python3 scripts/check_site.py
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
SITE_DIR = ROOT / 'site'
IMG_DIR = SITE_DIR / 'assets' / 'img'
MANIFEST = IMG_DIR / 'manifest.json'

MAX_SITE_BYTES = 3 * 1024 * 1024
#: Smallest plausible size for a generated site image. Anything below
#: this is a placeholder (a renamed text file, a 1x1 pixel, …).
MIN_IMAGE_BYTES = 4096

#: Hosts the page may link to (plain hyperlinks, not loaded resources).
ALLOWED_LINK_HOSTS = {'github.com', 'duo8097.github.io'}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(65536), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _flatten(node, prefix=''):
    """Flat ``a.b.c`` key list of a nested translation catalog."""
    keys = []
    if not isinstance(node, dict):
        return keys
    for key, value in node.items():
        path = f'{prefix}{key}'
        if isinstance(value, dict):
            keys.extend(_flatten(value, f'{path}.'))
        else:
            keys.append(path)
    return keys


def _html_files():
    return sorted(SITE_DIR.rglob('*.html'))


def _resource_urls(html: str):
    """External URLs the page *loads* (scripts, styles, images, fonts)."""
    urls = []
    patterns = (
        r'<script[^>]*\ssrc=["\']([^"\']+)["\']',
        r'<link[^>]*\shref=["\']([^"\']+)["\']',
        r'<img[^>]*\ssrc=["\']([^"\']+)["\']',
        r'<source[^>]*\ssrcset=["\']([^"\']+)["\']',
        r'<iframe[^>]*\ssrc=["\']([^"\']+)["\']',
    )
    for pattern in patterns:
        urls.extend(re.findall(pattern, html, flags=re.IGNORECASE))
    return urls


def _hyperlinks(html: str):
    patterns = (
        r'<a[^>]*\shref=["\']([^"\']+)["\']',
        r'<area[^>]*\shref=["\']([^"\']+)["\']',
    )
    links = []
    for pattern in patterns:
        links.extend(re.findall(pattern, html, flags=re.IGNORECASE))
    return links


def check_relative_targets():
    """Every relative link/image must resolve to a file inside site/."""
    issues = []
    for html_file in _html_files():
        html = html_file.read_text(encoding='utf-8')
        for url in _resource_urls(html) + _hyperlinks(html):
            if not url or url.startswith('#'):
                continue
            if url.startswith(('http://', 'https://', '//', 'mailto:', 'data:')):
                continue
            target = (html_file.parent / url.split('#', 1)[0]
                      .split('?', 1)[0]).resolve()
            try:
                target.relative_to(SITE_DIR.resolve())
            except ValueError:
                issues.append(f'{html_file.name}: link escapes site/: {url}')
                continue
            if not target.exists():
                issues.append(f'{html_file.name}: missing target: {url}')
    return issues


def check_i18n_parity():
    """Both catalogs must hold the same keys, and every used key exists."""
    issues = []
    catalogs = {}
    for locale in ('en', 'vi'):
        path = SITE_DIR / 'i18n' / f'{locale}.json'
        if not path.is_file():
            issues.append(f'missing translation file: {path.relative_to(ROOT)}')
            continue
        try:
            catalogs[locale] = json.loads(path.read_text(encoding='utf-8'))
        except ValueError as exc:
            issues.append(f'{path.name}: invalid JSON ({exc})')
            catalogs[locale] = {}

    if len(catalogs) == 2:
        en_keys = set(_flatten(catalogs['en']))
        vi_keys = set(_flatten(catalogs['vi']))
        for key in sorted(en_keys - vi_keys):
            issues.append(f'key missing in vi.json: {key}')
        for key in sorted(vi_keys - en_keys):
            issues.append(f'key missing in en.json: {key}')

    used = set()
    for html_file in _html_files():
        html = html_file.read_text(encoding='utf-8')
        used.update(re.findall(r'data-i18n=["\']([^"\']+)["\']', html))
        used.update(re.findall(
            r'data-i18n-attr-aria-label=["\']([^"\']+)["\']', html))
    for key in sorted(used):
        for locale, catalog in catalogs.items():
            if key not in set(_flatten(catalog)):
                issues.append(f'data-i18n key "{key}" not in {locale}.json')
    return issues


def check_external_resources():
    """No external http(s) resource may be loaded by the page."""
    issues = []
    for html_file in _html_files():
        html = html_file.read_text(encoding='utf-8')
        for url in _resource_urls(html):
            if not url.startswith(('http://', 'https://', '//')):
                continue
            host = urlparse(url if not url.startswith('//')
                            else 'https:' + url).netloc
            if host not in ALLOWED_LINK_HOSTS:
                issues.append(f'{html_file.name}: loads external resource {url}')
        for url in _hyperlinks(html):
            if not url.startswith(('http://', 'https://')):
                continue
            host = urlparse(url).netloc
            if host not in ALLOWED_LINK_HOSTS:
                issues.append(f'{html_file.name}: links to unexpected host {url}')

    for css_file in sorted(SITE_DIR.rglob('*.css')):
        css = css_file.read_text(encoding='utf-8')
        for url in re.findall(r'url\(["\']?([^"\')]+)', css):
            if url.startswith(('http://', 'https://', '//')):
                issues.append(f'{css_file.name}: loads external resource {url}')
        for url in re.findall(r'@import\s+["\']([^"\']+)', css):
            if url.startswith(('http://', 'https://', '//')):
                issues.append(f'{css_file.name}: imports external stylesheet {url}')

    for js_file in sorted(SITE_DIR.rglob('*.js')):
        js = js_file.read_text(encoding='utf-8')
        for url in re.findall(
                r'(?:import|require)\s*\(?\s*["\']([^"\']+)["\']', js):
            if url.startswith(('http://', 'https://', '//')):
                issues.append(f'{js_file.name}: loads external module {url}')

    if issues:
        return issues
    # The site must not reference a third-party origin at all.
    for html_file in _html_files():
        html = html_file.read_text(encoding='utf-8')
        for url in re.findall(r'https?://([^/"\'\s]+)', html):
            if url not in ALLOWED_LINK_HOSTS:
                issues.append(
                    f'{html_file.name}: references unknown host {url}')
    return issues


def _looks_like_image(path: Path) -> bool:
    """True when the file really is a PNG or an SVG document."""
    if path.suffix.lower() == '.png':
        return path.read_bytes()[:8] == b'\x89PNG\r\n\x1a\n'
    if path.suffix.lower() == '.svg':
        text = path.read_text(encoding='utf-8', errors='replace')
        return '<svg' in text[:2048]
    return False


def check_image_manifest():
    """Every image must be in the manifest, real and unmodified."""
    issues = []
    if not MANIFEST.is_file():
        return [f'missing image manifest: {MANIFEST.relative_to(ROOT)}']
    try:
        manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    except ValueError as exc:
        return [f'{MANIFEST.name}: invalid JSON ({exc})']

    entries = manifest.get('images')
    if not isinstance(entries, list) or not entries:
        return [f'{MANIFEST.name}: no "images" list']

    recorded = {}
    for entry in entries:
        name = entry.get('file')
        if not name:
            issues.append(f'{MANIFEST.name}: entry without "file"')
            continue
        if name in recorded:
            issues.append(f'{MANIFEST.name}: duplicate entry {name}')
        recorded[name] = entry
        path = IMG_DIR / name
        if not path.is_file():
            issues.append(f'{MANIFEST.name}: {name} is listed but missing')
            continue
        size = path.stat().st_size
        if size < MIN_IMAGE_BYTES:
            issues.append(
                f'{name}: {size} bytes is below the {MIN_IMAGE_BYTES} byte '
                'minimum — looks like a placeholder')
        if size != entry.get('bytes'):
            issues.append(
                f'{name}: size {size} does not match the manifest '
                f'({entry.get("bytes")})')
        digest = _sha256(path)
        if digest != entry.get('sha256'):
            issues.append(f'{name}: SHA-256 does not match the manifest')
        if not _looks_like_image(path):
            issues.append(f'{name}: not a real PNG/SVG file')
        if not entry.get('produced_by'):
            issues.append(f'{name}: manifest entry has no "produced_by"')

    # Images that exist but are not in the manifest (placeholders, …).
    for path in sorted(IMG_DIR.iterdir()):
        if not path.is_file() or path.name == MANIFEST.name:
            continue
        if path.name not in recorded:
            issues.append(
                f'{path.name}: present in site/assets/img but not in the '
                'manifest')

    # Images used by the page must exist and be in the manifest.
    for html_file in _html_files():
        html = html_file.read_text(encoding='utf-8')
        for url in re.findall(r'<img[^>]*\ssrc=["\']([^"\']+)["\']', html,
                              flags=re.IGNORECASE):
            if url.startswith(('http://', 'https://', '//', 'data:')):
                continue
            name = Path(url.split('#', 1)[0]).name
            if not name:
                continue
            if name not in recorded:
                issues.append(
                    f'{html_file.name}: image {url} is not in the manifest')
    return issues


def check_site_size():
    total = 0
    for path in SITE_DIR.rglob('*'):
        if path.is_file():
            total += path.stat().st_size
    if total > MAX_SITE_BYTES:
        return [f'site size is {total} bytes (limit {MAX_SITE_BYTES})'], total
    return [], total


def main() -> int:
    print('=== Easy Math Lang site check ===\n')
    failures = 0

    checks = (
        ('relative links and images resolve', check_relative_targets),
        ('i18n key parity (en/vi)', check_i18n_parity),
        ('no external resources loaded', check_external_resources),
        ('images match the manifest', check_image_manifest),
    )
    for label, check in checks:
        issues = check()
        if issues:
            failures += len(issues)
            print(f'FAIL  {label}: {len(issues)} problem(s)')
            for issue in issues:
                print(f'        - {issue}')
        else:
            print(f'ok    {label}')

    size_issues, total = check_site_size()
    if size_issues:
        failures += len(size_issues)
        print(f'FAIL  site size: {total} bytes')
        for issue in size_issues:
            print(f'        - {issue}')
    else:
        print(f'ok    site size: {total} bytes '
              f'({total / 1024:.1f} KiB, limit 3 MiB)')

    print()
    if failures:
        print(f'{failures} problem(s) found.')
        return 1
    print('All checks passed.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
