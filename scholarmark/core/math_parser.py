"""
LaTeX math transformation module for ScholarMark v3.0.
Converts Unicode mathematical alphanumeric symbols, Greek letters, and block equations
into standardized KaTeX / LaTeX format ($...$ and $$...$$) while avoiding false positives on prose.
"""

import re
import unicodedata

# Mapeo de letras griegas matemáticas Unicode (U+1D6FC - U+1D714 y estándar)
GREEK_MATH_MAP = {
    '\U0001d6fc': r'\alpha', '\U0001d6fd': r'\beta', '\U0001d6fe': r'\gamma', '\U0001d6ff': r'\delta',
    '\U0001d700': r'\epsilon', '\U0001d701': r'\zeta', '\U0001d702': r'\eta', '\U0001d703': r'\theta',
    '\U0001d704': r'\iota', '\U0001d705': r'\kappa', '\U0001d706': r'\lambda', '\U0001d707': r'\mu',
    '\U0001d708': r'\nu', '\U0001d709': r'\xi', '\U0001d70a': r'o', '\U0001d70b': r'\pi',
    '\U0001d70c': r'\rho', '\U0001d70d': r'\varsigma', '\U0001d70e': r'\sigma', '\U0001d70f': r'\tau',
    '\U0001d710': r'\upsilon', '\U0001d711': r'\phi', '\U0001d712': r'\chi', '\U0001d713': r'\psi',
    '\U0001d714': r'\omega',
    # Mayúsculas griegas
    '\U0001d6e2': r'\Alpha', '\U0001d6e3': r'\Beta', '\U0001d6e4': r'\Gamma', '\U0001d6e5': r'\Delta',
    '\U0001d6e6': r'\Epsilon', '\U0001d6e7': r'\Zeta', '\U0001d6e8': r'\Eta', '\U0001d6e9': r'\Theta',
    '\U0001d6ea': r'\Iota', '\U0001d6eb': r'\Kappa', '\U0001d6ec': r'\Lambda', '\U0001d6ed': r'\Mu',
    '\U0001d6ee': r'\Nu', '\U0001d6ef': r'\Xi', '\U0001d6f1': r'\Pi', '\U0001d6f2': r'\Rho',
    '\U0001d6f4': r'\Sigma', '\U0001d6f5': r'\Tau', '\U0001d6f6': r'\Upsilon', '\U0001d6f7': r'\Phi',
    '\U0001d6f8': r'\Chi', '\U0001d6f9': r'\Psi', '\U0001d6fa': r'\Omega',
    # Estándar Unicode
    '\u03b1': r'\alpha', '\u03b2': r'\beta', '\u03b3': r'\gamma', '\u03b4': r'\delta',
    '\u03b5': r'\epsilon', '\u03b6': r'\zeta', '\u03b7': r'\eta', '\u03b8': r'\theta',
    '\u03bb': r'\lambda', '\u03bc': r'\mu', '\u03c0': r'\pi', '\u03c3': r'\sigma',
    '\u03c4': r'\tau', '\u03c9': r'\omega',
}

MATH_OPERATORS = {
    '\u2208': r'\in', '\u2209': r'\notin', '\u2211': r'\sum', '\u220f': r'\prod',
    '\u222b': r'\int', '\u2248': r'\approx', '\u2260': r'\ne', '\u2264': r'\le',
    '\u2265': r'\ge', '\u2212': r'-', '\xd7': r'\times', '\u2202': r'\partial',
    '\u2207': r'\nabla', '\u2192': r'\to', '\u21d2': r'\implies', '\u221e': r'\infty',
}

_STRONG_MATH_OPS = ('=', r'\sum', r'\int', r'\prod', r'\times', r'\to', r'\in', r'\approx', r'\le', r'\ge', r'\ne', r'\partial', r'\nabla', r'\frac')
_PROSE_WORD_RE = re.compile(r'(?<!\\)\b[a-zA-Z]{4,}\b')


def unicode_char_to_latex(char: str) -> str:
    """Convierte un caracter alfanumérico matemático Unicode a LaTeX o carácter base."""
    if char in GREEK_MATH_MAP:
        return GREEK_MATH_MAP[char]
    if char in MATH_OPERATORS:
        return f" {MATH_OPERATORS[char]} "

    code = ord(char)
    if 0x1D400 <= code <= 0x1D7FF:
        try:
            norm = unicodedata.normalize('NFKD', char)
            if norm:
                return norm
        except Exception:
            pass
    return char


def clean_math_glyphs(text: str) -> str:
    """Reemplaza caracteres alfanuméricos matemáticos por caracteres equivalentes estándar."""
    return ''.join(unicode_char_to_latex(c) for c in text)


def format_inline_expressions(text: str) -> str:
    """Formatea ángulos, grados y letras griegas en modo matemático en línea ($...$)."""
    text = re.sub(r'(\d+)\s*<\s*sup\s*>.*?(?:circ|\u2218).*?<\s*/sup\s*>', lambda m: f"${m.group(1)}^\\circ$", text)
    text = re.sub(r'(?<!\$)\b(\d+)\s*\^\s*\\circ', lambda m: f"${m.group(1)}^\\circ$", text)

    for grk in set(GREEK_MATH_MAP.values()):
        escaped = re.escape(grk)
        text = re.sub(rf'_\s*{escaped}\s*_', lambda m, g=grk: f"${g}$", text)

    text = re.sub(r'<\s*sup\s*>(.*?)<\s*/sup\s*>', r'^{\1}', text)
    text = re.sub(r'<\s*sub\s*>(.*?)<\s*/sub\s*>', r'_{\1}', text)
    return text


def _is_genuine_equation_line(content: str) -> bool:
    """
    Evalúa si el texto previo a una etiqueta (n) es realmente una ecuación matemática
    y no una oración en prosa con un guión (ej. 'state-of-the-art method (1)').
    """
    if not content:
        return False

    has_strong_op = any(op in content for op in _STRONG_MATH_OPS)
    has_arith_op = any(op in content for op in (' + ', ' - ', '^', '_'))

    if not (has_strong_op or has_arith_op):
        return False

    # Contar palabras de prosa (>= 4 letras que no están precedidas por backslash LaTeX)
    prose_words = _PROSE_WORD_RE.findall(content)
    if len(prose_words) > 6:
        return False

    # Si no tiene '=' ni operador fuerte (solo '+' o '-'), exigir <= 2 palabras largas
    if not has_strong_op and len(prose_words) > 2:
        return False

    return True


def isolate_equations(text: str) -> str:
    """Detecta ecuaciones numeradas y las encapsula en bloques $$ ... \\tag{X} $$."""
    lines = text.splitlines()
    output = []

    for line in lines:
        stripped = line.strip()
        eq_match = re.search(r'^(.*?)\s*\((\d+[a-zA-Z]?)\)\s*$', stripped)
        is_table_or_heading = (
            stripped.startswith('#')
            or stripped.startswith('|')
            or stripped.startswith('**')
            or stripped.startswith('-')
            or stripped.startswith('* ')
        )

        if eq_match and not is_table_or_heading and len(stripped) < 260:
            content = eq_match.group(1).strip('_ ')
            tag = eq_match.group(2).strip()
            if _is_genuine_equation_line(content):
                output.append(f"\n$$\n{content} \\tag{{{tag}}}\n$$\n")
                continue

        output.append(line)

    return '\n'.join(output)


def sanitize_numeric_typography(text: str) -> str:
    """Sanitiza fracturas tipográficas de decimales y operadores causadas por itálicas OCR/PDF."""
    text = re.sub(r'(\d+)\s*_\s*\.\s*_\s*(\d+)', r'\1.\2', text)
    text = re.sub(r'(\d+)_\._\s*(\d+)', r'\1.\2', text)
    text = re.sub(r'(\d+)\s+\.\s+(\d+)', r'\1.\2', text)
    text = text.replace('\u2215', '/').replace('\u2044', '/')
    text = text.replace('\u2212', '-')
    return text


def parse_math(text: str) -> str:
    """Pipeline completo de transformación matemática."""
    t = sanitize_numeric_typography(text)
    t = clean_math_glyphs(t)
    t = format_inline_expressions(t)
    t = isolate_equations(t)
    return t
