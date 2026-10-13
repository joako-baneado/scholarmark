"""
Layout analysis, span mapping, and topological reading order package for ScholarMark v3.0.
"""

from .detector import LayoutDetector, LayoutRegion
from .span_mapper import map_spans_to_blocks
from .reading_order import order_page_blocks, stitch_cross_page_paragraphs

__all__ = [
    "LayoutDetector",
    "LayoutRegion",
    "map_spans_to_blocks",
    "order_page_blocks",
    "stitch_cross_page_paragraphs",
]
