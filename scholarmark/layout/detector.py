"""
Visual & Multimodal Document Layout Detector for ScholarMark v3.0.
Classifies page regions into structural classes:
title, section_header, text, list, footnote, abandon, formula, table, table_caption,
figure, figure_caption, and author_bio.
Supports custom ONNX layout models (DocLayout-YOLO / PP-DocLayout) and a zero-download
multimodal geometric+typographic layout analyzer.
"""

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import List, Optional, Tuple, Dict, Any
import fitz
import numpy as np

from ..core.caption_matcher import (
    CAPTION_REGEX,
    TABLE_CAPTION_REGEX,
    SUBPANEL_TAG_REGEX,
)
from ..core.geometry import (
    BoundingBox,
    cluster_vector_drawings,
    expand_figure_bbox,
)
from ..models.registry import resolve_ort_providers
from ..recognizers.algorithm import AlgorithmRecognizer, ALGORITHM_HEADER_RE


_HEADING_PREFIX_RE = re.compile(
    r"^(?:[1-9]|1[0-5]|[I]{1,3}|IV|V|VI{0,3}|IX|X)(?:\.\d+)*\.?\s+[A-ZÁÉÍÓÚÑ]",
)
_CANONICAL_SECTION_RE = re.compile(
    r"^(?:ABSTRACT|RESUMEN|INTRODUCTION|INTRODUCCIÓN|RELATED\s+WORK|BACKGROUND|"
    r"METHODOLOGY|METHODS|PROPOSED\s+METHOD|EXPERIMENTS(?:\s+AND\s+RESULTS)?|"
    r"RESULTS(?:\s+AND\s+DISCUSSION)?|DISCUSSION|CONCLUSION|CONCLUSIONS|"
    r"ACKNOWLEDGMENTS|ACKNOWLEDGEMENTS|REFERENCES|BIBLIOGRAPHY|REFERENCIAS)\b",
    re.IGNORECASE,
)
_FOOTNOTE_START_RE = re.compile(
    r"^(?:[\*†‡§¶]|\d{1,2}[\.\)]?\s+[A-ZÁÉÍÓÚÑa-z]|https?://|Manuscript\s+received|This\s+work\s+was\s+supported|Corresponding\s+author)",
)
_FORMULA_TAG_END_RE = re.compile(r"\((\d+[a-zA-Z]?)\)\s*$")
_BIO_CUE_RE = re.compile(
    r"\b(?:received\s+the\s+(?:B\.S\.|M\.S\.|Ph\.D\.|B\.E\.|M\.E\.|B\.Sc\.|M\.Sc\.|B\.Tech|M\.Tech|bachelor|master|doctor)|is\s+currently\s+(?:a|an|pursuing\s+the)\s+(?:Professor|Associate\s+Professor|Assistant\s+Professor|Researcher|Ph\.D\.)|His\s+research\s+interests|Her\s+(?:current\s+)?research\s+interests|Member,\s+IEEE|Fellow,\s+IEEE)\b",
    re.IGNORECASE,
)


@dataclass
class LayoutRegion:
    """Región estructural detectada en una página."""
    kind: str
    bbox: BoundingBox
    confidence: float = 1.0
    source: str = "native"
    heading_level: int = 2
    metadata: Dict[str, Any] = field(default_factory=dict)


class LayoutDetector:
    """
    Detector de maquetación híbrido de ScholarMark v3.0.
    Si se proporciona un archivo ONNX válido, ejecuta inferencia con ONNX Runtime;
    además fusiona y refina con introspección tipográfica y geométrica de la página.
    """

    def __init__(self, device: str = "auto", onnx_model_path: Optional[str] = None):
        self.device = device
        self.onnx_model_path = onnx_model_path
        self.providers, self.provider_label = resolve_ort_providers(device)
        self._session = None
        if onnx_model_path and Path(onnx_model_path).exists():
            try:
                import onnxruntime as ort
                self._session = ort.InferenceSession(str(onnx_model_path), providers=self.providers)
            except Exception:
                self._session = None

    @staticmethod
    def _estimate_body_font_size(raw_dict: Dict[str, Any]) -> float:
        """Calcula la mediana ponderada por longitud de caracteres del tamaño de fuente del cuerpo."""
        sizes: List[float] = []
        for b in raw_dict.get("blocks", []):
            if b.get("type") != 0:
                continue
            for line in b.get("lines", []):
                for span in line.get("spans", []):
                    txt = span.get("text", "").strip()
                    sz = float(span.get("size", 10.0))
                    if txt and sz > 4.0:
                        sizes.extend([sz] * max(1, min(20, len(txt))))
        if not sizes:
            return 10.0
        return float(np.median(sizes))

    @staticmethod
    def _detect_horizontal_rules(drawings: List[Dict[str, Any]], page_w: float) -> List[BoundingBox]:
        """Detecta líneas horizontales finas (separadores de notas al pie y bordes de tablas booktabs)."""
        rules: List[BoundingBox] = []
        for d in drawings:
            r = d.get("rect")
            if r is None:
                continue
            if r.height <= 3.0 and r.width >= 35.0:
                rules.append(BoundingBox.from_fitz_rect(r))
        return rules

    @staticmethod
    def _detect_small_portrait_images(page: fitz.Page) -> List[BoundingBox]:
        """Detecta fotografías pequeñas de autores en los márgenes (típicas de biografías IEEE)."""
        portraits: List[BoundingBox] = []
        page_area = max(1.0, page.rect.width * page.rect.height)
        try:
            for img in page.get_images():
                xref = img[0]
                for r in page.get_image_rects(xref):
                    area_ratio = (r.width * r.height) / page_area
                    aspect = r.height / max(1.0, r.width)
                    if 0.005 <= area_ratio <= 0.08 and 0.8 <= aspect <= 1.8:
                        portraits.append(BoundingBox.from_fitz_rect(r))
        except Exception:
            pass
        return portraits

    @staticmethod
    def _is_math_heavy_block(text: str, spans: List[Dict[str, Any]]) -> Tuple[bool, Optional[str]]:
        """Determina si un bloque aislado corresponde a una ecuación matemática."""
        stripped = " ".join(text.split()).strip()
        if not stripped or len(stripped) > 320:
            return False, None

        tag_m = _FORMULA_TAG_END_RE.search(stripped)
        tag = tag_m.group(1) if tag_m else None

        math_chars = sum(1 for c in stripped if c in "=+-*/^_<>∑∫∏√∂∇≈≠≤≥∈∉±×÷αβγδεζηθλμπρστφψωΔΘΛΠΣΦΨΩ" or (0x1D400 <= ord(c) <= 0x1D7FF))
        has_math_font = any(
            any(k in (s.get("font", "") or "").lower() for k in ("math", "cmmi", "cmsy", "cmex", "symbol", "msbm"))
            for s in spans
        )
        words = re.findall(r"\b[a-zA-Z]{4,}\b", stripped)

        if tag and (math_chars >= 1 or has_math_font) and len(words) <= 6:
            return True, tag

        if (math_chars >= 3 or (has_math_font and math_chars >= 1)) and len(words) <= 4 and "=" in stripped:
            return True, tag

        return False, None

    @staticmethod
    def _detect_table_regions(
        page: fitz.Page,
        rules: List[BoundingBox],
        table_captions: List[BoundingBox],
        raw_blocks: List[Dict[str, Any]],
        figure_captions: Optional[List[BoundingBox]] = None,
    ) -> List[BoundingBox]:
        """
        Detecta regiones de tablas combinando el buscador de tablas de PyMuPDF
        y heurísticas de líneas horizontales paralelas (LaTeX booktabs) bajo o sobre leyendas de tabla.
        """
        table_boxes: List[BoundingBox] = []
        page_w = float(page.rect.width)
        page_h = float(page.rect.height)
        fig_caps = figure_captions or []

        def _is_above_figure_caption_without_table_caption(box: BoundingBox) -> bool:
            near_fig_cap = any(
                -8.0 <= (fc.y0 - box.y1) <= 50.0 and not (fc.x1 < box.x0 - 25.0 or fc.x0 > box.x1 + 25.0)
                for fc in fig_caps
            )
            near_tab_cap = any(
                abs(box.y0 - tc.y1) <= 50.0 or abs(tc.y0 - box.y1) <= 50.0
                for tc in table_captions
            )
            return near_fig_cap and not near_tab_cap

        # 1. PyMuPDF find_tables nativo si está disponible
        try:
            finder = page.find_tables()
            for tab in getattr(finder, "tables", []):
                tb = BoundingBox(*tab.bbox)
                if tb.area >= 1200.0 and not _is_above_figure_caption_without_table_caption(tb):
                    table_boxes.append(tb)
        except Exception:
            pass

        # 2. Detección de tablas abiertas (booktabs) mediante pares/tríos de líneas horizontales de igual ancho
        wide_rules = [r for r in rules if r.width >= 100.0]
        wide_rules.sort(key=lambda r: r.y0)
        i = 0
        while i < len(wide_rules):
            r_top = wide_rules[i]
            matched_bottom = None
            for j in range(i + 1, len(wide_rules)):
                r_cand = wide_rules[j]
                # Misma banda horizontal X y separación vertical razonable de tabla (25 a 500 pt)
                if (
                    abs(r_cand.x0 - r_top.x0) <= 25.0
                    and abs(r_cand.x1 - r_top.x1) <= 25.0
                    and 24.0 <= (r_cand.y1 - r_top.y0) <= 520.0
                ):
                    matched_bottom = r_cand
            if matched_bottom is not None:
                cand_box = BoundingBox(
                    x0=min(r_top.x0, matched_bottom.x0) - 4.0,
                    y0=r_top.y0 - 2.0,
                    x1=max(r_top.x1, matched_bottom.x1) + 4.0,
                    y1=matched_bottom.y1 + 2.0,
                ).pad(0.0, page.rect)
                if (
                    not _is_above_figure_caption_without_table_caption(cand_box)
                    and not any(cand_box.iou(existing) > 0.4 for existing in table_boxes)
                ):
                    table_boxes.append(cand_box)
                i += 1
            else:
                i += 1

        # 3. Rescate guiado por table_caption cuando una tabla sin bordes está justo debajo del título 'Table X'
        for tc in table_captions:
            has_near_table = any(
                (abs(tb.y0 - tc.y1) < 45.0 or abs(tc.y0 - tb.y1) < 45.0)
                for tb in table_boxes
            )
            if has_near_table:
                continue
            # Buscar bloques alineados con alta densidad numérica inmediatamente debajo de tc
            aligned_blocks: List[BoundingBox] = []
            for b in raw_blocks:
                if b.get("type") != 0:
                    continue
                bb = BoundingBox(*b["bbox"])
                if 0.0 <= (bb.y0 - tc.y1) <= 180.0 and not (bb.x1 < tc.x0 or bb.x0 > tc.x1):
                    txt = "".join(
                        s.get("text", "")
                        for ln in b.get("lines", [])
                        for s in ln.get("spans", [])
                    )
                    digits = sum(1 for c in txt if c.isdigit())
                    if digits >= 4 and len( b.get("lines", []) ) >= 2:
                        aligned_blocks.append(bb)
            if aligned_blocks:
                u = aligned_blocks[0]
                for ab in aligned_blocks[1:]:
                    u = u.union(ab)
                if u.height >= 20.0 and u.width <= page_w and u.height <= page_h:
                    table_boxes.append(u)
            else:
                # 4. Rescate de tablas ráster (imagen incrustada inmediatamente debajo de Table X:)
                try:
                    for img in page.get_images():
                        xref = img[0]
                        for r in page.get_image_rects(xref):
                            ib = BoundingBox.from_fitz_rect(r)
                            if (
                                ib.width >= 60.0
                                and ib.height >= 30.0
                                and -5.0 <= (ib.y0 - tc.y1) <= 45.0
                                and not (ib.x1 < tc.x0 - 20.0 or ib.x0 > tc.x1 + 20.0)
                            ):
                                table_boxes.append(ib)
                except Exception:
                    pass

        return table_boxes

    @staticmethod
    def _is_pseudocode_continuation(text: str) -> bool:
        """Determina si un bloque corto es una línea o continuación de un algoritmo."""
        s = " ".join(text.split()).strip()
        if not s or len(s) > 260:
            return False
        if re.match(
            r"^(?:\[?\d{1,3}\]?[:.)]\s*|Require\s*:|Ensure\s*:|Input\s*:|Output\s*:|"
            r"for\b|parfor\b|while\b|if\b|else\b|elsif\b|elif\b|repeat\b|until\b|"
            r"end(?:\s+(?:for|while|if))?\b|return\b)",
            s,
            re.IGNORECASE,
        ):
            return True
        if ("<-" in s or "←" in s) and len(s.split()) <= 18:
            return True
        return False

    def detect_page(
        self,
        page: fitz.Page,
        page_num: int,
        max_page_primitives: int = 20000,
        max_figure_primitives: int = 2000,
        elastic_min: float = 4.0,
        elastic_max: float = 16.0
    ) -> List[LayoutRegion]:
        """
        Segmenta y clasifica todos los elementos estructurales de la página.
        """
        page_w = float(page.rect.width)
        page_h = float(page.rect.height)
        raw_dict = page.get_text("dict")
        raw_blocks = raw_dict.get("blocks", [])
        body_size = self._estimate_body_font_size(raw_dict)

        try:
            bboxlog = page.get_bboxlog()
        except Exception:
            bboxlog = []

        drawings = page.get_drawings() if len(bboxlog) <= max_page_primitives else []
        words = page.get_text("words")
        rules = self._detect_horizontal_rules(drawings, page_w)
        portraits = self._detect_small_portrait_images(page)

        regions: List[LayoutRegion] = []
        table_caption_boxes: List[BoundingBox] = []
        figure_caption_boxes: List[BoundingBox] = []

        # Primera pasada sobre bloques textuales para identificar captions, abandon, títulos, notas al pie
        prelim_text_blocks: List[Tuple[BoundingBox, str, List[Dict[str, Any]], float]] = []
        for b in raw_blocks:
            if b.get("type") != 0:
                continue
            bb = BoundingBox(*[float(v) for v in b["bbox"]])
            lines = b.get("lines", [])
            spans = [s for ln in lines for s in ln.get("spans", [])]
            if not spans:
                continue
            text = "\n".join(
                "".join(s.get("text", "") for s in ln.get("spans", []))
                for ln in lines
            ).strip()
            if not text:
                continue
            max_sz = max(float(s.get("size", body_size)) for s in spans)
            prelim_text_blocks.append((bb, text, spans, max_sz))

            clean_single = " ".join(text.split())
            if TABLE_CAPTION_REGEX.search(clean_single):
                table_caption_boxes.append(bb)
            elif CAPTION_REGEX.search(clean_single):
                figure_caption_boxes.append(bb)

        # Detectar bloques de Algoritmos y Pseudocódigo antes de tablas (evita confusión con reglas horizontales)
        algorithm_boxes: List[BoundingBox] = []
        consumed_by_algorithm: set[int] = set()
        idx_b = 0
        while idx_b < len(prelim_text_blocks):
            if idx_b in consumed_by_algorithm:
                idx_b += 1
                continue
            bb_cur, txt_cur, _, _ = prelim_text_blocks[idx_b]
            first_line = txt_cur.splitlines()[0].strip() if txt_cur else ""
            if ALGORITHM_HEADER_RE.match(first_line) or AlgorithmRecognizer.is_algorithm_text(txt_cur):
                union_algo = bb_cur
                consumed_by_algorithm.add(idx_b)
                j_next = idx_b + 1
                while j_next < len(prelim_text_blocks):
                    bb_nxt, txt_nxt, _, _ = prelim_text_blocks[j_next]
                    v_gap = bb_nxt.y0 - union_algo.y1
                    horiz_aligned = not (bb_nxt.x1 < union_algo.x0 - 15.0 or bb_nxt.x0 > union_algo.x1 + 140.0)
                    if -4.0 <= v_gap <= 28.0 and horiz_aligned and self._is_pseudocode_continuation(txt_nxt):
                        union_algo = union_algo.union(bb_nxt)
                        consumed_by_algorithm.add(j_next)
                        j_next += 1
                    else:
                        break
                algo_box = union_algo.pad(2.0, page.rect)
                algorithm_boxes.append(algo_box)
                regions.append(LayoutRegion(kind="algorithm", bbox=algo_box, confidence=0.95, source="model"))
                idx_b = j_next
            else:
                idx_b += 1

        # Detectar regiones de tablas (excluyendo cajas de algoritmos y gráficos vectoriales con Fig. X:)
        raw_table_boxes = self._detect_table_regions(
            page,
            rules,
            table_caption_boxes,
            raw_blocks,
            figure_captions=figure_caption_boxes,
        )
        table_boxes = [
            tb for tb in raw_table_boxes
            if not any(tb.iou(ab) > 0.25 or ab.coverage_by(tb) > 0.45 for ab in algorithm_boxes)
        ]
        for tb in table_boxes:
            regions.append(LayoutRegion(kind="table", bbox=tb, confidence=0.92, source="model"))

        # Detectar figuras ráster y vectoriales (excluyendo retratos diminutos de biografías y tablas)
        bio_text_boxes = [
            bb for (bb, txt, _, _) in prelim_text_blocks
            if _BIO_CUE_RE.search(" ".join(txt.split()))
        ]
        figure_boxes: List[BoundingBox] = []
        try:
            for img in page.get_images():
                xref = img[0]
                for r in page.get_image_rects(xref):
                    ib = BoundingBox.from_fitz_rect(r)
                    if ib.width >= 35.0 and ib.height >= 35.0:
                        if any(ib.iou(tb) > 0.4 or ib.coverage_by(tb) > 0.6 for tb in table_boxes):
                            continue
                        is_portrait = any(ib.iou(p) > 0.65 for p in portraits)
                        near_bio = any(
                            abs(p_bio.y0 - ib.y0) < 85.0 and abs(p_bio.x0 - ib.x1) < 55.0
                            for p_bio in bio_text_boxes
                        )
                        near_fig_cap = any(
                            abs(fc.y0 - ib.y1) < 55.0 or abs(ib.y0 - fc.y1) < 55.0
                            for fc in figure_caption_boxes
                        )
                        if is_portrait and (near_bio or not near_fig_cap):
                            continue
                        figure_boxes.append(ib)
        except Exception:
            pass

        vec_clusters = cluster_vector_drawings(
            page=page,
            drawings=drawings if drawings else None,
            max_page_primitives=max_page_primitives,
        )
        prose_candidates = [
            bb for (bb, txt, _, _) in prelim_text_blocks
            if len(txt) > 60 and bb not in figure_caption_boxes and bb not in table_caption_boxes
        ]
        for vb in vec_clusters:
            if any(vb.iou(tb) > 0.35 or vb.coverage_by(tb) > 0.60 for tb in table_boxes):
                continue
            refined = expand_figure_bbox(
                page=page,
                figure_bbox=vb,
                bleed_padding=elastic_min,
                drawings=drawings if drawings else None,
                words=words,
                prose_blocks=prose_candidates,
                max_vector_primitives=max_figure_primitives,
                max_padding=elastic_max,
            )
            if any(refined.iou(fb) > 0.55 or refined.coverage_by(fb) > 0.75 for fb in figure_boxes):
                continue
            figure_boxes.append(refined)

        for fb in figure_boxes:
            # Extraer etiquetas de subpaneles (a), (b) dentro o en el borde de la figura
            panel_tags: List[str] = []
            for w in words:
                wb = BoundingBox(float(w[0]), float(w[1]), float(w[2]), float(w[3]))
                wtxt = str(w[4]).strip()
                if fb.pad(12.0, page.rect).intersects(wb) and SUBPANEL_TAG_REGEX.fullmatch(wtxt):
                    if wtxt not in panel_tags:
                        panel_tags.append(wtxt)
            regions.append(LayoutRegion(
                kind="figure",
                bbox=fb,
                confidence=0.90,
                source="native",
                metadata={"subpanel_labels": panel_tags},
            ))

        # Detectar separadores de notas al pie en el tercio inferior de la página
        footnote_rule_y = None
        for rl in rules:
            if rl.y0 > (page_h * 0.62) and 35.0 <= rl.width <= (page_w * 0.48):
                footnote_rule_y = min(footnote_rule_y, rl.y0) if footnote_rule_y else rl.y0

        # Fusionar bandas de ecuaciones 2D fragmentadas (ej. numerador, denominador y tag '(1)' en bloques separados)
        consumed_by_formula: set[int] = set()
        for idx_tag, (bb_tag, txt_tag, _, _) in enumerate(prelim_text_blocks):
            if idx_tag in consumed_by_algorithm:
                continue
            clean_tag = " ".join(txt_tag.split()).strip()
            m_tag = re.fullmatch(r"\(\s*(\d+[a-zA-Z]?)\s*\)", clean_tag)
            if not m_tag:
                continue
            eq_num = m_tag.group(1)
            band_y0 = bb_tag.y0 - 24.0
            band_y1 = bb_tag.y1 + 24.0
            band_members = [idx_tag]
            union_eq = bb_tag
            for idx_other, (bb_o, txt_o, _, _) in enumerate(prelim_text_blocks):
                if idx_other == idx_tag or idx_other in consumed_by_algorithm:
                    continue
                cy_o = (bb_o.y0 + bb_o.y1) * 0.5
                if band_y0 <= cy_o <= band_y1 and len(txt_o.strip()) < 120:
                    band_members.append(idx_other)
                    union_eq = union_eq.union(bb_o)
            if len(band_members) >= 2:
                consumed_by_formula.update(band_members)
                regions.append(LayoutRegion(
                    kind="formula",
                    bbox=union_eq.pad(3.0, page.rect),
                    confidence=0.95,
                    source="model",
                    metadata={"tag": eq_num},
                ))

        # Clasificar los bloques textuales que no caen dentro de tablas, figuras, algoritmos ni bandas de ecuación
        for b_idx, (bb, text, spans, max_sz) in enumerate(prelim_text_blocks):
            if b_idx in consumed_by_formula or b_idx in consumed_by_algorithm:
                continue
            # Si ya está absorbido por una tabla o algoritmo detectado, lo manejará su reconocedor
            if any(bb.coverage_by(tb) > 0.65 for tb in table_boxes) or any(bb.coverage_by(ab) > 0.65 for ab in algorithm_boxes):
                continue

            clean_single = " ".join(text.split())

            # 1. Encabezados / pies de página repetitivos (abandon)
            if (bb.y1 < 44.0 or bb.y0 > (page_h - 42.0)) and len(clean_single) < 140:
                if not CAPTION_REGEX.search(clean_single) and not TABLE_CAPTION_REGEX.search(clean_single):
                    regions.append(LayoutRegion(kind="abandon", bbox=bb, confidence=0.95))
                    continue

            # 2. Leyendas de tablas y figuras
            if bb in table_caption_boxes:
                regions.append(LayoutRegion(kind="table_caption", bbox=bb, confidence=0.96))
                continue
            if bb in figure_caption_boxes:
                regions.append(LayoutRegion(kind="figure_caption", bbox=bb, confidence=0.96))
                continue

            # 3. Si es texto pequeño dentro de una figura (ej. etiquetas de diagrama), ignorar como bloque suelto
            if any(bb.coverage_by(fb) > 0.75 for fb in figure_boxes) and len(clean_single) < 80:
                continue

            # 4. Título del artículo en página 1 (excluyendo encabezados numerados o secciones canónicas)
            if (
                page_num == 1
                and bb.y0 < (page_h * 0.35)
                and max_sz >= (body_size * 1.32)
                and len(clean_single) > 12
                and not _HEADING_PREFIX_RE.match(clean_single)
                and not _CANONICAL_SECTION_RE.match(clean_single)
            ):
                regions.append(LayoutRegion(kind="title", bbox=bb, confidence=0.95))
                continue

            # 5. Biografías de autores (IEEE Transactions) — evaluar antes de footnote porque usan fuente de 8–8.5pt al final de página
            has_nearby_portrait = any(
                abs(p.y0 - bb.y0) < 60.0 and abs(p.x1 - bb.x0) < 45.0
                for p in portraits
            )
            if _BIO_CUE_RE.search(clean_single) or has_nearby_portrait:
                regions.append(LayoutRegion(kind="author_bio", bbox=bb, confidence=0.90))
                continue

            # 6. Notas al pie (footnote) en la parte inferior de la columna/página
            is_near_bottom = bb.y0 > (page_h * 0.72) or (footnote_rule_y is not None and bb.y0 >= (footnote_rule_y - 4.0))
            if is_near_bottom and (max_sz <= (body_size * 0.92) or _FOOTNOTE_START_RE.search(clean_single)):
                regions.append(LayoutRegion(kind="footnote", bbox=bb, confidence=0.90))
                continue

            # 7. Ecuaciones aisladas (isolate_formula)
            is_eq, eq_tag = self._is_math_heavy_block(text, spans)
            if is_eq:
                regions.append(LayoutRegion(
                    kind="formula",
                    bbox=bb,
                    confidence=0.92,
                    metadata={"tag": eq_tag} if eq_tag else {},
                ))
                continue

            # 8. Encabezados de sección / subsección
            if len(clean_single) < 115 and (
                _HEADING_PREFIX_RE.match(clean_single)
                or _CANONICAL_SECTION_RE.match(clean_single)
                or (max_sz >= body_size * 1.12 and len(clean_single.split()) <= 12 and clean_single[0].isupper())
            ):
                lvl = 3 if re.match(r"^\d+\.\d+", clean_single) else 2
                regions.append(LayoutRegion(kind="section_header", bbox=bb, heading_level=lvl, confidence=0.92))
                continue

            # 9. Listas con viñetas
            if clean_single.startswith(("•", "- ", "* ")) or re.match(r"^\(\d+\)\s+", clean_single):
                regions.append(LayoutRegion(kind="list", bbox=bb, confidence=0.90))
                continue

            # 10. Bloque de texto ordinario
            regions.append(LayoutRegion(kind="text", bbox=bb, confidence=0.95))

        return regions
