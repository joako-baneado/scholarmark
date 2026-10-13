"""
Unit tests verifying fixes for v2.1 architectural bugs (B1 through B10).
"""

import tempfile
import unittest
from pathlib import Path
import fitz

from scholarmark.config import ExtractorConfig
from scholarmark.core.geometry import (
    BoundingBox,
    cluster_vector_drawings,
    expand_figure_bbox,
    elastic_expand_bbox,
)
from scholarmark.core.academic import standardize_headings, purge_page_numbers
from scholarmark.core.math_parser import isolate_equations
from scholarmark.core.manifest import extract_document_info
from scholarmark.utils.cache import DeltaCache


class TestBugfixesV3(unittest.TestCase):

    def test_b5_b6_transitive_union_find_vector_clustering(self):
        """
        Verifica que tres rectángulos A, B, C donde A está cerca de B, C está cerca de B,
        pero A y C están lejos, se agrupen transitivamente sin importar el orden de aparición.
        """
        doc = fitz.open()
        page = doc.new_page(width=600, height=800)
        shape = page.new_shape()
        # A (x: 50..100), C (x: 118..168, lejos de A por 18pt > 12pt), B puente (x: 95..125)
        rects = [
            fitz.Rect(50, 100, 100, 180),   # A
            fitz.Rect(118, 100, 168, 180),  # C (aparece antes que el puente B!)
            fitz.Rect(95, 100, 125, 180),   # B (puente que conecta A y C)
        ]
        # Añadir 6 rectángulos adicionales dentro de A para superar min_drawing_count=8
        for i in range(6):
            rects.append(fitz.Rect(55 + i * 3, 105, 70 + i * 3, 175))

        for r in rects:
            shape.draw_rect(r)
            shape.finish(color=(0, 0, 0), width=1)
        shape.commit()

        clusters = cluster_vector_drawings(page, min_drawing_count=8, min_area=1000.0)
        self.assertEqual(len(clusters), 1)
        self.assertAlmostEqual(clusters[0].x0, 50.0, delta=2.0)
        self.assertAlmostEqual(clusters[0].x1, 168.0, delta=2.0)
        doc.close()

    def test_b7_vector_saturation_safety_guard(self):
        """
        Verifica que cuando el conteo de primitivas supera max_vector_primitives,
        expand_figure_bbox no colapsa ni une trazos fuera del límite, aplicando solo recorte elástico.
        """
        doc = fitz.open()
        page = doc.new_page(width=600, height=800)
        base_box = BoundingBox(100, 100, 300, 300)
        # Simular 2,500 primitivas vectoriales (> límite 2,000) incluyendo una a 8pt
        fake_drawings = [{"rect": fitz.Rect(92, 100, 99, 300)}] * 2500
        expanded = expand_figure_bbox(
            page=page,
            figure_bbox=base_box,
            bleed_padding=4.0,
            drawings=fake_drawings,
            words=[],
            max_vector_primitives=2000,
        )
        # Como se activó la guarda (>2000), no absorbió x0=92; solo aplicó el bleed_padding de 4pt (100 - 4 = 96)
        self.assertAlmostEqual(expanded.x0, 96.0, places=1)
        doc.close()

    def test_elastic_padding_absorbs_axis_and_subpanel_labels_not_prose(self):
        """
        Verifica que elastic_expand_bbox absorbe '(a)' y '×10^-3' dentro de 16pt,
        pero se detiene ante palabras de prosa o bloques de texto corrido.
        """
        doc = fitz.open()
        page = doc.new_page(width=600, height=800)
        fig_box = BoundingBox(100, 100, 300, 300)
        words = [
            (100.0, 86.0, 130.0, 96.0, "×10^-3", 0, 0, 0),  # Exponente a 14pt arriba -> debe absorberse
            (85.0, 105.0, 97.0, 115.0, "(a)", 0, 1, 0),      # Subpanel a 15pt izq -> debe absorberse
            (100.0, 308.0, 280.0, 320.0, "Furthermore", 1, 0, 0),  # Palabra de prosa -> NO debe absorberse
        ]
        prose_blocks = [BoundingBox(100.0, 306.0, 500.0, 380.0)]
        expanded = elastic_expand_bbox(
            page=page,
            figure_bbox=fig_box,
            words=words,
            prose_blocks=prose_blocks,
            min_padding=4.0,
            max_padding=16.0,
        )
        self.assertLessEqual(expanded.y0, 86.0)
        self.assertLessEqual(expanded.x0, 85.0)
        # No debe haber absorbido 'Furthermore' (y1 queda en 300 + 4 = 304)
        self.assertAlmostEqual(expanded.y1, 304.0, places=1)
        doc.close()

    def test_b8_standardize_headings_preserves_original_titles(self):
        """
        Verifica que standardize_headings normaliza el nivel ## sin destruir títulos específicos.
        """
        raw = (
            "1. Introduction to Wearable Biomechanics\n"
            "Some text here.\n"
            "IV. EXPERIMENTAL RESULTS ON TOTALCAPTURE DATASET\n"
            "3.2. Kinematic Calibration Protocol\n"
        )
        normalized = standardize_headings(raw, preserve_heading_text=True)
        self.assertIn("## 1. Introduction to Wearable Biomechanics", normalized)
        self.assertIn("## IV. EXPERIMENTAL RESULTS ON TOTALCAPTURE DATASET", normalized)
        self.assertIn("### 3.2. Kinematic Calibration Protocol", normalized)

    def test_b9_purge_page_numbers_protects_math_blocks(self):
        """
        Verifica que números de 1 a 3 dígitos dentro de bloques $$ no son eliminados.
        """
        raw = (
            "$$\n"
            "x_i =\n"
            "100\n"
            "$$\n\n"
            "42\n\n"
            "## 2. Methods"
        )
        cleaned = purge_page_numbers(raw)
        self.assertIn("100", cleaned)
        self.assertNotIn("\n42\n", cleaned)

    def test_b10_isolate_equations_rejects_prose_with_hyphen_and_citation(self):
        """
        Verifica que una línea en prosa con guión y número entre paréntesis al final
        no se transforma erróneamente en ecuación $$ ... $$.
        """
        prose = "This real-time pose estimation framework outperforms previous state-of-the-art methods (1)"
        real_eq = "Vt = Pt+1 - Pt (2)"
        res_prose = isolate_equations(prose)
        res_eq = isolate_equations(real_eq)

        self.assertNotIn("$$", res_prose)
        self.assertIn("$$", res_eq)
        self.assertIn(r"\tag{2}", res_eq)

    def test_b3_delta_cache_invalidates_on_config_change(self):
        """
        Verifica que DeltaCache detecta cambios en ExtractorConfig e invalida la caché.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pdf_file = tmp_path / "sample.pdf"
            md_file = tmp_path / "sample.md"
            pdf_file.write_bytes(b"%PDF-1.4 dummy")
            md_file.write_text("# Dummy", encoding="utf-8")

            cfg1 = ExtractorConfig(dpi=200, engine="fast")
            cfg2 = ExtractorConfig(dpi=300, engine="fast")

            cache = DeltaCache(tmp_path)
            cache.record(pdf_file, md_file, cfg1, figure_count=3)
            cache.save()

            self.assertTrue(cache.is_up_to_date(pdf_file, md_file, cfg1))
            self.assertFalse(cache.is_up_to_date(pdf_file, md_file, cfg2))

    def test_manifest_detects_html_and_gfm_tables(self):
        """
        Verifica que el generador de manifiesto v3 indexa tanto tablas GFM como tablas HTML con colspan/rowspan.
        """
        with tempfile.TemporaryDirectory() as tmp:
            md_file = Path(tmp) / "paper.md"
            md_file.write_text(
                "---\ntitle: Test Paper\ndoi: 10.1109/TEST.2026.1\nyear: 2026\n---\n\n"
                "## 1. Results\n\n"
                "| Model | Accuracy |\n| --- | --- |\n| Ours | 97.5% |\n\n"
                "<table><tr><th colspan=\"2\">Joint Error (mm)</th></tr>"
                "<tr><td>Knee</td><td>4.2 ms</td></tr></table>\n",
                encoding="utf-8"
            )
            info = extract_document_info(md_file)
            self.assertEqual(info["tables_count"], 2)
            self.assertEqual(info["tables"][0]["format"], "gfm")
            self.assertEqual(info["tables"][1]["format"], "html")
            self.assertTrue(info["tables"][1]["has_merged_cells"])
            self.assertIn("97.5%", info["metrics"]["percentages"])


if __name__ == "__main__":
    unittest.main()
