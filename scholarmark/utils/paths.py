"""
Cross-platform path handling utilities for Windows, macOS and Linux.
"""

import sys
from pathlib import Path
import re

def to_extended_path(p: Path) -> str:
    """Añade prefijo UNC en Windows para permitir rutas largas (> 260 caracteres)."""
    abs_str = str(p.resolve())
    if sys.platform == "win32" and not abs_str.startswith("\\\\?\\"):
        return "\\\\?\\" + abs_str
    return abs_str

def sanitize_slug(name: str) -> str:
    """Convierte un nombre de paper en un slug seguro para directorios y URLs."""
    clean = re.sub(r'[^\w\-]+', '_', name)
    clean = re.sub(r'_+', '_', clean).strip('_')
    return clean[:64]
