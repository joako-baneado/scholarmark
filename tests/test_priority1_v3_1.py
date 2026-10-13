"""
Unit and integration tests for ScholarMark Priority 1 (v3.1):
- AlgorithmRecognizer (hierarchical indentation, line numbering, no false table classification)
- FormulaRecognizer PUA / corrupted glyph repair and fallback telemetry
- TableRecognizer raster table morphological fallback when 0 native spans exist
- ONNX model registry SHA-256 verification and MODEL_SPECS
"""

import fitz
from pathlib import Path

from scholarmark.config import ExtractorConfig
from scholarmark.core.geometry import BoundingBox
from scholarmark.engines.vision import VisionEngine
from scholarmark.models.registry import MODEL_SPECS, verify_file_sha256
from scholarmark.recognizers.algorithm import AlgorithmRecognizer
from scholarmark.recognizers.formula import (
    FormulaRecognizer,
    has_corrupted_glyphs,
    sanitize_pua_text,
    validate_katex_syntax,
)
from scholarmark.recognizers.table import TableRecognizer
from scholarmark.render.markdown import render_markdown


def test_pua_glyph_detection_and_repair():
    corrupted = "L = \uf0e5_{i=1}^{N} \uf061_i + \ufffd"
    is_bad, count = has_corrupted_glyphs(corrupted)
    assert is_bad is True
    assert count == 3

    repaired, triggered = sanitize_pua_text(corrupted)
    assert triggered is True
    assert r"\sum" in repaired
    assert r"\alpha" in repaired
    assert "\ufffd" not in repaired

    ok, conf = validate_katex_syntax(repaired)
    assert ok is True
    assert conf > 0.90


def test_algorithm_recognizer_and_vision_engine_integration(tmp_path: Path):
    pdf_path = tmp_path / "algo_test.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    # Dibujar filetes horizontales estilo algorithm2e
    page.draw_line(fitz.Point(55, 85), fitz.Point(520, 85), color=(0, 0, 0), width=1.2)
    page.insert_text(fitz.Point(60, 100), "Algorithm 1: Adaptive Layout Graph Optimization", fontsize=10.5)
    page.draw_line(fitz.Point(55, 106), fitz.Point(520, 106), color=(0, 0, 0), width=0.6)
    page.insert_text(fitz.Point(60, 120), "Require: Page blocks B, threshold tau", fontsize=9.5)
    page.insert_text(fitz.Point(60, 134), "Ensure: Topological sequence S", fontsize=9.5)
    page.insert_text(fitz.Point(60, 150), "1:", fontsize=9.5)
    page.insert_text(fitz.Point(76, 150), "for each block b in B do", fontsize=9.5)
    page.insert_text(fitz.Point(60, 164), "2:", fontsize=9.5)
    page.insert_text(fitz.Point(88, 164), "if score(b) >= tau then", fontsize=9.5)
    page.insert_text(fitz.Point(60, 178), "3:", fontsize=9.5)
    page.insert_text(fitz.Point(100, 178), "S <- S + {b}", fontsize=9.5)
    page.insert_text(fitz.Point(60, 192), "4:", fontsize=9.5)
    page.insert_text(fitz.Point(88, 192), "end if", fontsize=9.5)
    page.insert_text(fitz.Point(60, 206), "5:", fontsize=9.5)
    page.insert_text(fitz.Point(76, 206), "end for", fontsize=9.5)
    page.insert_text(fitz.Point(60, 220), "6:", fontsize=9.5)
    page.insert_text(fitz.Point(76, 220), "return S", fontsize=9.5)
    page.draw_line(fitz.Point(55, 228), fitz.Point(520, 228), color=(0, 0, 0), width=1.2)

    doc.save(str(pdf_path))
    doc.close()

    cfg = ExtractorConfig(engine="vision", extract_images=False)
    eng = VisionEngine(cfg)
    with fitz.open(str(pdf_path)) as d:
        ir, _ = eng.parse(d, pdf_path)

    blocks = ir.all_blocks_ordered()
    algo_blocks = [b for b in blocks if b.kind == "algorithm"]
    table_blocks = [b for b in blocks if b.kind == "table"]

    assert len(algo_blocks) == 1
    assert len(table_blocks) == 0  # No debe confundirse con tabla booktabs

    ab = algo_blocks[0]
    assert ab.metadata.get("algorithm_id") == "1"
    lines_meta = ab.metadata.get("algorithm_lines", [])
    indents = [ln["indent"] for ln in lines_meta if not ln.get("is_spec")]
    assert indents == [0, 1, 2, 1, 0, 0]

    md = render_markdown(ir, cfg, "algo_test", "algo_test.pdf")
    assert "**Algorithm 1: Adaptive Layout Graph Optimization**" in md
    assert "        S <- S + {b}" in md


def test_raster_table_fallback_when_no_native_spans():
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    # Dibujar celdas simuladas únicamente con trazos vectoriales / bloques oscuros (0 texto nativo)
    for r in range(3):
        for c in range(3):
            x0 = 80 + c * 90
            y0 = 120 + r * 28
            page.draw_rect(fitz.Rect(x0, y0, x0 + 55, y0 + 10), color=(0, 0, 0), fill=(0.2, 0.2, 0.2))

    rec = TableRecognizer()
    html_out, gfm_out, has_merged = rec.recognize_table(page, BoundingBox(70, 110, 360, 220))
    doc.close()

    assert rec.last_fallback_triggered is True
    assert 'data-source="raster-' in html_out
    assert gfm_out is not None


def test_model_registry_specs_and_sha256(tmp_path: Path):
    assert "doclayout_yolo" in MODEL_SPECS
    assert "pp_formulanet_s" in MODEL_SPECS
    assert "slanet_plus" in MODEL_SPECS

    dummy = tmp_path / "dummy.onnx"
    dummy.write_bytes(b"onnx-weights-test")
    ok, digest = verify_file_sha256(dummy)
    assert ok is True
    assert len(digest) == 64

    ok_match, _ = verify_file_sha256(dummy, expected_sha256=digest)
    assert ok_match is True
    ok_bad, _ = verify_file_sha256(dummy, expected_sha256="0" * 64)
    assert ok_bad is False
