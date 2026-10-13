"""
Canonical JSON exporter for ScholarMark v3.0 DocumentIR.
Produces lossless structured JSON ready for Scientific RAG chunkers and graph indexers.
"""

import json
from pathlib import Path

from ..ir.document import DocumentIR
from ..utils.paths import to_extended_path


def export_canonical_json(ir: DocumentIR, target_json_path: Path) -> Path:
    """Exporta el DocumentIR a un archivo JSON estructurado UTF-8."""
    target_json_path = Path(target_json_path)
    target_json_path.parent.mkdir(parents=True, exist_ok=True)
    payload = ir.to_dict()
    with open(to_extended_path(target_json_path), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return target_json_path
