"""Comment stripping (// comments, with URL protection)."""

import re


def strip_comments(text):
    cleaned_lines = []
    for raw_line in text.splitlines():
        # Protect URL schemes (https://, http://, ftp://) from // comment stripping
        placeholder = '\x00URLSLASH\x00'
        line_prot = re.sub(r'([A-Za-z][A-Za-z0-9+.-]*://)', lambda m: m.group(1).replace('/', placeholder), raw_line)
        if '//' in line_prot:
            line_prot = line_prot.split('//', 1)[0]
        line = line_prot.replace(placeholder, '/')
        cleaned_lines.append(line)
    return '\n'.join(cleaned_lines)
