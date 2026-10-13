"""
FastEngine: High-speed hybrid heuristic + PyMuPDF4LLM GNN layout engine (ScholarMark v2.1 upgraded).
"""

from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
import fitz
import pymupdf4llm

from .base import BaseEngine
from ..core.academic import parse_academic_metadata
from ..core.caption_matcher import (
    extract_captions_from_page,
    match_figures_to_captions,
    CAPTION_REGEX,
    TABLE_CAPTION_REGEX,
)
from ..core.figure_manager import normalize_markdown_image_links
from ..core.geometry import (
    BoundingBox,
    VisualElement,
    cluster_vector_drawings,
    expand_figure_bbox,
    render_crop_300dpi,
)
from ..ir.document import DocumentIR, PageIR, Block
from ..utils.paths import sanitize_slug


class FastEngine(BaseEngine):
    """Motor rápido basado en PyMuPDF4LLM (GNN layout) + fusión vectorial y captions 1:N."""
    name = "fast"

    def available(self) -> Tuple[bool, str]:
        return True, "PyMuPDF + PyMuPDF4LLM GNN Layout ready"

    @staticmethod
    def _get_page_raster_boxes(page: fitz.Page) -> List[BoundingBox]:
        raster_boxes: List[BoundingBox] = []
        try:
            for img in page.get_images():
                xref = img[0]
                for r in page.get_image_rects(xref):
                    if r.width > 5.0 and r.height > 5.0:
                        raster_boxes.append(BoundingBox.from_fitz_rect(r))
        except Exception:
            pass
        return raster_boxes

    def _extract_hybrid_visuals(
        self,
        doc: fitz.Document,
        asset_dir: Path
    ) -> Tuple[Dict[str, str], List[VisualElement]]:
        caption_map: Dict[str, str] = {}
        saved_elements: List[VisualElement] = []

        for p_idx in range(len(doc)):
            page = doc[p_idx]
            page_w = page.rect.width

            captions = extract_captions_from_page(page) if self.config.caption_matching else []

            visual_elements: List[VisualElement] = []
            if self.config.extract_vector_graphics:
                try:
                    bboxlog = page.get_bboxlog()
                except Exception:
                    bboxlog = []

                drawings = (
                    page.get_drawings()
                    if len(bboxlog) <= self.config.max_page_vector_primitives
                    else None
                )
                words = page.get_text("words")
                raster_boxes = self._get_page_raster_boxes(page)

                vector_boxes = cluster_vector_drawings(
                    page=page,
                    drawings=drawings,
                    max_page_primitives=self.config.max_page_vector_primitives,
                )
                for v_box in vector_boxes:
                    refined = expand_figure_bbox(
                        page=page,
                        figure_bbox=v_box,
                        bleed_padding=self.config.elastic_padding_min,
                        drawings=drawings,
                        words=words,
                        max_vector_primitives=self.config.max_figure_vector_primitives,
                        max_padding=self.config.elastic_padding_max,
                    )
                    if any(refined.iou(rb) > 0.60 or refined.coverage_by(rb) > 0.75 for rb in raster_boxes):
                        continue

                    visual_elements.append(VisualElement(
                        bbox=refined,
                        category="Picture",
                        page_num=p_idx + 1,
                        is_vector=True,
                    ))

            if self.config.caption_matching and visual_elements and captions:
                match_figures_to_captions(visual_elements, captions, page_w)

            for v_idx, elem in enumerate(visual_elements, 1):
                filename = f"vec_p{elem.page_num}_{v_idx}.png"
                target_img = asset_dir / filename
                success = render_crop_300dpi(
                    page=page,
                    bbox=elem.bbox,
                    destination=target_img,
                    target_dpi=self.config.dpi,
                    image_format=self.config.image_format,
                )
                if success:
                    elem.saved_path = filename
                    saved_elements.append(elem)
                    if elem.caption_text:
                        caption_map[filename] = elem.caption_text

        return caption_map, saved_elements

    @staticmethod
    def _inject_vector_figures_in_context(
        raw_markdown: str,
        saved_elements: List[VisualElement],
        caption_map: Dict[str, str],
        slug: str
    ) -> str:
        if not saved_elements:
            return raw_markdown

        md = raw_markdown
        unplaced: List[str] = []

        for elem in saved_elements:
            v_name = elem.saved_path
            if not v_name:
                continue
            cap = caption_map.get(v_name, f"Vector Diagram p.{elem.page_num}")
            placed = False
            if elem.caption_text:
                prefix = elem.caption_text[:45].strip()
                if prefix and prefix in md and f"assets/{slug}/{v_name}" not in md:
                    idx = md.find(prefix)
                    line_start = md.rfind("\n", 0, idx)
                    insert_pos = line_start if line_start != -1 else idx
                    md = md[:insert_pos] + f"\n\n![{cap}](assets/{slug}/{v_name})\n\n" + md[insert_pos:]
                    placed = True

            if not placed:
                unplaced.append(f"![{cap}](assets/{slug}/{v_name})\n\n*{cap}*\n")

        if unplaced:
            md += "\n\n### Extracted Vector Figures & Diagrams\n\n" + "\n".join(unplaced)

        return md

    def _build_ir_pages(self, doc: fitz.Document, saved_vectors: List[VisualElement]) -> Tuple[List[PageIR], List[str]]:
        pages_ir: List[PageIR] = []
        global_order: List[str] = []

        vectors_by_page: Dict[int, List[VisualElement]] = {}
        for v in saved_vectors:
            vectors_by_page.setdefault(v.page_num, []).append(v)

        for p_idx in range(len(doc)):
            page = doc[p_idx]
            p_num = p_idx + 1
            page_blocks: List[Block] = []
            raw_blocks = page.get_text("blocks")

            for b_idx, b in enumerate(raw_blocks):
                if b[6] != 0:
                    continue
                txt = b[4].strip()
                if not txt:
                    continue
                bbox = BoundingBox(float(b[0]), float(b[1]), float(b[2]), float(b[3]))
                kind = "text"
                if CAPTION_REGEX.search(txt) and not TABLE_CAPTION_REGEX.search(txt):
                    kind = "figure_caption"
                elif TABLE_CAPTION_REGEX.search(txt):
                    kind = "table_caption"
                bid = f"p{p_num}_b{b_idx}"
                page_blocks.append(Block(
                    id=bid,
                    kind=kind,
                    bbox=bbox,
                    page=p_num,
                    text=" ".join(txt.split()),
                    source="native",
                ))

            for v_idx, v in enumerate(vectors_by_page.get(p_num, []), 1):
                bid = f"p{p_num}_vec{v_idx}"
                page_blocks.append(Block(
                    id=bid,
                    kind="figure",
                    bbox=v.bbox,
                    page=p_num,
                    asset=v.saved_path,
                    caption_text=v.caption_text,
                    source="native",
                ))

            p_order = [b.id for b in page_blocks]
            global_order.extend(p_order)
            pages_ir.append(PageIR(
                page_number=p_num,
                width=float(page.rect.width),
                height=float(page.rect.height),
                rotation=int(page.rotation),
                blocks=page_blocks,
                reading_order=p_order,
            ))

        return pages_ir, global_order

    def parse(
        self,
        doc: fitz.Document,
        pdf_path: Path,
        asset_dir: Optional[Path] = None
    ) -> Tuple[DocumentIR, Dict[str, Any]]:
        stem = pdf_path.stem
        caption_map: Dict[str, str] = {}
        saved_vectors: List[VisualElement] = []

        if self.config.extract_images and asset_dir and self.config.high_fidelity_figures:
            caption_map, saved_vectors = self._extract_hybrid_visuals(doc, asset_dir)

        raw_markdown = pymupdf4llm.to_markdown(
            str(pdf_path),
            write_images=self.config.extract_images,
            image_path=str(asset_dir) if (self.config.extract_images and asset_dir) else "",
            image_format=self.config.image_format,
            dpi=self.config.dpi,
            show_progress=False,
        )

        if saved_vectors:
            slug = sanitize_slug(stem)
            raw_markdown = self._inject_vector_figures_in_context(
                raw_markdown=raw_markdown,
                saved_elements=saved_vectors,
                caption_map=caption_map,
                slug=slug,
            )

        if self.config.extract_images:
            raw_markdown = normalize_markdown_image_links(raw_markdown, stem, caption_map=caption_map)

        pages_ir, global_order = self._build_ir_pages(doc, saved_vectors)
        meta = parse_academic_metadata(raw_markdown, pdf_path.name)
        meta["engine"] = self.name

        ir = DocumentIR(
            meta=meta,
            pages=pages_ir,
            reading_order=global_order,
            markdown_override=raw_markdown,
        )
        stats = {
            "vector_figures": len(saved_vectors),
            "caption_map": caption_map,
            "engine_used": self.name,
        }
        return ir, stats
