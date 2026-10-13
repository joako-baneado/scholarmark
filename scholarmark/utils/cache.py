"""
Deterministic delta-caching engine for ScholarMark v3.0.
Tracks PDF content metadata alongside package version and ExtractorConfig hash
so upgrades or configuration changes automatically invalidate stale outputs.
"""

import json
from pathlib import Path
from typing import Dict, Any

from .. import __version__
from ..config import ExtractorConfig


class DeltaCache:
    """Gestiona el índice de caché incremental en <output_dir>/.scholarmark/cache_index.json."""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.cache_dir = self.output_dir / ".scholarmark"
        self.index_path = self.cache_dir / "cache_index.json"
        self.entries: Dict[str, Dict[str, Any]] = self._load()

    def _load(self) -> Dict[str, Dict[str, Any]]:
        if not self.index_path.exists():
            return {}
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {}

    def save(self) -> None:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.index_path.write_text(
                json.dumps(self.entries, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
        except Exception:
            pass

    def is_up_to_date(self, pdf_path: Path, target_md: Path, config: ExtractorConfig) -> bool:
        """
        Retorna True solo si:
        1. El archivo Markdown de salida existe y su mtime >= mtime del PDF.
        2. La entrada en caché coincide con la versión actual de ScholarMark,
           el hash de configuración de ExtractorConfig y el tamaño del PDF.
        """
        if config.force or not target_md.exists() or not pdf_path.exists():
            return False

        pdf_stat = pdf_path.stat()
        md_stat = target_md.stat()
        if md_stat.st_mtime < pdf_stat.st_mtime:
            return False

        entry = self.entries.get(pdf_path.name)
        if not entry:
            return False

        if entry.get("version") != __version__:
            return False
        if entry.get("config_hash") != config.config_hash():
            return False
        if entry.get("pdf_size") != pdf_stat.st_size:
            return False

        return True

    def record(self, pdf_path: Path, target_md: Path, config: ExtractorConfig, figure_count: int = 0) -> None:
        """Registra una conversión exitosa en el índice de caché."""
        if not pdf_path.exists() or not target_md.exists():
            return
        pdf_stat = pdf_path.stat()
        self.entries[pdf_path.name] = {
            "version": __version__,
            "config_hash": config.config_hash(),
            "pdf_size": pdf_stat.st_size,
            "pdf_mtime": pdf_stat.st_mtime,
            "figure_count": figure_count,
        }
