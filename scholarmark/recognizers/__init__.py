"""
Specialized 2D Formula, Hierarchical Table, and Algorithm Recognizers for ScholarMark v3.1.
"""

from .algorithm import AlgorithmRecognizer, AlgorithmResult, AlgorithmLine, ALGORITHM_HEADER_RE
from .formula import (
    FormulaRecognizer,
    MathSpanToken,
    validate_katex_syntax,
    has_corrupted_glyphs,
    sanitize_pua_text,
)
from .table import TableRecognizer

__all__ = [
    "AlgorithmRecognizer",
    "AlgorithmResult",
    "AlgorithmLine",
    "ALGORITHM_HEADER_RE",
    "FormulaRecognizer",
    "MathSpanToken",
    "validate_katex_syntax",
    "has_corrupted_glyphs",
    "sanitize_pua_text",
    "TableRecognizer",
]
