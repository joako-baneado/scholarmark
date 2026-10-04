"""
Asset extraction and figure management module for ScholarMark.
"""

import re
from pathlib import Path
from ..utils.paths import sanitize_slug

def setup_asset_folder(target_base: Path, paper_stem: str) -> Path:
    """Crea la carpeta de figuras para un artículo específico."""
    slug = sanitize_slug(paper_stem)
    asset_dir = target_base / "assets" / slug
    asset_dir.mkdir(parents=True, exist_ok=True)
    return asset_dir

def normalize_markdown_image_links(markdown_text: str, paper_stem: str) -> str:
    """Asegura que los enlaces de imágenes usen rutas relativas limpias 'assets/<slug>/...'."""
    slug = sanitize_slug(paper_stem)
    pattern = re.compile(r'!\[(.*?)\]\([^\)]*assets[\\/]' + re.escape(slug) + r'[\\/]([^\)]+)\)')
    clean_text = pattern.sub(rf'![\1](assets/{slug}/\2)', markdown_text)
    # Evitar repetición de saltos triples de imagen
    clean_text = re.sub(r'(!\[.*?\]\(.*?\)\s*){3,}', r'\1\n', clean_text)
    return clean_text

def get_figure_count(asset_dir: Path) -> int:
    """Retorna el número de imágenes generadas en la carpeta de activos."""
    if not asset_dir.exists():
        return 0
    return len([f for f in asset_dir.iterdir() if f.suffix.lower() in ['.png', '.jpg', '.jpeg', '.webp']])
