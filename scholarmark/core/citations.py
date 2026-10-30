"""
Bibliography Parser & Bidirectional Citation Graph Linker for ScholarMark v3.2.
Extracts structured ReferenceEntry objects from IEEE/APA reference sections, resolves
citation ranges ([1]-[4], [2, 5], Author et al. (2024)), and links quantitative claims
(%, ms, FPS, GFLOPs, dB, mm) to their exact cited reference IDs and page coordinates.
"""

from dataclasses import dataclass, field
import re
from typing import List, Optional, Dict, Any, Set, Tuple

from ..ir.document import DocumentIR, Block


_REF_SECTION_RE = re.compile(
    r"\b(?:REFERENCES|BIBLIOGRAPHY|REFERENCIAS|LITERATURE\s+CITED)\b",
    re.IGNORECASE,
)
_DOI_RE = re.compile(r"\b(10\s*\.\s*\d{4,9}\s*/\s*[-._;()/:A-Za-z0-9]+(?:\s*[-._/]\s*[-._;()/:A-Za-z0-9]+)*)")
_YEAR_RE = re.compile(r"\b(19[5-9]\d|20[0-3]\d)\b")
_QUOTED_TITLE_RE = re.compile(
    r'(?:["“”]|‘{1,2}|`{1,2})\s*([^"“”’\']{8,260}?)\s*(?:["“”]|’{1,2}|\'{1,2})'
)
_METRIC_TOKEN_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:%|(?:ms|s|FPS|fps|Hz|kHz|GFLOPs|MFLOPs|MB|GB|params|dB|mm|mAP)\b)"
)

# Patrones de citas en texto: [1], [1, 2], [1]-[4], [1–4], [2]–[5]
_BRACKET_RANGE_SEPARATED_RE = re.compile(r"\[(\d{1,3})\]\s*[-–—]\s*\[(\d{1,3})\]")
_BRACKET_GROUP_RE = re.compile(r"\[(\d{1,3}(?:\s*[,;–—\-]\s*\d{1,3})*)\]")
_APA_INLINE_CITE_RE = re.compile(
    r"\b([A-ZÁÉÍÓÚÑ][a-záéíóúñA-Z\-]+)(?:\s+et\s+al\.)?(?:\s+(?:and|&|y)\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñA-Z\-]+)?\s*\(\s*(19[5-9]\d|20[0-3]\d)[a-z]?\s*\)"
)
_APA_PAREN_CITE_RE = re.compile(
    r"\(\s*([A-ZÁÉÍÓÚÑ][a-záéíóúñA-Z\-]+)(?:\s+et\s+al\.)?(?:\s+(?:and|&|y)\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñA-Z\-]+)?\s*,\s*(19[5-9]\d|20[0-3]\d)[a-z]?\s*\)"
)


_SUPERSCRIPT_CITE_RE = re.compile(
    r"(?<=[a-zA-Z0-9\.,;:\)\]])\^\{(\d+(?:\s*[\-–—]\s*\d+)?(?:\s*,\s*\d+(?:\s*[\-–—]\s*\d+)?)*)\}"
)
_UNICODE_SUPERSCRIPTS = {
    "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
    "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
    "⁻": "-", "–": "-", "—": "-", ",": ","
}
_UNICODE_SUPER_RE = re.compile(
    r"(?<=[a-zA-Z0-9\.,;:\)\]])([¹²³⁴⁵⁶⁷⁸⁹⁰]+(?:\s*[⁻–—]\s*[¹²³⁴⁵⁶⁷⁸⁹⁰]+)?(?:\s*,\s*[¹²³⁴⁵⁶⁷⁸⁹⁰]+(?:\s*[⁻–—]\s*[¹²³⁴⁵⁶⁷⁸⁹⁰]+)?)*)"
)


@dataclass
class ReferenceEntry:
    """Entrada bibliográfica canónica extraída de la sección References."""
    ref_id: str
    raw_text: str
    authors: str = ""
    year: Optional[int] = None
    title: str = ""
    venue: str = ""
    doi: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ref_id": self.ref_id,
            "authors": self.authors,
            "year": self.year,
            "title": self.title,
            "venue": self.venue,
            "doi": self.doi,
            "raw_text": self.raw_text,
        }


@dataclass
class GroundedClaim:
    """Afirmación del documento anclada a métricas cuantitativas y citas bibliográficas."""
    sentence: str
    page: int
    block_id: str
    metrics: List[str] = field(default_factory=list)
    cited_ref_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sentence": self.sentence,
            "page": self.page,
            "block_id": self.block_id,
            "metrics": self.metrics,
            "cited_ref_ids": self.cited_ref_ids,
        }


def expand_citation_markers(
    text: str,
    known_references: Optional[List[ReferenceEntry]] = None
) -> List[str]:
    """
    Extrae y expande todas las citas presentes en un fragmento de texto.
    Soporta rangos IEEE ([1]-[3], [1–3], [1, 4-6]), citas APA (Autor et al., 2024),
    y superíndices Vancouver/Nature (^{12-15}, ¹²⁻¹⁵) con validación O(1) contra bibliografía.
    """
    if not text:
        return []

    found_ids: List[str] = []
    seen: Set[str] = set()
    valid_ref_ids: Set[str] = {r.ref_id for r in known_references} if known_references else set()

    def _add(cid: str):
        if cid not in seen:
            seen.add(cid)
            found_ids.append(cid)

    # 1. Rangos con corchetes separados: [2]–[5] o [2]-[5]
    work_text = text
    for m in _BRACKET_RANGE_SEPARATED_RE.finditer(work_text):
        start_n, end_n = int(m.group(1)), int(m.group(2))
        if 1 <= start_n <= end_n <= (start_n + 50):
            for n in range(start_n, end_n + 1):
                _add(str(n))

    # 2. Grupos entre corchetes: [1], [1, 3, 5], [2-5], [1, 3–5]
    for m in _BRACKET_GROUP_RE.finditer(work_text):
        inner = m.group(1)
        parts = re.split(r"\s*[,;]\s*", inner)
        for p in parts:
            p = p.strip()
            m_rng = re.fullmatch(r"(\d{1,3})\s*[-–—]\s*(\d{1,3})", p)
            if m_rng:
                s_n, e_n = int(m_rng.group(1)), int(m_rng.group(2))
                if 1 <= s_n <= e_n <= (s_n + 50):
                    for n in range(s_n, e_n + 1):
                        _add(str(n))
            elif p.isdigit():
                val = int(p)
                if 1 <= val <= 500:
                    _add(str(val))

    # 3. Citas APA autor-año: (Zhang et al., 2024) o Zhang et al. (2024)
    apa_candidates = _APA_PAREN_CITE_RE.findall(work_text) + _APA_INLINE_CITE_RE.findall(work_text)
    for surname, yr_str in apa_candidates:
        yr = int(yr_str)
        matched_ref = False
        if known_references:
            for ref in known_references:
                if ref.year == yr and surname.lower() in (ref.authors or ref.raw_text).lower():
                    _add(ref.ref_id)
                    matched_ref = True
        if not matched_ref:
            _add(f"{surname}{yr}")

    # 4. Superíndices LaTeX: ^{1,3-5} o ^{12}
    for m in _SUPERSCRIPT_CITE_RE.finditer(work_text):
        start_idx = m.start()
        prefix = work_text[:start_idx].rstrip()
        is_math_exponent = False
        m_base = re.search(r"([a-zA-Z0-9\.,;:\)\]]+)$", prefix)
        if m_base:
            base_token = m_base.group(1)
            if (
                (len(base_token) <= 2 and base_token.isalpha())
                or base_token == "10"
                or bool(re.search(r"[=+\-*/]\s*[a-zA-Z0-9]+$", prefix))
            ):
                is_math_exponent = True

        if not is_math_exponent:
            inner = m.group(1)
            parts = re.split(r"\s*,\s*", inner)
            parsed_ids = []
            for p in parts:
                p = p.strip()
                m_rng = re.fullmatch(r"(\d{1,3})\s*[-–—]\s*(\d{1,3})", p)
                if m_rng:
                    s_n, e_n = int(m_rng.group(1)), int(m_rng.group(2))
                    if 1 <= s_n <= e_n <= (s_n + 50):
                        parsed_ids.extend(str(n) for n in range(s_n, e_n + 1))
                elif p.isdigit():
                    parsed_ids.append(p)

            if valid_ref_ids:
                for pid in parsed_ids:
                    if pid in valid_ref_ids:
                        _add(pid)
            else:
                has_punct = prefix.endswith((".", ",", ";", ":", ")", "]"))
                has_word = bool(re.search(r"[a-zA-Z]{2,}$", prefix))
                if has_punct or has_word:
                    for pid in parsed_ids:
                        if 1 <= int(pid) <= 500:
                            _add(pid)

    # 5. Superíndices Unicode directos: ¹²⁻¹⁵
    for m in _UNICODE_SUPER_RE.finditer(work_text):
        start_idx = m.start()
        prefix = work_text[:start_idx].rstrip()
        is_math_exponent = False
        m_base = re.search(r"([a-zA-Z0-9\.,;:\)\]]+)$", prefix)
        if m_base:
            base_token = m_base.group(1)
            if (len(base_token) == 1 and base_token.isalpha()) or base_token == "10":
                is_math_exponent = True

        if not is_math_exponent:
            raw_str = m.group(1)
            ascii_str = "".join(_UNICODE_SUPERSCRIPTS.get(ch, ch) for ch in raw_str)
            parts = re.split(r"\s*,\s*", ascii_str)
            parsed_ids = []
            for p in parts:
                p = p.strip()
                m_rng = re.fullmatch(r"(\d{1,3})\s*[-–—]\s*(\d{1,3})", p)
                if m_rng:
                    s_n, e_n = int(m_rng.group(1)), int(m_rng.group(2))
                    if 1 <= s_n <= e_n <= (s_n + 50):
                        parsed_ids.extend(str(n) for n in range(s_n, e_n + 1))
                elif p.isdigit():
                    parsed_ids.append(p)

            if valid_ref_ids:
                for pid in parsed_ids:
                    if pid in valid_ref_ids:
                        _add(pid)
            else:
                has_punct = prefix.endswith((".", ",", ";", ":", ")", "]"))
                has_word = bool(re.search(r"[a-zA-Z]{2,}$", prefix))
                if (has_punct or has_word) and parsed_ids:
                    for pid in parsed_ids:
                        if 1 <= int(pid) <= 500:
                            _add(pid)

    return found_ids


class BibliographyParser:
    """
    Analizador de secciones de referencias bibliográficas (IEEE numeradas y APA autor-año).
    """

    @staticmethod
    def _parse_single_entry(ref_id: str, raw_body: str) -> ReferenceEntry:
        clean_body = " ".join(raw_body.split()).strip()
        clean_body = re.sub(
            r"\s+[A-Z][A-Za-z.\-\s]{2,45}\s+received\s+the\s+(?:B\.S\.|M\.S\.|Ph\.D\.|B\.E\.|M\.E\.|B\.Tech|M\.Tech|bachelor|master|doctor).+$",
            "",
            clean_body,
            flags=re.IGNORECASE,
        ).strip()
        doi_m = _DOI_RE.search(clean_body)
        doi = re.sub(r"\s+", "", doi_m.group(1)).rstrip(".,;") if doi_m else None

        years = [int(y) for y in _YEAR_RE.findall(clean_body)]
        year = years[-1] if years else None

        title = ""
        authors = ""
        venue = ""

        # Formato IEEE con título entre comillas ("...", “...”, ‘‘...’’):
        q_m = _QUOTED_TITLE_RE.search(clean_body)
        if q_m:
            title = q_m.group(1).strip().rstrip(",.")
            authors = clean_body[: q_m.start()].strip().rstrip(",.")
            after_title = clean_body[q_m.end() :].strip().lstrip(",.")
            venue = after_title
        else:
            # Formato APA: Apellido, N. (2024). Título del artículo. Nombre de Revista, ...
            apa_m = re.match(r"^(.+?)\s*\(\s*(19[5-9]\d|20[0-3]\d)[a-z]?\s*\)\.?\s*(.+)$", clean_body)
            if apa_m:
                authors = apa_m.group(1).strip().rstrip(",.")
                year = int(apa_m.group(2))
                rest = apa_m.group(3).strip()
                segs = [s.strip() for s in re.split(r"(?<![A-Z])\.\s+", rest) if s.strip()]
                if segs:
                    title = segs[0]
                if len(segs) >= 2:
                    venue = ". ".join(segs[1:])
            else:
                # Separación por puntos ignorando iniciales de nombres (ej. "D. Mehta")
                segs = [s.strip() for s in re.split(r"(?<![A-Z])\.\s+", clean_body) if len(s.strip()) > 3]
                if len(segs) >= 2:
                    authors = segs[0]
                    title = segs[1]
                    venue = ". ".join(segs[2:]) if len(segs) >= 3 else ""
                else:
                    authors = clean_body[:60]
                    title = clean_body

        return ReferenceEntry(
            ref_id=ref_id,
            raw_text=clean_body,
            authors=authors,
            year=year,
            title=title,
            venue=venue,
            doi=doi,
        )

    @classmethod
    def parse_from_text(cls, references_text: str) -> List[ReferenceEntry]:
        """Extrae entradas bibliográficas desde un bloque de texto de la sección References."""
        if not references_text or not references_text.strip():
            return []

        text = references_text.strip()
        entries: List[ReferenceEntry] = []

        # 1. Intentar segmentación por marcadores IEEE [1], [2], ... (incluso si están en el mismo párrafo)
        bracket_splits = list(re.finditer(r"(?:^|\s)\[(\d{1,3})\]\s+", text))
        if len(bracket_splits) >= 1:
            for idx, m in enumerate(bracket_splits):
                ref_id = m.group(1)
                start_pos = m.end()
                end_pos = bracket_splits[idx + 1].start() if (idx + 1) < len(bracket_splits) else len(text)
                body = text[start_pos:end_pos].strip()
                if len(body) >= 10:
                    entries.append(cls._parse_single_entry(ref_id, body))
            if entries:
                return entries

        # 2. Intentar segmentación por líneas numeradas "1. Autor..." o APA por líneas
        lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
        cur_id: Optional[str] = None
        cur_buf: List[str] = []
        auto_idx = 1

        for ln in lines:
            m_num = re.match(r"^(\d{1,3})\.\s+([A-ZÁÉÍÓÚÑ].+)$", ln)
            m_apa = re.match(r"^([A-ZÁÉÍÓÚÑ][a-záéíóúñA-Z\-]+,\s*[A-Z]\..*\(\d{4}\).*)$", ln)
            if m_num:
                if cur_buf and cur_id:
                    entries.append(cls._parse_single_entry(cur_id, " ".join(cur_buf)))
                cur_id = m_num.group(1)
                cur_buf = [m_num.group(2)]
            elif m_apa:
                if cur_buf and cur_id:
                    entries.append(cls._parse_single_entry(cur_id, " ".join(cur_buf)))
                surname = ln.split(",", 1)[0].strip()
                yr_m = _YEAR_RE.search(ln)
                cur_id = f"{surname}{yr_m.group(1)}" if yr_m else str(auto_idx)
                auto_idx += 1
                cur_buf = [ln]
            else:
                if cur_buf:
                    cur_buf.append(ln)
                else:
                    cur_id = str(auto_idx)
                    auto_idx += 1
                    cur_buf = [ln]

        if cur_buf and cur_id and len(" ".join(cur_buf)) >= 12:
            entries.append(cls._parse_single_entry(cur_id, " ".join(cur_buf)))

        return entries

    @classmethod
    def parse_from_ir(cls, ir: DocumentIR) -> List[ReferenceEntry]:
        """Localiza la sección References dentro de un DocumentIR y extrae todas sus entradas."""
        blocks = ir.all_blocks_ordered()
        in_refs = False
        ref_texts: List[str] = []

        for b in blocks:
            if b.kind == "section_header":
                if _REF_SECTION_RE.search(b.text or ""):
                    in_refs = True
                    continue
                elif in_refs:
                    # Otra sección posterior (ej. Appendix o Author Biographies)
                    break
            if in_refs and b.kind in ("text", "list") and b.text:
                ref_texts.append(b.text.strip())

        if not ref_texts:
            # Respaldo: buscar bloques al final del documento que comiencen con "[1]"
            for b in blocks:
                if b.kind in ("text", "list") and b.text and re.match(r"^\s*\[1\]\s+", b.text):
                    ref_texts.append(b.text.strip())

        if not ref_texts:
            return []

        return cls.parse_from_text("\n".join(ref_texts))


class CitationLinker:
    """
    Construye el grafo bidireccional de citas entre bloques del documento,
    oraciones con métricas cuantitativas y entradas bibliográficas de References.
    """

    @staticmethod
    def link_document_ir(ir: DocumentIR) -> Tuple[List[ReferenceEntry], List[GroundedClaim]]:
        """
        Analiza el DocumentIR completo:
        1. Extrae la bibliografía estructurada.
        2. Anota cada bloque con `b.metadata["citations"]`.
        3. Extrae las afirmaciones cuantitativas (`GroundedClaim`) vinculadas a sus citas.
        """
        references = BibliographyParser.parse_from_ir(ir)
        claims: List[GroundedClaim] = []

        blocks = ir.all_blocks_ordered()
        in_refs = False

        for b in blocks:
            if b.kind == "section_header" and _REF_SECTION_RE.search(b.text or ""):
                in_refs = True
                continue
            if in_refs:
                continue

            # Construir texto inspeccionable del bloque (incluyendo captions y títulos de algoritmos)
            candidate_texts = [
                b.text or "",
                b.caption_text or "",
                str(b.metadata.get("algorithm_title") or ""),
            ]
            combined = " ".join(t for t in candidate_texts if t).strip()
            if not combined:
                continue

            block_cites = expand_citation_markers(combined, known_references=references)
            if block_cites:
                b.metadata["citations"] = block_cites

            # Segmentar en oraciones para extraer GroundedClaims (oraciones con métricas o citas)
            sentences = re.split(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ0-9\[])", combined)
            for sent in sentences:
                sent_clean = " ".join(sent.split()).strip()
                if len(sent_clean) < 15:
                    continue
                metrics = _METRIC_TOKEN_RE.findall(sent_clean)
                sent_cites = expand_citation_markers(sent_clean, known_references=references)
                if metrics or sent_cites:
                    claims.append(GroundedClaim(
                        sentence=sent_clean,
                        page=b.page,
                        block_id=b.id,
                        metrics=metrics,
                        cited_ref_ids=sent_cites,
                    ))

        ir.meta["bibliography"] = [r.to_dict() for r in references]
        ir.meta["grounded_claims"] = [c.to_dict() for c in claims[:50]]
        return references, claims
