"""
Optional Docling reference adapter for ScholarMark v3.0.
Used when 'docling' is installed in the environment for benchmarking or external validation.
"""

from pathlib import Path
from typing import Optional, Tuple, Dict, Any
import fitz

from .base import BaseEngine
from ..core.academic import parse_academic_metadata
from ..ir.document import DocumentIR


class DoclingEngine(BaseEngine):
    """Adaptador opcional hacia IBM Docling (v2+ layout RT-DETR + TableFormer)."""
    name = "docling"

    def available(self) -> Tuple[bool, str]:
        try:
            import docling.document_converter  # noqa: F401
            return True, "IBM Docling available"
        except ImportError:
            return False, "Package 'docling' not installed (install via: pip install scholarmark[docling])"

    def parse(
        self,
        doc: fitz.Document,
        pdf_path: Path,
        asset_dir: Optional[Path] = None
    ) -> Tuple[DocumentIR, Dict[str, Any]]:
        ok, msg = self.available()
        if not ok:
            raise RuntimeError(msg)

        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        conv_res = converter.convert(str(pdf_path))
        md_text = conv_res.document.export_to_markdown()
        meta = parse_academic_metadata(md_text, pdf_path.name)
        meta["engine"] = self.name

        ir = DocumentIR(
            meta=meta,
            pages=[],
            reading_order=[],
            markdown_override=md_text,
        )
        return ir, {"vector_figures": 0, "caption_map": {}, "engine_used": self.name}
