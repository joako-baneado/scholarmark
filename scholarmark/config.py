"""
Configuration settings and default parameters for ScholarMark v3.0.
"""

from dataclasses import dataclass, asdict
import hashlib
import json
from pathlib import Path
from typing import Optional


@dataclass
class ExtractorConfig:
    """Configuración operativa del extractor ScholarMark v3.0."""
    extract_images: bool = True
    dpi: int = 300
    image_format: str = "png"
    force: bool = False
    skip_manifest: bool = False
    clean_ocr_noise: bool = True
    normalize_headings: bool = True
    preserve_heading_text: bool = True
    inject_yaml_frontmatter: bool = True
    math_to_latex: bool = True
    word_kerning_fix: bool = True

    # Parámetros avanzados de Visión, Motores y Geometría Multimodal (v3.0)
    engine: str = "auto"  # "auto" | "fast" | "vision" | "docling"
    device: str = "auto"  # "auto" | "cpu" | "dml" | "cuda"
    export_json: bool = False
    export_chunks: bool = False
    chunk_max_chars: int = 1800
    html_complex_tables: bool = True
    extract_vector_graphics: bool = True
    high_fidelity_figures: bool = True
    caption_matching: bool = True
    triage_pages: bool = True
    elastic_padding_min: float = 4.0
    elastic_padding_max: float = 16.0
    max_figure_vector_primitives: int = 2000
    max_page_vector_primitives: int = 20000
    workers: int = 1
    models_dir: Optional[str] = None
    onnx_model_path: Optional[str] = None

    def config_hash(self) -> str:
        """Calcula un hash determinista de los parámetros que afectan la salida."""
        payload = asdict(self)
        # Parámetros operativos que no alteran el contenido extraído
        payload.pop("force", None)
        payload.pop("skip_manifest", None)
        payload.pop("workers", None)
        raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha1(raw).hexdigest()[:12]

