"""
Unit tests for DocumentIR, Markdown/JSON rendering, and pluggable Engine selection.
"""

import json
import tempfile
import unittest
from pathlib import Path

from scholarmark.config import ExtractorConfig
from scholarmark.core.geometry import BoundingBox
from scholarmark.ir import Block, PageIR, DocumentIR
from scholarmark.render import render_markdown, export_canonical_json
from scholarmark.engines import get_engine, FastEngine


class TestIRAndEngines(unittest.TestCase):

    def _build_sample_ir(self) -> DocumentIR:
        blocks = [
            Block(
                id="p1_title",
                kind="title",
                bbox=BoundingBox(50, 40, 550, 75),
                page=1,
                text="Spatio-Temporal Graph Networks for 3D Pose Estimation",
            ),
            Block(
                id="p1_sec1",
                kind="section_header",
                bbox=BoundingBox(50, 90, 280, 110),
                page=1,
                text="1. Introduction",
                heading_level=2,
            ),
            Block(
                id="p1_txt1",
                kind="text",
                bbox=BoundingBox(50, 120, 280, 220),
                page=1,
                text="We evaluate latency at 14 _._ 2 ms and accuracy of 98.4%.",
            ),
            Block(
                id="p1_eq1",
                kind="formula",
                bbox=BoundingBox(60, 230, 260, 265),
                page=1,
                text="L = x_i / y_i",
                latex=r"\mathcal{L} = \frac{x_i}{y_i}",
                confidence=0.95,
                source="model",
                metadata={"tag": "1"},
            ),
            Block(
                id="p1_tab1",
                kind="table",
                bbox=BoundingBox(310, 100, 550, 220),
                page=1,
                caption_text="TABLE I: Multi-level comparison",
                html='<table><tr><th colspan="2">Metrics</th></tr><tr><td>MPJPE</td><td>34.1 mm</td></tr></table>',
                source="model",
            ),
            Block(
                id="p1_fig1",
                kind="figure",
                bbox=BoundingBox(310, 240, 550, 380),
                page=1,
                asset="fig_p1_1.png",
                caption_id="p1_cap1",
                caption_text="Fig. 1: Network overview.",
            ),
            Block(
                id="p1_cap1",
                kind="figure_caption",
                bbox=BoundingBox(310, 385, 550, 405),
                page=1,
                text="Fig. 1: Network overview.",
            ),
            Block(
                id="p1_fn1",
                kind="footnote",
                bbox=BoundingBox(50, 720, 550, 745),
                page=1,
                text="1 Code available at https://example.org",
            ),
            Block(
                id="p1_hdr_abandon",
                kind="abandon",
                bbox=BoundingBox(50, 10, 550, 25),
                page=1,
                text="IEEE TRANSACTIONS ON PATTERN ANALYSIS, VOL. 48, 2026",
            ),
        ]
        reading_order = ["p1_title", "p1_sec1", "p1_txt1", "p1_eq1", "p1_tab1", "p1_fig1", "p1_cap1", "p1_fn1"]
        page = PageIR(page_number=1, width=612.0, height=792.0, blocks=blocks, reading_order=reading_order)
        return DocumentIR(
            meta={"title": "Spatio-Temporal Graph Networks for 3D Pose Estimation", "year": 2026, "engine": "vision"},
            pages=[page],
            reading_order=reading_order,
        )

    def test_render_markdown_preserves_html_tables_katex_and_footnotes(self):
        ir = self._build_sample_ir()
        cfg = ExtractorConfig(engine="vision", html_complex_tables=True)
        md = render_markdown(ir, cfg, paper_stem="pose_paper", pdf_filename="pose_paper.pdf")

        # 1. Abandon header excluded
        self.assertNotIn("IEEE TRANSACTIONS ON PATTERN ANALYSIS", md)
        # 2. Decimal fracture repaired in inline text
        self.assertIn("14.2 ms", md)
        # 3. Formula rendered with \frac and \tag{1}
        self.assertIn(r"\mathcal{L} = \frac{x_i}{y_i} \tag{1}", md)
        # 4. Complex table with colspan rendered as semantic HTML
        self.assertIn('<th colspan="2">Metrics</th>', md)
        # 5. Figure linked once without duplicating consumed figure_caption
        self.assertEqual(md.count("Fig. 1: Network overview."), 2)  # alt text + italic caption
        # 6. Footnote segregated at the end under ## Footnotes
        self.assertIn("## Footnotes", md)
        self.assertIn("Code available at https://example.org", md)

    def test_low_confidence_formula_includes_native_comment_fallback(self):
        ir = self._build_sample_ir()
        eq_block = [b for b in ir.pages[0].blocks if b.kind == "formula"][0]
        eq_block.confidence = 0.35
        cfg = ExtractorConfig(engine="vision")
        md = render_markdown(ir, cfg, paper_stem="pose_paper", pdf_filename="pose_paper.pdf")
        self.assertIn("<!-- sm:native L = x_i / y_i -->", md)

    def test_export_canonical_json_roundtrip(self):
        ir = self._build_sample_ir()
        with tempfile.TemporaryDirectory() as tmp:
            json_path = Path(tmp) / "pose_paper.scholarmark.json"
            export_canonical_json(ir, json_path)
            self.assertTrue(json_path.exists())
            loaded = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["schema_version"], "3.0.0")
            self.assertEqual(len(loaded["pages"]), 1)
            self.assertEqual(loaded["pages"][0]["blocks"][3]["kind"], "formula")

    def test_engine_factory_resolves_fast_engine(self):
        cfg = ExtractorConfig(engine="fast")
        eng = get_engine(cfg)
        self.assertIsInstance(eng, FastEngine)
        ok, _ = eng.available()
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()
