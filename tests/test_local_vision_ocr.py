"""
Tests for Local Hybrid Vision Pipeline (Selective ONNX OCR Gating) in ScholarMark v4.1.
Verifies that:
1. Native vector tables NEVER trigger OCR (0 ms OCR overhead, 0% hallucination).
2. Raster/path-only tables (e.g. IEEE Trans Table 1, IEEE Access Table 1) trigger
   the local RapidOCR ONNX gate and reconstruct accurate tabular data.
3. Fallback behaves safely when local vision is disabled.
"""

from pathlib import Path
import fitz
import pytest

from scholarmark.core.geometry import BoundingBox
from scholarmark.recognizers.ocr_engine import LocalOCREngine
from scholarmark.recognizers.table import TableRecognizer


BENCHMARK_DIR = Path(__file__).resolve().parent.parent / "benchmark_papers"
IEEE_TRANS_PDF = BENCHMARK_DIR / "Efficient Real-Time Sports Action Pose Estimation via EfficientPose and Temporal Graph Convolution.pdf"
IEEE_ACCESS_PDF = BENCHMARK_DIR / "A Deep Dive Into MediaPipe Pose for Postural Assessment_ A Comparative Investigation.pdf"


def test_ocr_engine_availability():
    """Verifica que el motor RapidOCR ONNX local esté disponible sin dependencias cloud."""
    assert LocalOCREngine.is_available() is True
    engine = LocalOCREngine()
    assert engine._get_engine() is not None


def test_gate_skips_ocr_for_native_tables():
    """
    Verifica la compuerta selectiva: si una tabla tiene texto nativo en el PDF,
    el OCR local NUNCA es ejecutado.
    """
    # Creamos un PDF sintético con texto vectorial nativo bien espaciado
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text(fitz.Point(100, 100), "ColA", fontsize=10)
    page.insert_text(fitz.Point(220, 100), "ColB", fontsize=10)
    page.insert_text(fitz.Point(100, 125), "ValA1", fontsize=10)
    page.insert_text(fitz.Point(220, 125), "ValB1", fontsize=10)
    page.insert_text(fitz.Point(100, 150), "ValA2", fontsize=10)
    page.insert_text(fitz.Point(220, 150), "ValB2", fontsize=10)

    rec = TableRecognizer(enable_local_vision=True)
    table_bbox = BoundingBox(90, 85, 300, 165)

    html_out, gfm_out, has_merged = rec.recognize_table(page, table_bbox)
    doc.close()

    # No debió activarse el fallback ráster/OCR
    assert rec.last_fallback_triggered is False
    assert "data-source=\"local-ocr\"" not in html_out
    assert gfm_out is not None
    assert "ColA" in gfm_out
    assert "ValB2" in gfm_out


@pytest.mark.skipif(not IEEE_TRANS_PDF.exists(), reason="IEEE Trans PDF benchmark no encontrado")
def test_ieee_trans_table1_local_vision():
    """
    Verifica la recuperación tabular mediante visión local en IEEE Trans Table 1,
    cuyos glifos fueron convertidos en curvas Bezier por InDesign/LaTeX.
    """
    doc = fitz.open(IEEE_TRANS_PDF)
    page = doc[7]  # Página 8 (0-indexed 7)
    bbox = BoundingBox(138.36, 84.21, 434.10, 160.74)

    rec = TableRecognizer(enable_local_vision=True, ocr_dpi=200)
    html_out, gfm_out, has_merged = rec.recognize_table(page, bbox)
    doc.close()

    assert rec.last_fallback_triggered is True
    assert 'data-source="local-ocr"' in html_out
    assert gfm_out is not None

    # Verificación de contenido recuperado
    assert "HRNet" in gfm_out or "HRNet(3D)" in gfm_out
    assert "EfficientPose+T-GCN" in gfm_out
    assert "38.9" in gfm_out
    assert "80.2" in gfm_out
    assert "MOTA" in gfm_out


@pytest.mark.skipif(not IEEE_ACCESS_PDF.exists(), reason="IEEE Access PDF benchmark no encontrado")
def test_ieee_access_table_local_vision():
    """
    Verifica la recuperación de celdas con métricas de varianza en IEEE Access
    (Z_TRUNK, Z_HEAD, 103.15±2.61).
    """
    doc = fitz.open(IEEE_ACCESS_PDF)
    page = doc[8]  # Página 9 (0-indexed 8)
    bbox = BoundingBox(299.01, 78.04, 448.37, 493.71)

    rec = TableRecognizer(enable_local_vision=True, ocr_dpi=200)
    html_out, gfm_out, has_merged = rec.recognize_table(page, bbox)
    doc.close()

    assert rec.last_fallback_triggered is True
    assert 'data-source="local-ocr"' in html_out
    assert "OPTO" in html_out or "OPTOa" in html_out
    assert "103.15" in html_out or "103.15±2.61" in html_out


def test_disabled_local_vision_fallback():
    """
    Verifica que al deshabilitar enable_local_vision, el sistema continúe funcionando
    de manera segura cayendo en la rejilla morfológica estándar (raster-fallback).
    """
    # PDF con un dibujo pero sin texto
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    # Dibujar líneas de tabla sin texto
    page.draw_line(fitz.Point(100, 100), fitz.Point(300, 100))
    page.draw_line(fitz.Point(100, 120), fitz.Point(300, 120))
    page.draw_line(fitz.Point(100, 140), fitz.Point(300, 140))

    rec = TableRecognizer(enable_local_vision=False)
    bbox = BoundingBox(95, 95, 305, 145)

    html_out, gfm_out, has_merged = rec.recognize_table(page, bbox)
    doc.close()

    assert rec.last_fallback_triggered is True
    assert 'data-source="raster-fallback"' in html_out
    assert 'data-source="local-ocr"' not in html_out
