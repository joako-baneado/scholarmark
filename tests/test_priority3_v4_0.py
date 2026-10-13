"""
Pruebas unitarias para Prioridad 3 (ScholarMark v4.0):
- SemanticChunker (fragmentación jerárquica consciente de DocumentIR).
- Chunks atómicos para tablas, figuras, algoritmos y ecuaciones.
- Hidratación O(1) de citas bibliográficas y vinculación de artefactos (Fig, Table, Algorithm, Eq).
- Aislamiento de biografías no rectangulares IEEE en ["Author Biographies"].
- Exportación *.chunks.jsonl desde ScholarExtractor y CLI.
"""

from __future__ import annotations

import json
from pathlib import Path

import fitz

from scholarmark.config import ExtractorConfig
from scholarmark.extractor import ScholarExtractor
from scholarmark.ir.document import Block, BoundingBox, DocumentIR, PageIR
from scholarmark.rag.chunker import SemanticChunker


def _build_sample_ir() -> DocumentIR:
    b_h1 = Block(
        id="p1_h1",
        kind="section_header",
        page=1,
        bbox=BoundingBox(50, 50, 300, 70),
        text="3. Methodology",
        heading_level=2,
    )
    b_h2 = Block(
        id="p1_h2",
        kind="section_header",
        page=1,
        bbox=BoundingBox(50, 80, 300, 98),
        text="3.1 Adaptive Graph Topology",
        heading_level=3,
    )
    b_prose = Block(
        id="p1_p1",
        kind="text",
        page=1,
        bbox=BoundingBox(50, 110, 520, 160),
        text=(
            "As shown in Fig. 2, Table 1, Algorithm 1, and Eq. (1), our model reduces latency "
            "by 41.2% at 144 FPS compared to prior work [1], [2]."
        ),
    )
    b_fig = Block(
        id="p1_fig2",
        kind="figure",
        page=1,
        bbox=BoundingBox(60, 170, 340, 290),
        caption_text="Fig. 2: Latency breakdown across GPU providers.",
        asset="sample_figs/fig_p1_1.png",
        metadata={
            "chart_semantics": {
                "axis_labels": ["Latency (ms)"],
                "legend_series": ["ScholarMark", "Baseline"],
                "data_annotations": ["4.2ms"],
            }
        },
    )
    b_tab = Block(
        id="p1_tab1",
        kind="table",
        page=1,
        bbox=BoundingBox(60, 310, 480, 410),
        caption_text="Table 1: Quantitative comparison on Gold Suite.",
        html="<table><tr><th>Method</th><th>TEDS</th></tr><tr><td>Ours</td><td>0.96</td></tr></table>",
    )
    b_algo = Block(
        id="p1_algo1",
        kind="algorithm",
        page=1,
        bbox=BoundingBox(60, 420, 480, 510),
        caption_text="Algorithm 1: Dynamic Span Grouping",
        gfm="Algorithm 1: Dynamic Span Grouping\n  1: return spans",
        metadata={"algorithm_id": "1", "algorithm_title": "Algorithm 1: Dynamic Span Grouping"},
    )
    b_eq = Block(
        id="p1_eq1",
        kind="formula",
        page=1,
        bbox=BoundingBox(120, 520, 400, 555),
        latex=r"\mathcal{L}_{total} = \alpha \mathcal{L}_{topo} + \beta \mathcal{L}_{vis} \quad (1)",
        metadata={"tag": "1"},
    )
    b_bio = Block(
        id="p1_bio1",
        kind="author_bio",
        page=1,
        bbox=BoundingBox(50, 650, 280, 730),
        text="Dr. Helena Vance received the Ph.D. degree in computer science from Stanford University in 2020.",
    )

    page = PageIR(
        page_number=1,
        width=595.0,
        height=842.0,
        blocks=[b_h1, b_h2, b_prose, b_fig, b_tab, b_algo, b_eq, b_bio],
        reading_order=["p1_h1", "p1_h2", "p1_p1", "p1_fig2", "p1_tab1", "p1_algo1", "p1_eq1", "p1_bio1"],
    )
    return DocumentIR(
        pages=[page],
        meta={
            "source_pdf": "sample_paper.pdf",
            "title": "Adaptive Scientific Document Extraction",
            "bibliography": [
                {
                    "ref_id": "1",
                    "raw_text": '[1] A. Author, "Graph Layout Analysis," CVPR, 2024.',
                    "authors": "A. Author",
                    "title": "Graph Layout Analysis",
                    "year": 2024,
                    "doi": "10.1109/CVPR.2024.100",
                },
                {
                    "ref_id": "2",
                    "raw_text": '[2] B. Researcher, "Visual Math Parsing," ICCV, 2025.',
                    "authors": "B. Researcher",
                    "title": "Visual Math Parsing",
                    "year": 2025,
                    "doi": None,
                },
            ],
        },
    )


def test_semantic_chunker_atomic_blocks_and_cross_references(tmp_path: Path):
    ir = _build_sample_ir()
    chunker = SemanticChunker(max_chars=1200)
    chunks = chunker.chunk_document(ir)

    prose_chunks = [c for c in chunks if c.chunk_type == "prose" and "3.1 Adaptive Graph Topology" in c.section_hierarchy]
    assert len(prose_chunks) == 1
    p_chunk = prose_chunks[0]

    # Verificar jerarquía de secciones
    assert p_chunk.section_hierarchy == ["3. Methodology", "3.1 Adaptive Graph Topology"]

    # Verificar vinculación cruzada a los 4 tipos de artefactos (Fig. 2, Table 1, Algorithm 1, Eq. 1)
    assert len(p_chunk.related_figures) == 1
    assert p_chunk.related_figures[0]["asset_path"] == "sample_figs/fig_p1_1.png"
    assert len(p_chunk.related_tables) == 1
    assert "Table 1" in p_chunk.related_tables[0]["caption"]
    assert len(p_chunk.related_algorithms) == 1
    assert "Algorithm 1" in p_chunk.related_algorithms[0]["caption"]
    assert len(p_chunk.related_equations) == 1

    # Verificar hidratación O(1) de citas [1] y [2] y extracción de métricas
    cited_ids = {c["ref_id"] for c in p_chunk.citations}
    assert cited_ids == {"1", "2"}
    assert "41.2%" in p_chunk.metrics
    assert "144 FPS" in p_chunk.metrics

    # Verificar chunks atómicos (figure, table, algorithm, formula)
    chunk_types = [c.chunk_type for c in chunks]
    assert "figure" in chunk_types
    assert "table" in chunk_types
    assert "algorithm" in chunk_types
    assert "formula" in chunk_types

    # Verificar aislamiento de biografías IEEE en ["Author Biographies"]
    bio_chunks = [c for c in chunks if c.section_hierarchy == ["Author Biographies"]]
    assert len(bio_chunks) == 1
    assert "received the Ph.D. degree" in bio_chunks[0].text
    assert "received the Ph.D. degree" not in p_chunk.text


def test_extractor_exports_chunks_jsonl_end_to_end(tmp_path: Path):
    pdf_path = tmp_path / "rag_e2e.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text(fitz.Point(55, 70), "1. Introduction", fontsize=12)
    page.insert_text(
        fitz.Point(55, 95),
        "Our method improves throughput by 52.0% at 3.1 ms latency [1].",
        fontsize=10,
    )
    page.insert_text(fitz.Point(55, 140), "References", fontsize=12)
    page.insert_text(
        fitz.Point(55, 165),
        '[1] K. Tanaka, "High-Speed Scientific RAG," NeurIPS, 2025.',
        fontsize=9.5,
    )
    doc.save(str(pdf_path))
    doc.close()

    out_dir = tmp_path / "out"
    cfg = ExtractorConfig(engine="vision", export_json=True, export_chunks=True)
    extractor = ScholarExtractor(config=cfg)
    res = extractor.convert_file(pdf_path, out_dir)

    assert res.status == "success"
    assert res.target_chunks is not None
    chunks_file = Path(res.target_chunks)
    assert chunks_file.exists()

    lines = [json.loads(line) for line in chunks_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) >= 1
    intro_chunks = [c for c in lines if "1. Introduction" in c["section_hierarchy"]]
    assert len(intro_chunks) == 1
    assert "52.0%" in intro_chunks[0]["metrics"]
    assert intro_chunks[0]["citations"][0]["ref_id"] == "1"
