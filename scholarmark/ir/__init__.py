"""
Intermediate Representation (IR) package for ScholarMark v3.0.
"""

from .document import Block, PageIR, DocumentIR, BlockKind, BlockSource

__all__ = ["Block", "PageIR", "DocumentIR", "BlockKind", "BlockSource"]
