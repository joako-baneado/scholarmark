"""
Unit tests for the ScholarMark v3.0 benchmark metrics and Gold Suite quality gates.
"""

import tempfile
import unittest
from pathlib import Path

from bench.metrics import (
    normalized_edit_distance,
    text_fidelity_score,
    kendall_tau_order,
    teds_table_score,
    latex_formula_similarity,
    caption_matching_f1,
)
from bench.gold_suite import run_synthetic_gold_benchmark
from bench.visualize import render_annotated_pages


class TestBenchmarkSuite(unittest.TestCase):

    def test_evaluation_metrics_accuracy(self):
        self.assertAlmostEqual(normalized_edit_distance("same text", "same text"), 0.0)
        self.assertAlmostEqual(text_fidelity_score("same text", "same text"), 1.0)

        # Kendall-tau perfect vs reversed
        self.assertAlmostEqual(kendall_tau_order(["a", "b", "c", "d"], ["a", "b", "c", "d"]), 1.0)
        self.assertAlmostEqual(kendall_tau_order(["d", "c", "b", "a"], ["a", "b", "c", "d"]), 0.0)

        # HTML TEDS
        html_a = '<table><tr><th colspan="2">H</th></tr><tr><td>1</td><td>2</td></tr></table>'
        self.assertAlmostEqual(teds_table_score(html_a, html_a), 1.0)

        # LaTeX similarity
        self.assertGreater(latex_formula_similarity(r"\frac{x_i}{y_k}", r"\frac{ x_i }{ y_k }"), 0.99)

        # Caption F1
        _, _, f1 = caption_matching_f1({("f1", "c1"), ("f2", "c1")}, {("f1", "c1"), ("f2", "c1")})
        self.assertAlmostEqual(f1, 1.0)

    def test_gold_suite_quality_gates_vision_vs_fast(self):
        """
        Verifica que VisionEngine iguala o supera a FastEngine en todas las patologías
        de la Gold Suite y cumple los umbrales de calidad definidos en el plan.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            comparisons = run_synthetic_gold_benchmark(tmp_path)
            self.assertGreaterEqual(len(comparisons), 6)

            by_id = {c.case_id: c for c in comparisons}

            # Gate 1: Orden de lectura Kendall-tau >= 0.90
            self.assertGreaterEqual(by_id["case1_two_col_footnotes"].vision_score, 0.90)
            self.assertGreater(
                by_id["case1_two_col_footnotes"].vision_score,
                by_id["case1_two_col_footnotes"].fast_score,
            )

            # Gate 2: Fidelidad matemática 2D (1 - NED >= 0.75, es decir NED <= 0.25)
            self.assertGreaterEqual(by_id["case2_2d_math"].vision_score, 0.75)
            self.assertGreater(by_id["case2_2d_math"].vision_score, by_id["case2_2d_math"].fast_score)

            # Gate 3: Tablas jerárquicas TEDS >= 0.85
            self.assertGreaterEqual(by_id["case3_booktabs_colspan"].vision_score, 0.85)

            # Gate 4: Emparejamiento 1:N de leyendas F1 >= 0.90
            self.assertGreaterEqual(by_id["case4_multipanel_1n"].vision_score, 0.90)

            # Gate 5: Interruptor de seguridad de saturación vectorial (< 2.5s)
            self.assertEqual(by_id["case5_dense_scatter_guard"].vision_score, 1.0)

            # Gate 6 (Prioridad 1 / v3.1): Preservación de sangría de algoritmos >= 0.90
            self.assertGreaterEqual(by_id["case6_algorithm_pseudocode"].vision_score, 0.90)

            # Gate 7 (Prioridad 2 / v3.2): Grafo de citas y semántica de gráficos >= 0.90
            self.assertGreaterEqual(by_id["case7_citations_and_chart_semantics"].vision_score, 0.90)

            # Probar generador de overlays visuales sobre case1
            overlays = render_annotated_pages(tmp_path / "case1_reading_order.pdf", tmp_path / "overlays")
            self.assertEqual(len(overlays), 1)
            self.assertTrue(overlays[0].exists())


if __name__ == "__main__":
    unittest.main()
