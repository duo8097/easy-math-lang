"""ASCII / *keyword symbol shortcuts (->, =>, *alpha, ...)."""

import re

SYMBOL_REPLACEMENTS = [
    ('|->', '↦'),
    ('<->', '↔'),
    ('<=>', '⇔'),
    ('=>', '⇒'),
    ('<=', '≤'),
    ('>=', '≥'),
    ('!=', '≠'),
    ('&&', '∧'),
    ('||', '∨'),
    ('==', '='),
    ('+-', '±'),
    ('-+', '∓'),
    ('...', '…'),
    ('::', '∷'),
    ('~=~', '≅'),
    ('~=', '≈'),
    ('~~', '≈'),
    ('**', '⋅'),
    ('<-', '←'),
    ('->', '→'),
]

WORD_REPLACEMENTS = [
    ('leq', '≤'), ('le', '≤'), ('geq', '≥'), ('ge', '≥'),
    ('neq', '≠'), ('ne', '≠'), ('approx', '≈'), ('cong', '≅'),
    ('pm', '±'), ('mp', '∓'), ('prop', '∝'), ('propto', '∝'),
    ('xx', '×'), ('times', '×'), ('cdot', '⋅'), ('div', '÷'),
    ('sqrt', '√'), ('cbrt', '∛'), ('deg', '°'), ('degree', '°'),
    ('angle', '∠'), ('triangle', '△'), ('parallel', '∥'), ('perp', '⊥'),
    ('infty', '∞'), ('infinity', '∞'), ('forall', '∀'), ('exists', '∃'),
    ('notin', '∉'), ('isin', '∈'), ('subseteq', '⊆'), ('supseteq', '⊇'),
    ('superseteq', '⊇'), ('subset', '⊂'), ('supset', '⊃'), ('superset', '⊃'),
    ('union', '∪'), ('intersect', '∩'), ('intersection', '∩'),
    ('emptyset', '∅'), ('empty', '∅'),
    ('land', '∧'), ('lor', '∨'), ('lnot', '¬'),
    ('therefore', '∴'), ('because', '∵'),
    ('alpha', 'α'), ('beta', 'β'), ('gamma', 'γ'), ('delta', 'δ'),
    ('epsilon', 'ε'), ('theta', 'θ'), ('lambda', 'λ'), ('mu', 'μ'),
    ('pi', 'π'), ('sigma', 'σ'), ('omega', 'ω'),
    ('Delta', 'Δ'), ('Sigma', 'Σ'), ('Omega', 'Ω'),
]


def replace_symbol_shortcuts(text):
    for old, new in SYMBOL_REPLACEMENTS:
        text = text.replace(old, new)
    for old, new in WORD_REPLACEMENTS:
        text = re.sub(rf'\*{re.escape(old)}\b', new, text)
    return text
