"""
Visual Layout Overlay Generator for ScholarMark v3.0.
Renders PDF pages with color-coded bounding boxes and numbered topological reading order
markers for visual inspection of LayoutDetector and ReadingOrderDAG.
"""

from pathlib import Path
import fitz

from scholarmark.config import ExtractorConfig
from scholarmark.engines.vision import VisionEngine

CLASS_COLORS = {
    "title": (0.85, 0.15, 0.15),
    "section_header": (0.80, 0.40, 0.05),
    "text": (0.15, 0.45, 0.85),
    "formula": (0.60, 0.15, 0.80),
    "table": (0.10, 0.65, 0.35),
    "table_caption": (0.05, 0.50, 0.25),
    "figure": (0.85, 0.55, 0.05),
    "figure_caption": (0.70, 0.45, 0.05),
    "footnote": (0.45, 0.45, 0.45),
    "author_bio": (0.10, 0.65, 0.70),
    "abandon": (0.75, 0.75, 0.75),
}


def render_annotated_pages(pdf_path: Path, output_dir: Path, max_pages: int = 5) -> list[Path]:
    """
    Genera imágenes PNG con las cajas delimitadoras y el orden de lectura (1, 2, 3...)
    superpuestos sobre cada página del PDF.
    """
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cfg = ExtractorConfig(engine="vision", extract_images=False)
    engine = VisionEngine(cfg)
    saved_pngs: list[Path] = []

    with fitz.open(str(pdf_path)) as doc:
        ir, _ = engine.parse(doc, pdf_path, asset_dir=None)
        for p_ir in ir.pages[:max_pages]:
            page = doc[p_ir.page_number - 1]
            shape = page.new_shape()
            for order_idx, block in enumerate(p_ir.ordered_blocks(), 1):
                color = CLASS_COLORS.get(block.kind, (0.2, 0.2, 0.2))
                rect = block.bbox.to_fitz_rect()
                shape.draw_rect(rect)
                shape.finish(color=color, width=1.4)
                label = f"[{order_idx}] {block.kind}"
                page.insert_text((rect.x0 + 2, max(10, rect.y0 - 2)), label, fontsize=7.5, color=color)
            shape.commit()
            pix = page.get_pixmap(dpi=150, alpha=False)
            out_png = output_dir / f"{pdf_path.stem}_p{p_ir.page_number}_overlay.png"
            pix.save(str(out_png))
            saved_pngs.append(out_png)

    return saved_pngs
