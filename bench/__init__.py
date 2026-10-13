"""
Benchmark and evaluation suite for ScholarMark v3.0.
"""

from .metrics import (
    normalized_edit_distance,
    text_fidelity_score,
    kendall_tau_order,
    teds_table_score,
    latex_formula_similarity,
    caption_matching_f1,
)
from .gold_suite import run_synthetic_gold_benchmark, CaseComparison

__all__ = [
    "normalized_edit_distance",
    "text_fidelity_score",
    "kendall_tau_order",
    "teds_table_score",
    "latex_formula_similarity",
    "caption_matching_f1",
    "run_synthetic_gold_benchmark",
    "CaseComparison",
]
