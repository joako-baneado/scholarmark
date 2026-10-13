"""
Unit and integration tests for ScholarMark Priority 2 (v3.2):
- BibliographyParser (IEEE numbered [N] and APA author-year references)
- CitationLinker & expand_citation_markers (range expansion [1]-[4], [2, 5-7], APA matching)
- ChartSemanticsExtractor (axis_labels, legend_series, data_annotations, subpanel exclusion)
- Manifest enrichment (references, grounded_claims, chart_semantics from .ir.json and .md)
"""

import json
from pathlib import Path
import fitz

from scholarmark.config import ExtractorConfig
from scholarmark.core.citations import (
    BibliographyParser,
    CitationLinker,
    expand_citation_markers,
)
from scholarmark.core.manifest import extract_document_info
from scholarmark.engines.vision import VisionEngine
from scholarmark.render.json_export import export_canonical_json
from scholarmark.render.markdown import render_markdown


def test_expand_citation_markers_ranges_and_apa():
    refs = BibliographyParser.parse_from_text(
        '[1] Y. Zhang et al., "Fast 3D Pose Estimation," in CVPR, 2024, doi: 10.1109/CVPR.2024.01.\n'
        '[2] M. Chen, "Sparse Transformers," IEEE TPAMI, 2025.\n'
        '[3] L. Wang, "Motion Capture," ACM TOG, 2024.\n'
        '[4] R. Gomez, "Neural Kinematics," NeurIPS, 2023.'
    )
    assert len(refs) == 4
    assert refs[0].ref_id == "1"
    assert refs[0].year == 2024
    assert "Fast 3D Pose Estimation" in refs[0].title
    assert refs[0].doi == "10.1109/CVPR.2024.01"

    cites = expand_citation_markers(
        "As shown in [1]–[3] and [2, 4], as well as (Zhang et al., 2024), accuracy improves.",
        known_references=refs,
    )
    assert cites == ["1", "2", "3", "4"]


def test_chart_semantics_and_citation_linking_end_to_end(tmp_path: Path):
    pdf_path = tmp_path / "paper_v3_2.pdf"
    doc = fitz.open()
    pg = doc.new_page(width=595, height=842)

    pg.insert_text(fitz.Point(55, 70), "4. Experimental Evaluation", fontsize=12)
    pg.insert_text(
        fitz.Point(55, 95),
        "Our architecture reduces latency by 38.4% and reaches 120 FPS compared to prior baselines [1]-[3].",
        fontsize=10,
    )
    # Gráfico vectorial con ejes, series, valores y etiqueta de subpanel (a) que debe filtrarse
    pg.draw_rect(fitz.Rect(70, 130, 360, 270), color=(0.1, 0.1, 0.1), width=1.0)
    for gy in (160, 190, 220, 250):
        pg.draw_line(fitz.Point(75, gy), fitz.Point(355, gy), color=(0.7, 0.7, 0.7), width=0.5)
    for gx in (120, 170, 220, 270):
        pg.draw_rect(fitz.Rect(gx, 165, gx + 32, 250), color=(0.2, 0.4, 0.8), fill=(0.2, 0.4, 0.8))
    pg.insert_text(fitz.Point(75, 142), "(a)", fontsize=8.5)
    pg.insert_text(fitz.Point(82, 155), "Accuracy (%)", fontsize=8.5)
    pg.insert_text(fitz.Point(190, 265), "Latency (ms)", fontsize=8.5)
    pg.insert_text(fitz.Point(122, 160), "89.1%", fontsize=8.0)
    pg.insert_text(fitz.Point(222, 160), "96.4%", fontsize=8.0)
    pg.insert_text(fitz.Point(312, 165), "YOLOv8", fontsize=8.5)
    pg.insert_text(fitz.Point(312, 182), "ScholarPose", fontsize=8.5)
    pg.insert_text(fitz.Point(70, 290), "Fig. 3: (a) Accuracy vs. latency trade-off across architectures.", fontsize=9.5)

    pg.insert_text(fitz.Point(55, 340), "References", fontsize=12)
    pg.insert_text(
        fitz.Point(55, 365),
        '[1] Y. Zhang and H. Liu, "Fast 3D Pose Estimation," in IEEE CVPR, 2024, doi: 10.1109/CVPR.2024.001.',
        fontsize=9.0,
    )
    pg.insert_text(
        fitz.Point(55, 385),
        '[2] M. Chen et al., "Sparse Skeletal Transformers," IEEE TPAMI, 2025, doi: 10.1109/TPAMI.2025.002.',
        fontsize=9.0,
    )
    pg.insert_text(
        fitz.Point(55, 405),
        '[3] L. Wang, "Real-Time Motion Capture," ACM TOG, 2024, doi: 10.1145/3650003.',
        fontsize=9.0,
    )
    doc.save(str(pdf_path))
    doc.close()

    cfg = ExtractorConfig(engine="vision", extract_images=True, export_json=True)
    eng = VisionEngine(cfg)
    asset_dir = tmp_path / "assets" / "paper_v3_2"
    asset_dir.mkdir(parents=True, exist_ok=True)

    with fitz.open(str(pdf_path)) as d:
        ir, _ = eng.parse(d, pdf_path, asset_dir)

    md_text = render_markdown(ir, cfg, "paper_v3_2", "paper_v3_2.pdf")
    md_file = tmp_path / "paper_v3_2.md"
    md_file.write_text(md_text, encoding="utf-8")
    export_canonical_json(ir, md_file.with_suffix(".ir.json"))

    assert "[Chart Metadata —" in md_text
    assert "YOLOv8" in md_text
    assert "ScholarPose" in md_text

    info = extract_document_info(md_file)
    assert info["references_count"] == 3
    assert len(info["grounded_claims"]) >= 1
    claim0 = info["grounded_claims"][0]
    assert set(claim0["cited_ref_ids"]) == {"1", "2", "3"}
    assert "38.4%" in claim0["metrics"]
    assert info["figures"][0]["chart_semantics"] is not None
    assert "(a)" not in info["figures"][0]["chart_semantics"]["legend_series"]
