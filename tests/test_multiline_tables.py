import pytest
from pathlib import Path
import fitz

from scholarmark.core.geometry import BoundingBox
from scholarmark.core.page_context import PageContext
from scholarmark.layout.detector import LayoutDetector
from scholarmark.recognizers.table import TableRecognizer


def test_multiline_cell_fragmentation_detection():
    recognizer = TableRecognizer()
    col_anchors = [(36.0, 94.0), (94.0, 189.0), (189.0, 369.0), (369.0, 576.0)]

    # Clean rows: every row starts in col 0
    clean_rows = [
        [(BoundingBox(40, 100, 90, 115), "Method"), (BoundingBox(100, 100, 180, 115), "Works")],
        [(BoundingBox(40, 120, 90, 135), "ConvNet"), (BoundingBox(100, 120, 180, 135), "Li et al.")],
        [(BoundingBox(40, 140, 90, 155), "RNN"), (BoundingBox(100, 140, 180, 155), "Feng et al.")],
        [(BoundingBox(40, 160, 90, 175), "GCN"), (BoundingBox(100, 160, 180, 175), "Yan et al.")],
    ]
    assert not recognizer._is_multi_line_fragmented(clean_rows, col_anchors)

    # Fragmented rows: wrapped cells create rows where col 0 is empty (first box starts in col 1 or col 2)
    fragmented_rows = [
        [(BoundingBox(40, 100, 90, 115), "Method"), (BoundingBox(100, 100, 180, 115), "Works")],
        [(BoundingBox(40, 120, 90, 135), "ConvNet"), (BoundingBox(100, 120, 180, 135), "Li et al.")],
        [(BoundingBox(100, 136, 140, 148), "[16]"), (BoundingBox(200, 136, 350, 148), "structures.")],
        [(BoundingBox(40, 155, 90, 170), "RNN"), (BoundingBox(100, 155, 180, 170), "Feng et al.")],
        [(BoundingBox(200, 172, 350, 185), "modeling.")],
    ]
    assert recognizer._is_multi_line_fragmented(fragmented_rows, col_anchors)


def test_astm_net_table_bounds_and_structure():
    pdf_path = Path("benchmark_papers/Lightweight and efficient skeleton-based sports activity recognition with ASTM-Net.pdf")
    if not pdf_path.exists():
        pytest.skip(f"Benchmark paper not found at {pdf_path}")

    doc = fitz.open(pdf_path)
    detector = LayoutDetector()
    recognizer = TableRecognizer()

    # 1. Page 4: Table 1 (Table with multi-line cells and booktabs lines)
    p4 = doc[3]
    ctx4 = PageContext.from_page(p4, page_num=3)
    regs4 = detector.detect_page(p4, page_num=3, ctx=ctx4)
    tab_regs4 = [r for r in regs4 if r.kind == "table"]

    assert len(tab_regs4) == 1, f"Expected exactly 1 table on page 4, found {len(tab_regs4)}"
    t1_box = tab_regs4[0].bbox
    # Must NOT swallow footer at y=744
    assert t1_box.y1 <= 705.0, f"Table 1 exceeded bottom boundary: {t1_box.y1}"
    assert 220.0 <= t1_box.height <= 260.0, f"Unexpected Table 1 height: {t1_box.height}"

    html_str, gfm_str, has_merged = recognizer.recognize_table(p4, t1_box, ctx=ctx4)
    assert gfm_str is not None, "Table 1 should be convertible to GFM markdown"
    gfm_lines = [l for l in gfm_str.splitlines() if l.startswith("|") and not l.startswith("| ---")]
    # Exactly 1 header + 8 data rows = 9 rows
    assert len(gfm_lines) == 9, f"Expected 9 GFM rows in Table 1, got {len(gfm_lines)}"
    assert "ConvNet-based" in gfm_str
    assert "Transformer-based" in gfm_str
    assert "Li et al. [15], Xie et al. [16]" in gfm_str

    # 2. Page 23: Table 11 (Must NOT swallow H. Visualizations prose or Fig 8)
    p23 = doc[22]
    ctx23 = PageContext.from_page(p23, page_num=22)
    regs23 = detector.detect_page(p23, page_num=22, ctx=ctx23)
    tab_regs23 = [r for r in regs23 if r.kind == "table"]

    assert len(tab_regs23) == 1, f"Expected 1 table on page 23, found {len(tab_regs23)}"
    t11_box = tab_regs23[0].bbox
    assert t11_box.y1 <= 215.0, f"Table 11 over-expanded past y=215, got y1={t11_box.y1}"
    assert t11_box.height < 120.0, f"Table 11 height swallowed body text: {t11_box.height}"

    html11, gfm11, _ = recognizer.recognize_table(p23, t11_box, ctx=ctx23)
    assert "Visualizations" not in html11, "Table 11 must not swallow Section H. Visualizations"
    assert "Fig 8" not in html11, "Table 11 must not swallow Figure 8 caption"
    assert "ASTM-Net-ALLs" in html11
