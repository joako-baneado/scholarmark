"""
Configuration settings and default parameters for ScholarMark.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ExtractorConfig:
    """Configuración operativa del extractor ScholarMark."""
    extract_images: bool = True
    dpi: int = 300
    image_format: str = "png"
    force: bool = False
    skip_manifest: bool = False
    clean_ocr_noise: bool = True
    normalize_headings: bool = True
    inject_yaml_frontmatter: bool = True
    math_to_latex: bool = True
    word_kerning_fix: bool = True
    
    # Parámetros avanzados de Visión y Geometría Multimodal
    extract_vector_graphics: bool = True
    high_fidelity_figures: bool = True
    caption_matching: bool = True
    triage_pages: bool = True
    onnx_model_path: Optional[str] = None
