"""
Unit and integration tests for ScholarMark v4.1 (Ultra-Light & Max-Efficiency).
Covers Task 1.1 through Task 4.2 validation criteria.
"""

import json
from pathlib import Path

from scholarmark.config import ExtractorConfig
from scholarmark.core.geometry import BoundingBox
from scholarmark.core.manifest import extract_document_info
from scholarmark.engines import get_engine, FastEngine, VisionEngine
from scholarmark.ir import Block, PageIR, DocumentIR
from scholarmark.render import export_canonical_json


def test_task1_1_auto_engine_promotes_vision_and_preserves_fast():
    cfg_auto = ExtractorConfig(engine="auto")
    eng_auto = get_engine(cfg_auto)
    assert isinstance(eng_auto, VisionEngine)

    cfg_fast = ExtractorConfig(engine="fast")
    eng_fast = get_engine(cfg_fast)
    assert isinstance(eng_fast, FastEngine)


def test_task1_1_manifest_reads_scholarmark_json_suffix(tmp_path: Path):
    b_algo = Block(
        id="p1_algo1",
        kind="algorithm",
        page=1,
        bbox=BoundingBox(50, 100, 400, 200),
        text="Algorithm 1: Pose Filter",
        metadata={"algorithm_id": "1"},
    )
    b_fig = Block(
        id="p1_fig1",
        kind="figure",
        page=1,
        bbox=BoundingBox(50, 220, 400, 380),
        asset="fig_p1_1.png",
        caption_text="Fig. 1: Latency comparison.",
        metadata={"chart_semantics": {"axis_labels": ["Latency (ms)"], "legend_series": ["Ours"]}},
    )
    page = PageIR(page_number=1, width=595.0, height=842.0, blocks=[b_algo, b_fig], reading_order=["p1_algo1", "p1_fig1"])
    ir = DocumentIR(
        meta={
            "title": "Boxing Pose Paper",
            "engine": "vision",
            "bibliography": [{"ref_id": "1", "authors": "Zhang et al.", "year": 2025, "title": "Fast Pose"}],
            "grounded_claims": [{"sentence": "Achieves 120 FPS [1].", "metrics": ["120 FPS"], "cited_ref_ids": ["1"]}],
        },
        pages=[page],
        reading_order=["p1_algo1", "p1_fig1"],
    )

    md_path = tmp_path / "sample.md"
    md_path.write_text("---\ntitle: Boxing Pose Paper\nengine: vision\n---\n\n# Boxing Pose Paper\n", encoding="utf-8")
    # Export using the standard .scholarmark.json suffix produced by ScholarExtractor
    export_canonical_json(ir, tmp_path / "sample.scholarmark.json")

    info = extract_document_info(md_path)
    assert info["algorithms_count"] == 1
    assert info["references_count"] == 1
    assert len(info["grounded_claims"]) == 1
    assert info["figures"][0]["chart_semantics"]["axis_labels"] == ["Latency (ms)"]


def test_task1_2_in_memory_manifest_without_json_export(tmp_path: Path):
    import fitz
    from scholarmark.extractor import ScholarExtractor

    src_dir = tmp_path / "src"
    out_dir = tmp_path / "out"
    src_dir.mkdir()
    pdf_path = src_dir / "batch_paper.pdf"

    doc = fitz.open()
    pg = doc.new_page(width=595, height=842)
    pg.insert_text(fitz.Point(55, 70), "1. Introduction", fontsize=12)
    pg.insert_text(fitz.Point(55, 95), "Algorithm 1: Real-Time Pose Filter", fontsize=10.5)
    pg.insert_text(fitz.Point(55, 110), "1: for each frame f do", fontsize=9.5)
    pg.insert_text(fitz.Point(70, 124), "2: return pose(f)", fontsize=9.5)
    pg.insert_text(fitz.Point(55, 138), "3: end for", fontsize=9.5)
    pg.insert_text(fitz.Point(55, 170), "Our framework reaches 144 FPS with 97.5% accuracy [1].", fontsize=10)
    pg.insert_text(fitz.Point(55, 210), "References", fontsize=12)
    pg.insert_text(fitz.Point(55, 235), '[1] J. Basas, "ShadowBox Pose Tracking," IEEE CVPR, 2026.', fontsize=9.5)
    doc.save(str(pdf_path))
    doc.close()

    # export_json=False, engine="auto" -> VisionEngine + in-memory manifest entry
    cfg = ExtractorConfig(engine="auto", export_json=False, extract_images=False)
    extractor = ScholarExtractor(config=cfg)
    results = extractor.convert_batch(src_dir, out_dir)

    assert len(results) == 1
    assert results[0].status == "success"
    assert results[0].engine_used == "vision"
    assert not (out_dir / "batch_paper.scholarmark.json").exists()

    manifest_file = out_dir / "scholarmark_manifest.json"
    assert manifest_file.exists()
    manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
    doc_entry = manifest_data["documents"]["batch_paper"]
    assert doc_entry["engine"] == "vision"
    assert doc_entry["algorithms_count"] == 1
    assert doc_entry["references_count"] == 1
    assert len(doc_entry["grounded_claims"]) >= 1


def test_task2_1_single_pass_page_context_eliminates_redundant_calls(tmp_path: Path):
    import fitz
    from unittest.mock import patch
    from scholarmark.core.page_context import PageContext

    pdf_path = tmp_path / "single_pass.pdf"
    doc = fitz.open()
    pg = doc.new_page(width=595, height=842)
    pg.insert_text(fitz.Point(55, 65), "1. Methodology", fontsize=12)
    pg.insert_text(fitz.Point(55, 95), "We compute the loss function as follows:", fontsize=10)
    pg.insert_text(fitz.Point(160, 130), "L = x + y (1)", fontsize=10.5)
    pg.insert_text(fitz.Point(55, 165), "Algorithm 1: Fast Step", fontsize=10.5)
    pg.insert_text(fitz.Point(55, 180), "1: for i in N do", fontsize=9.5)
    pg.insert_text(fitz.Point(70, 194), "2: x <- x + 1", fontsize=9.5)
    pg.insert_text(fitz.Point(55, 208), "3: end for", fontsize=9.5)
    doc.save(str(pdf_path))
    doc.close()

    cfg = ExtractorConfig(engine="vision", extract_images=False)
    eng = VisionEngine(cfg)

    with fitz.open(str(pdf_path)) as d:
        page = d[0]
        ctx = PageContext.from_page(page, 1)
        assert len(ctx.words) >= 10
        assert "Methodology" in ctx.full_text

        orig_get_text = fitz.Page.get_text
        rawdict_calls = []

        def tracked_get_text(self_page, option="text", *args, **kwargs):
            if option in ("rawdict", "dict"):
                rawdict_calls.append(option)
            return orig_get_text(self_page, option, *args, **kwargs)

        with patch.object(
            fitz.Page, "get_text", autospec=True, side_effect=tracked_get_text
        ):
            ir, _ = eng.parse(d, pdf_path)

        # PageContext.from_page executes exactly 1 "rawdict" call per page across all ScholarMark stages
        assert rawdict_calls == ["rawdict"]
        assert len(ir.pages) == 1


def test_task2_2_lazy_find_tables_gate_and_sla(tmp_path: Path):
    import time
    import fitz
    from unittest.mock import patch
    from bench.gold_suite import _create_case3_hierarchical_table
    from bench.metrics import teds_table_score

    p3 = tmp_path / "case3_hierarchical_table.pdf"
    vis_cfg = ExtractorConfig(engine="vision", extract_images=False, html_complex_tables=True)
    vis_eng = VisionEngine(vis_cfg)

    find_tables_calls = []
    orig_find_tables = fitz.Page.find_tables

    def tracked_find_tables(*args, **kwargs):
        find_tables_calls.append(1)
        return orig_find_tables(*args, **kwargs)

    with _create_case3_hierarchical_table(p3) as doc:
        with patch.object(fitz.Page, "find_tables", side_effect=tracked_find_tables):
            t0 = time.perf_counter()
            ir_vis, _ = vis_eng.parse(doc, p3)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

    # Lazy gate avoids calling expensive find_tables() on resolved booktabs tables
    assert len(find_tables_calls) == 0
    assert elapsed_ms < 150.0, f"Expected < 150 ms, got {elapsed_ms:.1f} ms"

    gold_html = (
        '<table>'
        '<tr><th rowspan="2">Method</th><th colspan="2">Human3.6M-Protocol</th></tr>'
        '<tr><th>MPJPE</th><th>P-MPJPE</th></tr>'
        '<tr><td>Baseline</td><td>42.8mm</td><td>33.5mm</td></tr>'
        '<tr><td>ScholarPose</td><td>31.4mm</td><td>24.1mm</td></tr>'
        '</table>'
    )
    vis_tabs = [b.html for b in ir_vis.all_blocks_ordered() if b.kind == "table" and b.html]
    assert len(vis_tabs) == 1
    teds = teds_table_score(vis_tabs[0], gold_html, structure_only=False)
    assert teds == 1.0


def test_task3_1_direct_xref_raster_dump_and_adaptive_vector_dpi(tmp_path: Path):
    import io
    import time
    import fitz
    from PIL import Image
    from unittest.mock import patch
    from scholarmark.core.geometry import export_figure_asset
    from scholarmark.core.page_context import PageContext

    # 1. Create a PDF with an embedded PNG raster image
    img = Image.new("RGB", (240, 160), color=(40, 120, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    pdf_raster = tmp_path / "raster_fig.pdf"
    doc = fitz.open()
    pg = doc.new_page(width=595, height=842)
    img_rect = fitz.Rect(80, 100, 320, 260)
    pg.insert_image(img_rect, stream=png_bytes)
    pg.insert_text(fitz.Point(80, 280), "Fig. 1: Embedded RGB keyframe.", fontsize=10)
    doc.save(str(pdf_raster))
    doc.close()

    out_png = tmp_path / "fig_raster.png"
    with fitz.open(str(pdf_raster)) as d:
        page = d[0]
        ctx = PageContext.from_page(page, 1)
        pixmap_calls = []
        orig_get_pixmap = fitz.Page.get_pixmap

        def tracked_pixmap(*args, **kwargs):
            pixmap_calls.append(1)
            return orig_get_pixmap(*args, **kwargs)

        t0 = time.perf_counter()
        with patch.object(fitz.Page, "get_pixmap", side_effect=tracked_pixmap):
            ok = export_figure_asset(
                page=page,
                bbox=BoundingBox(80, 100, 320, 260),
                destination=out_png,
                target_dpi=300,
                ctx=ctx,
            )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert ok is True
    assert out_png.exists()
    # Direct XREF dump does NOT call page.get_pixmap() and finishes in < 15 ms
    assert len(pixmap_calls) == 0
    assert elapsed_ms < 15.0

    # 2. Create a large vector chart (>15,000 pt^2) with >= 9pt labels and verify adaptive 200 DPI scaling
    pdf_vec = tmp_path / "vec_fig.pdf"
    doc2 = fitz.open()
    pg2 = doc2.new_page(width=595, height=842)
    sh = pg2.new_shape()
    sh.draw_rect(fitz.Rect(60, 100, 420, 300))  # 360 x 200 = 72,000 pt^2
    sh.finish(color=(0.1, 0.2, 0.5), width=1.2)
    sh.commit()
    pg2.insert_text(fitz.Point(100, 150), "Accuracy (98.4%)", fontsize=10)
    doc2.save(str(pdf_vec))
    doc2.close()

    out_vec = tmp_path / "fig_vec.png"
    with fitz.open(str(pdf_vec)) as d2:
        page2 = d2[0]
        ctx2 = PageContext.from_page(page2, 1)
        ok2 = export_figure_asset(
            page=page2,
            bbox=BoundingBox(60, 100, 420, 300),
            destination=out_vec,
            target_dpi=300,
            ctx=ctx2,
        )
    assert ok2 is True
    with Image.open(out_vec) as rendered_im:
        # At 200 DPI, width of 360 pt is 360 * (200 / 72) = 1000 px (whereas 300 DPI would be 1500 px)
        assert 995 <= rendered_im.width <= 1005


def test_task3_2_multiprocess_batch_pool_race_free_manifest(tmp_path: Path):
    import fitz
    from scholarmark.extractor import ScholarExtractor

    src_dir = tmp_path / "src_mp"
    out_dir = tmp_path / "out_mp"
    src_dir.mkdir()

    for k in range(1, 5):
        p = src_dir / f"paper_{k}.pdf"
        doc = fitz.open()
        pg = doc.new_page(width=595, height=842)
        pg.insert_text(fitz.Point(55, 70), f"Paper {k}: High-Speed Pose Estimation", fontsize=13)
        pg.insert_text(fitz.Point(55, 105), f"Our model {k} achieves {90 + k}.5% accuracy at {100 + k * 10} FPS [1].", fontsize=10)
        pg.insert_text(fitz.Point(55, 145), "References", fontsize=12)
        pg.insert_text(fitz.Point(55, 170), f'[1] Author {k}, "Fast Pose {k}," IEEE CVPR, 2026.', fontsize=9.5)
        doc.save(str(p))
        doc.close()

    cfg = ExtractorConfig(engine="vision", workers=2, extract_images=False, export_json=False)
    extractor = ScholarExtractor(config=cfg)
    results = extractor.convert_batch(src_dir, out_dir)

    assert len(results) == 4
    assert all(r.status == "success" for r in results)

    manifest_path = out_dir / "scholarmark_manifest.json"
    assert manifest_path.exists()
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest_data["total_papers"] == 4
    for k in range(1, 5):
        entry = manifest_data["documents"][f"paper_{k}"]
        assert entry["references_count"] == 1
        assert len(entry["grounded_claims"]) >= 1

    # Second run should skip all 4 via DeltaCache recorded in parent process
    results_cached = extractor.convert_batch(src_dir, out_dir)
    assert all(r.status == "skipped" for r in results_cached)
