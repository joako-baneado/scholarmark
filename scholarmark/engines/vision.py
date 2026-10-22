"""
VisionEngine: ScholarMark v4.1 Asymmetric Hybrid Modular Pipeline.
Combines Single-Pass PageContext, LayoutDetector, Native SpanMapper, 2D FormulaRecognizer,
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
from ..core.citations import CitationLinker
from ..core.geometry import VisualElement, render_crop_300dpi
from ..core.page_context import PageContext
from ..ir.document import DocumentIR, PageIR, Block
from ..layout import (
    LayoutDetector,
    map_spans_to_blocks,
    order_page_blocks,
    stitch_cross_page_paragraphs,
)
from ..models.registry import resolve_ort_providers
from ..recognizers import (
    FormulaRecognizer,
    TableRecognizer,
    AlgorithmRecognizer,
    ChartSemanticsExtractor,
)


class VisionEngine(BaseEngine):
    """
    Motor híbrido v4.1 sobre PageContext de paso único:
    1. Extracción unificada por página (PageContext: 1x rawdict + 1x bboxlog).
    2. Detección de regiones de diseño (LayoutDetector).
    3. Mapeo de spans vectoriales nativos + rescate de huérfanos (SpanMapper).
    4. Reconstrucción algebraica 2D de ecuaciones aisladas + fallback PUA (FormulaRecognizer).
    5. Reconstrucción tabular jerárquica HTML/GFM + fallback ráster (TableRecognizer).
    6. Reconstrucción de algoritmos y pseudocódigo con sangría exacta (AlgorithmRecognizer).
    7. Asociación de leyendas 1:N (CaptionMatcher), semántica de gráficos (ChartSemanticsExtractor) y recorte 300 DPI.
    8. Orden de lectura topológico DAG, unión inter-página y grafo bidireccional de citas (CitationLinker).
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
        self.algorithm_recognizer = AlgorithmRecognizer()

    def available(self) -> Tuple[bool, str]:
        _, label = resolve_ort_providers(self.config.device)
        return True, f"VisionEngine v4.1 ready ({label})"

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

            # Etapa 0: Extracción unificada de paso único en memoria (PageContext)
            ctx = PageContext.from_page(
                page=page,
                page_num=page_num,
                max_primitives=self.config.max_page_vector_primitives,
            )
            page_w = ctx.width
            page_h = ctx.height
            drawings = ctx.drawings

            # Etapa 1: Detección estructural de regiones
            regions = self.layout_detector.detect_page(
                page=page,
                page_num=page_num,
                max_page_primitives=self.config.max_page_vector_primitives,
                max_figure_primitives=self.config.max_figure_vector_primitives,
                elastic_min=self.config.elastic_padding_min,
                elastic_max=self.config.elastic_padding_max,
                ctx=ctx,
            )

            # Etapa 2: Intersección con spans nativos del PDF (0% alucinación en prosa)
            blocks = map_spans_to_blocks(
                page=page,
                page_num=page_num,
                regions=regions,
                rescue_orphans=True,
                ctx=ctx,
            )

            # Etapa 3A: Reconocimiento de fórmulas 2D + reparación de glifos PUA
            for b in blocks:
                if b.kind == "formula":
                    latex_str, conf, eq_tag = self.formula_recognizer.recognize_region(
                        page=page,
                        bbox=b.bbox,
                        fallback_text=b.text,
                        drawings=drawings,
                        ctx=ctx,
                    )
                    b.latex = latex_str
                    b.confidence = conf
                    b.source = "model"
                    if eq_tag and not b.metadata.get("tag"):
                        b.metadata["tag"] = eq_tag
                    if self.formula_recognizer.last_fallback_triggered:
                        b.metadata["fallback_triggered"] = True
                        b.metadata["corrupted_glyphs_repaired"] = self.formula_recognizer.last_corrupted_glyphs

            # Etapa 3B: Reconstrucción tabular jerárquica (HTML colspan/rowspan + GFM + fallback ráster)
            for b in blocks:
                if b.kind == "table":
                    html_str, gfm_str, has_merged = self.table_recognizer.recognize_table(
                        page=page,
                        bbox=b.bbox,
                        ctx=ctx,
                    )
                    b.html = html_str
                    b.gfm = gfm_str
                    b.source = "ocr" if self.table_recognizer.last_fallback_triggered else "model"
                    b.metadata["has_merged_cells"] = has_merged
                    if self.table_recognizer.last_fallback_triggered:
                        b.metadata["fallback_triggered"] = True

            # Etapa 3C: Reconstrucción de bloques de algoritmos y pseudocódigo
            for b in blocks:
                if b.kind == "algorithm":
                    algo_res = self.algorithm_recognizer.recognize_algorithm(
                        page=page,
                        bbox=b.bbox,
                        fallback_text=b.text,
                        ctx=ctx,
                    )
                    b.gfm = algo_res.formatted_markdown
                    b.confidence = algo_res.confidence
                    b.source = "model"
                    b.metadata["algorithm_title"] = algo_res.title
                    b.metadata["algorithm_id"] = algo_res.algorithm_id
                    b.metadata["algorithm_lines"] = [
                        {
                            "line_number": ln.line_number,
                            "indent": ln.indent_level,
                            "code": ln.code,
                            "is_spec": ln.is_spec,
                        }
                        for ln in algo_res.lines
                    ]

            # Etapa 4: Asociación 1:N de leyendas para figuras y tablas + semántica de gráficos + renderizado 300 DPI
            fig_blocks = [b for b in blocks if b.kind == "figure"]
            fig_cap_blocks = [b for b in blocks if b.kind == "figure_caption" and b.text.strip()]
            prose_boxes = [b.bbox for b in blocks if b.kind == "text" and len(b.text) > 50]

            for fb in fig_blocks:
                chart_sem = ChartSemanticsExtractor.extract_from_figure(
                    page=page,
                    bbox=fb.bbox,
                    exclude_subpanels=fb.metadata.get("subpanel_labels", []),
                    ctx=ctx,
                )
                if chart_sem.has_content:
                    fb.metadata["chart_semantics"] = chart_sem.to_dict()

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
                rotation=ctx.rotation,
                blocks=ordered_blocks,
                reading_order=[b.id for b in ordered_blocks],
            ))

        # Etapa 5B: Unión de párrafos partidos entre páginas y orden global
        global_order = stitch_cross_page_paragraphs(pages_ir)

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

        # Etapa 6: Parser estructural de bibliografía y grafo bidireccional de citas
        CitationLinker.link_document_ir(ir)

        stats = {
            "vector_figures": vector_fig_count,
            "caption_map": caption_map,
            "engine_used": self.name,
        }
        return ir, stats
