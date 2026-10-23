"""
Comprehensive Unit Tests for ScholarMark v4.1 Multi-Column Layout & DAG Reading Order.
Validates:
- 1-column, 2-column (symmetric & asymmetric), and 3-column gutter detection.
- Topological DAG reading order across columns and horizontal synchronization cuts.
- Anti-weaving guarantee in native vector span mapping.
"""

import unittest
from typing import List
import fitz

from scholarmark.core.geometry import (
    BoundingBox,
    detect_column_zones,
    detect_column_gutters,
    column_id_for_bbox,
    split_bbox_by_gutters,
)
from scholarmark.ir.document import Block
from scholarmark.layout.detector import LayoutRegion
from scholarmark.layout.reading_order import order_page_blocks, _find_band_gutters, _order_band_blocks
from scholarmark.layout.span_mapper import map_spans_to_blocks


class TestMultiColumnReadingOrder(unittest.TestCase):

    def test_gutter_detection_symmetric_two_column(self):
        """Verifica detección de medianera única en maquetación estándar de dos columnas (IEEE/ACM)."""
        lines: List[BoundingBox] = []
        for y in range(100, 700, 15):
            lines.append(BoundingBox(50.0, float(y), 280.0, float(y + 10)))
            lines.append(BoundingBox(320.0, float(y), 550.0, float(y + 10)))

        zones = detect_column_zones(lines, page_width=600.0, page_height=800.0)
        self.assertEqual(len(zones), 1)
        g0, g1, zy0, zy1 = zones[0]
        self.assertAlmostEqual(g0, 280.0, delta=2.0)
        self.assertAlmostEqual(g1, 320.0, delta=2.0)
        self.assertLessEqual(zy0, 110.0)
        self.assertGreaterEqual(zy1, 690.0)

    def test_gutter_detection_three_column(self):
        """Verifica detección de dos medianeras en maquetación de tres columnas."""
        lines: List[BoundingBox] = []
        for y in range(120, 680, 14):
            lines.append(BoundingBox(40.0, float(y), 190.0, float(y + 9)))
            lines.append(BoundingBox(215.0, float(y), 365.0, float(y + 9)))
            lines.append(BoundingBox(390.0, float(y), 540.0, float(y + 9)))

        zones = detect_column_zones(lines, page_width=595.0, page_height=842.0)
        self.assertEqual(len(zones), 2)
        # Primera medianera entre col 0 y col 1 (~190 a ~215)
        self.assertAlmostEqual(zones[0][0], 190.0, delta=3.0)
        self.assertAlmostEqual(zones[0][1], 215.0, delta=3.0)
        # Segunda medianera entre col 1 y col 2 (~365 a ~390)
        self.assertAlmostEqual(zones[1][0], 365.0, delta=3.0)
        self.assertAlmostEqual(zones[1][1], 390.0, delta=3.0)

    def test_gutter_detection_asymmetric_sidebar(self):
        """Verifica detección de medianera asimétrica (barra lateral estilo PLOS ONE)."""
        lines: List[BoundingBox] = []
        for y in range(150, 650, 16):
            lines.append(BoundingBox(45.0, float(y), 160.0, float(y + 10)))  # Barra lateral estrecha
            lines.append(BoundingBox(185.0, float(y), 560.0, float(y + 10)))  # Cuerpo principal ancho

        zones = detect_column_zones(lines, page_width=595.0, page_height=842.0)
        self.assertEqual(len(zones), 1)
        g0, g1, _, _ = zones[0]
        self.assertAlmostEqual(g0, 160.0, delta=3.0)
        self.assertAlmostEqual(g1, 185.0, delta=3.0)

    def test_column_id_classification(self):
        """Verifica la asignación correcta de cajas a su columna correspondiente."""
        zones = [(280.0, 315.0, 100.0, 700.0)]
        left_box = BoundingBox(50.0, 200.0, 275.0, 250.0)
        right_box = BoundingBox(320.0, 200.0, 545.0, 250.0)
        spanning_box = BoundingBox(50.0, 200.0, 545.0, 250.0)
        outside_box = BoundingBox(50.0, 40.0, 275.0, 70.0)

        self.assertEqual(column_id_for_bbox(left_box, zones), 0)
        self.assertEqual(column_id_for_bbox(right_box, zones), 1)
        self.assertEqual(column_id_for_bbox(spanning_box, zones), -1)
        self.assertEqual(column_id_for_bbox(outside_box, zones), -1)

    def test_split_bbox_by_gutters(self):
        """Verifica que split_bbox_by_gutters divide una caja amplia en subcajas por columna."""
        gutters = [(280.0, 315.0)]
        wide_box = BoundingBox(50.0, 150.0, 550.0, 220.0)
        sub_boxes = split_bbox_by_gutters(wide_box, gutters)
        self.assertEqual(len(sub_boxes), 2)
        self.assertEqual(sub_boxes[0], BoundingBox(50.0, 150.0, 280.0, 220.0))
        self.assertEqual(sub_boxes[1], BoundingBox(315.0, 150.0, 550.0, 220.0))

    def test_three_column_reading_order_topological(self):
        """Verifica que en 3 columnas la lectura procede Col 0 -> Col 1 -> Col 2 íntegramente."""
        blocks = [
            Block(id="c2_top", kind="text", bbox=BoundingBox(390, 100, 550, 200), page=1, text="Col 2 Top"),
            Block(id="c0_bot", kind="text", bbox=BoundingBox(40, 220, 200, 350), page=1, text="Col 0 Bot"),
            Block(id="c1_top", kind="text", bbox=BoundingBox(215, 100, 375, 200), page=1, text="Col 1 Top"),
            Block(id="c0_top", kind="text", bbox=BoundingBox(40, 100, 200, 200), page=1, text="Col 0 Top"),
            Block(id="c2_bot", kind="text", bbox=BoundingBox(390, 220, 550, 350), page=1, text="Col 2 Bot"),
            Block(id="c1_bot", kind="text", bbox=BoundingBox(215, 220, 375, 350), page=1, text="Col 1 Bot"),
        ]
        ordered = order_page_blocks(blocks, page_width=595.0)
        ordered_ids = [b.id for b in ordered]
        self.assertEqual(
            ordered_ids,
            ["c0_top", "c0_bot", "c1_top", "c1_bot", "c2_top", "c2_bot"],
        )

    def test_spanning_figure_xycut_barrier(self):
        """
        Verifica que una figura que cruza la medianera actúa como barrera de sincronización:
        Banda Superior (Col 0 -> Col 1) -> Figura Spanning -> Banda Inferior (Col 0 -> Col 1).
        """
        blocks = [
            Block(id="title", kind="title", bbox=BoundingBox(45, 40, 550, 75), page=1, text="Research Title"),
            Block(id="top_r", kind="text", bbox=BoundingBox(315, 90, 550, 180), page=1, text="Top right"),
            Block(id="top_l", kind="text", bbox=BoundingBox(45, 90, 280, 180), page=1, text="Top left"),
            # Figura de ancho completo cruzando la medianera central
            Block(id="fig_span", kind="figure", bbox=BoundingBox(45, 200, 550, 380), page=1, text=""),
            Block(id="bot_r", kind="text", bbox=BoundingBox(315, 400, 550, 520), page=1, text="Bottom right"),
            Block(id="bot_l", kind="text", bbox=BoundingBox(45, 400, 280, 520), page=1, text="Bottom left"),
        ]
        ordered = order_page_blocks(blocks, page_width=595.0)
        ordered_ids = [b.id for b in ordered]
        self.assertEqual(
            ordered_ids,
            ["title", "top_l", "top_r", "fig_span", "bot_l", "bot_r"],
        )

    def test_anti_weaving_span_mapper(self):
        """
        Verifica que map_spans_to_blocks no entreteje líneas de columnas opuestas
        incluso si existen a la misma altura visual 'y'.
        """
        doc = fitz.open()
        pg = doc.new_page(width=595, height=842)
        # Líneas en Columna 0
        pg.insert_text(fitz.Point(50, 120), "Left line one alpha beta", fontsize=10)
        pg.insert_text(fitz.Point(50, 140), "Left line two gamma delta", fontsize=10)
        # Líneas en Columna 1 a idéntica cota Y
        pg.insert_text(fitz.Point(320, 120), "Right line one epsilon zeta", fontsize=10)
        pg.insert_text(fitz.Point(320, 140), "Right line two eta theta", fontsize=10)

        # Región 1 en Columna 0, Región 2 en Columna 1
        reg_left = LayoutRegion(kind="text", bbox=BoundingBox(45, 105, 280, 160), confidence=0.95)
        reg_right = LayoutRegion(kind="text", bbox=BoundingBox(315, 105, 555, 160), confidence=0.95)

        blocks = map_spans_to_blocks(pg, page_num=1, regions=[reg_left, reg_right], rescue_orphans=False)
        doc.close()

        self.assertEqual(len(blocks), 2)
        left_text = blocks[0].text
        right_text = blocks[1].text

        self.assertIn("Left line one", left_text)
        self.assertIn("Left line two", left_text)
        self.assertNotIn("Right", left_text)

        self.assertIn("Right line one", right_text)
        self.assertIn("Right line two", right_text)
        self.assertNotIn("Left", right_text)


if __name__ == "__main__":
    unittest.main()
