"""
Comprehensive unit tests for the ScholarMark v3.0 VisionEngine components:
- Topological DAG reading order (2-column, full-width barriers, footnote isolation, author bios)
- Cross-page split paragraph stitching around floating figures
- 2D FormulaRecognizer (vector fraction bars, nested subscripts/superscripts, matrices)
- Hierarchical TableRecognizer (booktabs without vertical lines, colspan/rowspan headers, rotated pages)
- End-to-end VisionEngine PDF conversion with Canonical JSON export
"""

import tempfile
import unittest
from pathlib import Path
import fitz

from scholarmark import ScholarExtractor, ExtractorConfig
from scholarmark.core.geometry import BoundingBox
from scholarmark.ir import Block, PageIR
from scholarmark.layout.reading_order import order_page_blocks, stitch_cross_page_paragraphs
from scholarmark.recognizers.formula import FormulaRecognizer, MathSpanToken
from scholarmark.recognizers.table import TableRecognizer


class TestVisionPipeline(unittest.TestCase):

    def test_two_column_reading_order_isolates_footnotes_and_respects_barriers(self):
        """
        Verifica que en una página de dos columnas con título de ancho completo y una nota al pie
        en la base de la columna izquierda, el orden de lectura es:
        Title -> Left Col 1 -> Left Col 2 -> Right Col 1 -> Right Col 2 -> Footnote (al final).
        """
        blocks = [
            Block(id="title", kind="title", bbox=BoundingBox(50, 40, 550, 80), page=1, text="Paper Title"),
            Block(id="right_1", kind="text", bbox=BoundingBox(320, 100, 550, 220), page=1, text="Right top"),
            Block(id="left_1", kind="text", bbox=BoundingBox(50, 100, 280, 220), page=1, text="Left top"),
            Block(id="fn_left", kind="footnote", bbox=BoundingBox(50, 680, 280, 720), page=1, text="1 Footnote on left col"),
            Block(id="left_2", kind="text", bbox=BoundingBox(50, 240, 280, 400), page=1, text="Left bottom"),
            Block(id="right_2", kind="text", bbox=BoundingBox(320, 240, 550, 400), page=1, text="Right bottom"),
            Block(id="running_hdr", kind="abandon", bbox=BoundingBox(50, 10, 550, 25), page=1, text="IEEE TRANS"),
        ]
        ordered = order_page_blocks(blocks, page_width=600.0)
        ordered_ids = [b.id for b in ordered]
        self.assertEqual(
            ordered_ids,
            ["title", "left_1", "left_2", "right_1", "right_2", "fn_left"]
        )

    def test_cross_page_paragraph_stitching_around_top_float(self):
        """
        Verifica que cuando un párrafo al final de la página 1 queda inconcluso y la página 2
        inicia con una figura flotante seguida de la continuación en minúscula del párrafo,
        stitch_cross_page_paragraphs recompone la frase completa sin que la figura la corte.
        """
        p1_block = Block(
            id="p1_last",
            kind="text",
            bbox=BoundingBox(320, 620, 550, 720),
            page=1,
            text="The experimental results demonstrate that our spatio-temporal graph model",
        )
        p2_fig = Block(
            id="p2_fig",
            kind="figure",
            bbox=BoundingBox(50, 50, 550, 220),
            page=2,
            asset="fig_p2_1.png",
            caption_text="Fig. 2: Architecture.",
        )
        p2_cont = Block(
            id="p2_cont",
            kind="text",
            bbox=BoundingBox(50, 250, 280, 360),
            page=2,
            text="reduces average joint error by 18.4% across all subjects.",
        )

        page1 = PageIR(page_number=1, width=600, height=800, blocks=[p1_block], reading_order=["p1_last"])
        page2 = PageIR(page_number=2, width=600, height=800, blocks=[p2_fig, p2_cont], reading_order=["p2_fig", "p2_cont"])

        stitch_cross_page_paragraphs([page1, page2])
        self.assertEqual(
            p1_block.text,
            "The experimental results demonstrate that our spatio-temporal graph model reduces average joint error by 18.4% across all subjects."
        )

    def test_2d_formula_recognizer_reconstructs_fractions_and_nested_scripts(self):
        """
        Verifica que FormulaRecognizer reconstruye una fracción con barra vectorial y
        subíndices/superíndices anidados (x_{i}^{n+1}).
        """
        rec = FormulaRecognizer()
        # Numerador: x_i^{n+1} encima de barra en y=100; Denominador: y_k debajo de barra en y=100
        tokens = [
            MathSpanToken("x", BoundingBox(100, 75, 108, 88), font_size=11.0),
            MathSpanToken("i", BoundingBox(109, 83, 113, 90), font_size=7.5),
            MathSpanToken("n+1", BoundingBox(109, 70, 122, 77), font_size=7.5),
            MathSpanToken("y", BoundingBox(102, 106, 110, 118), font_size=11.0),
            MathSpanToken("k", BoundingBox(111, 113, 116, 120), font_size=7.5),
        ]
        bars = [BoundingBox(98, 99.0, 125, 100.5)]
        latex = rec._reconstruct_sequence(tokens, bars)
        self.assertIn(r"\frac{", latex)
        self.assertIn("x_{i}^{n+1}", latex)
        self.assertIn("y_{k}", latex)

    def test_2d_formula_recognizer_reconstructs_matrix(self):
        """
        Verifica que una disposición 2x2 de tokens se reconstruye como \\begin{pmatrix} ... \\end{pmatrix}.
        """
        rec = FormulaRecognizer()
        tokens = [
            MathSpanToken("a", BoundingBox(100, 100, 110, 112), font_size=10.0),
            MathSpanToken("b", BoundingBox(140, 100, 150, 112), font_size=10.0),
            MathSpanToken("c", BoundingBox(100, 125, 110, 137), font_size=10.0),
            MathSpanToken("d", BoundingBox(140, 125, 150, 137), font_size=10.0),
        ]
        latex = rec._reconstruct_sequence(tokens, [])
        self.assertEqual(latex, r"\begin{pmatrix} a & b \\ c & d \end{pmatrix}")

    def test_hierarchical_table_recognizer_recovers_colspan_and_rowspan(self):
        """
        Verifica que una tabla estilo booktabs con un encabezado superior combinado ('Human3.6M'
        abarcando 2 subcolumnas 'MPJPE' y 'P-MPJPE', mientras 'Method' en col 0 abarca las 2 filas)
        emite HTML semántico con colspan="2" y rowspan="2".
        """
        doc = fitz.open()
        page = doc.new_page(width=600, height=800)
        # Fila 0 de encabezado: 'Method' (x=60..110) y 'Human3.6MDataset' centrado sobre col 1 y col 2 (x=190..350)
        page.insert_text((60, 110), "Method", fontsize=10)
        page.insert_text((195, 110), "Human3.6M-Benchmark", fontsize=10)
        # Fila 1 de sub-encabezado: vacío en col 0, 'MPJPE' en col 1 (x=180..220), 'P-MPJPE' en col 2 (x=290..340)
        page.insert_text((180, 130), "MPJPE", fontsize=10)
        page.insert_text((290, 130), "P-MPJPE", fontsize=10)
        # Fila 2 de datos
        page.insert_text((60, 150), "Ours", fontsize=10)
        page.insert_text((180, 150), "34.2mm", fontsize=10)
        page.insert_text((290, 150), "27.8mm", fontsize=10)

        tab_rec = TableRecognizer()
        html_out, gfm_out, has_merged = tab_rec.recognize_table(
            page, BoundingBox(50, 95, 380, 165)
        )
        self.assertTrue(has_merged)
        self.assertIsNone(gfm_out)
        self.assertIn('colspan="2"', html_out)
        self.assertIn('rowspan="2"', html_out)
        self.assertIn("34.2mm", html_out)
        doc.close()

    def test_end_to_end_vision_engine_extraction_and_json_export(self):
        """
        Verifica el flujo de extremo a extremo de ScholarExtractor con engine='vision' y export_json=True.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            pdf_path = tmp_dir / "synthetic_paper.pdf"

            doc = fitz.open()
            page = doc.new_page(width=612, height=792)
            page.insert_text((72, 60), "Deep Kinematic Tracking at 120 FPS", fontsize=16)
            page.insert_text((72, 100), "1. Introduction", fontsize=12)
            page.insert_text((72, 125), "Our system achieves 99.1% accuracy with 4.5 ms latency.", fontsize=10)
            doc.save(str(pdf_path))
            doc.close()

            out_dir = tmp_dir / "out"
            extractor = ScholarExtractor(
                config=ExtractorConfig(engine="vision", export_json=True, extract_images=False)
            )
            res = extractor.convert_file(pdf_path, out_dir)

            self.assertEqual(res.status, "success")
            self.assertEqual(res.engine_used, "vision")
            self.assertIsNotNone(res.target_json)
            self.assertTrue(Path(res.target_md).exists())
            self.assertTrue(Path(res.target_json).exists())

            md_content = Path(res.target_md).read_text(encoding="utf-8")
            self.assertIn("Deep Kinematic Tracking at 120 FPS", md_content)
            self.assertIn("99.1%", md_content)


if __name__ == "__main__":
    unittest.main()
