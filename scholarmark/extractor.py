"""
Core ScholarExtractor pipeline implementation with hybrid visual fidelity.
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
    render_crop_300dpi
)
from .core.caption_matcher import extract_captions_from_page, match_figures_to_captions
from .core.figure_manager import setup_asset_folder, normalize_markdown_image_links, get_figure_count
from .core.manifest import generate_manifest
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


class ScholarExtractor:
    """
    Motor principal de extracción científica de alta precisión.
    Combina análisis de layout GNN, extracción de figuras vectoriales/ráster a 300+ DPI,
    asociación determinista de epígrafes y normalización KaTeX.
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
            "is_predominantly_scanned": len(scanned_pages) > (total_pages * 0.5)
        }

    def _extract_hybrid_visuals(
        self,
        doc: fitz.Document,
        asset_dir: Path
    ) -> Tuple[Dict[str, str], int]:
        """
        Extrae figuras vectoriales puras, expande cajas para incorporar ejes y subpaneles,
        asocia leyendas mediante optimización biyectiva y renderiza a 300 DPI (alpha=False).
        """
        caption_map: Dict[str, str] = {}
        vector_fig_count = 0

        for p_idx in range(len(doc)):
            page = doc[p_idx]
            page_w = page.rect.width

            # 1. Detectar leyendas textuales en la página
            captions = extract_captions_from_page(page) if self.config.caption_matching else []

            # 2. Extraer candidatos de figuras vectoriales densas
            visual_elements: List[VisualElement] = []
            if self.config.extract_vector_graphics:
                vector_boxes = cluster_vector_drawings(page)
                for v_box in vector_boxes:
                    refined = expand_figure_bbox(page, v_box)
                    visual_elements.append(VisualElement(
                        bbox=refined,
                        category="Picture",
                        page_num=p_idx + 1,
                        is_vector=True
                    ))

            # 3. Emparejamiento biyectivo figura-caption con el Algoritmo Húngaro
            if self.config.caption_matching and visual_elements and captions:
                match_figures_to_captions(visual_elements, captions, page_w)

            # 4. Renderizar a 300 DPI y guardar
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
                    vector_fig_count += 1
                    if elem.caption_text:
                        caption_map[filename] = elem.caption_text

        return caption_map, vector_fig_count

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
            doc = fitz.open(str(pdf_path))

            # Fase 1: Triaje estructural del documento
            triage_info = self.triage_document(doc) if self.config.triage_pages else {}

            # Fase 2: Extracción y enriquecimiento de recursos visuales híbridos
            caption_map = {}
            vector_count = 0
            if self.config.extract_images and asset_dir and self.config.high_fidelity_figures:
                caption_map, vector_count = self._extract_hybrid_visuals(doc, asset_dir)

            # Fase 3: Extracción estructural de texto y maquetación con PyMuPDF4LLM
            raw_markdown = pymupdf4llm.to_markdown(
                str(pdf_path),
                write_images=self.config.extract_images,
                image_path=str(asset_dir) if self.config.extract_images else "",
                image_format=self.config.image_format,
                dpi=self.config.dpi,
                show_progress=False
            )
            
            # Si se extrajeron figuras vectoriales adicionales, vincularlas al final del bloque
            if vector_count > 0:
                vector_md_links = ["\n\n### Extracted Vector Figures & Diagrams\n"]
                slug = sanitize_slug(stem)
                for p_idx in range(len(doc)):
                    for v_idx in range(1, 10):
                        v_name = f"vec_p{p_idx + 1}_{v_idx}.png"
                        if (asset_dir / v_name).exists():
                            cap = caption_map.get(v_name, f"Vector Diagram p.{p_idx + 1}")
                            vector_md_links.append(f"![{cap}](assets/{slug}/{v_name})\n\n*{cap}*\n")
                if len(vector_md_links) > 1:
                    raw_markdown += "\n".join(vector_md_links)

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
                md_final = format_academic(md_text, pdf_path.name)
            else:
                md_final = md_text

            # Si es página escaneada, inyectar advertencia en el frontmatter
            if triage_info.get("is_predominantly_scanned"):
                md_final = f"> [!WARNING]\n> Este documento contiene páginas predominantemente escaneadas ({len(triage_info.get('scanned_pages', []))} págs). Se recomienda post-procesamiento con OCR.\n\n" + md_final
                
            # Fase 7: Escritura segura en UTF-8
            with open(to_extended_path(target_md), 'w', encoding='utf-8') as f:
                f.write(md_final)
                
            elapsed = time.time() - start_time
            fig_count = get_figure_count(asset_dir) if asset_dir else 0
            
            doc.close()

            return ExtractionResult(
                status="success",
                source_pdf=pdf_path.name,
                target_md=str(target_md),
                char_count=len(md_final),
                figure_count=fig_count,
                vector_figures=vector_count,
                elapsed_seconds=elapsed
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
                error_message=str(e)
            )

    def convert_batch(self, source_dir: Path, output_dir: Path,
                      on_progress=None) -> List[ExtractionResult]:
        """Procesa incrementalmente un directorio completo de archivos PDF."""
        source_dir = Path(source_dir)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        pdf_files = sorted([f for f in source_dir.glob("*.pdf")])
        results = []
        
        for idx, pdf in enumerate(pdf_files, 1):
            target_md = output_dir / f"{pdf.stem}.md"
            
            # Comprobación incremental (delta)
            if target_md.exists() and not self.config.force:
                if target_md.stat().st_mtime >= pdf.stat().st_mtime:
                    res = ExtractionResult(
                        status="skipped",
                        source_pdf=pdf.name,
                        target_md=str(target_md),
                        char_count=target_md.stat().st_size,
                        figure_count=0,
                        vector_figures=0,
                        elapsed_seconds=0.0
                    )
                    results.append(res)
                    if on_progress:
                        on_progress(idx, len(pdf_files), pdf, res)
                    continue
                    
            res = self.convert_file(pdf, output_dir)
            results.append(res)
            if on_progress:
                on_progress(idx, len(pdf_files), pdf, res)
                
        # Manifiesto de grounding
        if not self.config.skip_manifest:
            manifest_path = output_dir / "scholarmark_manifest.json"
            generate_manifest(output_dir, manifest_path)
            
        return results
