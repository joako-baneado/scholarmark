"""
Base engine protocol and interface for ScholarMark v3.0 pluggable extraction backends.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
import fitz

from ..config import ExtractorConfig
from ..ir.document import DocumentIR


class BaseEngine(ABC):
    """Contrato común para todos los motores de extracción de ScholarMark."""
    name: str = "base"

    def __init__(self, config: ExtractorConfig):
        self.config = config

    @abstractmethod
    def available(self) -> Tuple[bool, str]:
        """Retorna (disponible, detalle_estado) indicando si el motor puede ejecutarse."""
        raise NotImplementedError

    @abstractmethod
    def parse(
        self,
        doc: fitz.Document,
        pdf_path: Path,
        asset_dir: Optional[Path] = None
    ) -> Tuple[DocumentIR, Dict[str, Any]]:
        """
        Procesa el documento PDF y retorna (DocumentIR, stats_dict).
        stats_dict incluye conteo de figuras vectoriales y mapas de leyendas.
        """
        raise NotImplementedError
