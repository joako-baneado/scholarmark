"""
Algorithm & Pseudocode Block Recognizer for ScholarMark v3.1.
Recovers hierarchical indentation, line numbering, Input/Output/Require/Ensure headers,
and inline mathematical notation from floating algorithm environments (algorithm2e,
algpseudocode, algorithmic) in IEEE, ACM, Springer, and arXiv papers.
"""

from dataclasses import dataclass, field
import re
from typing import List, Optional, Tuple, Dict, Any
import fitz

from ..core.geometry import BoundingBox
from ..core.math_parser import clean_math_glyphs, sanitize_numeric_typography


ALGORITHM_HEADER_RE = re.compile(
    r"^\s*(?:Algorithm|Algoritmo|Procedure|Procedimiento|Protocol)\s+([0-9IVX]+)\s*[:.\-\u2013\u2014]?\s*(.*)$",
    re.IGNORECASE,
)
_LINE_NUM_PREFIX_RE = re.compile(r"^\s*(?:\[?\d{1,3}\]?[:.)])\s*(.*)$")
_SPEC_KEYWORD_RE = re.compile(
    r"^\s*(Require|Ensure|Input|Inputs|Output|Outputs|Parameters|Initialize|Initialization)\s*:\s*(.*)$",
    re.IGNORECASE,
)
_BLOCK_OPEN_RE = re.compile(
    r"^\s*(?:for\b|parfor\b|while\b|if\b|repeat\b|loop\b|function\b|procedure\b|def\b)",
    re.IGNORECASE,
)
_BLOCK_MID_RE = re.compile(
    r"^\s*(?:else\b|elsif\b|elif\b|else\s+if\b)",
    re.IGNORECASE,
)
_BLOCK_CLOSE_RE = re.compile(
    r"^\s*(?:end(?:\s+(?:for|while|if|loop|function|procedure))?\b|until\b|done\b|fi\b|od\b)",
    re.IGNORECASE,
)


@dataclass
class AlgorithmLine:
    """Línea individual estructurada dentro de un bloque de algoritmo."""
    line_number: Optional[str]
    indent_level: int
    code: str
    is_spec: bool = False
    raw_x0: float = 0.0


@dataclass
class AlgorithmResult:
    """Resultado completo de la reconstrucción de un algoritmo."""
    title: str
    algorithm_id: Optional[str]
    lines: List[AlgorithmLine] = field(default_factory=list)
    formatted_markdown: str = ""
    confidence: float = 0.95


def _clean_algo_code(text: str) -> str:
    """Normaliza símbolos matemáticos y flechas de asignación dentro de pseudocódigo."""
    t = sanitize_numeric_typography(text.strip())
    t = t.replace("←", "<-").replace("⟵", "<-").replace("→", "->")
    t = clean_math_glyphs(t)
    return " ".join(t.split())


class AlgorithmRecognizer:
    """
    Reconstructor híbrido de bloques de algoritmos y pseudocódigo.
    Combina el desplazamiento horizontal físico (Δx) de los spans después del número de línea
    con el análisis sintáctico de bloques de control (for/while/if/else/end) para preservar
    exactamente la sangría anidada.
    """

    def __init__(self, indent_step_pt: float = 10.0):
        self.indent_step_pt = max(4.0, indent_step_pt)

    @staticmethod
    def is_algorithm_text(text: str) -> bool:
        """Determina si un texto corresponde a un bloque de algoritmo/pseudocódigo."""
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if not lines:
            return False

        if ALGORITHM_HEADER_RE.match(lines[0]):
            return True

        # Contar señales de pseudocódigo (Require/Ensure/Input/Output, números de línea 1:, for/while/end)
        spec_hits = sum(1 for ln in lines[:4] if _SPEC_KEYWORD_RE.match(ln))
        numbered_hits = sum(1 for ln in lines if _LINE_NUM_PREFIX_RE.match(ln))
        kw_hits = sum(
            1 for ln in lines
            if _BLOCK_OPEN_RE.match(_LINE_NUM_PREFIX_RE.sub(r"\1", ln))
            or _BLOCK_CLOSE_RE.match(_LINE_NUM_PREFIX_RE.sub(r"\1", ln))
        )
        return (spec_hits >= 1 and (numbered_hits >= 2 or kw_hits >= 2)) or (numbered_hits >= 3 and kw_hits >= 2)

    def recognize_algorithm(
        self,
        page: fitz.Page,
        bbox: BoundingBox,
        fallback_text: str = ""
    ) -> AlgorithmResult:
        """
        Extrae y estructura un bloque de algoritmo en la región dada de la página.
        """
        clip = bbox.pad(3.0, page.rect).to_fitz_rect()
        raw_dict = page.get_text("dict", clip=clip)

        raw_lines: List[Tuple[float, float, Optional[str], str]] = []
        # Cada tupla: (y0, code_x0, line_num_str, code_text)

        for b in raw_dict.get("blocks", []):
            if b.get("type") != 0:
                continue
            for ln in b.get("lines", []):
                spans = [s for s in ln.get("spans", []) if str(s.get("text", "")).strip()]
                if not spans:
                    continue
                spans.sort(key=lambda s: float(s["bbox"][0]))
                y0 = float(ln["bbox"][1])

                first_txt = str(spans[0].get("text", "")).strip()
                first_x0 = float(spans[0]["bbox"][0])

                # Caso A: El primer span es exclusivamente el número de línea (ej. "1:", "2.")
                if re.fullmatch(r"\[?\d{1,3}\]?[:.)]?", first_txt) and len(spans) >= 2:
                    line_num = first_txt.rstrip(":.)").strip("[]")
                    code_x0 = float(spans[1]["bbox"][0])
                    code_str = " ".join(str(s.get("text", "")).strip() for s in spans[1:])
                    raw_lines.append((y0, code_x0, line_num, code_str))
                    continue

                # Caso B: Toda la línea viene en uno o varios spans donde el primero empieza con "1: ..."
                full_txt = " ".join(str(s.get("text", "")).strip() for s in spans)
                m_num = _LINE_NUM_PREFIX_RE.match(full_txt)
                if m_num:
                    prefix_part = full_txt[: full_txt.find(m_num.group(1))]
                    line_num = re.sub(r"[^\d]", "", prefix_part) or None
                    code_str = m_num.group(1).strip()
                    # Estimar code_x0 a partir de espacios o posición del span
                    leading_spaces = len(m_num.group(1)) - len(m_num.group(1).lstrip(" "))
                    code_x0 = first_x0 + 14.0 + (leading_spaces * 4.0)
                    raw_lines.append((y0, code_x0, line_num, code_str))
                else:
                    raw_lines.append((y0, first_x0, None, full_txt))

        if not raw_lines and fallback_text:
            for idx, ln_str in enumerate(fallback_text.splitlines()):
                if ln_str.strip():
                    raw_lines.append((float(idx * 12), 0.0, None, ln_str.strip()))

        raw_lines.sort(key=lambda item: (round(item[0], 1), item[1]))

        title = "Algorithm"
        algo_id: Optional[str] = None
        start_idx = 0

        if raw_lines:
            first_code = raw_lines[0][3].strip()
            m_hdr = ALGORITHM_HEADER_RE.match(first_code)
            if m_hdr:
                algo_id = m_hdr.group(1)
                rest_title = _clean_algo_code(m_hdr.group(2))
                title = f"Algorithm {algo_id}: {rest_title}" if rest_title else f"Algorithm {algo_id}"
                start_idx = 1

        body_tuples = raw_lines[start_idx:]
        if not body_tuples:
            md = f"**{title}**"
            return AlgorithmResult(title=title, algorithm_id=algo_id, lines=[], formatted_markdown=md)

        # Determinar el margen base x_min de las instrucciones de código (excluyendo specs si están pegadas al borde)
        code_x0_candidates = [
            x0 for (_, x0, _, c_txt) in body_tuples
            if not _SPEC_KEYWORD_RE.match(c_txt)
        ]
        base_x0 = min(code_x0_candidates) if code_x0_candidates else min(x[1] for x in body_tuples)

        # Detectar si el algoritmo usa cierres explícitos (end, end for, end if, until)
        has_explicit_closures = any(
            _BLOCK_CLOSE_RE.match(_clean_algo_code(raw_c))
            for (_, _, _, raw_c) in body_tuples
        )

        structured_lines: List[AlgorithmLine] = []
        logical_depth = 0

        for _, code_x0, line_num, raw_code in body_tuples:
            clean_code = _clean_algo_code(raw_code)
            if not clean_code:
                continue

            m_spec = _SPEC_KEYWORD_RE.match(clean_code)
            if m_spec and logical_depth == 0:
                spec_label = m_spec.group(1).capitalize()
                spec_body = m_spec.group(2).strip()
                structured_lines.append(AlgorithmLine(
                    line_number=line_num,
                    indent_level=0,
                    code=f"{spec_label}: {spec_body}",
                    is_spec=True,
                    raw_x0=code_x0,
                ))
                continue

            # Si es una instrucción de cierre (end, end for, end if, until) o intermedia (else), reducir nivel antes
            is_close = bool(_BLOCK_CLOSE_RE.match(clean_code))
            is_mid = bool(_BLOCK_MID_RE.match(clean_code))

            if is_close or is_mid:
                logical_depth = max(0, logical_depth - 1)

            # Calcular nivel físico por desplazamiento horizontal Δx (paso típico 12pt = 1.2em)
            dx = max(0.0, code_x0 - base_x0)
            phys_indent = int(round(dx / max(12.0, self.indent_step_pt)))

            if has_explicit_closures:
                effective_indent = logical_depth
            else:
                effective_indent = max(phys_indent, logical_depth)
            effective_indent = min(effective_indent, 8)

            structured_lines.append(AlgorithmLine(
                line_number=line_num,
                indent_level=effective_indent,
                code=clean_code,
                is_spec=False,
                raw_x0=code_x0,
            ))

            # Si abre un bloque (for ... do, while ... do, if ... then) o es else, incrementar profundidad
            is_open = bool(_BLOCK_OPEN_RE.match(clean_code)) and not re.search(r"\bend\b", clean_code, re.IGNORECASE)
            if is_open or is_mid:
                logical_depth += 1

        # Renderizar a Markdown estructurado
        md_lines = [f"**{title}**", "```text"]
        for idx, al in enumerate(structured_lines, 1):
            indent_spaces = "    " * al.indent_level
            if al.is_spec:
                md_lines.append(f"{al.code}")
            elif al.line_number is not None:
                num_prefix = f"{al.line_number:>2}: "
                md_lines.append(f"{num_prefix}{indent_spaces}{al.code}")
            else:
                md_lines.append(f"{indent_spaces}{al.code}")
        md_lines.append("```")

        return AlgorithmResult(
            title=title,
            algorithm_id=algo_id,
            lines=structured_lines,
            formatted_markdown="\n".join(md_lines),
            confidence=0.96,
        )
