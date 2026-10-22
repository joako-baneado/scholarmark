"""
ScholarMark: High-Precision Scientific Paper to Markdown Extractor & RAG Grounding Engine.
"""

__version__ = "4.1.0"
__author__ = "ScholarMark Contributors"

from .config import ExtractorConfig
from .extractor import ScholarExtractor, ExtractionResult
from .core.manifest import generate_manifest
from .rag.chunker import SemanticChunk, SemanticChunker, export_chunks_jsonl

__all__ = [
    "ScholarExtractor",
    "ExtractionResult",
    "ExtractorConfig",
    "generate_manifest",
    "SemanticChunk",
    "SemanticChunker",
    "export_chunks_jsonl",
    "__version__",
]
