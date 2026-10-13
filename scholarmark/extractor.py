"""
Core ScholarExtractor pipeline implementation with pluggable engines (fast, vision, docling)
and canonical DocumentIR serialization (Markdown + JSON).
"""

import time
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

import fitz  # PyMuPDF

from .config import ExtractorConfig
from .core.figure_manager import setup_asset_folder, get_figure_count
from .core.manifest import generate_manifest
from .engines import get_engine
from .rag.chunker import export_chunks_jsonl
from .render import render_markdown, export_canonical_json
from .utils.cache import DeltaCache
from .utils.paths import to_extended_path


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
    target_json: Optional[str] = None
    target_chunks: Optional[str] = None


class ScholarExtractor:
    """
    Motor principal de extracción científica de alta precisión v4.0.
    Orquesta triaje documental, motores intercambiables (fast, vision, docling),
    renderizado Markdown/HTML/KaTeX, exportación JSON canónica, chunks JSONL y manifiestos de grounding RAG.
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

            if len(text) < 50 and len(images) >= 1:
                page_area = page.rect.width * page.rect.height
                if page_area > 0:
                    for img in images:
                        xref = img[0]
                        for r in page.get_image_rects(xref):
                            if (r.width * r.height) / page_area > 0.85:
                                scanned_pages.append(p_idx + 1)
                                break

            if len(text) > 0 and (text.count("\ufffd") / len(text)) > 0.15:
                corrupted_pages.append(p_idx + 1)

        return {
            "total_pages": total_pages,
            "scanned_pages": scanned_pages,
            "corrupted_pages": corrupted_pages,
            "is_predominantly_scanned": len(scanned_pages) > (total_pages * 0.5) if total_pages > 0 else False,
        }

    def convert_file(self, pdf_path: Path, output_dir: Path) -> ExtractionResult:
        """Convierte un único archivo PDF a Markdown de alta fidelidad (y opcionalmente JSON canónico y chunks JSONL)."""
        pdf_path = Path(pdf_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        stem = pdf_path.stem
        target_md = output_dir / f"{stem}.md"
        target_json = (output_dir / f"{stem}.scholarmark.json") if self.config.export_json else None
        target_chunks = (output_dir / f"{stem}.chunks.jsonl") if self.config.export_chunks else None
        start_time = time.time()

        asset_dir = None
        if self.config.extract_images:
            asset_dir = setup_asset_folder(output_dir, stem)

        engine = get_engine(self.config)

        try:
            with fitz.open(str(pdf_path)) as doc:
                triage_info = self.triage_document(doc) if self.config.triage_pages else {}
                ir, stats = engine.parse(doc=doc, pdf_path=pdf_path, asset_dir=asset_dir)

            md_final = render_markdown(
                ir=ir,
                config=self.config,
                paper_stem=stem,
                pdf_filename=pdf_path.name,
            )

            if triage_info.get("is_predominantly_scanned"):
                md_final = (
                    f"> [!WARNING]\n> Este documento contiene páginas predominantemente escaneadas "
                    f"({len(triage_info.get('scanned_pages', []))} págs). Se recomienda post-procesamiento con OCR.\n\n"
                    + md_final
                )

            with open(to_extended_path(target_md), "w", encoding="utf-8") as f:
                f.write(md_final)

            if target_json is not None:
                export_canonical_json(ir, target_json)

            if target_chunks is not None:
                export_chunks_jsonl(
                    ir,
                    target_chunks,
                    max_chars=self.config.chunk_max_chars,
                )

            elapsed = time.time() - start_time
            fig_count = get_figure_count(asset_dir) if asset_dir else 0
            vector_count = int(stats.get("vector_figures", 0))
            engine_used = str(stats.get("engine_used", engine.name))

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
                engine_used=engine_used,
                target_json=str(target_json) if target_json else None,
                target_chunks=str(target_chunks) if target_chunks else None,
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
                engine_used=engine.name,
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
                    engine_used=self.config.engine,
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

        if not self.config.skip_manifest:
            manifest_path = output_dir / "scholarmark_manifest.json"
            generate_manifest(output_dir, manifest_path)

        return results
