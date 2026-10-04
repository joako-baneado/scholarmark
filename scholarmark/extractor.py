"""
Core ScholarExtractor pipeline implementation.
"""

import time
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

import pymupdf4llm

from .config import ExtractorConfig
from .core.math_parser import parse_math
from .core.academic import format_academic
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
    elapsed_seconds: float
    error_message: Optional[str] = None

class ScholarExtractor:
    """
    Motor principal de extracción científica de alta precisión.
    Combina análisis de layout GNN, extracción de figuras, OCR asistido y normalización KaTeX.
    """

    def __init__(self, config: Optional[ExtractorConfig] = None, **kwargs):
        if config:
            self.config = config
        else:
            self.config = ExtractorConfig(**kwargs)

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
            # 1. Extracción estructural y OCR mediante PyMuPDF4LLM
            raw_markdown = pymupdf4llm.to_markdown(
                str(pdf_path),
                write_images=self.config.extract_images,
                image_path=str(asset_dir) if self.config.extract_images else "",
                image_format=self.config.image_format,
                dpi=self.config.dpi,
                show_progress=False
            )
            
            # 2. Normalizar enlaces de imágenes relativos
            if self.config.extract_images:
                md_text = normalize_markdown_image_links(raw_markdown, stem)
            else:
                md_text = raw_markdown
                
            # 3. Transformación matemática a LaTeX
            if self.config.math_to_latex:
                md_text = parse_math(md_text)
                
            # 4. Formateo y metadatos académicos
            if self.config.normalize_headings or self.config.inject_yaml_frontmatter:
                md_final = format_academic(md_text, pdf_path.name)
            else:
                md_final = md_text
                
            # 5. Escritura segura en UTF-8
            with open(to_extended_path(target_md), 'w', encoding='utf-8') as f:
                f.write(md_final)
                
            elapsed = time.time() - start_time
            fig_count = get_figure_count(asset_dir) if asset_dir else 0
            
            return ExtractionResult(
                status="success",
                source_pdf=pdf_path.name,
                target_md=str(target_md),
                char_count=len(md_final),
                figure_count=fig_count,
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
