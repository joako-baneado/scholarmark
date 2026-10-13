"""
Core ScholarExtractor pipeline implementation with hybrid visual fidelity (v3.0).
"""

import time
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple

import fitz  # PyMuPDF
import pymupdf4llm

from .config import ExtractorConfig
from .core.math_parser import parse_math
from .core.academic import format_academic
from .core.geometry import (
    BoundingBox,
    VisualElement,
    expand_figure_bbox,
    cluster_vector_drawings,
    render_crop_300dpi,
)
from .core.caption_matcher import extract_captions_from_page, match_figures_to_captions
from .core.figure_manager import setup_asset_folder, normalize_markdown_image_links, get_figure_count
from .core.manifest import generate_manifest
from .utils.cache import DeltaCache
from .utils.paths import to_extended_path, sanitize_slug


@dataclass
class ExtractionResult:
    """Resultado estructurado de la extracción de un documento."""
    status: str
    source_pdf: str
    target_md: str
    char_count: int
    figure_count: int
    vector_figures: int
    elapsed_seconds: float
    error_message: Optional[str] = None
    engine_used: str = "fast"


class ScholarExtractor:
    """
    Motor principal de extracción científica de alta precisión.
    Combina análisis de layout, extracción de figuras vectoriales/ráster a 300+ DPI,
    asociación de epígrafes y normalización KaTeX.
    """

    def __init__(self, config: Optional[ExtractorConfig] = None, **kwargs):
        if config:
            self.config = config
        else:
            self.config = ExtractorConfig(**kwargs)

    def triage_document(self, doc: fitz.Document) -> Dict[str, Any]:
        """Clasifica el documento para detectar páginas escaneadas o tipografías corruptas."""
        total_pages = len(doc)
        scanned_pages = []
        corrupted_pages = []

        for p_idx in range(total_pages):
            page = doc[p_idx]
            text = page.get_text("text").strip()
            images = page.get_images()

            # Escaneo: casi sin texto pero con imagen dominante
            if len(text) < 50 and len(images) >= 1:
                page_area = page.rect.width * page.rect.height
                if page_area > 0:
                    for img in images:
                        xref = img[0]
                        for r in page.get_image_rects(xref):
                            if (r.width * r.height) / page_area > 0.85:
                                scanned_pages.append(p_idx + 1)
                                break

            # Corrupción tipográfica
            if len(text) > 0 and (text.count("\ufffd") / len(text)) > 0.15:
                corrupted_pages.append(p_idx + 1)

        return {
            "total_pages": total_pages,
            "scanned_pages": scanned_pages,
            "corrupted_pages": corrupted_pages,
            "is_predominantly_scanned": len(scanned_pages) > (total_pages * 0.5) if total_pages > 0 else False
        }

    @staticmethod
    def _get_page_raster_boxes(page: fitz.Page) -> List[BoundingBox]:
        """Obtiene todas las cajas delimitadoras de imágenes ráster embebidas en la página."""
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
        """
        Extrae figuras vectoriales puras (una sola llamada get_drawings por página),
        descarta duplicados que se solapan con imágenes ráster (IoU > 0.6),
        expande cajas elásticamente (4-16 pt), asocia leyendas y renderiza a 300 DPI.
        """
        caption_map: Dict[str, str] = {}
        saved_elements: List[VisualElement] = []

        for p_idx in range(len(doc)):
            page = doc[p_idx]
            page_w = page.rect.width

            # 1. Detectar leyendas textuales en la página
            captions = extract_captions_from_page(page) if self.config.caption_matching else []

            # 2. Extraer candidatos de figuras vectoriales densas (B5: una sola extracción por página)
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
                    max_page_primitives=self.config.max_page_vector_primitives
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
                    # B2: Deduplicar si la región vectorial ya está cubierta por una imagen ráster
                    if any(refined.iou(rb) > 0.60 or refined.coverage_by(rb) > 0.75 for rb in raster_boxes):
                        continue

                    visual_elements.append(VisualElement(
                        bbox=refined,
                        category="Picture",
                        page_num=p_idx + 1,
                        is_vector=True
                    ))

            # 3. Emparejamiento figura-caption
            if self.config.caption_matching and visual_elements and captions:
                match_figures_to_captions(visual_elements, captions, page_w)

            # 4. Renderizar a 300 DPI y guardar (B1: sin límite de 9 figuras por página)
            for v_idx, elem in enumerate(visual_elements, 1):
                filename = f"vec_p{elem.page_num}_{v_idx}.png"
                target_img = asset_dir / filename
                success = render_crop_300dpi(
                    page=page,
                    bbox=elem.bbox,
                    destination=target_img,
                    target_dpi=self.config.dpi,
                    image_format=self.config.image_format
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
        """
        Inserta cada figura vectorial junto a su leyenda correspondiente en el flujo del documento.
        Las figuras cuya leyenda no se encuentre en el texto se agrupan limpiamente al cierre.
        """
        if not saved_elements:
            return raw_markdown

        md = raw_markdown
        unplaced: List[str] = []

        for elem in saved_elements:
            v_name = elem.saved_path
            if not v_name:
                continue
            cap = caption_map.get(v_name, f"Vector Diagram p.{elem.page_num}")
            link_snippet = f"\n\n![{cap}](assets/{slug}/{v_name})\n\n*{cap}*\n\n"

            # Intentar posicionar justo encima de su leyenda en el texto extraído
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

    def convert_file(self, pdf_path: Path, output_dir: Path) -> ExtractionResult:
        """Convierte un único archivo PDF a Markdown de alta fidelidad."""
        pdf_path = Path(pdf_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        stem = pdf_path.stem
        target_md = output_dir / f"{stem}.md"
        start_time = time.time()

        asset_dir = None
        if self.config.extract_images:
            asset_dir = setup_asset_folder(output_dir, stem)

        try:
            # B4: Garantizar liberación determinista del descriptor de archivo con context manager
            with fitz.open(str(pdf_path)) as doc:
                # Fase 1: Triaje estructural del documento
                triage_info = self.triage_document(doc) if self.config.triage_pages else {}

                # Fase 2: Extracción y enriquecimiento de recursos visuales híbridos
                caption_map: Dict[str, str] = {}
                saved_vectors: List[VisualElement] = []
                if self.config.extract_images and asset_dir and self.config.high_fidelity_figures:
                    caption_map, saved_vectors = self._extract_hybrid_visuals(doc, asset_dir)
                vector_count = len(saved_vectors)

            # Fase 3: Extracción estructural de texto y maquetación con PyMuPDF4LLM
            raw_markdown = pymupdf4llm.to_markdown(
                str(pdf_path),
                write_images=self.config.extract_images,
                image_path=str(asset_dir) if self.config.extract_images else "",
                image_format=self.config.image_format,
                dpi=self.config.dpi,
                show_progress=False
            )

            if vector_count > 0:
                slug = sanitize_slug(stem)
                raw_markdown = self._inject_vector_figures_in_context(
                    raw_markdown=raw_markdown,
                    saved_elements=saved_vectors,
                    caption_map=caption_map,
                    slug=slug
                )

            # Fase 4: Normalizar enlaces de imágenes relativos y aplicar captions emparejados
            if self.config.extract_images:
                md_text = normalize_markdown_image_links(raw_markdown, stem, caption_map=caption_map)
            else:
                md_text = raw_markdown

            # Fase 5: Transformación matemática a LaTeX
            if self.config.math_to_latex:
                md_text = parse_math(md_text)

            # Fase 6: Formateo y metadatos académicos
            if self.config.normalize_headings or self.config.inject_yaml_frontmatter:
                md_final = format_academic(
                    md_text,
                    pdf_path.name,
                    preserve_heading_text=self.config.preserve_heading_text
                )
            else:
                md_final = md_text

            # Si es página escaneada, inyectar advertencia
            if triage_info.get("is_predominantly_scanned"):
                md_final = (
                    f"> [!WARNING]\n> Este documento contiene páginas predominantemente escaneadas "
                    f"({len(triage_info.get('scanned_pages', []))} págs). Se recomienda post-procesamiento con OCR.\n\n"
                    + md_final
                )

            # Fase 7: Escritura segura en UTF-8
            with open(to_extended_path(target_md), 'w', encoding='utf-8') as f:
                f.write(md_final)

            elapsed = time.time() - start_time
            fig_count = get_figure_count(asset_dir) if asset_dir else 0

            # Registrar en caché delta determinista (B3)
            cache = DeltaCache(output_dir)
            cache.record(pdf_path, target_md, self.config, figure_count=fig_count)
            cache.save()

            return ExtractionResult(
                status="success",
                source_pdf=pdf_path.name,
                target_md=str(target_md),
                char_count=len(md_final),
                figure_count=fig_count,
                vector_figures=vector_count,
                elapsed_seconds=elapsed,
                engine_used="fast"
            )

        except Exception as e:
            elapsed = time.time() - start_time
            return ExtractionResult(
                status="error",
                source_pdf=pdf_path.name,
                target_md=str(target_md),
                char_count=0,
                figure_count=0,
                vector_figures=0,
                elapsed_seconds=elapsed,
                error_message=str(e),
                engine_used="fast"
            )

    def convert_batch(
        self,
        source_dir: Path,
        output_dir: Path,
        on_progress=None
    ) -> List[ExtractionResult]:
        """Procesa incrementalmente un directorio completo de archivos PDF."""
        source_dir = Path(source_dir)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        pdf_files = sorted([f for f in source_dir.glob("*.pdf")])
        results: List[ExtractionResult] = []
        cache = DeltaCache(output_dir)

        for idx, pdf in enumerate(pdf_files, 1):
            target_md = output_dir / f"{pdf.stem}.md"

            # B3: Comprobación incremental determinista (mtime + versión + config_hash)
            if cache.is_up_to_date(pdf, target_md, self.config):
                cached_entry = cache.entries.get(pdf.name, {})
                res = ExtractionResult(
                    status="skipped",
                    source_pdf=pdf.name,
                    target_md=str(target_md),
                    char_count=target_md.stat().st_size,
                    figure_count=cached_entry.get("figure_count", 0),
                    vector_figures=0,
                    elapsed_seconds=0.0,
                    engine_used=self.config.engine
                )
                results.append(res)
                if on_progress:
                    on_progress(idx, len(pdf_files), pdf, res)
                continue

            res = self.convert_file(pdf, output_dir)
            cache.record(pdf, target_md, self.config, figure_count=res.figure_count)
            results.append(res)
            if on_progress:
                on_progress(idx, len(pdf_files), pdf, res)

        cache.save()

        # Manifiesto de grounding
        if not self.config.skip_manifest:
            manifest_path = output_dir / "scholarmark_manifest.json"
            generate_manifest(output_dir, manifest_path)

        return results
