#!/usr/bin/env python3
"""Bump the project version everywhere in one command.

Single source of truth: ``pyproject.toml`` ``[project] version``. This
script rewrites every other hard-coded copy of the version, refreshes
``uv.lock`` by running ``uv lock`` (never by hand-editing it), moves
``CHANGELOG.md``'s ``## [Unreleased]`` section to ``## [X.Y.Z] - DATE``
(inserting a fresh empty ``## [Unreleased]`` above it), keeps the
changelog mirrored in ``README.md`` consistent, and (optionally) makes
one commit with exactly the files it touched. It never pushes and
never creates a tag.

Usage (from the repo root)::

    uv run python scripts/bump_version.py <major|minor|patch|X.Y.Z[-rc.N]>
        [--dry-run] [--no-changelog] [--commit] [--date YYYY-MM-DD] [--force]

Rules:
  * The target must be strictly greater than the current version
    (semver ordering as implemented in ``compiler.update``), unless
    ``--force`` is given.
  * Prereleases (``7.1.0-rc.1``) are supported. ``installer/PKGBUILD``
    carries a pacman-safe placeholder (``7.1.0rc1``) because ``pkgver``
    cannot contain ``-``.
  * Every location is matched with an exact, anchored regex; a location
    that is missing or matches more than once aborts the run before
    anything is written. All writes are atomic (temp file + replace)
    and the tree is left untouched when anything fails.
  * ``--dry-run`` prints a unified diff of every change and writes
    nothing.
  * ``--commit`` makes one ``chore(release): vX.Y.Z`` commit containing
    only the files this script touched, then prints the exact ``git tag``
    / ``git push origin`` commands for you to run yourself.
"""

from __future__ import annotations

import argparse
import difflib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from compiler.update import compare_versions, normalize_version  # noqa: E402

# Anchors are anchored regexes with exactly one match required. Each
# value is a function (old_version, new_version, new_pkgver) ->
# replacement string, and a callable to extract the current value from
# the file text (used by --check mode / scripts/check_tag_version.py).
RELEASE_URL = 'https://github.com/duo8097/easy-math-lang'
CHANGELOG_UNRELEASED = '## [Unreleased]'
VERSION_RE = re.compile(r'^\d+\.\d+\.\d+(-rc\.\d+)?$')
# pacman's pkgver may not contain '-'; the rc suffix is squashed
# ('7.1.0-rc.1' -> '7.1.0rc1'). installers and tests share this rule.
_PKUVER_RE = re.compile(r'^(\d+\.\d+\.\d+)(?:-rc\.(\d+))?$')


class BumpError(Exception):
    """Any failure before/while writing; the tree is left untouched."""


def pkgbuild_pkgver(version):
    """Map a semver version to a pacman-safe ``pkgver`` placeholder."""
    match = _PKUVER_RE.match(normalize_version(version))
    if not match:
        raise BumpError(f'cannot map {version!r} to a pacman pkgver')
    core, rc = match.group(1), match.group(2)
    return f'{core}rc{rc}' if rc else core


def project_version(root=ROOT):
    """The version declared in ``pyproject.toml``."""
    import tomllib

    with open(root / 'pyproject.toml', 'rb') as handle:
        return tomllib.load(handle)['project']['version']


def _sub_count(pattern, text, name):
    matches = pattern.findall(text)
    if len(matches) != 1:
        raise BumpError(
            f'{name}: expected exactly one match, found {len(matches)} '
            f'(anchor missing or duplicated?)')
    return matches[0]


# ----------------------------------------------------------------------
# Per-file edits (simple literal replacements)
# ----------------------------------------------------------------------

def edit_pyproject(text, old_version, new_version):
    pattern = re.compile(r'(?m)^version = "[^"]+"$')
    _sub_count(pattern, text, 'pyproject.toml [project] version')
    return pattern.sub(f'version = "{new_version}"', text, count=1)


def edit_update_py(text, old_version, new_version):
    pattern = re.compile(r"(?m)^FALLBACK_VERSION = '[^']*'$")
    _sub_count(pattern, text, 'src/compiler/update.py FALLBACK_VERSION')
    return pattern.sub(f"FALLBACK_VERSION = '{new_version}'", text, count=1)


def edit_lsp_server(text, old_version, new_version):
    pattern = re.compile(r"(?m)^SERVER_VERSION = '[^']*'$")
    _sub_count(pattern, text, 'src/lsp/server.py SERVER_VERSION')
    return pattern.sub(f"SERVER_VERSION = '{new_version}'", text, count=1)


def edit_editor_app(text, old_version, new_version):
    pattern = re.compile(r"(?m)^    return '[^']*'$")
    _sub_count(pattern, text, 'src/editor/app.py frozen-build fallback')
    return pattern.sub(f"    return '{new_version}'", text, count=1)


def edit_help_dialogs(text, old_version, new_version):
    pattern = re.compile(r"(?m)^    def __init__\(self, version='[^']*', parent=None\):$")
    _sub_count(pattern, text, 'src/editor/help_dialogs.py AboutDialog default')
    return pattern.sub(f"    def __init__(self, version='{new_version}', parent=None):",
                       text, count=1)


def edit_pkgbuild(text, old_version, new_version):
    pattern = re.compile(r'(?m)^pkgver=[^\s]+$')
    _sub_count(pattern, text, 'installer/PKGBUILD pkgver')
    return pattern.sub(f'pkgver={pkgbuild_pkgver(new_version)}', text, count=1)


def edit_bug_report(text, old_version, new_version):
    pattern = re.compile(r'(?m)^(\s*)placeholder: "[^"]*"$')
    _sub_count(pattern, text, '.github/ISSUE_TEMPLATE/bug_report.yml placeholder')
    return pattern.sub(lambda m: f'{m.group(1)}placeholder: "{new_version}"',
                       text, count=1)


LITERAL_FILES = [
    ('pyproject.toml', edit_pyproject, 'pyproject.toml [project] version'),
    ('src/compiler/update.py', edit_update_py,
     'src/compiler/update.py FALLBACK_VERSION'),
    ('src/lsp/server.py', edit_lsp_server,
     'src/lsp/server.py SERVER_VERSION'),
    ('src/editor/app.py', edit_editor_app,
     'src/editor/app.py frozen-build fallback'),
    ('src/editor/help_dialogs.py', edit_help_dialogs,
     'src/editor/help_dialogs.py AboutDialog default'),
    ('installer/PKGBUILD', edit_pkgbuild, 'installer/PKGBUILD pkgver'),
    ('.github/ISSUE_TEMPLATE/bug_report.yml', edit_bug_report,
     '.github/ISSUE_TEMPLATE/bug_report.yml placeholder'),
]

CHANGELOG = 'CHANGELOG.md'
README = 'README.md'


# ----------------------------------------------------------------------
# CHANGELOG / README
# ----------------------------------------------------------------------

def _split_lines_keepends(text):
    return text.splitlines(keepends=True)


def _section_bounds(lines, start_index):
    """(start, end) line indices of the section starting at *start_index*."""
    end = len(lines)
    for i in range(start_index + 1, len(lines)):
        if lines[i].startswith('## '):
            end = i
            break
    return start_index, end


def _entry_body(lines, start, end):
    body = [line.rstrip('\n') for line in lines[start + 1:end]]
    while body and not body[0].strip():
        body.pop(0)
    while body and not body[-1].strip():
        body.pop()
    return body


def edit_changelog(text, old_version, new_version, date, force):
    """Rename [Unreleased] -> [NEW] - DATE; insert fresh [Unreleased]."""
    lines = _split_lines_keepends(text)
    unrel = [i for i, line in enumerate(lines)
             if line.rstrip('\n') == CHANGELOG_UNRELEASED]
    if len(unrel) != 1:
        raise BumpError(
            f'CHANGELOG.md: expected exactly one "{CHANGELOG_UNRELEASED}" '
            f'heading, found {len(unrel)}')
    start, end = _section_bounds(lines, unrel[0])
    body = _entry_body(lines, start, end)
    if not body and not force:
        raise BumpError(
            'CHANGELOG.md: [Unreleased] is empty — add entries first '
            '(or pass --force)')
    new_section = ['## [Unreleased]\n', '\n',
                   f'## [{new_version}] - {date}\n', '\n']
    if body:
        new_section.extend(line + '\n' for line in body)
        new_section.append('\n')
    new_lines = lines[:start] + new_section + lines[end:]
    text = ''.join(new_lines)
    # Compare links at the bottom: bump [Unreleased] to the new tag and
    # add the [NEW] compare link right below it.
    link_pattern = re.compile(
        r'(?m)^\[Unreleased\]: ' + re.escape(RELEASE_URL)
        + r'/compare/v[^\s]+\.\.\.HEAD$')
    _sub_count(link_pattern, text, 'CHANGELOG.md [Unreleased] compare link')
    text = link_pattern.sub(
        f'[Unreleased]: {RELEASE_URL}/compare/v{new_version}...HEAD\n'
        f'[{new_version}]: {RELEASE_URL}/compare/v{old_version}...v{new_version}',
        text, count=1)
    return text


def demote_changelog_body(body_lines):
    """Demote heading levels one notch (## -> ###, ### -> ####)."""
    demoted = []
    for line in body_lines:
        if line.startswith('### '):
            demoted.append('#### ' + line[4:])
        elif line.startswith('## '):
            demoted.append('### ' + line[3:])
        else:
            demoted.append(line)
    return demoted


def edit_readme(text, old_version, new_version, date, entry_body):
    """Keep the mirrored 'latest release' section consistent."""
    heading = re.compile(
        r'(?m)^### \[' + re.escape(old_version)
        + r'\] - \d{4}-\d{2}-\d{2}$')
    _sub_count(heading, text, 'README.md mirrored release heading')
    lines = _split_lines_keepends(text)
    idx = next(i for i, line in enumerate(lines) if heading.match(line.rstrip('\n')))
    # Body runs until the "Earlier releases" line (or end of section).
    end = len(lines)
    for i in range(idx + 1, len(lines)):
        if lines[i].startswith('Earlier releases'):
            end = i
            break
        if lines[i].startswith('## '):
            end = i
            break
    body = demote_changelog_body(entry_body)
    new_lines = lines[:idx] + [f'### [{new_version}] - {date}\n', '\n']
    if body:
        new_lines.extend(line + '\n' for line in body)
        new_lines.append('\n')
    new_lines.extend(lines[end:])
    text = ''.join(new_lines)
    link = re.compile(
        r'(?m)^\[' + re.escape(old_version) + r'\]: '
        + re.escape(RELEASE_URL) + r'/compare/v[^/\s]+\.\.\.v'
        + re.escape(old_version) + r'$')
    _sub_count(link, text, 'README.md compare link')
    text = link.sub(
        f'[{new_version}]: {RELEASE_URL}/compare/v{old_version}...v{new_version}',
        text, count=1)
    return text


def changelog_entry_for(text):
    """Body lines of the (new) [version] section just written."""
    lines = _split_lines_keepends(text)
    start = next(i for i, line in enumerate(lines)
                 if line.startswith('## [') and '[Unreleased]' not in line)
    _s, end = _section_bounds(lines, start)
    return _entry_body(lines, start, end)


# ----------------------------------------------------------------------
# Orchestration
# ----------------------------------------------------------------------

class FileEdit:
    def __init__(self, relpath, old, new, label):
        self.relpath = relpath
        self.old = old
        self.new = new
        self.label = label


def compute_edits(root, new_version, date, no_changelog=False, force=False):
    """Compute all edits in memory; raises BumpError before any write."""
    old_version = project_version(root)
    edits = []

    for relpath, edit_fn, label in LITERAL_FILES:
        path = root / relpath
        try:
            old_text = path.read_text(encoding='utf-8')
        except OSError as exc:
            raise BumpError(f'cannot read {relpath}: {exc}') from exc
        new_text = edit_fn(old_text, old_version, new_version)
        edits.append(FileEdit(relpath, old_text, new_text, label))

    if not no_changelog:
        changelog_path = root / CHANGELOG
        readme_path = root / README
        try:
            changelog_old = changelog_path.read_text(encoding='utf-8')
        except OSError as exc:
            raise BumpError(f'cannot read {CHANGELOG}: {exc}') from exc
        try:
            readme_old = readme_path.read_text(encoding='utf-8')
        except OSError as exc:
            raise BumpError(f'cannot read {README}: {exc}') from exc
        old_version = project_version(root)
        changelog_new = edit_changelog(changelog_old, old_version,
                                       new_version, date, force)
        entry_body = changelog_entry_for(changelog_new)
        readme_new = edit_readme(readme_old, old_version, new_version,
                                 date, entry_body)
        edits.append(FileEdit(CHANGELOG, changelog_old, changelog_new,
                              'CHANGELOG.md'))
        edits.append(FileEdit(README, readme_old, readme_new, 'README.md'))
    return edits


def find_version_mismatches(root):
    """Return a list of (relpath, label, found) where relpath disagrees
    with pyproject.toml. Used by --check, tests and the tag guard."""
    import tomllib

    mismatches = []
    with open(root / 'pyproject.toml', 'rb') as handle:
        version = tomllib.load(handle)['project']['version']
    pkgver = pkgbuild_pkgver(version)

    def _check(relpath, pattern, label, expect=None):
        path = root / relpath
        try:
            text = path.read_text(encoding='utf-8')
        except OSError as exc:
            mismatches.append((relpath, label, f'unreadable: {exc}'))
            return
        match = re.search(pattern, text)
        found = match.group(1) if match else None
        want = expect if expect is not None else version
        if found != want:
            mismatches.append((relpath, label, found if found is not None else 'missing'))

    _check('src/compiler/update.py', r"(?m)^FALLBACK_VERSION = '([^']*)'$",
           'compiler.update.FALLBACK_VERSION')
    _check('src/lsp/server.py', r"(?m)^SERVER_VERSION = '([^']*)'$",
           'lsp.server.SERVER_VERSION')
    _check('src/editor/app.py', r"(?m)^    return '([^']*)'$",
           'editor.app frozen-build fallback')
    _check('src/editor/help_dialogs.py',
           r"(?m)^    def __init__\(self, version='([^']*)', parent=None\):$",
           'AboutDialog default')
    _check('installer/PKGBUILD', r'(?m)^pkgver=([^\s]+)$',
           'PKGBUILD pkgver (pacman-safe)', expect=pkgver)
    _check('.github/ISSUE_TEMPLATE/bug_report.yml',
           r'(?m)^\s*placeholder: "([^"]*)"$', 'bug_report.yml placeholder')

    # uv.lock: the easy-math-lang package entry must match.
    lock_path = root / 'uv.lock'
    try:
        lock_text = lock_path.read_text(encoding='utf-8')
    except OSError as exc:
        mismatches.append(('uv.lock', 'uv.lock easy-math-lang entry',
                           f'unreadable: {exc}'))
    else:
        match = re.search(
            r'(?m)^name = "easy-math-lang"\nversion = "([^"]+)"$', lock_text)
        found = match.group(1) if match else None
        if found != version:
            mismatches.append(('uv.lock', 'uv.lock easy-math-lang entry',
                               found if found is not None else 'missing'))

    # Changelog: the released section and both compare links must exist.
    cl_path = root / CHANGELOG
    try:
        cl = cl_path.read_text(encoding='utf-8')
    except OSError as exc:
        mismatches.append((CHANGELOG, 'CHANGELOG.md released section',
                           f'unreadable: {exc}'))
    else:
        if not re.search(r'(?m)^## \[' + re.escape(version) + r'\] - \d{4}-\d{2}-\d{2}$', cl):
            mismatches.append((CHANGELOG, 'CHANGELOG.md released section',
                               'missing or wrong version heading'))
        if not re.search(r'(?m)^\[Unreleased\]: .*compare/v' + re.escape(version) + r'\.\.\.HEAD$', cl):
            mismatches.append((CHANGELOG, 'CHANGELOG.md [Unreleased] link',
                               'missing or stale compare target'))

    # README mirrors the latest release.
    rd_path = root / README
    try:
        rd = rd_path.read_text(encoding='utf-8')
    except OSError as exc:
        mismatches.append((README, 'README.md mirrored release',
                           f'unreadable: {exc}'))
    else:
        if not re.search(r'(?m)^### \[' + re.escape(version) + r'\] - \d{4}-\d{2}-\d{2}$', rd):
            mismatches.append((README, 'README.md mirrored release',
                               'missing or wrong version heading'))
        if not re.search(r'(?m)^\[' + re.escape(version) + r'\]: .*$', rd):
            mismatches.append((README, 'README.md compare link',
                               'missing compare link'))
    return mismatches


def _atomic_write_file(path, text):
    """Write *text* to *path* atomically (temp file in same dir + replace)."""
    directory = path.parent
    fd, tmp = _mkstemp_in(directory)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _mkstemp_in(directory):
    import tempfile

    os.makedirs(directory, exist_ok=True)
    return tempfile.mkstemp(dir=str(directory), prefix='.bump-version-')


def write_edits(root, edits):
    """Write all *edits*; on any failure restore the original contents."""
    snapshots = {}
    written = []
    try:
        for edit in edits:
            path = root / edit.relpath
            snapshots[edit.relpath] = edit.old
            _atomic_write_file(path, edit.new)
            written.append(edit.relpath)
    except BaseException:
        for relpath, old in snapshots.items():
            try:
                _atomic_write_file(root / relpath, old)
            except OSError:
                pass  # best effort; report below
        raise BumpError('a write failed — all files were restored') from None
    return written


def run_uv_lock(root, uv_runner=None, uv_lock_name='uv'):
    """Refresh uv.lock via ``uv lock``; never hand-edit the file."""
    lock_path = root / 'uv.lock'
    before = None
    try:
        before = lock_path.read_bytes()
    except OSError:
        before = None
    if uv_runner is not None:
        result = uv_runner([uv_lock_name, 'lock'], cwd=str(root))
        if result != 0:
            restore_uv_lock(lock_path, before)
            raise BumpError(f'`{uv_lock_name} lock` exited with {result}')
        return
    if shutil.which(uv_lock_name) is None:
        restore_uv_lock(lock_path, before)
        raise BumpError(
            'uv is missing — install it (https://docs.astral.sh/uv/) and '
            'run `uv lock` yourself, or re-run this script')
    result = subprocess.run([uv_lock_name, 'lock'], cwd=str(root))
    if result.returncode != 0:
        restore_uv_lock(lock_path, before)
        raise BumpError(f'`{uv_lock_name} lock` exited with {result.returncode}')


def restore_uv_lock(lock_path, before):
    """Best-effort restore of uv.lock after a failed refresh."""
    if before is None:
        return
    try:
        lock_path.write_bytes(before)
    except OSError:
        pass


def _restore_files(root, snapshots):
    """Best-effort restore of every file from *snapshots*."""
    for relpath, old in snapshots.items():
        try:
            _atomic_write_file(Path(root) / relpath, old)
        except OSError:
            pass


def unified_diff(edits):
    out = []
    for edit in edits:
        old_lines = edit.old.splitlines(keepends=True)
        new_lines = edit.new.splitlines(keepends=True)
        out.extend(difflib.unified_diff(
            old_lines, new_lines,
            fromfile=f'a/{edit.relpath}', tofile=f'b/{edit.relpath}'))
    return ''.join(out)


def validate_target(current, target, force):
    if not VERSION_RE.match(target):
        raise BumpError(
            f'invalid version {target!r} (expected X.Y.Z or X.Y.Z-rc.N)')
    # Refuse a version that is not strictly greater than the current one.
    try:
        cmp_result = compare_versions(target, current)
    except Exception as exc:
        raise BumpError(f'cannot compare {target!r} with {current!r}: {exc}')
    if cmp_result <= 0 and not force:
        relation = 'equal to' if cmp_result == 0 else 'lower than'
        raise BumpError(
            f'refusing to set version {target}: it is {relation} the current '
            f'version {current} (pass --force to override)')
    return target


def resolve_target(current, spec, force):
    """Resolve major/minor/patch/literal to a concrete X.Y.Z[-rc.N]."""
    if spec in ('major', 'minor', 'patch'):
        base = normalize_version(current).split('-', 1)[0]
        match = re.match(r'^(\d+)\.(\d+)\.(\d+)$', base)
        if not match:
            raise BumpError(f'current version {current!r} is not X.Y.Z — '
                            f'pass an explicit version')
        major, minor, patch = (int(part) for part in match.groups())
        if spec == 'major':
            return f'{major + 1}.0.0'
        if spec == 'minor':
            return f'{major}.{minor + 1}.0'
        return f'{major}.{minor}.{patch + 1}'
    return validate_target(current, normalize_version(spec), force)


def build_parser():
    parser = argparse.ArgumentParser(
        prog='bump_version.py',
        description='Bump the project version everywhere in one command.')
    parser.add_argument('target',
                        help='major | minor | patch | X.Y.Z[-rc.N]')
    parser.add_argument('--dry-run', action='store_true',
                        help='print a unified diff and write nothing')
    parser.add_argument('--no-changelog', action='store_true',
                        help='skip CHANGELOG.md and the README.md mirror')
    parser.add_argument('--commit', action='store_true',
                        help='make one chore(release): vX.Y.Z commit with only '
                             'the touched files (never pushes, never tags)')
    parser.add_argument('--date', default=None, metavar='YYYY-MM-DD',
                        help='release date for the changelog (default: today)')
    parser.add_argument('--force', action='store_true',
                        help='allow a target that is not strictly greater, '
                             'and an empty [Unreleased] section')
    parser.add_argument('--root', default=None,
                        help='repo root (defaults to the repo this script '
                             'lives in; used by tests)')
    return parser


def main(argv=None, *, root=None, uv_runner=None, out=print, err=None):
    root_path = Path(root) if root is not None else ROOT
    err = err or (lambda msg: print(msg, file=sys.stderr))
    parser = build_parser()
    args = parser.parse_args(argv)

    date = args.date
    if date is not None:
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', date):
            err(f'error: --date must be YYYY-MM-DD (got {date!r})')
            return 2
        try:
            import datetime

            datetime.date.fromisoformat(date)
        except ValueError:
            err(f'error: --date is not a real date (got {date!r})')
            return 2
    else:
        import datetime

        date = datetime.date.today().isoformat()

    try:
        current = project_version(root_path)
        new_version = resolve_target(current, args.target, args.force)
        edits = compute_edits(root_path, new_version, date,
                              no_changelog=args.no_changelog,
                              force=args.force)
    except BumpError as exc:
        err(f'error: {exc}')
        return 1

    if args.dry_run:
        out(f'Dry run: would bump {current} -> {new_version}')
        out(unified_diff(edits))
        out('Would run: uv lock')
        return 0

    try:
        snapshots = {edit.relpath: edit.old for edit in edits}
        uv_lock_path = root_path / 'uv.lock'
        try:
            uv_before = uv_lock_path.read_bytes()
        except OSError:
            uv_before = None
        written = write_edits(root_path, edits)
        run_uv_lock(root_path, uv_runner=uv_runner)
    except BumpError as exc:
        # Anything failed: put the whole tree back exactly as it was.
        _restore_files(root_path, snapshots)
        restore_uv_lock(uv_lock_path, uv_before)
        err(f'error: {exc}')
        return 1

    out(f'Bumped {current} -> {new_version}')
    for path in written:
        out(f'  wrote {path}')
    out('  refreshed uv.lock (uv lock)')

    if args.commit:
        try:
            subprocess.run(['git', '-C', str(root_path), 'add', '--'] + written
                           + ['uv.lock'], check=True)
            subprocess.run(['git', '-C', str(root_path), 'commit', '-m',
                            f'chore(release): v{new_version}'],
                           check=True)
        except (subprocess.CalledProcessError, OSError) as exc:
            err(f'error: git commit failed: {exc}')
            return 1
        out(f'Committed chore(release): v{new_version} (not pushed, no tag)')
        out('To publish, run:')
        out(f'  git tag -a v{new_version} -m "Easy Math Lang v{new_version}"')
        out(f'  git push origin v{new_version}')
    else:
        out('Review the diff, then commit, then tag (no tag was created):')
        out(f'  git tag -a v{new_version} -m "Easy Math Lang v{new_version}"')
        out(f'  git push origin v{new_version}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
