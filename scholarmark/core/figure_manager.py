"""
Asset extraction and figure management module for ScholarMark.
"""

import re
from pathlib import Path
from typing import Dict, Optional
from ..utils.paths import sanitize_slug

def setup_asset_folder(target_base: Path, paper_stem: str) -> Path:
    """Crea la carpeta de figuras para un artículo específico."""
    slug = sanitize_slug(paper_stem)
    asset_dir = target_base / "assets" / slug
    asset_dir.mkdir(parents=True, exist_ok=True)
    return asset_dir

def normalize_markdown_image_links(
    markdown_text: str,
    paper_stem: str,
    caption_map: Optional[Dict[str, str]] = None
) -> str:
    """
    Asegura que los enlaces de imágenes usen rutas relativas limpias 'assets/<slug>/...'.
    Si se proporciona un mapa de leyendas {nombre_archivo: texto_caption}, inyecta el alt-text
    y el pie de figura correspondiente.
    """
    slug = sanitize_slug(paper_stem)
    pattern = re.compile(r'!\[(.*?)\]\([^\)]*assets[\\/]' + re.escape(slug) + r'[\\/]([^\)]+)\)')

    def _replace_link(match):
        alt = match.group(1)
        filename = match.group(2)
        if caption_map and filename in caption_map and caption_map[filename]:
            cap = caption_map[filename]
            return f"![{cap}](assets/{slug}/{filename})\n\n*{cap}*"
        return f"![{alt}](assets/{slug}/{filename})"

    clean_text = pattern.sub(_replace_link, markdown_text)
    # Evitar repetición de saltos triples de imagen
    clean_text = re.sub(r'(!\[.*?\]\(.*?\)\s*){3,}', r'\1\n', clean_text)
    return clean_text

def get_figure_count(asset_dir: Path) -> int:
    """Retorna el número de imágenes generadas en la carpeta de activos."""
    if not asset_dir.exists():
        return 0
    return len([f for f in asset_dir.iterdir() if f.suffix.lower() in ['.png', '.jpg', '.jpeg', '.webp']])
