"""
Single-Pass PageContext for ScholarMark v4.1.
Executes a single `page.get_text("rawdict")`, `page.get_bboxlog()`, and conditional
`page.get_drawings()` per page, synthesizing `dict`, `rawdict`, `words`, and `image_boxes`
in-memory in O(N) time to eliminate redundant CFFI/SWIG calls across pipeline stages.
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Any, Optional
import fitz

from .geometry import BoundingBox


@dataclass
class PageContext:
    """Contexto inmutable de paso único para todas las primitivas de una página PDF."""
    page: fitz.Page
    page_num: int
    width: float
    height: float
    rotation: int
    raw_dict: Dict[str, Any]
    bboxlog: List[Tuple[str, Any]]
    drawings: List[Dict[str, Any]]
    words: List[Tuple[float, float, float, float, str, int, int, int]]
    image_boxes: List[Tuple[int, BoundingBox]] = field(default_factory=list)
    column_zones: List[Tuple[float, float, float, float]] = field(default_factory=list)
    full_text: str = ""

    @classmethod
    def from_page(
        cls,
        page: fitz.Page,
        page_num: int,
        max_primitives: int = 20000,
    ) -> "PageContext":
        width = float(page.rect.width)
        height = float(page.rect.height)
        rotation = int(page.rotation)

        # 1. Única llamada a page.get_text("rawdict") por página
        raw_dict = page.get_text("rawdict")
        words: List[Tuple[float, float, float, float, str, int, int, int]] = []
        text_lines: List[str] = []

        for b_idx, b in enumerate(raw_dict.get("blocks", [])):
            if b.get("type") != 0:
                continue
            for l_idx, ln in enumerate(b.get("lines", [])):
                line_parts: List[str] = []
                w_idx = 0
                cur_w_chars: List[str] = []
                cur_wx0 = cur_wy0 = float("inf")
                cur_wx1 = cur_wy1 = float("-inf")
                prev_cx1: Optional[float] = None

                for sp in ln.get("spans", []):
                    sz = float(sp.get("size", 10.0))
                    chars = sp.get("chars", [])
                    if chars:
                        sp_chars_str: List[str] = []
                        for ch in chars:
                            c_str = ch.get("c", "")
                            sp_chars_str.append(c_str)
                            cb = ch.get("bbox")
                            if not c_str or c_str.isspace():
                                if cur_w_chars:
                                    words.append((
                                        cur_wx0, cur_wy0, cur_wx1, cur_wy1,
                                        "".join(cur_w_chars), b_idx, l_idx, w_idx
                                    ))
                                    w_idx += 1
                                    cur_w_chars = []
                                    cur_wx0 = cur_wy0 = float("inf")
                                    cur_wx1 = cur_wy1 = float("-inf")
                                prev_cx1 = float(cb[2]) if cb else prev_cx1
                                continue

                            if cb is not None:
                                cx0, cy0, cx1, cy1 = float(cb[0]), float(cb[1]), float(cb[2]), float(cb[3])
                                # Si hay un salto horizontal físico mayor al umbral de espacio (kerning), separar palabra
                                if cur_w_chars and prev_cx1 is not None and (cx0 - prev_cx1) > (sz * 0.18):
                                    words.append((
                                        cur_wx0, cur_wy0, cur_wx1, cur_wy1,
                                        "".join(cur_w_chars), b_idx, l_idx, w_idx
                                    ))
                                    w_idx += 1
                                    cur_w_chars = []
                                    cur_wx0 = cur_wy0 = float("inf")
                                    cur_wx1 = cur_wy1 = float("-inf")

                                cur_w_chars.append(c_str)
                                if cx0 < cur_wx0:
                                    cur_wx0 = cx0
                                if cy0 < cur_wy0:
                                    cur_wy0 = cy0
                                if cx1 > cur_wx1:
                                    cur_wx1 = cx1
                                if cy1 > cur_wy1:
                                    cur_wy1 = cy1
                                prev_cx1 = cx1
                        sp_text = "".join(sp_chars_str)
                        sp["text"] = sp_text
                        if sp_text:
                            line_parts.append(sp_text)
                    else:
                        sp_text = str(sp.get("text", ""))
                        if sp_text:
                            line_parts.append(sp_text)
                            sb = sp.get("bbox")
                            if sb:
                                for tok in sp_text.split():
                                    words.append((
                                        float(sb[0]), float(sb[1]), float(sb[2]), float(sb[3]),
                                        tok, b_idx, l_idx, w_idx
                                    ))
                                    w_idx += 1

                if cur_w_chars:
                    words.append((
                        cur_wx0, cur_wy0, cur_wx1, cur_wy1,
                        "".join(cur_w_chars), b_idx, l_idx, w_idx
                    ))

                if line_parts:
                    text_lines.append("".join(line_parts))

        # 2. Única llamada a get_bboxlog() y get_drawings() condicional
        try:
            bboxlog = page.get_bboxlog()
        except Exception:
            bboxlog = []

        drawings: List[Dict[str, Any]] = []
        if len(bboxlog) <= max_primitives:
            try:
                drawings = page.get_drawings()
            except Exception:
                drawings = []

        # 3. Única inspección de cajas de imágenes ráster incrustadas
        image_boxes: List[Tuple[int, BoundingBox]] = []
        try:
            for img in page.get_images():
                xref = int(img[0])
                for r in page.get_image_rects(xref):
                    image_boxes.append((xref, BoundingBox.from_fitz_rect(r)))
        except Exception:
            pass

        return cls(
            page=page,
            page_num=page_num,
            width=width,
            height=height,
            rotation=rotation,
            raw_dict=raw_dict,
            bboxlog=bboxlog,
            drawings=drawings,
            words=words,
            image_boxes=image_boxes,
            full_text="\n".join(text_lines),
        )

    def clip_words(
        self,
        bbox: BoundingBox,
        pad: float = 2.0,
    ) -> List[Tuple[float, float, float, float, str, int, int, int]]:
        """
        Retorna todas las palabras de la página que intersectan `bbox.pad(pad)` en memoria,
        sin invocar `page.get_text("words", clip=...)`.
        """
        pad_box = bbox.pad(pad, self.page.rect)
        px0, py0, px1, py1 = pad_box.x0, pad_box.y0, pad_box.x1, pad_box.y1
        result = []
        for w in self.words:
            wx0, wy0, wx1, wy1 = w[0], w[1], w[2], w[3]
            w_cx = (wx0 + wx1) * 0.5
            w_cy = (wy0 + wy1) * 0.5
            if (px0 <= w_cx <= px1 and py0 <= w_cy <= py1) or not (
                wx1 < px0 or wx0 > px1 or wy1 < py0 or wy0 > py1
            ):
                result.append(w)
        return result

    def clip_rawdict(
        self,
        bbox: BoundingBox,
        pad: float = 4.0,
    ) -> Dict[str, Any]:
        """
        Filtra en memoria `self.raw_dict` al rectángulo `bbox.pad(pad)`,
        evitando invocar `page.get_text("rawdict", clip=...)` o `page.get_text("dict", clip=...)`.
        """
        pad_box = bbox.pad(pad, self.page.rect)
        px0, py0, px1, py1 = pad_box.x0, pad_box.y0, pad_box.x1, pad_box.y1
        clipped_blocks: List[Dict[str, Any]] = []

        for b in self.raw_dict.get("blocks", []):
            if b.get("type") != 0:
                continue
            bb = b.get("bbox")
            if bb is not None and (bb[2] < px0 or bb[0] > px1 or bb[3] < py0 or bb[1] > py1):
                continue

            clipped_lines: List[Dict[str, Any]] = []
            for ln in b.get("lines", []):
                lb = ln.get("bbox")
                if lb is not None and (lb[2] < px0 or lb[0] > px1 or lb[3] < py0 or lb[1] > py1):
                    continue

                clipped_spans: List[Dict[str, Any]] = []
                for sp in ln.get("spans", []):
                    sb = sp.get("bbox")
                    if sb is not None and (sb[2] < px0 or sb[0] > px1 or sb[3] < py0 or sb[1] > py1):
                        continue

                    chars = sp.get("chars", [])
                    if chars:
                        in_chars = [
                            ch for ch in chars
                            if ch.get("bbox") is not None and (
                                px0 <= ((ch["bbox"][0] + ch["bbox"][2]) * 0.5) <= px1
                                and py0 <= ((ch["bbox"][1] + ch["bbox"][3]) * 0.5) <= py1
                            )
                        ]
                        if not in_chars:
                            continue
                        new_sp = dict(sp)
                        new_sp["chars"] = in_chars
                        new_sp["text"] = "".join(c.get("c", "") for c in in_chars)
                        clipped_spans.append(new_sp)
                    else:
                        clipped_spans.append(sp)

                if clipped_spans:
                    new_ln = dict(ln)
                    new_ln["spans"] = clipped_spans
                    clipped_lines.append(new_ln)

            if clipped_lines:
                new_b = dict(b)
                new_b["lines"] = clipped_lines
                clipped_blocks.append(new_b)

        return {"blocks": clipped_blocks}
