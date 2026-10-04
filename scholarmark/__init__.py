"""
ScholarMark: High-Precision Scientific Paper to Markdown Extractor & RAG Grounding Engine.
"""

__version__ = "2.0.0"
__author__ = "ScholarMark Contributors"

from .extractor import ScholarExtractor
from .core.manifest import generate_manifest

__all__ = ["ScholarExtractor", "generate_manifest"]
