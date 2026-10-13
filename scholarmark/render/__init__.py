"""
Rendering modules for ScholarMark v3.0 DocumentIR (Markdown and Canonical JSON).
"""

from .markdown import render_markdown
from .json_export import export_canonical_json

__all__ = ["render_markdown", "export_canonical_json"]
