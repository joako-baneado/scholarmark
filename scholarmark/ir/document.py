"""
Canonical Intermediate Representation (DocumentIR) for ScholarMark v3.0.
Preserves spatial bounding boxes, topological reading order, native vs. model provenance,
LaTeX equations, semantic HTML tables, and 1:N figure-caption links.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Literal

from ..core.geometry import BoundingBox

BlockKind = Literal[
    "title",
    "section_header",
    "text",
    "footnote",
    "abandon",
    "formula",
    "formula_caption",
    "table",
    "table_caption",
    "figure",
    "figure_caption",
    "list",
    "author_bio",
]

BlockSource = Literal["native", "model", "ocr"]


@dataclass
class Block:
    """Unidad estructural atómica dentro de una página científica."""
    id: str
    kind: str
    bbox: BoundingBox
    page: int
    text: str = ""
    latex: Optional[str] = None
    html: Optional[str] = None
    gfm: Optional[str] = None
    asset: Optional[str] = None
    caption_id: Optional[str] = None
    caption_text: Optional[str] = None
    heading_level: int = 2
    confidence: float = 1.0
    source: BlockSource = "native"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "page": self.page,
            "bbox": [
                round(self.bbox.x0, 2),
                round(self.bbox.y0, 2),
                round(self.bbox.x1, 2),
                round(self.bbox.y1, 2),
            ],
            "text": self.text,
            "latex": self.latex,
            "html": self.html,
            "gfm": self.gfm,
            "asset": self.asset,
            "caption_id": self.caption_id,
            "caption_text": self.caption_text,
            "heading_level": self.heading_level,
            "confidence": round(self.confidence, 4),
            "source": self.source,
            "metadata": self.metadata,
        }


@dataclass
class PageIR:
    """Representación estructural de una página individual."""
    page_number: int
    width: float
    height: float
    rotation: int = 0
    blocks: List[Block] = field(default_factory=list)
    reading_order: List[str] = field(default_factory=list)

    def ordered_blocks(self) -> List[Block]:
        if not self.reading_order:
            return [b for b in self.blocks if b.kind != "abandon"]
        by_id = {b.id: b for b in self.blocks}
        ordered = [by_id[bid] for bid in self.reading_order if bid in by_id]
        seen = set(self.reading_order)
        for b in self.blocks:
            if b.id not in seen and b.kind != "abandon":
                ordered.append(b)
        return ordered

    def to_dict(self) -> Dict[str, Any]:
        return {
            "page_number": self.page_number,
            "width": round(self.width, 2),
            "height": round(self.height, 2),
            "rotation": self.rotation,
            "reading_order": self.reading_order,
            "blocks": [b.to_dict() for b in self.blocks],
        }


@dataclass
class DocumentIR:
    """Representación canónica completa de un artículo científico."""
    meta: Dict[str, Any] = field(default_factory=dict)
    pages: List[PageIR] = field(default_factory=list)
    reading_order: List[str] = field(default_factory=list)
    markdown_override: Optional[str] = None

    def all_blocks_ordered(self) -> List[Block]:
        """Retorna todos los bloques activos del documento según el orden topológico global."""
        by_id: Dict[str, Block] = {}
        for p in self.pages:
            for b in p.blocks:
                by_id[b.id] = b

        if self.reading_order:
            ordered = [by_id[bid] for bid in self.reading_order if bid in by_id and by_id[bid].kind != "abandon"]
            seen = set(self.reading_order)
            for p in self.pages:
                for b in p.ordered_blocks():
                    if b.id not in seen and b.kind != "abandon":
                        ordered.append(b)
            return ordered

        result: List[Block] = []
        for p in self.pages:
            result.extend(p.ordered_blocks())
        return result

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": "3.0.0",
            "meta": self.meta,
            "reading_order": self.reading_order,
            "pages": [p.to_dict() for p in self.pages],
        }
