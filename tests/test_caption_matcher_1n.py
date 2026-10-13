"""
Unit tests for 1:N multipanel caption matching, intervening text penalties,
composite subfigure consolidation, and table caption association.
"""

import unittest
from scholarmark.core.geometry import BoundingBox, VisualElement
from scholarmark.core.caption_matcher import (
    match_figures_to_captions,
    merge_composite_subfigures,
    match_tables_to_captions,
)


class TestCaptionMatcher1N(unittest.TestCase):

    def test_1_to_n_multipanel_caption_assignment(self):
        """
        Verifica que tres subpaneles (a), (b), (c) dispuestos en fila encima de una leyenda
        multipanel 'Fig. 1: (a) Raw RGB, (b) 2D Pose, (c) 3D Mesh' se asocien TODOS a Fig. 1,
        sin que ninguno robe la leyenda distante 'Fig. 2: Latency comparison' en otra región.
        """
        panel_a = VisualElement(
            bbox=BoundingBox(50.0, 80.0, 180.0, 180.0),
            page_num=1,
            subpanel_labels=["(a)"],
        )
        panel_b = VisualElement(
            bbox=BoundingBox(200.0, 80.0, 330.0, 180.0),
            page_num=1,
            subpanel_labels=["(b)"],
        )
        panel_c = VisualElement(
            bbox=BoundingBox(350.0, 80.0, 480.0, 180.0),
            page_num=1,
            subpanel_labels=["(c)"],
        )
        fig2 = VisualElement(
            bbox=BoundingBox(350.0, 420.0, 520.0, 540.0),
            page_num=1,
        )

        cap1_text = "Fig. 1: Overview of stages: (a) Raw RGB, (b) 2D Pose, and (c) 3D Mesh reconstruction."
        cap2_text = "Fig. 2: Latency comparison across edge GPUs."
        captions = [
            (BoundingBox(50.0, 190.0, 480.0, 215.0), cap1_text),
            (BoundingBox(350.0, 550.0, 520.0, 570.0), cap2_text),
        ]

        figures = [panel_a, panel_b, panel_c, fig2]
        match_figures_to_captions(figures, captions, page_width=600.0)

        self.assertEqual(panel_a.caption_text, cap1_text)
        self.assertEqual(panel_b.caption_text, cap1_text)
        self.assertEqual(panel_c.caption_text, cap1_text)
        self.assertEqual(fig2.caption_text, cap2_text)
        self.assertIsNotNone(panel_a.composite_group_id)
        self.assertEqual(panel_a.composite_group_id, panel_b.composite_group_id)
        self.assertEqual(panel_b.composite_group_id, panel_c.composite_group_id)

        # Consolidar los 3 subpaneles en una figura compuesta
        consolidated = merge_composite_subfigures(figures)
        self.assertEqual(len(consolidated), 2)
        comp = consolidated[0]
        self.assertEqual(comp.bbox.x0, 50.0)
        self.assertEqual(comp.bbox.x1, 480.0)
        self.assertEqual(comp.caption_text, cap1_text)

    def test_intervening_prose_blocks_prevent_false_caption_stealing(self):
        """
        Verifica que una figura sin leyenda propia separada por un bloque grande de prosa
        de una leyenda muy inferior no robe esa leyenda.
        """
        orphan_fig = VisualElement(bbox=BoundingBox(50.0, 60.0, 250.0, 150.0), page_num=1)
        prose_obstacle = BoundingBox(50.0, 180.0, 250.0, 460.0)
        unrelated_cap = (BoundingBox(50.0, 520.0, 250.0, 545.0), "Fig. 4: Unrelated bottom diagram.")

        match_figures_to_captions(
            [orphan_fig],
            [unrelated_cap],
            page_width=600.0,
            prose_blocks=[prose_obstacle],
        )
        self.assertIsNone(orphan_fig.caption_text)

    def test_table_caption_matching_above_table(self):
        """
        Verifica que las leyendas 'Table I: ...' situadas encima de la tabla se asocien con precisión.
        """
        tab1 = VisualElement(bbox=BoundingBox(60.0, 140.0, 540.0, 280.0), category="Table", page_num=2)
        cap_above = (BoundingBox(60.0, 110.0, 540.0, 132.0), "TABLE I: Quantitative MPJPE (mm) on Human3.6M")

        match_tables_to_captions([tab1], [cap_above], page_width=600.0)
        self.assertEqual(tab1.caption_text, "TABLE I: Quantitative MPJPE (mm) on Human3.6M")


if __name__ == "__main__":
    unittest.main()
