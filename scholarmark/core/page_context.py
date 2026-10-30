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
    high_density_zones: List[BoundingBox] = field(default_factory=list)
    ocr_injected: bool = False
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

        high_density_zones: List[BoundingBox] = []
        drawings: List[Dict[str, Any]] = []
        if len(bboxlog) <= max_primitives:
            try:
                drawings = page.get_drawings()
            except Exception:
                drawings = []
        else:
            high_density_zones, drawings = cls._partition_dense_bboxlog_16x16(
                bboxlog=bboxlog,
                page_w=width,
                page_h=height,
                cell_density_threshold=800,
            )

        # 3. Única inspección de cajas de imágenes ráster incrustadas
        image_boxes: List[Tuple[int, BoundingBox]] = []
        try:
            for img in page.get_images():
                xref = int(img[0])
                for r in page.get_image_rects(xref):
                    image_boxes.append((xref, BoundingBox.from_fitz_rect(r)))
        except Exception:
            pass

        # 4. Triaje para páginas escaneadas o fuentes Type 3 corruptas
        ocr_injected = False
        has_corrupted_type3 = False
        for b in raw_dict.get("blocks", []):
            if b.get("type") != 0:
                continue
            for ln in b.get("lines", []):
                for sp in ln.get("spans", []):
                    font_name = str(sp.get("font", "")).lower()
                    sp_text = str(sp.get("text", ""))
                    if "\ufffd" in sp_text or "type3" in font_name:
                        has_corrupted_type3 = True
                        break
                if has_corrupted_type3:
                    break
            if has_corrupted_type3:
                break

        has_large_image = any(
            (ib.width * ib.height) >= (width * height * 0.40)
            for _, ib in image_boxes
        )
        needs_ocr_triage = has_corrupted_type3 or (len(words) < 15 and has_large_image)

        if needs_ocr_triage:
            try:
                from ..recognizers.ocr_engine import LocalOCREngine
                if LocalOCREngine.is_available():
                    engine = LocalOCREngine()
                    ocr_words = engine.extract_words_from_region(
                        page=page,
                        bbox=BoundingBox(0.0, 0.0, width, height),
                        dpi=150,
                    )
                    if ocr_words:
                        ocr_injected = True
                        b_idx = len(raw_dict.get("blocks", []))
                        synth_spans = []
                        for box, txt, score in ocr_words:
                            for tok in txt.split():
                                w_idx = len(words)
                                words.append((box.x0, box.y0, box.x1, box.y1, tok, b_idx, 0, w_idx))
                                synth_spans.append({
                                    "bbox": (box.x0, box.y0, box.x1, box.y1),
                                    "text": tok,
                                    "size": 10.0,
                                    "font": "OCR-Synthesized",
                                    "chars": [],
                                })
                        if synth_spans:
                            raw_dict.setdefault("blocks", []).append({
                                "type": 0,
                                "bbox": (0.0, 0.0, width, height),
                                "lines": [{
                                    "bbox": (0.0, 0.0, width, height),
                                    "spans": synth_spans,
                                    "dir": (1.0, 0.0),
                                }]
                            })
                            text_lines.append(" ".join(t for _, _, _, _, t, _, _, _ in words))
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
            high_density_zones=high_density_zones,
            ocr_injected=ocr_injected,
            full_text="\n".join(text_lines),
        )

    @classmethod
    def _partition_dense_bboxlog_16x16(
        cls,
        bboxlog: List[Tuple[str, Any]],
        page_w: float,
        page_h: float,
        cell_density_threshold: int = 800,
    ) -> Tuple[List[BoundingBox], List[Dict[str, Any]]]:
        """
        Particiona una página con saturación vectorial (>20,000 primitivas) mediante una
        rejilla espacial uniforme de 16x16 celdas, aislando regiones de alta densidad
        (HighDensityVectorZone) y rescatando reglas lineales fuera de dichas zonas.
        """
        GRID_SIZE = 16
        cw = page_w / float(GRID_SIZE)
        ch = page_h / float(GRID_SIZE)
        if cw <= 0 or ch <= 0:
            return [], []

        grid_counts: Dict[Tuple[int, int], int] = {}
        candidate_rules: List[fitz.Rect] = []

        for item in bboxlog:
            kind = item[0]
            rect_tuple = item[1]
            if rect_tuple is None:
                continue
            r = fitz.Rect(rect_tuple)
            rx0, ry0, rx1, ry1 = float(r.x0), float(r.y0), float(r.x1), float(r.y1)
            rw = rx1 - rx0
            rh = ry1 - ry0

            if kind not in ("fill-text", "stroke-text", "clip-path"):
                rcx = (rx0 + rx1) * 0.5
                rcy = (ry0 + ry1) * 0.5
                gx = min(GRID_SIZE - 1, max(0, int(rcx / cw)))
                gy = min(GRID_SIZE - 1, max(0, int(rcy / ch)))
                grid_counts[(gx, gy)] = grid_counts.get((gx, gy), 0) + 1

                if rh <= 3.0 and rw >= 6.0:
                    candidate_rules.append(r)

        dense_cells = {cell for cell, count in grid_counts.items() if count >= cell_density_threshold}
        high_density_zones: List[BoundingBox] = []

        if dense_cells:
            visited = set()
            for cell in dense_cells:
                if cell in visited:
                    continue
                comp = []
                queue = [cell]
                visited.add(cell)
                while queue:
                    curr = queue.pop()
                    comp.append(curr)
                    cgx, cgy = curr
                    for dx in (-1, 0, 1):
                        for dy in (-1, 0, 1):
                            if dx == 0 and dy == 0:
                                continue
                            nb = (cgx + dx, cgy + dy)
                            if nb in dense_cells and nb not in visited:
                                visited.add(nb)
                                queue.append(nb)

                min_gx = min(c[0] for c in comp)
                max_gx = max(c[0] for c in comp)
                min_gy = min(c[1] for c in comp)
                max_gy = max(c[1] for c in comp)

                zone_bbox = BoundingBox(
                    min_gx * cw,
                    min_gy * ch,
                    min(page_w, (max_gx + 1) * cw),
                    min(page_h, (max_gy + 1) * ch),
                )
                high_density_zones.append(zone_bbox)

        drawings: List[Dict[str, Any]] = []
        for r in candidate_rules:
            rule_box = BoundingBox.from_fitz_rect(r)
            in_zone = any(rule_box.intersects(zone) for zone in high_density_zones)
            if not in_zone:
                drawings.append({
                    "rect": r,
                    "type": "bboxlog_rule",
                    "items": [("re", r)],
                    "width": float(r.height),
                })

        return high_density_zones, drawings

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
