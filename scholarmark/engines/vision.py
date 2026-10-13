"""
VisionEngine: ScholarMark v3.0 Asymmetric Hybrid Modular Pipeline.
Combines LayoutDetector (ONNX / Multimodal), Native SpanMapper, 2D FormulaRecognizer,
Hierarchical HTML TableRecognizer, 1:N Bipartite CaptionMatcher, and DAG Reading Order Solver.
"""

from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
import fitz

from .base import BaseEngine
from ..core.academic import parse_academic_metadata
from ..core.caption_matcher import (
    match_figures_to_captions,
    match_tables_to_captions,
)
from ..core.geometry import VisualElement, render_crop_300dpi
from ..ir.document import DocumentIR, PageIR, Block
from ..layout import (
    LayoutDetector,
    map_spans_to_blocks,
    order_page_blocks,
    stitch_cross_page_paragraphs,
)
from ..models.registry import resolve_ort_providers
from ..recognizers import FormulaRecognizer, TableRecognizer


class VisionEngine(BaseEngine):
    """
    Motor híbrido v3.0:
    1. Detección de regiones de diseño (LayoutDetector).
    2. Mapeo de spans vectoriales nativos + rescate de huérfanos (SpanMapper).
    3. Reconstrucción algebraica 2D de ecuaciones aisladas (FormulaRecognizer).
    4. Reconstrucción tabular jerárquica HTML/GFM (TableRecognizer).
    5. Asociación de leyendas 1:N (CaptionMatcher) y recorte elástico a 300 DPI.
    6. Orden de lectura topológico DAG + unión de párrafos entre páginas.
    """
    name = "vision"

    def __init__(self, config):
        super().__init__(config)
        self.layout_detector = LayoutDetector(
            device=config.device,
            onnx_model_path=config.onnx_model_path,
        )
        self.formula_recognizer = FormulaRecognizer(
            device=config.device,
            onnx_model_path=config.onnx_model_path,
        )
        self.table_recognizer = TableRecognizer(
            device=config.device,
            onnx_model_path=config.onnx_model_path,
        )

    def available(self) -> Tuple[bool, str]:
        _, label = resolve_ort_providers(self.config.device)
        return True, f"VisionEngine v3.0 ready ({label})"

    def parse(
        self,
        doc: fitz.Document,
        pdf_path: Path,
        asset_dir: Optional[Path] = None
    ) -> Tuple[DocumentIR, Dict[str, Any]]:
        pages_ir: List[PageIR] = []
        caption_map: Dict[str, str] = {}
        vector_fig_count = 0

        for p_idx in range(len(doc)):
            page = doc[p_idx]
            page_num = p_idx + 1
            page_w = float(page.rect.width)
            page_h = float(page.rect.height)

            # Etapa 1: Detección estructural de regiones
            regions = self.layout_detector.detect_page(
                page=page,
                page_num=page_num,
                max_page_primitives=self.config.max_page_vector_primitives,
                max_figure_primitives=self.config.max_figure_vector_primitives,
                elastic_min=self.config.elastic_padding_min,
                elastic_max=self.config.elastic_padding_max,
            )

            # Etapa 2: Intersección con spans nativos del PDF (0% alucinación en prosa)
            blocks = map_spans_to_blocks(
                page=page,
                page_num=page_num,
                regions=regions,
                rescue_orphans=True,
            )

            try:
                bboxlog = page.get_bboxlog()
            except Exception:
                bboxlog = []
            drawings = (
                page.get_drawings()
                if len(bboxlog) <= self.config.max_page_vector_primitives
                else None
            )

            # Etapa 3A: Reconocimiento de fórmulas 2D
            for b in blocks:
                if b.kind == "formula":
                    latex_str, conf, eq_tag = self.formula_recognizer.recognize_region(
                        page=page,
                        bbox=b.bbox,
                        fallback_text=b.text,
                        drawings=drawings,
                    )
                    b.latex = latex_str
                    b.confidence = conf
                    b.source = "model"
                    if eq_tag and not b.metadata.get("tag"):
                        b.metadata["tag"] = eq_tag

            # Etapa 3B: Reconstrucción tabular jerárquica (HTML colspan/rowspan + GFM)
            for b in blocks:
                if b.kind == "table":
                    html_str, gfm_str, has_merged = self.table_recognizer.recognize_table(
                        page=page,
                        bbox=b.bbox,
                    )
                    b.html = html_str
                    b.gfm = gfm_str
                    b.source = "model"
                    b.metadata["has_merged_cells"] = has_merged

            # Etapa 4: Asociación 1:N de leyendas para figuras y tablas + renderizado 300 DPI
            fig_blocks = [b for b in blocks if b.kind == "figure"]
            fig_cap_blocks = [b for b in blocks if b.kind == "figure_caption" and b.text.strip()]
            prose_boxes = [b.bbox for b in blocks if b.kind == "text" and len(b.text) > 50]

            if fig_blocks and fig_cap_blocks and self.config.caption_matching:
                vis_figs = [
                    VisualElement(
                        bbox=fb.bbox,
                        category="Picture",
                        page_num=page_num,
                        subpanel_labels=fb.metadata.get("subpanel_labels", []),
                    )
                    for fb in fig_blocks
                ]
                cap_tuples = [(cb.bbox, cb.text) for cb in fig_cap_blocks]
                match_figures_to_captions(
                    figures=vis_figs,
                    captions=cap_tuples,
                    page_width=page_w,
                    prose_blocks=prose_boxes,
                    allow_many_to_one=True,
                )
                cap_text_to_id = {cb.text: cb.id for cb in fig_cap_blocks}
                for fb, vf in zip(fig_blocks, vis_figs):
                    if vf.caption_text:
                        fb.caption_text = vf.caption_text
                        fb.caption_id = cap_text_to_id.get(vf.caption_text)
                    if vf.composite_group_id:
                        fb.metadata["composite_group_id"] = vf.composite_group_id

            # Renderizar activos visuales de figuras
            if self.config.extract_images and asset_dir:
                for f_idx, fb in enumerate(fig_blocks, 1):
                    filename = f"fig_p{page_num}_{f_idx}.png"
                    target_img = asset_dir / filename
                    if render_crop_300dpi(
                        page=page,
                        bbox=fb.bbox,
                        destination=target_img,
                        target_dpi=self.config.dpi,
                        image_format=self.config.image_format,
                    ):
                        fb.asset = filename
                        vector_fig_count += 1
                        if fb.caption_text:
                            caption_map[filename] = fb.caption_text

            # Asociación de títulos de tablas (Table I: ...)
            tab_blocks = [b for b in blocks if b.kind == "table"]
            tab_cap_blocks = [b for b in blocks if b.kind == "table_caption" and b.text.strip()]
            if tab_blocks and tab_cap_blocks and self.config.caption_matching:
                vis_tabs = [
                    VisualElement(bbox=tb.bbox, category="Table", page_num=page_num)
                    for tb in tab_blocks
                ]
                tcap_tuples = [(cb.bbox, cb.text) for cb in tab_cap_blocks]
                match_tables_to_captions(vis_tabs, tcap_tuples, page_width=page_w)
                tcap_text_to_id = {cb.text: cb.id for cb in tab_cap_blocks}
                for tb, vt in zip(tab_blocks, vis_tabs):
                    if vt.caption_text:
                        tb.caption_text = vt.caption_text
                        tb.caption_id = tcap_text_to_id.get(vt.caption_text)

            # Etapa 5A: Orden de lectura topológico DAG dentro de la página
            ordered_blocks = order_page_blocks(blocks, page_width=page_w)
            pages_ir.append(PageIR(
                page_number=page_num,
                width=page_w,
                height=page_h,
                rotation=int(page.rotation),
                blocks=ordered_blocks,
                reading_order=[b.id for b in ordered_blocks],
            ))

        # Etapa 5B: Unión de párrafos partidos entre páginas y orden global
        global_order = stitch_cross_page_paragraphs(pages_ir)

        # Extraer metadatos del documento desde los primeros bloques
        sample_text = "\n".join(
            (f"# {b.text}" if b.kind == "title" else b.text)
            for p in pages_ir[:2]
            for b in p.blocks
            if b.text
        )
        meta = parse_academic_metadata(sample_text, pdf_path.name)
        meta["engine"] = self.name

        ir = DocumentIR(
            meta=meta,
            pages=pages_ir,
            reading_order=global_order,
            markdown_override=None,
        )
        stats = {
            "vector_figures": vector_fig_count,
            "caption_map": caption_map,
            "engine_used": self.name,
        }
        return ir, stats
