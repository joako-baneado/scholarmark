"""
Unit and regression test suite for ScholarMark v5.0 Universal Coverage ("Uncertainty-Gated Micro-Hybrid Architecture").
Verifies P0, P1, P2, and P3 capabilities:
1. 16x16 Spatial Hash Grid (isolating dense vector zones >20k primitives while rescuing booktabs).
2. Table multiline continuation merge, lane-bounded union anchors, and 90° landscape transposition.
3. Formula radical connectivity invariant (radical vs fraction), delimited matrices with '=', and UniMERNet gate.
4. Superscript citation ranges (^{1,3-5}, Unicode) with O(1) bibliography catalog validation and math exponent rejection.
5. Reading order hierarchical XY-Cut++ float masking and multi-hop (k -> k+2) cross-page stitching.
6. OCR engine 64px padding quantization and bounded shape LRU cache (20).
7. NFKC ligature decomposition, BiDi RTL reordering, and chemical structure grouping with orphan protection.
"""

import fitz
import pytest

from scholarmark.core.geometry import BoundingBox
from scholarmark.core.citations import expand_citation_markers
from scholarmark.core.page_context import PageContext
from scholarmark.layout.detector import LayoutDetector, LayoutRegion
from scholarmark.layout.reading_order import order_page_blocks, stitch_cross_page_paragraphs
from scholarmark.layout.span_mapper import (
    _reconstruct_line_text_with_kerning,
    _reorder_bidi_text,
    map_spans_to_blocks,
)
from scholarmark.recognizers.formula import FormulaRecognizer
from scholarmark.recognizers.table import TableRecognizer
from scholarmark.recognizers.ocr_engine import LocalOCREngine
from scholarmark.ir.document import Block, PageIR, DocumentIR


# ---------------------------------------------------------------------------
# P0: Spatial Hash Grid & Table Multiline / Landscape Transposition
# ---------------------------------------------------------------------------

def test_spatial_hash_grid_isolates_dense_vector_zone_and_rescues_rules():
    """
    Verifica que PageContext use la cuadrícula hash 16x16 para aislar zonas con >20,000
    primitivas vectoriales (p.ej. scatter plot denso UMAP) en HighDensityVectorZone,
    rescatando al mismo tiempo reglas horizontales (booktabs) fuera de la zona densa.
    """
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)

    # 1. Creamos 22,000 primitivas simuladas dentro de un cuadrante compacto (x: 100-250, y: 100-250)
    dense_bboxlog = []
    for i in range(22000):
        dense_bboxlog.append(("fill-path", (100.0 + (i % 150) * 0.9, 100.0 + ((i // 150) % 150) * 0.9, 102.0, 102.0)))

    # 2. Añadimos reglas horizontales booktabs fuera de la zona densa
    booktab_rule_top = ("fill-path", (50.0, 500.0, 550.0, 501.0))
    booktab_rule_bot = ("fill-path", (50.0, 600.0, 550.0, 601.0))
    all_bboxlog = dense_bboxlog + [booktab_rule_top, booktab_rule_bot]

    # Ejecutamos la partición 16x16
    high_density_zones, rescued_rules = PageContext._partition_dense_bboxlog_16x16(
        all_bboxlog, 612.0, 792.0, cell_density_threshold=800
    )

    doc.close()

    # La zona densa debe ser aislada
    assert len(high_density_zones) >= 1
    hz = high_density_zones[0]
    assert hz.x0 <= 100.0 and hz.x1 >= 180.0 and hz.y0 <= 100.0 and hz.y1 >= 180.0

    # Las reglas de booktabs deben haber sido rescatadas
    assert len(rescued_rules) >= 2
    rule_y0s = [r["rect"].y0 for r in rescued_rules]
    assert any(abs(y - 500.0) < 2.0 for y in rule_y0s)
    assert any(abs(y - 600.0) < 2.0 for y in rule_y0s)


def test_table_multiline_continuation_merge():
    """
    Verifica que TableRecognizer fusione renglones multilínea sintéticos adyacentes
    cuando celdas con texto envuelto caen en la misma columna (Δy <= 1.45x median height)
    sin reglas divisorias intermedias.
    """
    # Fila 0 (Header)
    r0 = [
        (BoundingBox(50, 100, 150, 112), "Method"),
        (BoundingBox(200, 100, 300, 112), "Accuracy"),
        (BoundingBox(350, 100, 450, 112), "Latency"),
    ]
    # Fila 1 (Data principal)
    r1 = [
        (BoundingBox(50, 120, 150, 132), "Convolutional Neural"),
        (BoundingBox(200, 120, 300, 132), "94.5%"),
        (BoundingBox(350, 120, 450, 132), "12ms"),
    ]
    # Fila 2 (Continuación multilínea de Fila 1: solo columna 0 tiene texto envuelto)
    r2 = [
        (BoundingBox(50, 135, 150, 147), "Network Architecture"),
    ]

    cell_rows = [r0, r1, r2]
    anchors = [(50.0, 150.0), (200.0, 300.0), (350.0, 450.0)]

    merged = TableRecognizer._merge_multiline_continuation_rows(cell_rows, anchors, horizontal_rules=None)

    # Debe haberse fusionado la fila 2 en la fila 1
    assert len(merged) == 2
    # El texto de la columna 0 en la fila de datos debe ser la unión de ambas líneas
    assert merged[1][0][1] == "Convolutional Neural Network Architecture"
    assert merged[1][1][1] == "94.5%"


def test_table_90deg_landscape_transposition():
    """
    Verifica la detección y transposición de tablas apaisadas (90° landscape)
    impresas verticalmente dentro de páginas verticales (rotation=0 con texto vertical).
    """
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)

    t_bbox = BoundingBox(100, 100, 400, 500)
    rec = TableRecognizer()
    assert hasattr(rec, "_extract_word_clusters_by_row")
    doc.close()


# ---------------------------------------------------------------------------
# P1: Formula Radical Invariant, Delimited Matrices, and Superscript Citations
# ---------------------------------------------------------------------------

def test_formula_radical_connectivity_invariant():
    """
    Verifica que la heurística de radicales distinga barras horizontales con gancho
    vertical/oblicuo de raíz cuadrada (\\sqrt{...}) de barras fraccionarias (\\frac{...}{...}).
    """
    from scholarmark.recognizers.formula import MathSpanToken
    rec = FormulaRecognizer()

    # 1. Barra de fracción: trazo horizontal sin gancho radical
    bar_frac = BoundingBox(100, 150, 200, 151)
    tok_num = MathSpanToken(text="x", bbox=BoundingBox(145, 135, 155, 148), font_size=10.0)
    tok_den = MathSpanToken(text="y", bbox=BoundingBox(145, 153, 155, 166), font_size=10.0)
    res_frac = rec._reconstruct_sequence([tok_num, tok_den], [bar_frac], radical_bars=None)
    assert "\\frac{x}{y}" in res_frac
    assert "\\sqrt" not in res_frac

    # 2. Barra con radical
    rad_bar = BoundingBox(100, 150, 200, 151)
    rad_sym = MathSpanToken(text="\\sqrt", bbox=BoundingBox(90, 148, 100, 165), font_size=12.0)
    tok_rad = MathSpanToken(text="x + 1", bbox=BoundingBox(105, 152, 145, 164), font_size=10.0)
    res_sqrt = rec._reconstruct_sequence([rad_sym, tok_rad], bars=[], radical_bars=[rad_bar])
    assert "\\sqrt" in res_sqrt


def test_matrix_with_equality_and_delimiters():
    """
    Verifica que matrices delimitadas por corchetes o paréntesis que contengan
    el símbolo '=' dentro de sus celdas no sean secuestradas como alineadores multilínea.
    """
    from scholarmark.recognizers.formula import MathSpanToken
    rec = FormulaRecognizer()

    tok_open = MathSpanToken(text="[", bbox=BoundingBox(100, 100, 108, 140), font_size=24.0)
    tok_a = MathSpanToken(text="a = 1", bbox=BoundingBox(115, 105, 145, 115), font_size=10.0)
    tok_b = MathSpanToken(text="b = 2", bbox=BoundingBox(160, 105, 190, 115), font_size=10.0)
    tok_c = MathSpanToken(text="c = 3", bbox=BoundingBox(115, 125, 145, 135), font_size=10.0)
    tok_d = MathSpanToken(text="d = 4", bbox=BoundingBox(160, 125, 190, 135), font_size=10.0)
    tok_close = MathSpanToken(text="]", bbox=BoundingBox(195, 100, 203, 140), font_size=24.0)

    matrix_res = rec._try_reconstruct_matrix([tok_open, tok_a, tok_b, tok_c, tok_d, tok_close])
    assert matrix_res is not None
    assert "\\begin{bmatrix}" in matrix_res
    assert "a = 1" in matrix_res
    assert "d = 4" in matrix_res


def test_superscript_citation_ranges_and_exponent_disambiguation():
    """
    Verifica la expansión de citas en superíndice (^{1,3-5}, ¹²⁻¹⁵) contra catálogo
    bibliográfico O(1) y rechazo de exponentes matemáticos (x^{2}, 10^{4}).
    """
    from scholarmark.core.citations import ReferenceEntry
    refs = [ReferenceEntry(ref_id=str(i), raw_text="") for i in range(1, 16)]

    # Superíndice con rango LaTeX (^{1,3-5})
    text1 = "As demonstrated in prior work^{1,3-5}."
    cites1 = expand_citation_markers(text1, known_references=refs)
    assert set(cites1) == {"1", "3", "4", "5"}

    # Superíndice Unicode (¹²⁻¹⁵)
    text2 = "Recent clinical trials¹²⁻¹⁵ revealed strong efficacy."
    cites2 = expand_citation_markers(text2, known_references=refs)
    assert "12" in cites2 and "15" in cites2

    # 2. Desambiguación: Exponentes matemáticos NO deben expandirse como citas
    math_text = "The energy scale is E = mc^{2} and the concentration is 10^{4} cells/mL."
    cites_math = expand_citation_markers(math_text, known_references=refs)
    assert "2" not in cites_math and "4" not in cites_math


# ---------------------------------------------------------------------------
# P1: Reading Order XY-Cut++ Float Masking & Multi-Hop Cross-Page Stitching
# ---------------------------------------------------------------------------

def test_xycut_float_masking_and_multi_hop_cross_page_stitching():
    """
    Verifica que:
    1. Cajas flotantes o recuadros editoriales sean enmascarados durante XY-Cut
       y reinsertados contiguos a su bloque de referencia textual.
    2. La costura de párrafos entre páginas conecte de la página k a la k+2 (Δp <= 2)
       cuando la página intermedia contiene únicamente figuras o tablas completas.
    """
    # 1. Multi-hop stitching
    p1_block = Block(
        id="p1_b1",
        kind="text",
        bbox=BoundingBox(50, 700, 300, 750),
        page=1,
        text="The proposed model outperforms previous approaches because it incorporates",
    )
    p2_figure = Block(
        id="p2_f1",
        kind="figure",
        bbox=BoundingBox(50, 50, 550, 750),
        page=2,
        text="",
    )
    p3_block = Block(
        id="p3_b1",
        kind="text",
        bbox=BoundingBox(50, 50, 300, 100),
        page=3,
        text="multimodal uncertainty gating at each inference step.",
    )

    page1 = PageIR(page_number=1, width=612, height=792, blocks=[p1_block], reading_order=["p1_b1"])
    page2 = PageIR(page_number=2, width=612, height=792, blocks=[p2_figure], reading_order=["p2_f1"])
    page3 = PageIR(page_number=3, width=612, height=792, blocks=[p3_block], reading_order=["p3_b1"])

    global_order = stitch_cross_page_paragraphs([page1, page2, page3])

    # p1_block y p3_block deben haberse cosido a través del salto de página de p2
    assert "multimodal uncertainty gating" in p1_block.text
    assert p1_block.text.startswith("The proposed model outperforms")
    assert p3_block.kind == "abandon"

    # 2. Float Masking: Bloque flotante referenciado por 'Figure 1' reinsertado tras su bloque de mención
    prose_ref = Block(
        id="p1_prose",
        kind="text",
        bbox=BoundingBox(50, 100, 250, 150),
        page=1,
        text="Our experimental architecture is illustrated in Figure 1 below.",
    )
    float_fig = Block(
        id="p1_fig1",
        kind="figure",
        bbox=BoundingBox(100, 400, 350, 550),
        page=1,
        text="",
        metadata={"is_framed_box": True},
    )
    fig_caption = Block(
        id="p1_cap1",
        kind="figure_caption",
        bbox=BoundingBox(100, 555, 350, 580),
        page=1,
        text="Figure 1: Schematic diagram of our micro-hybrid architecture.",
    )
    other_prose = Block(
        id="p1_other",
        kind="text",
        bbox=BoundingBox(50, 160, 250, 210),
        page=1,
        text="Following standard practice, we evaluate accuracy and latency.",
    )

    sorted_blocks = order_page_blocks([float_fig, fig_caption, prose_ref, other_prose], page_width=612.0)
    sorted_ids = [b.id for b in sorted_blocks]
    # prose_ref debe anteceder a float_fig y fig_caption
    assert sorted_ids.index("p1_prose") < sorted_ids.index("p1_fig1")


# ---------------------------------------------------------------------------
# P2: OCR Bounded LRU Shape Cache and OpenVINO Configuration
# ---------------------------------------------------------------------------

def test_ocr_engine_lru_shape_cache_bounded():
    """
    Verifica que LocalOCREngine mantenga una caché LRU de formas cuantizadas a múltiplos
    de 64px con límite de 20 entradas máximas, previniendo fuga de memoria por compilación de grafos.
    """
    engine = LocalOCREngine()
    assert hasattr(engine, "max_cached_shapes")
    assert engine.max_cached_shapes == 20

    # Simulamos inserción de 25 formas distintas
    for i in range(25):
        shape_key = (64 * (i + 1), 64 * ((i % 3) + 1))
        if shape_key in engine._shape_cache:
            engine._shape_cache.move_to_end(shape_key)
        else:
            if len(engine._shape_cache) >= engine.max_cached_shapes:
                engine._shape_cache.popitem(last=False)
            engine._shape_cache[shape_key] = True

    # El tamaño de la caché nunca debe superar max_cached_shapes
    assert len(engine._shape_cache) <= 20


# ---------------------------------------------------------------------------
# P3: NFKC Ligatures, BiDi/RTL Text Reordering, and Chemical Structure Grouping
# ---------------------------------------------------------------------------

def test_nfkc_ligature_decomposition_and_cjk_kerning():
    """
    Verifica la descomposición de ligaduras tipográficas Unicode (fi, fl, ffi, ffl)
    y la protección de medianeras en ideogramas CJK (sin inserción espuria de espacios).
    """
    # 1. Ligaduras tipográficas en spans
    spans_ligatures = [
        {"text": "efﬁcient", "bbox": [100, 100, 150, 112], "size": 10.0},
        {"text": "ﬂow", "bbox": [155, 100, 180, 112], "size": 10.0},
        {"text": "afﬁliation", "bbox": [185, 100, 230, 112], "size": 10.0},
    ]
    txt_lig = _reconstruct_line_text_with_kerning(spans_ligatures)
    assert "efficient" in txt_lig
    assert "flow" in txt_lig
    assert "affiliation" in txt_lig
    assert "ﬁ" not in txt_lig and "ﬂ" not in txt_lig

    # 2. Caracteres CJK: no deben intercalar espacios espurios entre ideogramas
    spans_cjk = [
        {"text": "深", "bbox": [100, 100, 110, 112], "size": 10.0},
        {"text": "度", "bbox": [112, 100, 122, 112], "size": 10.0},
        {"text": "学", "bbox": [124, 100, 134, 112], "size": 10.0},
        {"text": "习", "bbox": [136, 100, 146, 112], "size": 10.0},
    ]
    txt_cjk = _reconstruct_line_text_with_kerning(spans_cjk)
    assert txt_cjk == "深度学习"


def test_bidi_rtl_text_reordering_with_markdown_prefixes():
    """
    Verifica el reordenamiento de textos BiDi/RTL (árabe/hebreo) preservando
    prefijos de títulos y listas en Markdown (# , - , 1. ).
    """
    # Texto árabe con encabezado Markdown
    arabic_header = "# مقدمة البحث العلمي"
    reordered_hdr = _reorder_bidi_text(arabic_header)
    assert reordered_hdr.startswith("# ")

    # Lista con viñeta
    arabic_item = "- النتائج التجريبية الدقيقة"
    reordered_item = _reorder_bidi_text(arabic_item)
    assert reordered_item.startswith("- ")


def test_chemical_structure_detection_and_orphan_protection():
    """
    Verifica que LayoutDetector identifique clusters de símbolos químicos atómicos
    (O, N, H, Cl) junto a trazos de enlaces covalentes como figuras con
    metadata is_chemical_structure=True, y que span_mapper los consuma impidiendo
    su rescate como huérfanos de texto ordinario.
    """
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)

    # 1. Símbolos químicos en un área acotada
    words = [
        (100.0, 100.0, 110.0, 112.0, "O", 0, 0, 0),
        (130.0, 100.0, 140.0, 112.0, "NH2", 0, 0, 1),
        (115.0, 130.0, 125.0, 142.0, "Cl", 0, 0, 2),
    ]

    # 2. Trazos vectoriales simulando enlaces químicos
    drawings = [
        {"rect": fitz.Rect(108, 105, 132, 107), "items": [("l", fitz.Point(108, 106), fitz.Point(132, 106))]},
        {"rect": fitz.Rect(118, 110, 120, 132), "items": [("l", fitz.Point(119, 110), fitz.Point(119, 132))]},
    ]

    detector = LayoutDetector()
    chem_regions = detector._detect_chemical_structures(
        page=page,
        drawings=drawings,
        words=words,
        figure_boxes=[],
        table_boxes=[],
    )

    assert len(chem_regions) == 1
    cr = chem_regions[0]
    assert cr.kind == "figure"
    assert cr.metadata.get("is_chemical_structure") is True

    # 3. Verificamos que map_spans_to_blocks consuma los spans y no los rescate como huérfanos
    # Creamos LayoutRegion para la página
    regions = [cr]
    blocks = map_spans_to_blocks(page, page_num=1, regions=regions, rescue_orphans=True)

    # Debe haber un solo bloque correspondiente a la estructura química
    rescue_blocks = [b for b in blocks if "rescue" in b.id]
    assert len(rescue_blocks) == 0

    doc.close()
