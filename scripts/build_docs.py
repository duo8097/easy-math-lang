#!/usr/bin/env python3
"""Render docs/*.md to static HTML under site/docs/.

Keeps docs/ as the single source of truth. Re-run after editing docs.
Usage:
    python3 scripts/build_docs.py
"""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / 'docs'
SITE_DIR = ROOT / 'site'
OUT_DIR = SITE_DIR / 'docs'
DATA_DIR = SITE_DIR / 'assets' / 'data'

MD_FILES = sorted(DOCS_DIR.glob('*.md'))


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'\s+', '-', text)
    return text.strip('-')


def inline(text: str) -> str:
    # code spans
    text = re.sub(r'`([^`]+)`', lambda m: '<code>' + html.escape(m.group(1)) + '</code>', text)
    # bold
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    # italic (single *)
    text = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<em>\1</em>', text)
    # links
    def _link(m):
        href = m.group(2)
        # Rewrite in-repo markdown links to their rendered site pages.
        if href.endswith('.md'):
            href = href[:-3] + '.html'
        if '.md#' in href:
            href = href.replace('.md#', '.html#')
        # Links that leave site/docs/ (repo root files, examples, ...)
        # cannot resolve inside the published site; point them at GitHub.
        if href.startswith('../'):
            path = href[3:]
            anchor = ''
            if '#' in path:
                path, anchor = path.split('#', 1)
                anchor = '#' + anchor
            github_path = path
            if github_path.endswith('.html'):
                github_path = github_path[:-5] + '.md'
            url = 'https://github.com/duo8097/easy-math-lang/blob/main/' + github_path + anchor
            return '<a href="' + html.escape(url, quote=True) + '">' + m.group(1) + '</a>'
        return '<a href="' + html.escape(href, quote=True) + '">' + m.group(1) + '</a>'
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', _link, text)
    return text


def markdown_to_html(md: str) -> tuple[str, list[tuple[str, str]]]:
    lines = md.split('\n')
    out: list[str] = []
    toc: list[tuple[str, str]] = []
    i = 0
    n = len(lines)
    in_code = False
    code_buf: list[str] = []
    list_stack: list[str] = []

    def close_lists():
        while list_stack:
            out.append('</' + list_stack.pop() + '>')

    while i < n:
        line = lines[i]
        if line.strip().startswith('```'):
            if in_code:
                out.append('<pre class="code"><code>' + html.escape('\n'.join(code_buf)) + '</code></pre>')
                code_buf = []
                in_code = False
            else:
                close_lists()
                in_code = True
            i += 1
            continue
        if in_code:
            code_buf.append(line)
            i += 1
            continue
        stripped = line.strip()
        m = re.match(r'^(#{1,6})\s+(.*)$', stripped)
        if m:
            close_lists()
            level = len(m.group(1))
            text = m.group(2).strip()
            anchor = slugify(text)
            if level <= 3:
                toc.append((anchor, text))
            out.append(f'<h{level} id="{anchor}">{inline(text)}</h{level}>')
            i += 1
            continue
        if stripped == '':
            close_lists()
            i += 1
            continue
        if re.match(r'^---+$', stripped):
            close_lists()
            out.append('<hr>')
            i += 1
            continue
        # tables
        if '|' in stripped and i + 1 < n and re.match(r'^\|?[\s\-:|]+\|?$', lines[i + 1].strip()):
            close_lists()
            header_cells = [c.strip() for c in stripped.strip('|').split('|')]
            out.append('<table><thead><tr>' + ''.join(f'<th>{inline(c)}</th>' for c in header_cells) + '</tr></thead><tbody>')
            i += 2
            while i < n and lines[i].strip().startswith('|'):
                cells = [c.strip() for c in lines[i].strip().strip('|').split('|')]
                out.append('<tr>' + ''.join(f'<td>{inline(c)}</td>' for c in cells) + '</tr>')
                i += 1
            out.append('</tbody></table>')
            continue
        # unordered list
        m = re.match(r'^[-*+]\s+(.*)$', stripped)
        if m:
            if not list_stack or list_stack[-1] != 'ul':
                close_lists()
                out.append('<ul>')
                list_stack.append('ul')
            out.append('<li>' + inline(m.group(1)) + '</li>')
            i += 1
            continue
        # ordered list
        m = re.match(r'^\d+\.\s+(.*)$', stripped)
        if m:
            if not list_stack or list_stack[-1] != 'ol':
                close_lists()
                out.append('<ol>')
                list_stack.append('ol')
            out.append('<li>' + inline(m.group(1)) + '</li>')
            i += 1
            continue
        # html comments (toc markers) - skip
        if stripped.startswith('<!--') and stripped.endswith('-->'):
            i += 1
            continue
        close_lists()
        out.append('<p>' + inline(stripped) + '</p>')
        i += 1
    close_lists()
    if in_code:
        out.append('<pre class="code"><code>' + html.escape('\n'.join(code_buf)) + '</code></pre>')
    return '\n'.join(out), toc


def page_template(title: str, body: str, toc: list[tuple[str, str]], sidebar: str) -> str:
    toc_html = ''
    if toc:
        toc_html = '<nav class="doc-toc"><strong>On this page</strong><ul>' + ''.join(
            f'<li><a href="#{a}">{html.escape(t)}</a></li>' for a, t in toc) + '</ul></nav>'
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} — Easy Math Lang Docs</title>
<meta property="og:title" content="{html.escape(title)} — Easy Math Lang Docs">
<meta property="og:description" content="Easy Math Lang documentation.">
<meta property="og:image" content="https://duo8097.github.io/easy-math-lang/assets/img/og-image.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="../assets/css/style.css">
<link rel="stylesheet" href="../assets/css/docs.css">
</head>
<body>
<header class="site-header"><div class="wrap header-inner">
  <a class="brand" href="../index.html">Easy Math Lang</a>
</div></header>
<main class="wrap docs-layout">
  <aside class="docs-sidebar">{sidebar}</aside>
  <article class="docs-content">
    <p class="muted">Documentation is currently English-only.</p>
    <h1>{html.escape(title)}</h1>
    {toc_html}
    {body}
  </article>
</main>
</body>
</html>'''


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    sidebar_items = []
    for md_path in MD_FILES:
        slug = md_path.stem
        sidebar_items.append((slug, md_path.stem.replace('-', ' ').title()))
    sidebar = '<ul>' + ''.join(f'<li><a href="{s}.html">{html.escape(t)}</a></li>' for s, t in sidebar_items) + '</ul>'

    search_index = []
    for md_path in MD_FILES:
        md = md_path.read_text(encoding='utf-8')
        # title from first heading
        m = re.search(r'^#\s+(.+)$', md, re.MULTILINE)
        title = m.group(1).strip() if m else md_path.stem
        body, toc = markdown_to_html(md)
        html_page = page_template(title, body, toc, sidebar)
        (OUT_DIR / (md_path.stem + '.html')).write_text(html_page, encoding='utf-8')
        text = re.sub(r'```.*?```', ' ', md, flags=re.DOTALL)
        text = re.sub(r'[#*`\[\]()]', ' ', text)
        search_index.append({'slug': md_path.stem, 'title': title, 'text': ' '.join(text.split())[:4000]})

    # index page
    (OUT_DIR / 'index.html').write_text(page_template('Documentation', '<p>Choose a topic from the sidebar.</p>', [], sidebar), encoding='utf-8')

    (DATA_DIR / 'docs-search.json').write_text(json.dumps(search_index, ensure_ascii=False), encoding='utf-8')
    print(f'rendered {len(MD_FILES)} docs')
    return 0


if __name__ == '__main__':
    sys.exit(main())
