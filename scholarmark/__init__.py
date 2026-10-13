"""
ScholarMark: High-Precision Scientific Paper to Markdown Extractor & RAG Grounding Engine.
"""

__version__ = "3.0.0"
__author__ = "ScholarMark Contributors"

from .config import ExtractorConfig
from .extractor import ScholarExtractor, ExtractionResult
from .core.manifest import generate_manifest

__all__ = ["ScholarExtractor", "ExtractionResult", "ExtractorConfig", "generate_manifest", "__version__"]

