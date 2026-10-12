"""
Unit tests for ScholarMark math transformation module.
"""

import unittest
from scholarmark.core.math_parser import (
    clean_math_glyphs,
    format_inline_expressions,
    isolate_equations,
    parse_math,
    sanitize_numeric_typography
)

class TestMathParser(unittest.TestCase):

    def test_greek_letters_conversion(self):
        raw = "The angles are _\U0001d6fc_ and _\U0001d6fd_."
        res = parse_math(raw)
        self.assertIn(r"$\alpha$", res)
        self.assertIn(r"$\beta$", res)

    def test_degree_symbol_conversion(self):
        raw = "The pitch was 90<sup>_\u2218_</sup> and roll 45^\\circ."
        res = parse_math(raw)
        self.assertIn(r"$90^\circ$", res)
        self.assertIn(r"$45^\circ$", res)

    def test_block_equation_isolation(self):
        raw = "Velocity is computed as:\nVt = Pt+1 - Pt (2)\nwhere Pt is position."
        res = parse_math(raw)
        self.assertIn("$$\nVt = Pt+1 - Pt \\tag{2}\n$$", res)

    def test_clean_math_glyphs(self):
        raw = "\U0001d449 \U0001d443"
        res = clean_math_glyphs(raw)
        self.assertIn("V", res)
        self.assertIn("P", res)

    def test_decimal_fracture_with_spaces(self):
        """Test: '5 _._ 77 m/s' debe convertirse a '5.77 m/s'."""
        raw = "the minimum velocity is _v_ = 5 _._ 77 m\u2215s."
        res = sanitize_numeric_typography(raw)
        self.assertIn("5.77", res)
        self.assertIn("m/s", res)
        self.assertNotIn("_._", res)

    def test_decimal_fracture_compact(self):
        """Test: '14_._4 ms' → '14.4 ms'."""
        raw = "computation time of 14_._4 ms"
        res = sanitize_numeric_typography(raw)
        self.assertIn("14.4", res)
        self.assertNotIn("_._", res)

    def test_decimal_fracture_various(self):
        """Test múltiples patrones de fractura decimal."""
        raw = "values 0 _._ 5 mm and 1 _._ 0 mm, time 1 _._ 2 ms"
        res = sanitize_numeric_typography(raw)
        self.assertIn("0.5", res)
        self.assertIn("1.0", res)
        self.assertIn("1.2", res)
        self.assertNotIn("_._", res)

    def test_unicode_division_slash(self):
        """Test: ∕ (U+2215) → /."""
        raw = "velocity 5.77 m\u2215s"
        res = sanitize_numeric_typography(raw)
        self.assertIn("m/s", res)

    def test_unicode_minus_sign(self):
        """Test: − (U+2212) → -."""
        raw = "temperature \u221220\u00b0C"
        res = sanitize_numeric_typography(raw)
        self.assertIn("-20", res)

    def test_pipeline_handles_fractures(self):
        """Test: el pipeline completo parse_math() procesa fracturas correctamente."""
        raw = "5 _._ 77 m\u2215s and 14 _._ 4 ms"
        res = parse_math(raw)
        self.assertIn("5.77", res)
        self.assertIn("14.4", res)
        self.assertIn("m/s", res)
        self.assertNotIn("_._", res)

if __name__ == "__main__":
    unittest.main()
