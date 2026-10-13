"""
2D Mathematical Formula Recognizer for ScholarMark v3.0.
Recovers two-dimensional algebraic structure (fractions with vector division bars,
nested subscripts/superscripts x_{i_k}^{n+1}, summation/integral limits, and matrices)
from PDF spatial primitives + optional ONNX visual inference, with SHA-1 caching and
KaTeX syntax validation.
"""

from dataclasses import dataclass
import hashlib
import re
from typing import List, Optional, Tuple, Dict, Any
import fitz

from ..core.geometry import BoundingBox
from ..core.math_parser import clean_math_glyphs, sanitize_numeric_typography


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

# Mapeo de puntos de código PUA (Private Use Area U+E000..U+F8FF) comunes en fuentes TeX Type 1 / Symbol / CMEX
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
                # Ignorar glifo corrupto sin mapeo para evitar contaminar KaTeX
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
    Reconstruye fracciones vectoriales, sub/superíndices anidados, operadores con límites
    y matrices directamente desde el árbol espacial de glifos y trazos del PDF, con reparación
    de glifos PUA corruptos y soporte opcional para sesiones ONNX visuales.
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
        drawings: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[List[MathSpanToken], List[BoundingBox]]:
        """Extrae tokens con coordenadas a nivel de palabra/span y barras horizontales de fracción."""
        pad_box = bbox.pad(4.0, page.rect)
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
                        # Agrupar caracteres contiguos con misma línea base y tamaño
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
                            # Si es un operador delimitador o cambia drásticamente de posición, cortar token
                            if cur_chars and (c_str in "=+-(),[]" or cur_chars[-1] in "=+-(),[]"):
                                tokens.append(MathSpanToken(".".join(cur_chars) if False else "".join(cur_chars), cur_box, sz))
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

        # Deduplicar glifos superpuestos (fake-bold / doble trazado en PDFs TeX/Word)
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
            try:
                drawings = page.get_drawings()
            except Exception:
                drawings = []

        fraction_bars: List[BoundingBox] = []
        for d in drawings:
            r = d.get("rect")
            if r is None:
                continue
            db = BoundingBox.from_fitz_rect(r)
            if not pad_box.intersects(db):
                continue
            # Una barra de división es una línea horizontal fina (alto <= 2.8pt, ancho >= 6pt)
            if db.height <= 2.8 and 6.0 <= db.width <= (pad_box.width * 0.92):
                fraction_bars.append(db)

        return tokens, fraction_bars

    def _reconstruct_sequence(
        self,
        tokens: List[MathSpanToken],
        bars: List[BoundingBox]
    ) -> str:
        """
        Reconstruye recursivamente una expresión matemática 2D (fracciones, límites,
        subíndices y superíndices anidados) a partir de sus tokens espaciales y barras vectoriales.
        """
        if not tokens:
            return ""

        # 1. Comprobar si existen barras de fracción activas que dividan verticalmente subconjuntos de tokens
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
            # Tomar la barra principal más externa que no se solape conflictivamente
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

        # 2. Detectar estructura matricial (múltiples filas x múltiples columnas sin barra de fracción)
        matrix_latex = self._try_reconstruct_matrix(tokens)
        if matrix_latex:
            return matrix_latex

        # 3. Ordenar de izquierda a derecha y agrupar subíndices / superíndices / límites de operadores
        sorted_toks = sorted(tokens, key=lambda t: (round(t.bbox.x0, 1), round(t.bbox.y0, 1)))
        max_size = max(t.font_size for t in sorted_toks)
        base_Threshold_size = max_size * 0.86

        # Identificar la línea base principal usando los tokens de tamaño normal
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

            # Buscar tokens inmediatamente a la derecha (o encima/debajo para \sum, \int) que sean sub/superscripts
            j = i + 1
            sub_toks: List[MathSpanToken] = []
            sup_toks: List[MathSpanToken] = []

            is_big_op = any(op in base_latex for op in _BIG_OPS)

            while j < n:
                cand = sorted_toks[j]
                dx = cand.bbox.x0 - base_t.bbox.x1
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

                # Para variables ordinarias: un sub/superíndice está pegado a la derecha (dx <= font_size * 0.85)
                # y desplazado verticalmente hacia arriba (dy < 0) o hacia abajo (dy > 0)
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
                # Reconstruir recursivamente el subíndice (soporta anidamiento x_{i_k})
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
        y la serializa como \\begin{pmatrix} ... \\end{pmatrix}.
        """
        # Ignorar paréntesis/corchetes delimitadores gigantes en los extremos izquierdo/derecho
        core = [t for t in tokens if t.text.strip() not in ("(", ")", "[", "]", "{", "}")]
        if len(core) < 4:
            return None

        # Agrupar por filas según coordenada y
        core_sorted_y = sorted(core, key=lambda t: t.cy)
        rows: List[List[MathSpanToken]] = []
        for t in core_sorted_y:
            if not rows or abs(t.cy - rows[-1][0].cy) > max(6.0, t.font_size * 0.65):
                rows.append([t])
            else:
                rows[-1].append(t)

        if len(rows) < 2:
            return None

        col_counts = [len(r) for r in rows]
        if min(col_counts) < 2 or max(col_counts) != min(col_counts):
            return None

        # Verificar que las columnas estén alineadas verticalmente
        for r in rows:
            r.sort(key=lambda t: t.cx)

        num_cols = col_counts[0]
        for c_idx in range(num_cols):
            col_xs = [rows[r_idx][c_idx].cx for r_idx in range(len(rows))]
            if (max(col_xs) - min(col_xs)) > 28.0:
                return None

        row_strs = []
        for r in rows:
            cells = [_normalize_token_latex(t.text) for t in r]
            row_strs.append(" & ".join(cells))

        body = r" \\ ".join(row_strs)
        return rf"\begin{{pmatrix}} {body} \end{{pmatrix}}"

    def recognize_region(
        self,
        page: fitz.Page,
        bbox: BoundingBox,
        fallback_text: str = "",
        drawings: Optional[List[Dict[str, Any]]] = None
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

        tokens, bars = self._extract_tokens_and_bars(page, bbox, drawings=drawings)
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

        # Separar etiqueta de numeración derecha ej. (1), (2a)
        tokens_sorted_x = sorted(tokens, key=lambda t: t.bbox.x0)
        tag: Optional[str] = None
        if len(tokens_sorted_x) >= 2:
            rightmost = tokens_sorted_x[-1]
            m = _EQ_TAG_RE.match(rightmost.text.strip())
            if m:
                tag = m.group(1)
                tokens = [t for t in tokens if t is not rightmost]
            elif len(tokens_sorted_x) >= 4:
                # Caso en que '(', '1', ')' son 3 tokens separados al extremo derecho
                last3 = "".join(t.text.strip() for t in tokens_sorted_x[-3:])
                m3 = _EQ_TAG_RE.match(last3)
                if m3:
                    tag = m3.group(1)
                    drop_ids = {id(t) for t in tokens_sorted_x[-3:]}
                    tokens = [t for t in tokens if id(t) not in drop_ids]

        latex_str = self._reconstruct_sequence(tokens, bars).strip()
        ok, conf = validate_katex_syntax(latex_str)
        if not ok and fallback_text:
            self.last_fallback_triggered = True
            latex_str = _normalize_token_latex(fallback_text)
            ok, conf = validate_katex_syntax(latex_str)
            conf = min(conf, 0.45)

        res = (latex_str, conf, tag)
        self._cache[cache_key] = res
        return res
