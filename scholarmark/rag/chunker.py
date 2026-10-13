"""
DocumentIR-Aware Hierarchical Semantic Chunker for ScholarMark v4.0.
Partitions scientific papers into self-contained RAG chunks that:
1. Never split atomic blocks (tables, 2D formulas, algorithms, lists, figures).
2. Preserve hierarchical section breadcrumbs (H2 > H3) and exact (page, bbox) coordinates.
3. Hydrate cited_references in O(1) from the v3.2 Citation Graph.
4. Resolve in-text cross-references (Fig. N, Table N/Roman, Algorithm N, Eq. (N)) into linked_elements.
5. Segregate IEEE Author Biographies under a dedicated ["Author Biographies"] section path.
"""

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import List, Optional, Dict, Any, Set

from ..core.citations import expand_citation_markers, ReferenceEntry
from ..ir.document import DocumentIR, Block


_FIG_REF_RE = re.compile(r"\b(?:Fig\.?|Figure|Figura)\s*(\d+[a-zA-Z]?)\b", re.IGNORECASE)
_TAB_REF_RE = re.compile(r"\b(?:Table|Tab\.?|Tabla|Cuadro)\s*([0-9IVX]+)\b", re.IGNORECASE)
_ALGO_REF_RE = re.compile(r"\b(?:Algorithm|Alg\.?|Algoritmo|Procedure)\s*([0-9IVX]+)\b", re.IGNORECASE)
_EQ_REF_RE = re.compile(r"\b(?:Eq\.?|Equation|Ecuación)\s*\(?\s*(\d+[a-zA-Z]?)\s*\)?", re.IGNORECASE)
_EQ_TRAIL_TAG_RE = re.compile(r"\((\d+[a-zA-Z]?)\)\s*$")
_AUTHOR_BIO_TEXT_RE = re.compile(
    r"\b(?:received\s+the\s+(?:B\.S\.|M\.S\.|Ph\.D\.|B\.Eng\.|M\.Eng\.)\s+degree|research\s+interests\s+include|is\s+currently\s+a(?:n)?\s+(?:Professor|Associate\s+Professor|Assistant\s+Professor|Postdoctoral|Fellow))\b",
    re.IGNORECASE,
)
_METRIC_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:%|(?:ms|s|FPS|GFLOPs|MFLOPs|MB|GB|dB|mAP|IoU|Hz|kHz|MHz|GHz|mm|cm)\b)"
)


@dataclass
class SemanticChunk:
    """Unidad semántica autocontenida y verificable para Scientific RAG."""
    chunk_id: str
    doc_id: str
    title: str
    section_path: List[str]
    text: str
    pages: List[int] = field(default_factory=list)
    bboxes: List[Dict[str, Any]] = field(default_factory=list)
    block_kinds: List[str] = field(default_factory=list)
    cited_references: List[Dict[str, Any]] = field(default_factory=list)
    linked_elements: List[Dict[str, Any]] = field(default_factory=list)
    metrics: List[str] = field(default_factory=list)

    @property
    def section_hierarchy(self) -> List[str]:
        return self.section_path

    @property
    def citations(self) -> List[Dict[str, Any]]:
        return self.cited_references

    @property
    def chunk_type(self) -> str:
        if len(self.block_kinds) == 1 and self.block_kinds[0] in ("table", "figure", "algorithm", "formula"):
            return self.block_kinds[0]
        return "prose"

    @property
    def related_figures(self) -> List[Dict[str, Any]]:
        return [e for e in self.linked_elements if e.get("type") == "figure"]

    @property
    def related_tables(self) -> List[Dict[str, Any]]:
        return [e for e in self.linked_elements if e.get("type") == "table"]

    @property
    def related_algorithms(self) -> List[Dict[str, Any]]:
        return [e for e in self.linked_elements if e.get("type") == "algorithm"]

    @property
    def related_equations(self) -> List[Dict[str, Any]]:
        return [e for e in self.linked_elements if e.get("type") == "formula"]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "title": self.title,
            "chunk_type": self.chunk_type,
            "section_path": self.section_path,
            "section_hierarchy": self.section_path,
            "text": self.text,
            "char_count": len(self.text),
            "pages": self.pages,
            "bboxes": self.bboxes,
            "block_kinds": self.block_kinds,
            "metrics": self.metrics,
            "cited_references": self.cited_references,
            "citations": self.cited_references,
            "linked_elements": self.linked_elements,
            "related_figures": self.related_figures,
            "related_tables": self.related_tables,
            "related_algorithms": self.related_algorithms,
            "related_equations": self.related_equations,
        }


def _render_block_for_chunk(b: Block) -> str:
    """Serializa un bloque individual para su inclusión íntegra (atómica) dentro de un SemanticChunk."""
    if b.kind == "title":
        return f"# {b.text.strip()}" if b.text else ""
    if b.kind in ("section_header", "heading"):
        lvl = max(2, min(4, b.heading_level))
        return f"{'#' * lvl} {b.text.strip()}" if b.text else ""
    if b.kind == "formula":
        latex = (b.latex or b.text or "").strip()
        tag = b.metadata.get("tag")
        if tag and r"\tag{" not in latex:
            latex = f"{latex} \\tag{{{tag}}}"
        return f"$$\n{latex}\n$$" if latex else ""
    if b.kind == "table":
        parts = []
        if b.caption_text:
            parts.append(f"**{b.caption_text.strip()}**")
        if b.html and b.metadata.get("has_merged_cells"):
            parts.append(b.html.strip())
        elif b.gfm:
            parts.append(b.gfm.strip())
        elif b.html:
            parts.append(b.html.strip())
        elif b.text:
            parts.append(b.text.strip())
        return "\n".join(parts)
    if b.kind == "algorithm":
        return (b.gfm or b.text or getattr(b, "code", "") or "").strip()
    if b.kind == "figure":
        cap = (b.caption_text or b.text or f"Figure p.{b.page}").strip()
        lines = [f"[Figure: {cap}]"]
        c_sem = b.metadata.get("chart_semantics") or {}
        if c_sem:
            if c_sem.get("axis_labels"):
                lines.append(f"Axes: {', '.join(c_sem['axis_labels'])}")
            if c_sem.get("legend_series"):
                lines.append(f"Series: {', '.join(c_sem['legend_series'])}")
            if c_sem.get("data_annotations"):
                lines.append(f"Values: {', '.join(c_sem['data_annotations'])}")
        return " | ".join(lines)
    return (b.text or "").strip()


class SemanticChunker:
    """
    Particionador jerárquico consciente de DocumentIR (ScholarMark v4.0).
    """

    def __init__(self, max_chars: int = 1800):
        self.max_chars = max(300, max_chars)

    @staticmethod
    def _build_artifact_index(blocks: List[Block]) -> Dict[str, Dict[str, Any]]:
        """
        Pre-indexa tablas, figuras, algoritmos y ecuaciones por su identificador canónico
        (ej. 'fig:3', 'table:1', 'table:I', 'algo:1', 'eq:1') para resolución cruzada O(1).
        """
        index: Dict[str, Dict[str, Any]] = {}

        for b in blocks:
            if b.kind == "figure":
                cap = b.caption_text or b.text or ""
                m = _FIG_REF_RE.search(cap)
                if m:
                    fid = m.group(1).lower()
                    index[f"fig:{fid}"] = {
                        "type": "figure",
                        "ref_key": f"Fig. {m.group(1)}",
                        "block_id": b.id,
                        "page": b.page,
                        "caption": cap,
                        "asset": b.asset,
                        "asset_path": b.asset,
                        "chart_semantics": b.metadata.get("chart_semantics"),
                    }
            elif b.kind == "table":
                cap = b.caption_text or b.text or ""
                m = _TAB_REF_RE.search(cap)
                if m:
                    tid = m.group(1).upper()
                    index[f"table:{tid}"] = {
                        "type": "table",
                        "ref_key": f"Table {m.group(1)}",
                        "block_id": b.id,
                        "page": b.page,
                        "caption": cap,
                        "has_merged_cells": b.metadata.get("has_merged_cells", False),
                    }
            elif b.kind == "algorithm":
                aid = str(b.metadata.get("algorithm_id") or "").strip().upper()
                cap = b.caption_text or b.gfm or b.text or ""
                if not aid:
                    m_alg = _ALGO_REF_RE.search(cap)
                    if m_alg:
                        aid = m_alg.group(1).upper()
                if aid:
                    title = b.metadata.get("algorithm_title") or cap.splitlines()[0] if cap else f"Algorithm {aid}"
                    index[f"algo:{aid}"] = {
                        "type": "algorithm",
                        "ref_key": f"Algorithm {aid}",
                        "block_id": b.id,
                        "page": b.page,
                        "title": title,
                        "caption": title,
                    }
            elif b.kind == "formula":
                raw_latex = b.latex or b.text or ""
                tag = str(b.metadata.get("tag") or "").strip().lower()
                if not tag:
                    m_eq = _EQ_TRAIL_TAG_RE.search(raw_latex.strip())
                    if m_eq:
                        tag = m_eq.group(1).lower()
                if tag:
                    index[f"eq:{tag}"] = {
                        "type": "formula",
                        "ref_key": f"Eq. ({tag})",
                        "block_id": b.id,
                        "page": b.page,
                        "latex": raw_latex,
                    }

        return index

    @staticmethod
    def _resolve_cross_references(text: str, artifact_index: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Busca menciones a Fig. X, Table Y, Algorithm Z o Eq. (W) y retorna sus descriptores."""
        linked: List[Dict[str, Any]] = []
        seen_keys: Set[str] = set()

        def _try_add(key: str):
            if key not in seen_keys and key in artifact_index:
                seen_keys.add(key)
                linked.append(artifact_index[key])

        for m in _FIG_REF_RE.finditer(text):
            _try_add(f"fig:{m.group(1).lower()}")
        for m in _TAB_REF_RE.finditer(text):
            _try_add(f"table:{m.group(1).upper()}")
        for m in _ALGO_REF_RE.finditer(text):
            _try_add(f"algo:{m.group(1).upper()}")
        for m in _EQ_REF_RE.finditer(text):
            _try_add(f"eq:{m.group(1).lower()}")

        return linked

    def chunk_document(self, ir: DocumentIR, doc_id: str = "document") -> List[SemanticChunk]:
        """
        Genera la lista ordenada de SemanticChunk a partir de un DocumentIR.
        """
        blocks = ir.all_blocks_ordered()
        title = str(ir.meta.get("title") or getattr(ir, "title", None) or doc_id)

        # Índice O(1) de bibliografía (Ajuste A de Gate 2)
        raw_bib = ir.meta.get("bibliography") or []
        bib_by_id: Dict[str, Dict[str, Any]] = {
            str(entry.get("ref_id")): entry
            for entry in raw_bib
            if isinstance(entry, dict) and entry.get("ref_id")
        }
        ref_objs = [
            ReferenceEntry(
                ref_id=str(e.get("ref_id", "")),
                raw_text=str(e.get("raw_text", "")),
                authors=str(e.get("authors", "")),
                year=e.get("year"),
                title=str(e.get("title", "")),
                venue=str(e.get("venue", "")),
                doi=e.get("doi"),
            )
            for e in raw_bib
            if isinstance(e, dict)
        ]

        # Índice O(1) de artefactos cruzados (Ajuste B de Gate 2)
        artifact_index = self._build_artifact_index(blocks)

        consumed_caption_ids: Set[str] = {
            b.caption_id for b in blocks if b.caption_id and b.kind in ("figure", "table", "formula")
        }

        chunks: List[SemanticChunk] = []
        current_section_path: List[str] = ["Introduction"]
        buf_blocks: List[Block] = []
        buf_texts: List[str] = []
        buf_chars: int = 0

        def _flush_buffer(override_path: Optional[List[str]] = None):
            nonlocal buf_blocks, buf_texts, buf_chars
            if not buf_blocks or not buf_texts:
                buf_blocks = []
                buf_texts = []
                buf_chars = 0
                return

            chunk_idx = len(chunks) + 1
            chunk_text = "\n\n".join(buf_texts).strip()
            pages = sorted({b.page for b in buf_blocks})
            bboxes = [
                {
                    "page": b.page,
                    "bbox": [round(b.bbox.x0, 2), round(b.bbox.y0, 2), round(b.bbox.x1, 2), round(b.bbox.y1, 2)],
                    "block_id": b.id,
                    "kind": b.kind,
                }
                for b in buf_blocks
            ]
            kinds = [b.kind for b in buf_blocks]

            # Recolectar citas bibliográficas del chunk (desde metadata + respaldo por regex)
            cite_ids: List[str] = []
            seen_cites: Set[str] = set()
            for b in buf_blocks:
                for cid in b.metadata.get("citations", []):
                    if cid not in seen_cites:
                        seen_cites.add(cid)
                        cite_ids.append(cid)
            for cid in expand_citation_markers(chunk_text, known_references=ref_objs):
                if cid not in seen_cites:
                    seen_cites.add(cid)
                    cite_ids.append(cid)

            cited_refs = [
                bib_by_id[cid] if cid in bib_by_id else {"ref_id": cid}
                for cid in cite_ids
            ]

            linked = self._resolve_cross_references(chunk_text, artifact_index)
            metrics = sorted({m.group(0).strip() for m in _METRIC_RE.finditer(chunk_text)})

            chunks.append(SemanticChunk(
                chunk_id=f"{doc_id}_chunk_{chunk_idx:03d}",
                doc_id=doc_id,
                title=title,
                section_path=list(override_path if override_path is not None else current_section_path),
                text=chunk_text,
                pages=pages,
                bboxes=bboxes,
                block_kinds=kinds,
                cited_references=cited_refs,
                linked_elements=linked,
                metrics=metrics,
            ))
            buf_blocks = []
            buf_texts = []
            buf_chars = 0

        for b in blocks:
            if b.kind == "abandon":
                continue
            if b.id in consumed_caption_ids and b.kind in ("figure_caption", "table_caption", "formula_caption"):
                continue

            if b.kind in ("section_header", "heading"):
                _flush_buffer()
                hdr_clean = " ".join((b.text or "").split()).strip()
                if hdr_clean:
                    if b.heading_level <= 2 or not current_section_path:
                        current_section_path = [hdr_clean]
                    else:
                        current_section_path = [current_section_path[0], hdr_clean]
                continue

            # Ajuste C de Gate 2: Aislar biografías de autores IEEE en su propio chunk y ruta semántica
            is_author_bio = (b.kind == "author_bio") or (
                b.kind in ("text", "paragraph") and bool(_AUTHOR_BIO_TEXT_RE.search(b.text or ""))
            )
            if is_author_bio:
                _flush_buffer()
                rendered_bio = _render_block_for_chunk(b)
                if rendered_bio:
                    buf_blocks = [b]
                    buf_texts = [rendered_bio]
                    buf_chars = len(rendered_bio)
                    _flush_buffer(override_path=["Author Biographies"])
                continue

            # Emitir tablas, figuras, algoritmos y fórmulas como chunks atómicos dedicados
            if b.kind in ("table", "figure", "algorithm", "formula"):
                _flush_buffer()
                rendered_atomic = _render_block_for_chunk(b)
                if rendered_atomic:
                    buf_blocks = [b]
                    buf_texts = [rendered_atomic]
                    buf_chars = len(rendered_atomic)
                    _flush_buffer()
                continue

            rendered = _render_block_for_chunk(b)
            if not rendered:
                continue

            if buf_chars > 0 and (buf_chars + len(rendered) + 2) > self.max_chars:
                _flush_buffer()

            buf_blocks.append(b)
            buf_texts.append(rendered)
            buf_chars += len(rendered) + 2

        _flush_buffer()
        return chunks


def export_chunks_jsonl(
    source: Any,
    output_path: Path,
    max_chars: int = 1800,
    doc_id: str = "document",
) -> List[SemanticChunk]:
    """
    Exporta un DocumentIR o una lista de SemanticChunk hacia un archivo JSON Lines (*.chunks.jsonl)
    y retorna la lista de SemanticChunk exportados.
    """
    if isinstance(source, DocumentIR):
        chunks = SemanticChunker(max_chars=max_chars).chunk_document(source, doc_id=doc_id)
    else:
        chunks = list(source)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for ch in chunks:
            f.write(json.dumps(ch.to_dict(), ensure_ascii=False) + "\n")
    return chunks
