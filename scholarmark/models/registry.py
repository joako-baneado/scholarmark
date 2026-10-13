"""
ONNX Runtime Execution Provider & Model Registry for ScholarMark v3.0.
Handles hardware acceleration detection (DirectML, CUDA, OpenVINO, CPU) and
lightweight model session management.
"""

import hashlib
import os
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any


MODEL_SPECS: Dict[str, Dict[str, Any]] = {
    "doclayout_yolo": {
        "filename": "doclayout_yolo_docstructbench_imgsz1024_int8.onnx",
        "task": "layout_detection",
        "quantization": "INT8",
        "approx_size_mb": 42,
        "sha256": None,
    },
    "pp_formulanet_s": {
        "filename": "pp_formulanet_s_int8.onnx",
        "task": "formula_recognition",
        "quantization": "INT8",
        "approx_size_mb": 78,
        "sha256": None,
    },
    "slanet_plus": {
        "filename": "slanet_plus_table_structure_int8.onnx",
        "task": "table_structure",
        "quantization": "INT8",
        "approx_size_mb": 26,
        "sha256": None,
    },
}


def verify_file_sha256(file_path: Path, expected_sha256: Optional[str] = None) -> Tuple[bool, str]:
    """Calcula el digest SHA-256 de un archivo de pesos ONNX y valida contra expected_sha256."""
    if not file_path.exists():
        return False, ""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    digest = h.hexdigest()
    if expected_sha256 and digest.lower() != expected_sha256.lower():
        return False, digest
    return True, digest


def load_onnx_session(
    model_key: str,
    device: str = "auto",
    custom_path: Optional[str] = None,
    models_dir: Optional[str] = None,
):
    """
    Carga una sesión de inferencia ONNX Runtime si el archivo de pesos existe en disco
    o en el directorio de caché local (~/.cache/scholarmark/models).
    """
    try:
        import onnxruntime as ort
    except ImportError:
        return None

    candidate: Optional[Path] = None
    if custom_path and Path(custom_path).exists():
        candidate = Path(custom_path)
    else:
        spec = MODEL_SPECS.get(model_key)
        if spec:
            cache_file = get_models_cache_dir(models_dir) / spec["filename"]
            if cache_file.exists():
                ok, _ = verify_file_sha256(cache_file, spec.get("sha256"))
                if ok:
                    candidate = cache_file

    if candidate is None:
        return None

    providers, _ = resolve_ort_providers(device)
    try:
        return ort.InferenceSession(str(candidate), providers=providers)
    except Exception:
        return None


def get_models_cache_dir(custom_dir: Optional[str] = None) -> Path:
    """Retorna el directorio local donde se almacenan en caché los pesos ONNX."""
    if custom_dir:
        p = Path(custom_dir)
    else:
        local_app = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~/.cache")
        p = Path(local_app) / "scholarmark" / "models"
    p.mkdir(parents=True, exist_ok=True)
    return p


def resolve_ort_providers(device: str = "auto") -> Tuple[List[str], str]:
    """
    Determina la lista priorizada de proveedores de ejecución de ONNX Runtime
    según el dispositivo solicitado ('auto', 'dml', 'cuda', 'cpu').
    """
    try:
        import onnxruntime as ort
        available = ort.get_available_providers()
    except ImportError:
        return [], "onnxruntime not installed"

    req = (device or "auto").lower().strip()
    if req == "cpu":
        return ["CPUExecutionProvider"], "CPUExecutionProvider"

    if req == "dml":
        if "DmlExecutionProvider" in available:
            return ["DmlExecutionProvider", "CPUExecutionProvider"], "DmlExecutionProvider (DirectX 12 GPU)"
        return ["CPUExecutionProvider"], "CPUExecutionProvider (DML unavailable)"

    if req == "cuda":
        if "CUDAExecutionProvider" in available:
            return ["CUDAExecutionProvider", "CPUExecutionProvider"], "CUDAExecutionProvider"
        return ["CPUExecutionProvider"], "CPUExecutionProvider (CUDA unavailable)"

    # Modo 'auto': priorizar TensorRT -> CUDA -> DirectML -> OpenVINO -> CPU
    priority = [
        ("TensorrtExecutionProvider", "TensorRT GPU"),
        ("CUDAExecutionProvider", "CUDA GPU"),
        ("DmlExecutionProvider", "DirectML GPU"),
        ("OpenVINOExecutionProvider", "OpenVINO CPU/NPU"),
        ("CPUExecutionProvider", "CPUExecutionProvider"),
    ]
    selected: List[str] = []
    primary_label = "CPUExecutionProvider"
    for prov, label in priority:
        if prov in available:
            selected.append(prov)
            if len(selected) == 1:
                primary_label = label

    if not selected:
        selected = ["CPUExecutionProvider"]
    return selected, primary_label


def get_runtime_diagnostics(device: str = "auto", models_dir: Optional[str] = None) -> Dict[str, Any]:
    """Genera un informe diagnóstico de hardware, proveedores ONNX y paquetes instalados."""
    providers, active_label = resolve_ort_providers(device)
    try:
        import onnxruntime as ort
        ort_version = ort.__version__
        all_providers = ort.get_available_providers()
    except ImportError:
        ort_version = "not installed"
        all_providers = []

    try:
        import pymupdf.layout  # noqa: F401
        pymupdf_layout_ok = True
    except ImportError:
        pymupdf_layout_ok = False

    cache_dir = get_models_cache_dir(models_dir)
    onnx_files = [f.name for f in cache_dir.glob("*.onnx")] if cache_dir.exists() else []

    return {
        "onnxruntime_version": ort_version,
        "available_providers": all_providers,
        "selected_providers": providers,
        "active_accelerator": active_label,
        "pymupdf_gnn_layout": pymupdf_layout_ok,
        "models_cache_dir": str(cache_dir),
        "cached_onnx_models": onnx_files,
        "model_specs": list(MODEL_SPECS.keys()),
    }
