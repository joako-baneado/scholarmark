"""
Unit tests for ScholarMark math transformation module.
"""

import unittest
from scholarmark.core.math_parser import (
    clean_math_glyphs,
    format_inline_expressions,
    isolate_equations,
    parse_math
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

if __name__ == "__main__":
    unittest.main()
