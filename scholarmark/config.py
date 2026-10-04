"""
Configuration settings and default parameters for ScholarMark.
"""

from dataclasses import dataclass
from pathlib import Path

@dataclass
class ExtractorConfig:
    """Configuración operativa del extractor ScholarMark."""
    extract_images: bool = True
    dpi: int = 200
    image_format: str = "png"
    force: bool = False
    skip_manifest: bool = False
    clean_ocr_noise: bool = True
    normalize_headings: bool = True
    inject_yaml_frontmatter: bool = True
    math_to_latex: bool = True
    word_kerning_fix: bool = True
