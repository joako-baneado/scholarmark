"""
2D Mathematical Formula Recognizer for ScholarMark v4.1.
Recovers two-dimensional algebraic structure (fractions with vector division bars,
nested subscripts/superscripts x_{i_k}^{n+1}, summation/integral limits, and matrices)
from PDF spatial primitives via Single-Pass PageContext, with SHA-1 caching and
KaTeX syntax validation.
"""

from dataclasses import dataclass
import hashlib
import re
from typing import List, Optional, Tuple, Dict, Any
import fitz

from ..core.geometry import BoundingBox
from ..core.math_parser import clean_math_glyphs, sanitize_numeric_typography
from ..core.page_context import PageContext


_EQ_TAG_RE = re.compile(r"^\(\s*([0-9]+[a-zA-Z]?|[A-Z]\.[0-9]+)\s*\)$")
_BIG_OPS = {r"\sum", r"\prod", r"\int", r"\iint", r"\iiint", r"\oint", "∑", "∏", "∫", "∬", "∭", "∮", "lim"}
_UNICODE_BIG_OP_MAP = {
    "∑": r"\sum",
    "∏": r"\prod",
    "∫": r"\int",
    "∬": r"\iint",
    "∭": r"\iiint",
    "∮": r"\oint",
    "√": r"\sqrt",
}

_PUA_GLYPH_MAP = {
    "\ue000": r"\sum",
    "\ue001": r"\prod",
    "\ue002": r"\int",
    "\ue003": r"\oint",
    "\ue004": r"\sqrt",
    "\ue050": r"\sum",
    "\ue051": r"\prod",
    "\ue052": r"\int",
    "\uf0e5": r"\sum",
    "\uf0d5": r"\prod",
    "\uf0f2": r"\int",
    "\uf0d6": r"\sqrt",
    "\uf0a5": r"\infty",
    "\uf0b6": r"\partial",
    "\uf0d1": r"\nabla",
    "\uf0ce": r"\in",
    "\uf0a3": r"\leq",
    "\uf0b3": r"\geq",
    "\uf0bb": r"\approx",
    "\uf0b9": r"\neq",
    "\uf0b4": r"\times",
    "\uf0b1": r"\pm",
    "\uf061": r"\alpha",
    "\uf062": r"\beta",
    "\uf067": r"\gamma",
    "\uf064": r"\delta",
    "\uf06c": r"\lambda",
    "\uf06d": r"\mu",
    "\uf073": r"\sigma",
    "\uf071": r"\theta",
    "\uf077": r"\omega",
}


def has_corrupted_glyphs(text: str) -> Tuple[bool, int]:
    """
    Detecta si una cadena contiene caracteres en el Área de Uso Privado (PUA U+E000..U+F8FF),
    el carácter de reemplazo Unicode (U+FFFD) o códigos de control inválidos de fuentes sin ToUnicode.
    """
    if not text:
        return False, 0
    count = 0
    for ch in text:
        code = ord(ch)
        if (
            0xE000 <= code <= 0xF8FF
            or code == 0xFFFD
            or code >= 0xF0000
            or (1 <= code < 32 and ch not in ("\t", "\n", "\r"))
        ):
            count += 1
    return count > 0, count


def sanitize_pua_text(text: str) -> Tuple[str, bool]:
    """
    Reemplaza glifos PUA conocidos de fuentes matemáticas antiguas por sus comandos LaTeX
    y purga glifos corruptos no mapeados. Retorna (texto_limpio, hubo_reparacion).
    """
    has_bad, _ = has_corrupted_glyphs(text)
    if not has_bad:
        return text, False

    out_chars: List[str] = []
    for ch in text:
        if ch in _PUA_GLYPH_MAP:
            out_chars.append(f" {_PUA_GLYPH_MAP[ch]} ")
        else:
            code = ord(ch)
            if (
                0xE000 <= code <= 0xF8FF
                or code == 0xFFFD
                or code >= 0xF0000
                or (1 <= code < 32 and ch not in ("\t", "\n", "\r"))
            ):
                continue
            out_chars.append(ch)
    return "".join(out_chars), True


@dataclass
class MathSpanToken:
    """Token matemático posicionado en el plano 2D de la ecuación."""
    text: str
    bbox: BoundingBox
    font_size: float

    @property
    def cx(self) -> float:
        return (self.bbox.x0 + self.bbox.x1) * 0.5

    @property
    def cy(self) -> float:
        return (self.bbox.y0 + self.bbox.y1) * 0.5


def validate_katex_syntax(latex: str) -> Tuple[bool, float]:
    """
    Verifica que el código LaTeX generado tenga llaves balanceadas, entornos cerrados
    y ausencia de secuencias degeneradas. Retorna (es_valido, confianza).
    """
    if not latex or not latex.strip():
        return False, 0.0

    has_bad, _ = has_corrupted_glyphs(latex)
    if has_bad:
        return False, 0.20

    depth = 0
    for ch in latex:
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth < 0:
                return False, 0.25
    if depth != 0:
        return False, 0.30

    begins = re.findall(r"\\begin\{([^}]+)\}", latex)
    ends = re.findall(r"\\end\{([^}]+)\}", latex)
    if begins != ends:
        return False, 0.35

    if r"\frac{}" in latex or r"\frac{" in latex and latex.count("{") < 2:
        return False, 0.35

    return True, 0.96


def _normalize_token_latex(raw_text: str) -> str:
    repaired, _ = sanitize_pua_text(raw_text.strip())
    txt = sanitize_numeric_typography(repaired)
    for u_op, l_op in _UNICODE_BIG_OP_MAP.items():
        txt = txt.replace(u_op, f" {l_op} ")
    txt = clean_math_glyphs(txt)
    return " ".join(txt.split())


class FormulaRecognizer:
    """
    Reconocedor híbrido 2D de ecuaciones científicas.
    """

    def __init__(self, device: str = "auto", onnx_model_path: Optional[str] = None):
        self.device = device
        self.onnx_model_path = onnx_model_path
        self._cache: Dict[str, Tuple[str, float, Optional[str]]] = {}
        self.last_fallback_triggered: bool = False
        self.last_corrupted_glyphs: int = 0

    @staticmethod
    def _extract_tokens_and_bars(
        page: fitz.Page,
        bbox: BoundingBox,
        drawings: Optional[List[Dict[str, Any]]] = None,
        ctx: Optional[PageContext] = None,
    ) -> Tuple[List[MathSpanToken], List[BoundingBox]]:
        """Extrae tokens con coordenadas a nivel de palabra/span y barras horizontales de fracción."""
        pad_box = bbox.pad(4.0, page.rect)
        if ctx is not None:
            raw = ctx.clip_rawdict(bbox, pad=4.0)
        else:
            raw = page.get_text("rawdict", clip=pad_box.to_fitz_rect())

        tokens: List[MathSpanToken] = []
        for b in raw.get("blocks", []):
            if b.get("type") != 0:
                continue
            for ln in b.get("lines", []):
                for sp in ln.get("spans", []):
                    sz = float(sp.get("size", 10.0))
                    chars = sp.get("chars", [])
                    if chars:
                        cur_chars = []
                        cur_box: Optional[BoundingBox] = None
                        for ch in chars:
                            c_str = ch.get("c", "")
                            if not c_str or c_str.isspace():
                                if cur_chars and cur_box:
                                    tokens.append(MathSpanToken("".join(cur_chars), cur_box, sz))
                                    cur_chars = []
                                    cur_box = None
                                continue
                            cb = BoundingBox(*[float(v) for v in ch["bbox"]])
                            if cur_chars and (c_str in "=+-(),[]" or cur_chars[-1] in "=+-(),[]"):
                                tokens.append(MathSpanToken("".join(cur_chars), cur_box, sz))
                                cur_chars = [c_str]
                                cur_box = cb
                            else:
                                cur_chars.append(c_str)
                                cur_box = cb if cur_box is None else cur_box.union(cb)
                        if cur_chars and cur_box:
                            tokens.append(MathSpanToken("".join(cur_chars), cur_box, sz))
                    else:
                        stxt = sp.get("text", "").strip()
                        if stxt:
                            sb = BoundingBox(*[float(v) for v in sp["bbox"]])
                            tokens.append(MathSpanToken(stxt, sb, sz))

        deduped_tokens: List[MathSpanToken] = []
        for tk in tokens:
            is_dup = False
            for prev in deduped_tokens:
                if tk.text == prev.text and (
                    tk.bbox.iou(prev.bbox) > 0.50
                    or (abs(tk.bbox.x0 - prev.bbox.x0) < 2.2 and abs(tk.bbox.y0 - prev.bbox.y0) < 2.2)
                ):
                    is_dup = True
                    break
            if not is_dup:
                deduped_tokens.append(tk)
        tokens = deduped_tokens

        if drawings is None:
            if ctx is not None:
                drawings = ctx.drawings
            else:
                try:
                    drawings = page.get_drawings()
                except Exception:
                    drawings = []

        fraction_bars: List[BoundingBox] = []
        radical_bars: List[BoundingBox] = []
        for d in drawings:
            r = d.get("rect")
            if r is None:
                continue
            db = BoundingBox.from_fitz_rect(r)
            if not pad_box.intersects(db):
                continue
            if db.height <= 2.8 and 6.0 <= db.width <= (pad_box.width * 0.92):
                # Invariante de vinculum radical:
                # 1. Glifo de raíz a la izquierda (√, \u221a, \sqrt, CMEX)
                is_radical = False
                rad_glyphs = [
                    t for t in tokens
                    if (t.text in ("\u221a", "√", "\\sqrt") or "cmex" in getattr(t, "font_name", "").lower())
                    and (db.x0 - 22.0) <= t.cx <= (db.x0 + 5.0)
                    and (db.y0 - 5.0) <= t.cy <= (db.y1 + db.height + 40.0)
                ]
                has_diag_hook = False
                for other_d in drawings:
                    if other_d is d:
                        continue
                    or_rect = other_d.get("rect")
                    if or_rect is not None:
                        if abs(or_rect.x1 - db.x0) <= 3.5 and abs(or_rect.y0 - db.y0) <= 5.0:
                            has_diag_hook = True
                            break

                tokens_under = [t for t in tokens if (db.x0 - 2.0) <= t.cx <= (db.x1 + 3.0) and t.cy >= (db.y0 - 0.5)]
                tokens_above_right = [t for t in tokens if t.cx >= (db.x0 + 3.5) and t.cy < (db.y0 - 0.5)]

                if (rad_glyphs or has_diag_hook) and tokens_under and not tokens_above_right:
                    is_radical = True

                if is_radical:
                    radical_bars.append(db)
                else:
                    fraction_bars.append(db)

        return tokens, fraction_bars, radical_bars

    def _reconstruct_sequence(
        self,
        tokens: List[MathSpanToken],
        bars: List[BoundingBox],
        radical_bars: Optional[List[BoundingBox]] = None,
    ) -> str:
        """
        Reconstruye recursivamente una expresión matemática 2D (raíces, fracciones, límites,
        matrices, subíndices y superíndices anidados) a partir de sus tokens espaciales y barras vectoriales.
        """
        if not tokens:
            return ""

        # 1. Procesamiento de radicales antes de fracciones
        if radical_bars:
            sorted_rads = sorted(radical_bars, key=lambda b: b.width, reverse=True)
            for rbar in sorted_rads:
                rad_syms = [
                    t for t in tokens
                    if (t.text in ("\u221a", "√", "\\sqrt") or "cmex" in getattr(t, "font_name", "").lower())
                    and (rbar.x0 - 22.0) <= t.cx <= (rbar.x0 + 5.0)
                ]
                idx_toks = [
                    t for t in tokens
                    if (rbar.x0 - 22.0) <= t.cx < (rbar.x0 + 2.0)
                    and t.cy <= rbar.y0
                    and t not in rad_syms
                ]
                radicand_toks = [
                    t for t in tokens
                    if (rbar.x0 - 2.0) <= t.cx <= (rbar.x1 + 3.0)
                    and t.cy >= (rbar.y0 - 0.5)
                    and t not in rad_syms
                ]

                if radicand_toks:
                    consumed_ids = {id(t) for t in idx_toks} | {id(t) for t in radicand_toks} | {id(t) for t in rad_syms}
                    remaining_rads = [b for b in radical_bars if b is not rbar]
                    left_toks = [t for t in tokens if id(t) not in consumed_ids and t.cx < rbar.x0]
                    right_toks = [t for t in tokens if id(t) not in consumed_ids and t.cx >= rbar.x1]

                    left_bars = [b for b in bars if b.x1 <= rbar.x0]
                    inner_bars = [b for b in bars if b.x0 >= (rbar.x0 - 2.0) and b.x1 <= (rbar.x1 + 2.0)]
                    right_bars = [b for b in bars if b.x0 >= rbar.x1]

                    radicand_str = self._reconstruct_sequence(radicand_toks, inner_bars, remaining_rads)
                    idx_str = self._reconstruct_sequence(idx_toks, []) if idx_toks else ""
                    if idx_str:
                        rad_latex = rf"\sqrt[{idx_str}]{{{radicand_str}}}"
                    else:
                        rad_latex = rf"\sqrt{{{radicand_str}}}"

                    left_str = self._reconstruct_sequence(left_toks, left_bars, [b for b in remaining_rads if b.x1 <= rbar.x0])
                    right_str = self._reconstruct_sequence(right_toks, right_bars, [b for b in remaining_rads if b.x0 >= rbar.x1])

                    parts = [p for p in (left_str, rad_latex, right_str) if p]
                    return " ".join(parts)

        valid_bars: List[Tuple[BoundingBox, List[MathSpanToken], List[MathSpanToken]]] = []
        for bar in sorted(bars, key=lambda b: b.width, reverse=True):
            num_toks = [
                t for t in tokens
                if (bar.x0 - 4.0) <= t.cx <= (bar.x1 + 4.0) and t.cy <= (bar.y0 + 1.5)
            ]
            den_toks = [
                t for t in tokens
                if (bar.x0 - 4.0) <= t.cx <= (bar.x1 + 4.0) and t.cy >= (bar.y1 - 1.5)
            ]
            if num_toks and den_toks:
                valid_bars.append((bar, num_toks, den_toks))

        if valid_bars:
            main_bar, num_toks, den_toks = valid_bars[0]
            consumed_ids = {id(t) for t in num_toks} | {id(t) for t in den_toks}
            remaining_bars = [b for b in bars if b is not main_bar]

            left_toks = [t for t in tokens if id(t) not in consumed_ids and t.cx < main_bar.x0]
            right_toks = [t for t in tokens if id(t) not in consumed_ids and t.cx >= main_bar.x0]

            left_bars = [b for b in remaining_bars if b.x1 <= main_bar.x0]
            inner_num_bars = [b for b in remaining_bars if b.x0 >= (main_bar.x0 - 2.0) and b.x1 <= (main_bar.x1 + 2.0) and b.y1 <= main_bar.y0]
            inner_den_bars = [b for b in remaining_bars if b.x0 >= (main_bar.x0 - 2.0) and b.x1 <= (main_bar.x1 + 2.0) and b.y0 >= main_bar.y1]
            right_bars = [b for b in remaining_bars if b.x0 >= main_bar.x1]

            left_str = self._reconstruct_sequence(left_toks, left_bars)
            num_str = self._reconstruct_sequence(num_toks, inner_num_bars)
            den_str = self._reconstruct_sequence(den_toks, inner_den_bars)
            right_str = self._reconstruct_sequence(right_toks, right_bars)

            parts = [p for p in (left_str, rf"\frac{{{num_str}}}{{{den_str}}}", right_str) if p]
            return " ".join(parts)

        matrix_latex = self._try_reconstruct_matrix(tokens)
        if matrix_latex:
            return matrix_latex

        multiline_latex = self._try_reconstruct_multiline_aligned(tokens, bars)
        if multiline_latex:
            return multiline_latex

        sorted_toks = sorted(tokens, key=lambda t: (round(t.bbox.x0, 1), round(t.bbox.y0, 1)))
        max_size = max(t.font_size for t in sorted_toks)
        base_Threshold_size = max_size * 0.86

        main_toks = [t for t in sorted_toks if t.font_size >= base_Threshold_size]
        if not main_toks:
            main_toks = sorted_toks

        out_parts: List[str] = []
        i = 0
        n = len(sorted_toks)

        while i < n:
            base_t = sorted_toks[i]
            base_latex = _normalize_token_latex(base_t.text)
            base_cy = base_t.cy
            base_h = max(4.0, base_t.bbox.height)

            j = i + 1
            sub_toks: List[MathSpanToken] = []
            sup_toks: List[MathSpanToken] = []

            is_big_op = any(op in base_latex for op in _BIG_OPS)

            while j < n:
                cand = sorted_toks[j]
                horiz_overlap = not (cand.bbox.x1 < (base_t.bbox.x0 - 4.0) or cand.bbox.x0 > (base_t.bbox.x1 + 14.0))
                dy = cand.cy - base_cy
                is_smaller = cand.font_size < (base_t.font_size * 0.90)

                if is_big_op and horiz_overlap and abs(dy) > (base_h * 0.18):
                    if dy < 0:
                        sup_toks.append(cand)
                    else:
                        sub_toks.append(cand)
                    j += 1
                    continue

                last_x1 = max(
                    [base_t.bbox.x1]
                    + [t.bbox.x1 for t in sub_toks]
                    + [t.bbox.x1 for t in sup_toks]
                )
                if (cand.bbox.x0 - last_x1) <= max(6.0, base_t.font_size * 0.65) and (
                    is_smaller or abs(dy) >= (base_h * 0.22)
                ) and abs(dy) >= (base_h * 0.14):
                    if dy < 0:
                        sup_toks.append(cand)
                    else:
                        sub_toks.append(cand)
                    j += 1
                else:
                    break

            piece = base_latex
            if sub_toks:
                sub_str = self._reconstruct_sequence(sub_toks, [])
                piece += f"_{{{sub_str}}}"
            if sup_toks:
                sup_str = self._reconstruct_sequence(sup_toks, [])
                piece += f"^{{{sup_str}}}"

            out_parts.append(piece)
            i = j

        return " ".join(out_parts)

    @staticmethod
    def _try_reconstruct_matrix(tokens: List[MathSpanToken]) -> Optional[str]:
        """
        Detecta si un conjunto de tokens forma una matriz bidimensional (>= 2 filas y >= 2 columnas)
        y la serializa como \\begin{pmatrix|bmatrix|vmatrix} ... \\end{...}.
        Soporta '=' dentro de celdas cuando está envuelta por delimitadores (>=75% altura de cuadrícula).
        """
        if not tokens:
            return None

        delims = [t for t in tokens if t.text.strip() in ("(", ")", "[", "]", "|", "||", "{", "}")]
        core = [t for t in tokens if t not in delims]
        if len(core) < 4:
            return None

        grid_y0 = min(t.bbox.y0 for t in core)
        grid_y1 = max(t.bbox.y1 for t in core)
        grid_height = max(1.0, grid_y1 - grid_y0)

        left_delims = [t for t in delims if t.cx <= min(t.cx for t in core)]
        right_delims = [t for t in delims if t.cx >= max(t.cx for t in core)]

        has_left = any(t.bbox.height >= (grid_height * 0.70) for t in left_delims)
        has_right = any(t.bbox.height >= (grid_height * 0.70) for t in right_delims)
        has_wrapper = has_left and has_right

        if not has_wrapper and any(t.text.strip() == "=" for t in core):
            return None

        env = "pmatrix"
        if has_wrapper:
            left_text = "".join(t.text.strip() for t in left_delims)
            if "[" in left_text:
                env = "bmatrix"
            elif "|" in left_text:
                env = "vmatrix"

        core_sorted_y = sorted(core, key=lambda t: t.cy)
        raw_rows: List[List[MathSpanToken]] = []
        for t in core_sorted_y:
            if not raw_rows or abs(t.cy - raw_rows[-1][0].cy) > max(6.0, t.font_size * 0.65):
                raw_rows.append([t])
            else:
                raw_rows[-1].append(t)

        if len(raw_rows) < 2:
            return None

        grouped_rows: List[List[str]] = []
        col_xs_per_row: List[List[float]] = []

        for r in raw_rows:
            r.sort(key=lambda t: t.cx)
            cells: List[str] = []
            xs: List[float] = []
            cur_cell_toks: List[MathSpanToken] = []

            for t in r:
                if not cur_cell_toks:
                    cur_cell_toks.append(t)
                else:
                    gap = t.bbox.x0 - cur_cell_toks[-1].bbox.x1
                    if gap <= 9.0:
                        cur_cell_toks.append(t)
                    else:
                        cell_str = " ".join(_normalize_token_latex(ct.text) for ct in cur_cell_toks)
                        cell_cx = (cur_cell_toks[0].bbox.x0 + cur_cell_toks[-1].bbox.x1) * 0.5
                        cells.append(cell_str)
                        xs.append(cell_cx)
                        cur_cell_toks = [t]

            if cur_cell_toks:
                cell_str = " ".join(_normalize_token_latex(ct.text) for ct in cur_cell_toks)
                cell_cx = (cur_cell_toks[0].bbox.x0 + cur_cell_toks[-1].bbox.x1) * 0.5
                cells.append(cell_str)
                xs.append(cell_cx)

            grouped_rows.append(cells)
            col_xs_per_row.append(xs)

        col_counts = [len(r) for r in grouped_rows]
        if min(col_counts) < 2 or max(col_counts) != min(col_counts):
            return None

        num_cols = col_counts[0]
        for c_idx in range(num_cols):
            col_xs = [col_xs_per_row[r_idx][c_idx] for r_idx in range(len(grouped_rows))]
            if (max(col_xs) - min(col_xs)) > 35.0:
                return None

        row_strs = [" & ".join(r) for r in grouped_rows]
        body = r" \\ ".join(row_strs)
        return rf"\begin{{{env}}} {body} \end{{{env}}}"

    def _try_reconstruct_multiline_aligned(
        self,
        tokens: List[MathSpanToken],
        bars: List[BoundingBox],
    ) -> Optional[str]:
        """
        Detecta bloques de ecuaciones multilínea (2+ líneas horizontales disjuntas en Y no separadas
        por una barra de fracción) y los serializa como \\begin{aligned} ... \\\\ ... \\end{aligned}.
        """
        if len(tokens) < 4:
            return None

        max_size = max(t.font_size for t in tokens)
        main_toks = [t for t in tokens if t.font_size >= (max_size * 0.85)]
        if len(main_toks) < 4:
            return None

        main_sorted_y = sorted(main_toks, key=lambda t: t.cy)
        bands: List[List[MathSpanToken]] = []
        for t in main_sorted_y:
            if not bands:
                bands.append([t])
            else:
                prev_cy = sum(x.cy for x in bands[-1]) / len(bands[-1])
                if (t.cy - prev_cy) > (max_size * 1.35):
                    bands.append([t])
                else:
                    bands[-1].append(t)

        if len(bands) < 2:
            return None

        # Si alguna barra de fracción separa dos bandas consecutivas, no es una ecuación multilínea independiente
        band_cys = [sum(x.cy for x in b) / len(b) for b in bands]
        for k in range(len(band_cys) - 1):
            y_top, y_bot = band_cys[k], band_cys[k + 1]
            for bar in bars:
                bar_cy = (bar.y0 + bar.y1) * 0.5
                if (y_top - 2.0) <= bar_cy <= (y_bot + 2.0):
                    return None

        # Requerir que cada banda tenga al menos 2 tokens principales
        if any(len(b) < 2 for b in bands):
            return None

        full_bands: List[List[MathSpanToken]] = [[] for _ in bands]
        for t in tokens:
            best_k = min(range(len(band_cys)), key=lambda k: abs(t.cy - band_cys[k]))
            full_bands[best_k].append(t)

        band_bars: List[List[BoundingBox]] = [[] for _ in bands]
        for bar in bars:
            bar_cy = (bar.y0 + bar.y1) * 0.5
            best_k = min(range(len(band_cys)), key=lambda k: abs(bar_cy - band_cys[k]))
            band_bars[best_k].append(bar)

        row_latex_list: List[str] = []
        for k in range(len(bands)):
            # Reconstruir cada línea de forma independiente
            row_str = self._reconstruct_single_line(full_bands[k], band_bars[k]).strip()
            if row_str:
                row_latex_list.append(row_str)

        if len(row_latex_list) < 2:
            return None

        has_equals = sum(1 for r in row_latex_list if "=" in r) >= 2
        if has_equals:
            row_latex_list = [r.replace("=", "&=", 1) if "=" in r else r for r in row_latex_list]

        joined = r" \\ ".join(row_latex_list)
        return rf"\begin{{aligned}} {joined} \end{{aligned}}"

    def _reconstruct_single_line(
        self,
        tokens: List[MathSpanToken],
        bars: List[BoundingBox],
    ) -> str:
        """Reconstruye una única línea de ecuación (con posibles fracciones internas y scripts)."""
        if not tokens:
            return ""
        sorted_toks = sorted(tokens, key=lambda t: (round(t.bbox.x0, 1), round(t.bbox.y0, 1)))
        out_parts: List[str] = []
        i = 0
        n = len(sorted_toks)
        while i < n:
            base_t = sorted_toks[i]
            base_latex = _normalize_token_latex(base_t.text)
            base_cy = base_t.cy
            base_h = max(4.0, base_t.bbox.height)
            j = i + 1
            sub_toks: List[MathSpanToken] = []
            sup_toks: List[MathSpanToken] = []
            is_big_op = any(op in base_latex for op in _BIG_OPS)
            while j < n:
                cand = sorted_toks[j]
                horiz_overlap = not (cand.bbox.x1 < (base_t.bbox.x0 - 4.0) or cand.bbox.x0 > (base_t.bbox.x1 + 14.0))
                dy = cand.cy - base_cy
                is_smaller = cand.font_size < (base_t.font_size * 0.90)
                if is_big_op and horiz_overlap and abs(dy) > (base_h * 0.18):
                    if dy < 0:
                        sup_toks.append(cand)
                    else:
                        sub_toks.append(cand)
                    j += 1
                    continue
                last_x1 = max(
                    [base_t.bbox.x1]
                    + [t.bbox.x1 for t in sub_toks]
                    + [t.bbox.x1 for t in sup_toks]
                )
                if (cand.bbox.x0 - last_x1) <= max(6.0, base_t.font_size * 0.65) and (
                    is_smaller or abs(dy) >= (base_h * 0.22)
                ) and abs(dy) >= (base_h * 0.14):
                    if dy < 0:
                        sup_toks.append(cand)
                    else:
                        sub_toks.append(cand)
                    j += 1
                else:
                    break
            piece = base_latex
            if sub_toks:
                sub_str = self._reconstruct_single_line(sub_toks, [])
                piece += f"_{{{sub_str}}}"
            if sup_toks:
                sup_str = self._reconstruct_single_line(sup_toks, [])
                piece += f"^{{{sup_str}}}"
            out_parts.append(piece)
            i = j
        return " ".join(out_parts)

    def _run_unimernet_onnx_gate(self, page: fitz.Page, bbox: BoundingBox) -> Optional[str]:
        """
        Micro-compuerta ONNX perezosa para UniMERNet-Tiny en CPU cuando la sintaxis KaTeX
        o los glifos PUA de la ruta vectorial nativa presentan degradación.
        """
        try:
            from ..models.registry import load_onnx_session
            session = load_onnx_session("unimernet_tiny")
            if session is None:
                return None

            import numpy as np
            import cv2
            pix = page.get_pixmap(clip=bbox.to_fitz_rect(), dpi=150, colorspace=fitz.csGRAY)
            if pix.width < 4 or pix.height < 4:
                return None

            arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width))
            target_h, target_w = 192, 672
            resized = cv2.resize(arr, (target_w, target_h), interpolation=cv2.INTER_AREA)
            img_input = (resized.astype(np.float32) / 255.0 - 0.5) / 0.5
            img_input = img_input[np.newaxis, np.newaxis, :, :]

            input_name = session.get_inputs()[0].name
            outputs = session.run(None, {input_name: img_input})
            if outputs and len(outputs) > 0 and isinstance(outputs[0], str):
                return outputs[0]
        except Exception:
            return None
        return None

    def recognize_region(
        self,
        page: fitz.Page,
        bbox: BoundingBox,
        fallback_text: str = "",
        drawings: Optional[List[Dict[str, Any]]] = None,
        ctx: Optional[PageContext] = None,
    ) -> Tuple[str, float, Optional[str]]:
        """
        Reconstruye la ecuación en la región dada y retorna (latex, confidence, tag).
        Utiliza caché SHA-1 sobre las coordenadas y texto del bloque.
        """
        self.last_fallback_triggered = False
        self.last_corrupted_glyphs = 0

        cache_key = hashlib.sha1(
            f"{page.number}:{round(bbox.x0,1)}:{round(bbox.y0,1)}:{round(bbox.x1,1)}:{round(bbox.y1,1)}:{fallback_text}".encode("utf-8")
        ).hexdigest()

        tokens, bars, radical_bars = self._extract_tokens_and_bars(page, bbox, drawings=drawings, ctx=ctx)
        raw_concat = " ".join(t.text for t in tokens) + " " + (fallback_text or "")
        has_bad, bad_count = has_corrupted_glyphs(raw_concat)
        if has_bad:
            self.last_fallback_triggered = True
            self.last_corrupted_glyphs = bad_count

        if cache_key in self._cache:
            return self._cache[cache_key]

        if not tokens:
            self.last_fallback_triggered = True
            clean_fb = _normalize_token_latex(fallback_text)
            ok, conf = validate_katex_syntax(clean_fb)
            res = (clean_fb, conf if ok else 0.4, None)
            self._cache[cache_key] = res
            return res

        tokens_sorted_x = sorted(tokens, key=lambda t: t.bbox.x0)
        tag: Optional[str] = None
        if len(tokens_sorted_x) >= 2:
            rightmost = tokens_sorted_x[-1]
            m = _EQ_TAG_RE.match(rightmost.text.strip())
            if m:
                tag = m.group(1)
                tokens = [t for t in tokens if t is not rightmost]
            elif len(tokens_sorted_x) >= 4:
                last3 = "".join(t.text.strip() for t in tokens_sorted_x[-3:])
                m3 = _EQ_TAG_RE.match(last3)
                if m3:
                    tag = m3.group(1)
                    drop_ids = {id(t) for t in tokens_sorted_x[-3:]}
                    tokens = [t for t in tokens if id(t) not in drop_ids]

        latex_str = self._reconstruct_sequence(tokens, bars, radical_bars=radical_bars).strip()
        ok, conf = validate_katex_syntax(latex_str)

        # Micro-compuerta UniMERNet-Tiny ONNX si KaTeX falla o hay glifos PUA corruptos
        if not ok or has_bad:
            onnx_latex = self._run_unimernet_onnx_gate(page, bbox)
            if onnx_latex:
                latex_str = onnx_latex
                ok, conf = validate_katex_syntax(latex_str)

        if not ok and fallback_text:
            self.last_fallback_triggered = True
            latex_str = _normalize_token_latex(fallback_text)
            ok, conf = validate_katex_syntax(latex_str)
            conf = min(conf, 0.45)

        res = (latex_str, conf, tag)
        self._cache[cache_key] = res
        return res
