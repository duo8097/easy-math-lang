"""ASCII / *keyword symbol shortcuts (->, =>, *alpha, ...).

Ordering rules (do not reorder carelessly):
- SYMBOL_REPLACEMENTS uses plain str.replace in list order, so any
  sequence containing another as a substring must come first
  ('!==' before '==', '<==' before '<=').
- WORD_REPLACEMENTS uses ``\\*word\\b`` regexes, so order does not matter,
  but every new word must be checked against existing ones (e.g. '*to'
  must not swallow '*theta' — the ``\\b`` boundary prevents that).
"""

import re

SYMBOL_REPLACEMENTS = [
    ('|->', '↦'),
    ('<->', '↔'),
    ('<=>', '⇔'),
    ('<==', '⇐'),
    ('==>', '⇒'),
    ('=>', '⇒'),
    ('!==', '≢'),
    ('===', '≡'),
    ('!=', '≠'),
    ('<=', '≤'),
    ('>=', '≥'),
    ('<<', '≪'),
    ('>>', '≫'),
    ('&&', '∧'),
    ('||', '∨'),
    ('|-', '⊢'),
    ('-|', '⊣'),
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
    # Comparisons.
    ('leq', '≤'), ('le', '≤'), ('geq', '≥'), ('ge', '≥'),
    ('neq', '≠'), ('ne', '≠'), ('approx', '≈'), ('cong', '≅'),
    ('equiv', '≡'), ('sim', '∼'), ('simeq', '≃'), ('asymp', '≍'),
    ('doteq', '≐'),
    ('ll', '≪'), ('gg', '≫'),
    ('prec', '≺'), ('succ', '≻'), ('preceq', '⪯'), ('succeq', '⪰'),
    ('pm', '±'), ('mp', '∓'), ('prop', '∝'), ('propto', '∝'),
    ('mid', '∣'), ('ni', '∋'),
    # Arithmetic / set operators.
    ('xx', '×'), ('times', '×'), ('cdot', '⋅'), ('div', '÷'),
    ('oplus', '⊕'), ('otimes', '⊗'), ('circ', '∘'), ('bullet', '•'),
    ('star', '⋆'), ('dagger', '†'),
    ('cap', '∩'), ('cup', '∪'), ('setminus', '∖'),
    ('sqrt', '√'), ('surd', '√'), ('cbrt', '∛'),
    ('deg', '°'), ('degree', '°'),
    ('angle', '∠'), ('triangle', '△'), ('square', '□'), ('diamond', '◇'),
    ('parallel', '∥'), ('perp', '⊥'), ('top', '⊤'), ('bot', '⊥'),
    ('vdash', '⊢'), ('dashv', '⊣'), ('bowtie', '⋈'),
    ('prime', '′'),
    # Logic / sets.
    ('infty', '∞'), ('infinity', '∞'), ('forall', '∀'), ('exists', '∃'),
    ('notin', '∉'), ('isin', '∈'),
    ('subseteq', '⊆'), ('supseteq', '⊇'),
    ('superseteq', '⊇'), ('subset', '⊂'), ('supset', '⊃'), ('superset', '⊃'),
    ('union', '∪'), ('intersect', '∩'), ('intersection', '∩'),
    ('emptyset', '∅'), ('empty', '∅'),
    ('land', '∧'), ('lor', '∨'), ('lnot', '¬'),
    ('therefore', '∴'), ('because', '∵'),
    # Arrows.
    ('to', '→'), ('rightarrow', '→'), ('gets', '←'), ('leftarrow', '←'),
    ('implies', '⇒'), ('Rightarrow', '⇒'),
    ('impliedby', '⇐'), ('Leftarrow', '⇐'),
    ('leftrightarrow', '↔'), ('iff', '⇔'),
    ('uparrow', '↑'), ('downarrow', '↓'), ('updownarrow', '↕'),
    ('mapsto', '↦'),
    # Dots and ellipsis.
    ('ldots', '…'), ('cdots', '⋯'), ('vdots', '⋮'), ('ddots', '⋱'),
    # Delimiters.
    ('langle', '⟨'), ('rangle', '⟩'),
    ('lfloor', '⌊'), ('rfloor', '⌋'),
    ('lceil', '⌈'), ('rceil', '⌉'),
    # Misc symbols.
    ('partial', '∂'), ('nabla', '∇'),
    ('aleph', 'ℵ'), ('hbar', 'ℏ'), ('ell', 'ℓ'),
    ('Re', 'ℜ'), ('Im', 'ℑ'), ('wp', '℘'),
    # Full lowercase Greek alphabet.
    ('alpha', 'α'), ('beta', 'β'), ('gamma', 'γ'), ('delta', 'δ'),
    ('epsilon', 'ε'), ('zeta', 'ζ'), ('eta', 'η'), ('theta', 'θ'),
    ('iota', 'ι'), ('kappa', 'κ'), ('lambda', 'λ'), ('mu', 'μ'),
    ('nu', 'ν'), ('xi', 'ξ'), ('omicron', 'ο'), ('pi', 'π'),
    ('rho', 'ρ'), ('sigma', 'σ'), ('tau', 'τ'), ('upsilon', 'υ'),
    ('phi', 'φ'), ('chi', 'χ'), ('psi', 'ψ'), ('omega', 'ω'),
    # Capital Greek letters that differ from Latin capitals.
    ('Gamma', 'Γ'), ('Delta', 'Δ'), ('Theta', 'Θ'), ('Lambda', 'Λ'),
    ('Xi', 'Ξ'), ('Pi', 'Π'), ('Sigma', 'Σ'), ('Upsilon', 'Υ'),
    ('Phi', 'Φ'), ('Psi', 'Ψ'), ('Omega', 'Ω'),
]


def replace_symbol_shortcuts(text):
    for old, new in SYMBOL_REPLACEMENTS:
        text = text.replace(old, new)
    for old, new in WORD_REPLACEMENTS:
        text = re.sub(rf'\*{re.escape(old)}\b', new, text)
    return text
