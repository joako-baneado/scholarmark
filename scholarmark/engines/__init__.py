"""
Engine registry and factory for ScholarMark v3.0.
"""

from typing import Dict, Type
from .base import BaseEngine
from .fast import FastEngine
from .docling_engine import DoclingEngine
from ..config import ExtractorConfig

ENGINE_REGISTRY: Dict[str, Type[BaseEngine]] = {
    "fast": FastEngine,
    "docling": DoclingEngine,
}


def register_engine(name: str, engine_cls: Type[BaseEngine]) -> None:
    ENGINE_REGISTRY[name] = engine_cls


def get_engine(config: ExtractorConfig) -> BaseEngine:
    """
    Selecciona e instancia el motor de extracción solicitado en config.engine:
    - 'auto': prioriza 'vision' si está registrado y disponible; de lo contrario usa 'fast'.
    - 'fast' | 'vision' | 'docling': instancia explícitamente el motor solicitado.
    """
    requested = (config.engine or "auto").lower().strip()
    if requested == "auto":
        if "vision" in ENGINE_REGISTRY:
            vis = ENGINE_REGISTRY["vision"](config)
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


__all__ = ["BaseEngine", "FastEngine", "DoclingEngine", "ENGINE_REGISTRY", "register_engine", "get_engine"]
