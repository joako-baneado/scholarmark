"""
Engine registry and factory for ScholarMark v4.1.
"""

from typing import Dict, Type
from .base import BaseEngine
from .fast import FastEngine
from .vision import VisionEngine
from .docling_engine import DoclingEngine
from ..config import ExtractorConfig

ENGINE_REGISTRY: Dict[str, Type[BaseEngine]] = {
    "fast": FastEngine,
    "vision": VisionEngine,
    "docling": DoclingEngine,
}


def register_engine(name: str, engine_cls: Type[BaseEngine]) -> None:
    ENGINE_REGISTRY[name] = engine_cls


def get_engine(config: ExtractorConfig) -> BaseEngine:
    """
    Selecciona e instancia el motor de extracción solicitado en config.engine:
    - 'auto': usa 'vision' (motor híbrido geométrico-tipográfico 2D sin requerir GPU ni descargas)
      como motor predeterminado de alta precisión y baja latencia; cae a 'fast' solo si no está disponible.
    - 'fast' | 'vision' | 'docling': instancia explícitamente el motor solicitado.
    """
    requested = (config.engine or "auto").lower().strip()
    if requested == "auto":
        vis = VisionEngine(config)
        ok, _ = vis.available()
        if ok:
            return vis
        return FastEngine(config)

    if requested not in ENGINE_REGISTRY:
        raise ValueError(f"Unknown engine '{requested}'. Available: {sorted(ENGINE_REGISTRY.keys())}")

    engine = ENGINE_REGISTRY[requested](config)
    ok, reason = engine.available()
    if not ok:
        raise RuntimeError(f"Engine '{requested}' is not available: {reason}")
    return engine


__all__ = [
    "BaseEngine",
    "FastEngine",
    "VisionEngine",
    "DoclingEngine",
    "ENGINE_REGISTRY",
    "register_engine",
    "get_engine",
]
