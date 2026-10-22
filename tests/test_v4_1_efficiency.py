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
