"""
Unit tests for visual element extraction, bounding box fusion, and caption matching.
"""

import unittest
import fitz
from scholarmark.core.geometry import BoundingBox, VisualElement, expand_figure_bbox
from scholarmark.core.caption_matcher import CAPTION_REGEX, match_figures_to_captions

class TestVisualExtraction(unittest.TestCase):

    def test_bounding_box_operations(self):
        """Prueba operaciones geométricas de BoundingBox: área, padding y unión."""
        b1 = BoundingBox(10.0, 10.0, 50.0, 50.0)
        self.assertEqual(b1.width, 40.0)
        self.assertEqual(b1.height, 40.0)
        self.assertEqual(b1.area, 1600.0)

        # Padding
        padded = b1.pad(5.0)
        self.assertEqual(padded.x0, 5.0)
        self.assertEqual(padded.y0, 5.0)
        self.assertEqual(padded.x1, 55.0)
        self.assertEqual(padded.y1, 55.0)

        # Unión
        b2 = BoundingBox(40.0, 40.0, 80.0, 80.0)
        u = b1.union(b2)
        self.assertEqual(u.x0, 10.0)
        self.assertEqual(u.y0, 10.0)
        self.assertEqual(u.x1, 80.0)
        self.assertEqual(u.y1, 80.0)

    def test_caption_regex_patterns(self):
        """Verifica la detección robusta de patrones de leyenda científica."""
        valid_captions = [
            "Fig. 1: Architecture of the proposed neural network.",
            "Figure 2. Comparison between baseline and proposed method.",
            "FIG. 3 - Performance curves over 100 epochs.",
            "Figura 4: Diagrama cinemático de articulaciones.",
            "Fig. 5(a) Confusion matrix for training split.",
            "Abbildung 1: Schematische Darstellung."
        ]
        for cap in valid_captions:
            self.assertIsNotNone(CAPTION_REGEX.search(cap), f"Failed to match: {cap}")

        invalid_captions = [
            "In this figure, we observe the following results.",
            "Table 1: Hyperparameter configurations.",
            "This confirms the hypothesis presented in Fig. 1."
        ]
        for inv in invalid_captions:
            self.assertIsNone(CAPTION_REGEX.search(inv), f"Incorrectly matched: {inv}")

    def test_deterministic_caption_matching(self):
        """Verifica el emparejamiento biyectivo espacial figura-caption."""
        # Figura 1 en parte superior izquierda
        fig1 = VisualElement(bbox=BoundingBox(50.0, 50.0, 200.0, 150.0), page_num=1)
        # Figura 2 en parte inferior izquierda
        fig2 = VisualElement(bbox=BoundingBox(50.0, 300.0, 200.0, 400.0), page_num=1)

        # Leyenda 1 directamente bajo Figura 1
        cap1 = (BoundingBox(50.0, 155.0, 200.0, 175.0), "Fig. 1: Top Architecture Overview")
        # Leyenda 2 directamente bajo Figura 2
        cap2 = (BoundingBox(50.0, 405.0, 200.0, 425.0), "Fig. 2: Bottom Precision Curve")

        figures = [fig1, fig2]
        captions = [cap2, cap1]  # En orden invertido para comprobar resolución óptima

        match_figures_to_captions(figures, captions, page_width=600.0)

        self.assertEqual(fig1.caption_text, "Fig. 1: Top Architecture Overview")
        self.assertEqual(fig2.caption_text, "Fig. 2: Bottom Precision Curve")

if __name__ == "__main__":
    unittest.main()
