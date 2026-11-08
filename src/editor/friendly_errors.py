"""Plain-language explanations for common editor errors.

Qt-free: maps the raw compiler/LSP diagnostic text (which must stay
unchanged — the compiler and LSP protocol are untouched by this
feature) to a small ``(key, params)`` pair whose title/help/hint live
in the i18n catalogs. The UI always keeps the raw message visible
below the friendly text. Only the most common errors are mapped;
anything else falls back to the generic entry.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass

try:  # Reuse the compiler's known-command table when importable.
    from compiler.diagnostics import KNOWN_COMMANDS, _SUGGESTIONS
except Exception:  # pragma: no cover - defensive
    KNOWN_COMMANDS = frozenset()
    _SUGGESTIONS = {}


@dataclass(frozen=True)
class FriendlyError:
    """One mapped error: catalog key + placeholder values."""

    key: str
    params: dict

    @property
    def title_key(self):
        return f'{self.key}.title'

    @property
    def help_key(self):
        return f'{self.key}.help'

    @property
    def hint_key(self):
        return f'{self.key}.hint'


_VAR_RE = re.compile(r'Undefined variable <([^<>]+)>')
_CMD_RE = re.compile(r'Unknown command \*([^\W\d_][\w\-]*)(?:\(\.\.\.\))?')
_SUGGEST_RE = re.compile(r"Did you mean '?(\*?[^'\s]+)'?\??")
_DID_YOU_MEAN_VAR_RE = re.compile(r"Did you mean '([^']+)'\?")


def _suggest_command(cmd):
    if not cmd:
        return None
    hint = _SUGGESTIONS.get(cmd)
    if hint:
        return hint
    if not KNOWN_COMMANDS:
        return None
    close = difflib.get_close_matches(
        cmd, sorted(KNOWN_COMMANDS), n=1, cutoff=0.8)
    return close[0] if close else None


def explain(raw_message):
    """Map one raw diagnostic message to a :class:`FriendlyError`.

    Never raises; unknown messages get the generic explanation.
    """
    text = raw_message if isinstance(raw_message, str) else str(raw_message or '')
    message = text.strip()
    if not message:
        return FriendlyError('friendly.generic', {})

    suggested = _DID_YOU_MEAN_VAR_RE.search(message)
    if message.startswith('Undefined variable <'):
        match = _VAR_RE.search(message)
        name = match.group(1).strip() if match else ''
        params = {'name': name}
        if suggested:
            params['_hint_name'] = suggested.group(1)
        return FriendlyError('friendly.undefined_variable', params)

    if 'Unknown command *' in message:
        match = _CMD_RE.search(message)
        cmd = match.group(1) if match else ''
        hint = _suggest_command(cmd)
        params = {'command': hint} if hint else {}
        return FriendlyError('friendly.unknown_command', params)

    if 'only valid inside *draw' in message:
        return FriendlyError('friendly.geometry_outside_draw', {})

    if 'Unclosed math delimiter' in message or 'missing closing \\' in message:
        # Plain membership test would also match the parse fallback
        # below; keep this branch before the generic parenthesis one.
        return FriendlyError('friendly.unclosed_math', {})

    if 'Unclosed block' in message:
        return FriendlyError('friendly.unclosed_block', {})

    if 'Unclosed' in message and 'missing closing parenthesis' in message:
        return FriendlyError('friendly.unclosed_paren', {})

    if 'Unclosed parenthesis in calc' in message:
        return FriendlyError('friendly.unclosed_paren', {})

    if 'Empty math expression' in message:
        return FriendlyError('friendly.empty_math', {})

    if '[Calc Error' in message or 'calc()' in message and 'Error' in message:
        return FriendlyError('friendly.calc_error', {})

    if 'cannot be used inside math' in message:
        return FriendlyError('friendly.table_in_math', {})

    if 'is empty' in message and ('*table' in message or '*matrix' in message
                                  or '*mat' in message):
        return FriendlyError('friendly.table_shape', {})

    if 'is empty' in message and ('*doc_title' in message
                                  or '*doc_font' in message
                                  or '*title' in message):
        return FriendlyError('friendly.empty_control', {})

    if message == 'Invalid document text':
        return FriendlyError('friendly.invalid_doc', {})

    if message.startswith('Analysis failed:'):
        return FriendlyError('friendly.analysis_failed', {})

    if 'rows have different lengths' in message:
        return FriendlyError('friendly.table_shape', {})

    if 'GeometryError' in message or 'GeometryWarning' in message:
        return FriendlyError('friendly.geometry_error', {})

    return FriendlyError('friendly.generic', {})


def hint_params(friendly):
    """Placeholder values for the hint line, if the error has a hint."""
    if not isinstance(friendly, FriendlyError):
        return None
    hint = friendly.params.get('_hint')
    if isinstance(hint, dict) and hint:
        return hint
    if friendly.key == 'friendly.unknown_command':
        command = friendly.params.get('command')
        return {'command': command} if command else None
    if friendly.key == 'friendly.undefined_variable':
        # The help text already names the variable; the optional
        # "did you mean" line only appears when the raw message
        # carried one.
        suggested = friendly.params.get('_hint_name')
        return {'name': suggested} if suggested else None
    return None


def format_friendly(raw_message, translator=None):
    """``'Title. Help. Did you mean …?'`` in the translator's language.

    *translator* is anything with a ``tr(key, **params)`` method; the
    current i18n translator is used when omitted.
    """
    if translator is None:
        from .i18n import current_translator
        translator = current_translator()
    friendly = explain(raw_message)
    params = {k: v for k, v in friendly.params.items()
              if not k.startswith('_')}
    parts = [translator.tr(friendly.title_key, **params),
             translator.tr(friendly.help_key, **params)]
    hint = hint_params(friendly)
    if hint:
        parts.append(translator.tr(friendly.hint_key, **hint))
    return ' '.join(part for part in parts if part)


def format_for_display(raw_message, translator=None):
    """Friendly text with the raw technical message kept below it."""
    if translator is None:
        from .i18n import current_translator
        translator = current_translator()
    friendly_text = format_friendly(raw_message, translator)
    raw = raw_message if isinstance(raw_message, str) else str(raw_message or '')
    detail_label = translator.tr('friendly.technical_details')
    return f'{friendly_text}\n\n{detail_label}\n{raw}'
