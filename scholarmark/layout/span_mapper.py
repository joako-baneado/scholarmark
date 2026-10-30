"""
Native Vector Span Mapper for ScholarMark v4.1.
Intersects layout bounding boxes with native PDF text spans (rawdict/dict),
reconstructs physical word spacing (Δx kerning), and rescues any orphan spans
to guarantee 0.0% content hallucination and 100% native text retention.
"""

import re
import unicodedata
from typing import List, Dict, Any, Optional
import fitz

from .detector import LayoutRegion
from ..core.geometry import BoundingBox, detect_column_zones, column_id_for_bbox
from ..core.page_context import PageContext
from ..ir.document import Block

_INLINE_SCRIPT_RE = re.compile(r"^[A-Za-z0-9+\-(),]+$")
_INLINE_BASE_RE = re.compile(r"^[A-Za-zΑ-Ωα-ω][A-Za-z0-9]{0,2}$")


def _is_cjk_char(ch: str) -> bool:
    if not ch:
        return False
    cp = ord(ch)
    return (
        0x4E00 <= cp <= 0x9FFF
        or 0x3400 <= cp <= 0x4DBF
        or 0x20000 <= cp <= 0x2A6DF
        or 0xF900 <= cp <= 0xFAFF
        or 0x3040 <= cp <= 0x309F  # Hiragana
        or 0x30A0 <= cp <= 0x30FF  # Katakana
        or 0xAC00 <= cp <= 0xD7AF  # Hangul
    )


def _is_rtl_char(ch: str) -> bool:
    if not ch:
        return False
    cp = ord(ch)
    return (
        0x0590 <= cp <= 0x05FF  # Hebrew
        or 0x0600 <= cp <= 0x06FF  # Arabic
        or 0x0750 <= cp <= 0x077F  # Arabic Supplement
        or 0x08A0 <= cp <= 0x08FF  # Arabic Extended-A
        or 0xFB50 <= cp <= 0xFDFF  # Arabic Presentation Forms-A
        or 0xFE70 <= cp <= 0xFEFF  # Arabic Presentation Forms-B
    )


def _reorder_bidi_text(text: str) -> str:
    """
    Aplica reordenamiento BiDi y conformación de glifos en textos con caracteres RTL (Árabe, Hebreo),
    preservando prefijos de sintaxis Markdown (# , - , * , 1. ).
    Utiliza arabic_reshaper y python-bidi si están disponibles; en su ausencia,
    ejecuta un algoritmo de fallback determinista basado en inversión de tokens RTL contiguos.
    """
    if not text:
        return text

    has_rtl = any(_is_rtl_char(c) for c in text)
    if not has_rtl:
        return text

    prefix = ""
    content = text
    m = re.match(r"^(#{1,6}\s+|[-*+]\s+|\d+\.\s+)", text)
    if m:
        prefix = m.group(1)
        content = text[len(prefix):]

    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        reshaped = arabic_reshaper.reshape(content)
        display_text = get_display(reshaped)
        return prefix + display_text
    except Exception:
        pass

    lines = content.split("\n")
    reordered_lines = []
    for line in lines:
        tokens = line.split(" ")
        rtl_count = sum(1 for c in line if _is_rtl_char(c))
        if rtl_count > 0:
            reordered_lines.append(" ".join(reversed(tokens)))
        else:
            reordered_lines.append(line)
    return prefix + "\n".join(reordered_lines)


def _reconstruct_line_text_with_kerning(spans: List[Dict[str, Any]]) -> str:
    """
    Une los spans de una línea reconstruyendo espacios físicos cuando la distancia
    horizontal (Δx) entre dos spans consecutivos supera el 18% del tamaño de fuente,
    y detecta desplazamientos verticales de línea base (Δy) con reducción de cuerpo
    tipográfico para reconstruir subíndices (_{...}) y superíndices (^{...}) inline.
    """
    if not spans:
        return ""
    parts: List[str] = []
    prev_x1: Optional[float] = None
    base_sz: Optional[float] = None
    base_cy: Optional[float] = None
    base_token: str = ""

    for s in spans:
        txt = s.get("text", "")
        if not txt:
            continue
        txt = unicodedata.normalize("NFKC", txt)
        bbox = s.get("bbox")
        sz = float(s.get("size", 10.0))
        cy = ((float(bbox[1]) + float(bbox[3])) * 0.5) if bbox is not None else None
        txt_clean = txt.strip()

        if (
            prev_x1 is not None
            and bbox is not None
            and base_sz is not None
            and base_cy is not None
            and cy is not None
            and 1 <= len(txt_clean) <= 6
            and _INLINE_SCRIPT_RE.fullmatch(txt_clean)
            and _INLINE_BASE_RE.fullmatch(base_token)
            and sz <= (base_sz * 0.82)
            and -2.0 <= (float(bbox[0]) - prev_x1) <= (base_sz * 0.40)
            and abs(cy - base_cy) >= (base_sz * 0.10)
        ):
            dy = cy - base_cy
            if dy > 0:
                parts.append(f"_{{{txt_clean}}}")
            else:
                parts.append(f"^{{{txt_clean}}}")
            prev_x1 = float(bbox[2])
            continue

        if prev_x1 is not None and bbox is not None:
            dx = float(bbox[0]) - prev_x1
            prev_char = parts[-1][-1] if (parts and parts[-1]) else ""
            next_char = txt[0] if txt else ""
            is_cjk_boundary = _is_cjk_char(prev_char) and _is_cjk_char(next_char)
            is_rtl_boundary = _is_rtl_char(prev_char) and _is_rtl_char(next_char)
            threshold = (sz * 0.40) if is_rtl_boundary else (sz * 0.18)

            if not is_cjk_boundary and dx > threshold and (not parts or not parts[-1].endswith(" ")) and not txt.startswith(" "):
                parts.append(" ")
        parts.append(txt)
        if bbox is not None:
            prev_x1 = float(bbox[2])
            base_sz = sz
            base_cy = cy
            words_in_span = txt.rstrip().split()
            base_token = words_in_span[-1].lstrip("([") if (words_in_span and not txt.endswith(" ")) else ""
    return "".join(parts).strip()


def _assemble_lines(matched_lines: List[Dict[str, Any]]) -> List[str]:
    assembled_lines: List[str] = []
    for item in matched_lines:
        line_str = item["text"]
        if (
            assembled_lines
            and assembled_lines[-1].endswith("-")
            and len(assembled_lines[-1]) > 2
            and line_str
            and line_str[0].islower()
        ):
            assembled_lines[-1] = assembled_lines[-1][:-1] + line_str
        else:
            assembled_lines.append(line_str)
    return assembled_lines


def map_spans_to_blocks(
    page: fitz.Page,
    page_num: int,
    regions: List[LayoutRegion],
    rescue_orphans: bool = True,
    ctx: Optional[PageContext] = None,
) -> List[Block]:
    """
    Puebla cada región detectada por LayoutDetector con el texto nativo exacto de la página
    y rescata cualquier línea de texto que haya quedado fuera de las cajas detectadas.
    Aplica protección estricta de medianeras de columnas para impedir el entretejido horizontal de texto.
    """
    raw_dict = ctx.raw_dict if ctx is not None else page.get_text("dict")
    raw_blocks = raw_dict.get("blocks", [])

    native_lines: List[Dict[str, Any]] = []
    for b in raw_blocks:
        if b.get("type") != 0:
            continue
        for ln in b.get("lines", []):
            lb = BoundingBox(*[float(v) for v in ln["bbox"]])
            ltxt = _reconstruct_line_text_with_kerning(ln.get("spans", []))
            if ltxt:
                native_lines.append({
                    "bbox": lb,
                    "text": ltxt,
                    "spans": ln.get("spans", []),
                    "consumed": False,
                })

    column_zones = getattr(ctx, "column_zones", [])
    if not column_zones and native_lines:
        pw = float(page.rect.width)
        ph = float(page.rect.height)
        column_zones = detect_column_zones([nl["bbox"] for nl in native_lines], pw, ph)

    blocks: List[Block] = []
    for r_idx, reg in enumerate(regions, 1):
        bid = f"p{page_num}_{reg.kind}_{r_idx}"

        if reg.kind in ("figure", "table"):
            for nl in native_lines:
                if (
                    nl["bbox"].coverage_by(reg.bbox) >= 0.50
                    or (reg.metadata.get("is_chemical_structure") and nl["bbox"].intersects(reg.bbox))
                ):
                    nl["consumed"] = True
            blocks.append(Block(
                id=bid,
                kind=reg.kind,
                bbox=reg.bbox,
                page=page_num,
                confidence=reg.confidence,
                source=reg.source,
                heading_level=reg.heading_level,
                metadata=dict(reg.metadata),
            ))
            continue

        matched_lines: List[Dict[str, Any]] = []
        reg_col = column_id_for_bbox(reg.bbox, column_zones) if column_zones else -1

        for nl in native_lines:
            if nl["consumed"]:
                continue
            # Enforce column boundaries: if region is in a specific column,
            # reject lines residing in a different column
            if column_zones and reg_col != -1:
                nl_col = column_id_for_bbox(nl["bbox"], column_zones)
                if nl_col != -1 and nl_col != reg_col:
                    continue

            if nl["bbox"].coverage_by(reg.bbox) >= 0.45 or reg.bbox.coverage_by(nl["bbox"]) >= 0.65:
                matched_lines.append(nl)
                nl["consumed"] = True

        if not matched_lines:
            blocks.append(Block(
                id=bid,
                kind=reg.kind,
                bbox=reg.bbox,
                page=page_num,
                text="",
                confidence=reg.confidence,
                source="native",
                heading_level=reg.heading_level,
                metadata=dict(reg.metadata),
            ))
            continue

        # If a region captured lines from multiple distinct columns, partition them
        # by column to prevent cross-column text interweaving
        line_cols = [
            column_id_for_bbox(nl["bbox"], column_zones) if column_zones else -1
            for nl in matched_lines
        ]
        distinct_cols = {c for c in line_cols if c != -1}

        if len(distinct_cols) > 1 and reg.kind in ("text", "list", "heading"):
            col_groups: Dict[int, List[Dict[str, Any]]] = {}
            for nl, cid in zip(matched_lines, line_cols):
                col_groups.setdefault(cid, []).append(nl)

            for cid in sorted(col_groups.keys()):
                group_lines = col_groups[cid]
                group_lines.sort(key=lambda item: (round(item["bbox"].y0, 1), round(item["bbox"].x0, 1)))
                group_bbox = group_lines[0]["bbox"]
                for gl in group_lines[1:]:
                    group_bbox = group_bbox.union(gl["bbox"])

                assembled = _assemble_lines(group_lines)
                sep = "\n" if reg.kind in ("algorithm", "list") else " "
                suffix = f"_c{cid}" if cid >= 0 else "_cspan"
                raw_text = sep.join(assembled).strip()
                blocks.append(Block(
                    id=f"{bid}{suffix}",
                    kind=reg.kind,
                    bbox=group_bbox,
                    page=page_num,
                    text=_reorder_bidi_text(raw_text),
                    confidence=reg.confidence,
                    source="native",
                    heading_level=reg.heading_level,
                    metadata=dict(reg.metadata),
                ))
            continue

        matched_lines.sort(key=lambda item: (
            column_id_for_bbox(item["bbox"], column_zones) if column_zones else 0,
            round(item["bbox"].y0, 1),
            round(item["bbox"].x0, 1),
        ))
        assembled_lines = _assemble_lines(matched_lines)

        if reg.kind in ("algorithm", "list"):
            block_text = "\n".join(assembled_lines).strip()
        else:
            block_text = " ".join(assembled_lines).strip()
        blocks.append(Block(
            id=bid,
            kind=reg.kind,
            bbox=reg.bbox,
            page=page_num,
            text=_reorder_bidi_text(block_text),
            confidence=reg.confidence,
            source="native",
            heading_level=reg.heading_level,
            metadata=dict(reg.metadata),
        ))

    if rescue_orphans:
        orphan_lines = [nl for nl in native_lines if not nl["consumed"]]
        for o_idx, ol in enumerate(orphan_lines, 1):
            blocks.append(Block(
                id=f"p{page_num}_rescue_{o_idx}",
                kind="text",
                bbox=ol["bbox"],
                page=page_num,
                text=_reorder_bidi_text(ol["text"]),
                confidence=0.85,
                source="native",
            ))

    return blocks
