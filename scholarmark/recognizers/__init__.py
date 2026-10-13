"""
Specialized 2D Formula, Hierarchical Table, Algorithm, and Chart Semantics Recognizers for ScholarMark v3.2.
"""

from .algorithm import AlgorithmRecognizer, AlgorithmResult, AlgorithmLine, ALGORITHM_HEADER_RE
from .chart import ChartSemanticsExtractor, ChartSemantics
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
    "ChartSemanticsExtractor",
    "ChartSemantics",
    "FormulaRecognizer",
    "MathSpanToken",
    "validate_katex_syntax",
    "has_corrupted_glyphs",
    "sanitize_pua_text",
    "TableRecognizer",
]
