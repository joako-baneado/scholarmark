"""
Geometry and visual element extraction engine for ScholarMark v4.1.
Handles multimodal bounding box fusion, transitive Union-Find vector clustering,
vector density safety guards, elastic axis/subpanel padding, and high-DPI rendering.
"""

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import List, Optional, Tuple, Dict, Any
import fitz  # PyMuPDF


AXIS_OR_PANEL_TOKEN_RE = re.compile(
    r"^(?:"
    r"[\(\[][a-zA-Z0-9]{1,2}[\)\]]|"
    r"[a-zA-Z][\)\.]|"
    r"(?:[×xX\*]\s*)?10(?:\^\s*\{?[-−+]?\d+\}?|[⁻⁺]?[⁰¹²³⁴⁵⁶⁷⁸⁹]+|[-−+]\d+)|"
    r"[-−+]?\d+(?:[.,]\d+)?(?:[eE][-−+]?\d+)?%?|"
    r"(?:Hz|kHz|ms|s|mm|cm|m|px|dB|deg|°|rad)"
    r")$"
)


@dataclass
class BoundingBox:
    """Representación rectangular en el sistema de coordenadas de puntos del PDF."""
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return max(0.0, self.x1 - self.x0)

    @property
    def height(self) -> float:
        return max(0.0, self.y1 - self.y0)

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center(self) -> Tuple[float, float]:
        return ((self.x0 + self.x1) / 2.0, (self.y0 + self.y1) / 2.0)

    def to_fitz_rect(self) -> fitz.Rect:
        return fitz.Rect(self.x0, self.y0, self.x1, self.y1)

    @classmethod
    def from_fitz_rect(cls, rect: fitz.Rect) -> "BoundingBox":
        return cls(x0=float(rect.x0), y0=float(rect.y0), x1=float(rect.x1), y1=float(rect.y1))

    def pad(self, padding: float, page_rect: Optional[fitz.Rect] = None) -> "BoundingBox":
        """Añade margen de guarda (bleed padding) sin exceder los límites de la página."""
        max_w = float(page_rect.width) if page_rect else float("inf")
        max_h = float(page_rect.height) if page_rect else float("inf")
        return BoundingBox(
            x0=max(0.0, self.x0 - padding),
            y0=max(0.0, self.y0 - padding),
            x1=min(max_w, self.x1 + padding),
            y1=min(max_h, self.y1 + padding),
        )

    def union(self, other: Any) -> "BoundingBox":
        """Calcula la caja envolvente mínima de la unión con otro BoundingBox o fitz.Rect."""
        if isinstance(other, fitz.Rect):
            ox0, oy0, ox1, oy1 = other.x0, other.y0, other.x1, other.y1
        elif isinstance(other, BoundingBox):
            ox0, oy0, ox1, oy1 = other.x0, other.y0, other.x1, other.y1
        else:
            raise TypeError(f"Unsupported type for union: {type(other)}")

        return BoundingBox(
            x0=min(self.x0, ox0),
            y0=min(self.y0, oy0),
            x1=max(self.x1, ox1),
            y1=max(self.y1, oy1),
        )

    def intersects(self, other: Any) -> bool:
        """Determina si existe intersección geométrica."""
        if isinstance(other, fitz.Rect):
            ox0, oy0, ox1, oy1 = other.x0, other.y0, other.x1, other.y1
        elif isinstance(other, BoundingBox):
            ox0, oy0, ox1, oy1 = other.x0, other.y0, other.x1, other.y1
        else:
            return False
        return not (self.x1 < ox0 or self.x0 > ox1 or self.y1 < oy0 or self.y0 > oy1)

    def intersection_area(self, other: Any) -> float:
        """Calcula el área de intersección con otro BoundingBox o fitz.Rect."""
        if isinstance(other, fitz.Rect):
            ox0, oy0, ox1, oy1 = other.x0, other.y0, other.x1, other.y1
        elif isinstance(other, BoundingBox):
            ox0, oy0, ox1, oy1 = other.x0, other.y0, other.x1, other.y1
        else:
            return 0.0
        ix0 = max(self.x0, ox0)
        iy0 = max(self.y0, oy0)
        ix1 = min(self.x1, ox1)
        iy1 = min(self.y1, oy1)
        if ix1 <= ix0 or iy1 <= iy0:
            return 0.0
        return float((ix1 - ix0) * (iy1 - iy0))

    def iou(self, other: Any) -> float:
        """Calcula Intersection over Union (IoU) entre dos cajas."""
        inter = self.intersection_area(other)
        if inter <= 0.0:
            return 0.0
        if isinstance(other, fitz.Rect):
            other_area = max(0.0, float(other.width * other.height))
        elif isinstance(other, BoundingBox):
            other_area = other.area
        else:
            return 0.0
        denom = self.area + other_area - inter
        return inter / denom if denom > 0.0 else 0.0

    def coverage_by(self, other: Any) -> float:
        """Fracción de esta caja cubierta por 'other'."""
        if self.area <= 0.0:
            return 0.0
        return self.intersection_area(other) / self.area


@dataclass
class VisualElement:
    """Elemento visual científico (figura, gráfico vectorial, esquema o diagrama)."""
    bbox: BoundingBox
    category: str = "Picture"
    confidence: float = 1.0
    caption_text: Optional[str] = None
    saved_path: Optional[str] = None
    page_num: int = 0
    is_vector: bool = False
    subpanel_labels: List[str] = field(default_factory=list)
    composite_group_id: Optional[str] = None


class _UnionFind:
    """Estructura Disjoint-Set con compresión de caminos para agrupamiento transitivo O(N α(N))."""

    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, i: int) -> int:
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def union(self, i: int, j: int) -> None:
        ri, rj = self.find(i), self.find(j)
        if ri == rj:
            return
        if self.rank[ri] < self.rank[rj]:
            self.parent[ri] = rj
        elif self.rank[ri] > self.rank[rj]:
            self.parent[rj] = ri
        else:
            self.parent[rj] = ri
            self.rank[ri] += 1


def _rects_within_threshold(r1: fitz.Rect, r2: fitz.Rect, threshold: float) -> bool:
    """Comprueba de forma simétrica y sin ambigüedad booleana si dos rectángulos distan <= threshold."""
    return not (
        (r1.x1 + threshold) < r2.x0
        or (r2.x1 + threshold) < r1.x0
        or (r1.y1 + threshold) < r2.y0
        or (r2.y1 + threshold) < r1.y0
    )


def elastic_expand_bbox(
    page: fitz.Page,
    figure_bbox: BoundingBox,
    words: Optional[List[Any]] = None,
    prose_blocks: Optional[List[BoundingBox]] = None,
    min_padding: float = 4.0,
    max_padding: float = 16.0
) -> BoundingBox:
    """
    Expande elásticamente (entre min_padding y max_padding pt) una caja de figura para capturar
    marcas numéricas de ejes, exponentes cartesianos (×10^-3) y etiquetas de subpaneles (a), (b),
    deteniéndose ante bloques de texto corrido (prose_blocks) para no invadir párrafos.
    """
    refined = figure_bbox
    if words is None:
        try:
            words = page.get_text("words")
        except Exception:
            words = []

    prose_boxes = prose_blocks or []

    for _ in range(2):
        search_band = refined.pad(max_padding, page.rect)
        changed = False
        for w in words:
            wx0, wy0, wx1, wy1, text = float(w[0]), float(w[1]), float(w[2]), float(w[3]), str(w[4]).strip()
            if not text:
                continue
            w_box = BoundingBox(wx0, wy0, wx1, wy1)
            if not search_band.intersects(w_box):
                continue
            if refined.intersects(w_box):
                continue
            if any(pb.intersects(w_box) for pb in prose_boxes):
                continue

            if AXIS_OR_PANEL_TOKEN_RE.match(text):
                refined = refined.union(w_box)
                changed = True
        if not changed:
            break

    return refined.pad(min_padding, page.rect)


def expand_figure_bbox(
    page: fitz.Page,
    figure_bbox: BoundingBox,
    proximity_threshold: float = 10.0,
    bleed_padding: float = 4.0,
    drawings: Optional[List[Dict[str, Any]]] = None,
    words: Optional[List[Any]] = None,
    prose_blocks: Optional[List[BoundingBox]] = None,
    max_vector_primitives: int = 2000,
    max_padding: float = 16.0
) -> BoundingBox:
    """
    Fusiona la caja base de una figura con primitivas vectoriales (ejes, marcas, curvas)
    y notaciones adyacentes para evitar truncamientos de escalas o etiquetas cartesianas.
    """
    refined_box = figure_bbox
    fig_rect = figure_bbox.to_fitz_rect()

    if drawings is None:
        try:
            drawings = page.get_drawings()
        except Exception:
            drawings = []

    if len(drawings) <= max_vector_primitives:
        for draw in drawings:
            d_rect = draw.get("rect")
            if d_rect is None:
                continue
            if _rects_within_threshold(fig_rect, d_rect, proximity_threshold):
                is_hf_rule = (d_rect.y1 <= 85.0 or d_rect.y0 >= page.rect.height - 70.0) and d_rect.height <= 3.5 and d_rect.width >= (page.rect.width * 0.45)
                is_fullwidth = d_rect.height <= 3.5 and d_rect.width >= (page.rect.width * 0.72)
                if is_hf_rule or is_fullwidth:
                    continue
                if d_rect.width < (page.rect.width * 0.95) and d_rect.height < (page.rect.height * 0.95):
                    refined_box = refined_box.union(d_rect)
                    fig_rect = refined_box.to_fitz_rect()

    return elastic_expand_bbox(
        page=page,
        figure_bbox=refined_box,
        words=words,
        prose_blocks=prose_blocks,
        min_padding=bleed_padding,
        max_padding=max(bleed_padding, max_padding),
    )


def _cluster_dense_bboxlog_grid(
    bboxlog: List[Tuple[str, Tuple[float, float, float, float]]],
    page_w: float,
    page_h: float,
    min_drawing_count: int,
    min_area: float,
    cell_size: float = 16.0
) -> List[BoundingBox]:
    """
    Modo de emergencia O(N) por rejilla espacial para páginas con decenas de miles de puntos
    vectoriales (scatter plots masivos), evitando explosión cuadrática de memoria y CPU.
    """
    cols = max(1, int(page_w // cell_size) + 1)
    rows = max(1, int(page_h // cell_size) + 1)
    grid_counts: Dict[Tuple[int, int], int] = {}
    grid_rects: Dict[Tuple[int, int], fitz.Rect] = {}

    for kind, rect_tuple in bboxlog:
        if kind == "fill-text" or kind == "stroke-text":
            continue
        r = fitz.Rect(rect_tuple)
        if r.width >= page_w * 0.92 or r.height >= page_h * 0.92:
            continue
        if r.width <= 0.0 and r.height <= 0.0:
            continue
        cx = max(0, min(cols - 1, int(((r.x0 + r.x1) * 0.5) // cell_size)))
        cy = max(0, min(rows - 1, int(((r.y0 + r.y1) * 0.5) // cell_size)))
        key = (cx, cy)
        grid_counts[key] = grid_counts.get(key, 0) + 1
        grid_rects[key] = grid_rects[key] | r if key in grid_rects else r

    active_cells = list(grid_rects.keys())
    if not active_cells:
        return []

    cell_idx = {cell: idx for idx, cell in enumerate(active_cells)}
    uf = _UnionFind(len(active_cells))
    for idx, (cx, cy) in enumerate(active_cells):
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nb = (cx + dx, cy + dy)
                if nb in cell_idx:
                    uf.union(idx, cell_idx[nb])

    groups: Dict[int, List[Tuple[int, int]]] = {}
    for idx, cell in enumerate(active_cells):
        root = uf.find(idx)
        groups.setdefault(root, []).append(cell)

    results: List[BoundingBox] = []
    for cells in groups.values():
        total_items = sum(grid_counts[c] for c in cells)
        if total_items < min_drawing_count:
            continue
        u = grid_rects[cells[0]]
        for c in cells[1:]:
            u = u | grid_rects[c]
        area = u.width * u.height
        if area >= min_area and u.width < page_w * 0.95 and u.height < page_h * 0.95:
            results.append(BoundingBox.from_fitz_rect(u))
    return results


def cluster_vector_drawings(
    page: fitz.Page,
    min_drawing_count: int = 8,
    min_area: float = 3500.0,
    drawings: Optional[List[Dict[str, Any]]] = None,
    max_page_primitives: int = 20000,
    bboxlog: Optional[List[Tuple[str, Any]]] = None,
) -> List[BoundingBox]:
    """
    Agrupa trazos vectoriales densos que constituyen gráficos funcionales sin mapas de bits.
    Usa Union-Find transitivo con indexación en rejilla y guarda de saturación vectorial.
    """
    page_w = page.rect.width
    page_h = page.rect.height

    if bboxlog is not None and len(bboxlog) > max_page_primitives:
        return _cluster_dense_bboxlog_grid(
            bboxlog=bboxlog,
            page_w=page_w,
            page_h=page_h,
            min_drawing_count=min_drawing_count,
            min_area=min_area,
        )

    if drawings is None:
        try:
            b_log = bboxlog if bboxlog is not None else page.get_bboxlog()
            if len(b_log) > max_page_primitives:
                return _cluster_dense_bboxlog_grid(
                    bboxlog=b_log,
                    page_w=page_w,
                    page_h=page_h,
                    min_drawing_count=min_drawing_count,
                    min_area=min_area,
                )
        except Exception:
            pass
        drawings = page.get_drawings()

    if not drawings:
        return []

    if len(drawings) > max_page_primitives:
        pseudo_log = [("path", (d["rect"].x0, d["rect"].y0, d["rect"].x1, d["rect"].y1)) for d in drawings if "rect" in d]
        return _cluster_dense_bboxlog_grid(
            bboxlog=pseudo_log,
            page_w=page_w,
            page_h=page_h,
            min_drawing_count=min_drawing_count,
            min_area=min_area,
        )

    candidate_rects: List[fitz.Rect] = []
    for d in drawings:
        r = d.get("rect")
        if r is None:
            continue
        if r.width >= page_w * 0.92 or r.height >= page_h * 0.92:
            continue
        is_hf_rule = (r.y1 <= 85.0 or r.y0 >= page_h - 70.0) and r.height <= 3.5 and r.width >= page_w * 0.45
        is_fullwidth = r.height <= 3.5 and r.width >= page_w * 0.72
        if is_hf_rule or is_fullwidth:
            continue
        if r.width < 2.0 and r.height < 2.0:
            continue
        candidate_rects.append(r)

    n = len(candidate_rects)
    if n < min_drawing_count:
        return []

    threshold = 12.0
    uf = _UnionFind(n)

    cell_size = max(24.0, threshold * 2.0)
    buckets: Dict[Tuple[int, int], List[int]] = {}
    for idx, r in enumerate(candidate_rects):
        gx0 = int((r.x0 - threshold) // cell_size)
        gy0 = int((r.y0 - threshold) // cell_size)
        gx1 = int((r.x1 + threshold) // cell_size)
        gy1 = int((r.y1 + threshold) // cell_size)
        seen_candidates = set()
        for gx in range(gx0, gx1 + 1):
            for gy in range(gy0, gy1 + 1):
                key = (gx, gy)
                for other_idx in buckets.get(key, ()):
                    if other_idx not in seen_candidates:
                        seen_candidates.add(other_idx)
                        if _rects_within_threshold(r, candidate_rects[other_idx], threshold):
                            uf.union(idx, other_idx)
                buckets.setdefault(key, []).append(idx)

    clusters_map: Dict[int, List[fitz.Rect]] = {}
    for idx, r in enumerate(candidate_rects):
        root = uf.find(idx)
        clusters_map.setdefault(root, []).append(r)

    result_boxes: List[BoundingBox] = []
    for c in clusters_map.values():
        if len(c) < min_drawing_count:
            continue

        u = c[0]
        for item in c[1:]:
            u = u | item

        area = u.width * u.height
        if area >= min_area and u.width < page_w * 0.95 and u.height < page_h * 0.95:
            result_boxes.append(BoundingBox.from_fitz_rect(u))

    result_boxes.sort(key=lambda b: (round(b.y0, 1), round(b.x0, 1)))
    return result_boxes


def render_crop_300dpi(
    page: fitz.Page,
    bbox: BoundingBox,
    destination: Path,
    target_dpi: int = 300,
    image_format: str = "png"
) -> bool:
    """
    Exporta la región con escalado afín exacto a 300+ DPI.
    Usa alpha=False explícito para eliminar halos grises causados por antialiasing en curvas vectoriales.
    """
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        scale_factor = target_dpi / 72.0
        affine_matrix = fitz.Matrix(scale_factor, scale_factor)
        clip_rect = bbox.to_fitz_rect()

        pix = page.get_pixmap(matrix=affine_matrix, clip=clip_rect, alpha=False)
        pix.save(str(destination))
        return True
    except Exception:
        return False


def export_figure_asset(
    page: fitz.Page,
    bbox: BoundingBox,
    destination: Path,
    target_dpi: int = 300,
    image_format: str = "png",
    ctx: Optional[Any] = None,
) -> bool:
    """
    Exporta una figura optimizando la ruta según su naturaleza geométrica:
    1. Fast Path (XREF Stream Directo): Si la región corresponde a una imagen ráster pura
       (IoU >= 0.85, xref > 0) sin trazos vectoriales ni texto superpuesto, extrae el stream
       nativo del PDF sin invocar page.get_pixmap().
    2. Adaptive Vector DPI: Si la figura es vectorial/híbrida, grande (area > 15,000 pt^2)
       y carece de micro-texto (< 6.5 pt), escala a 200 DPI en lugar de 300 DPI (2.25x menos píxeles).
    """
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        clip_rect = bbox.to_fitz_rect()
        page_w = float(page.rect.width)
        page_h = float(page.rect.height)

        image_boxes: List[Tuple[int, BoundingBox]] = (
            ctx.image_boxes
            if ctx is not None
            else [
                (int(img[0]), BoundingBox.from_fitz_rect(r))
                for img in page.get_images()
                for r in page.get_image_rects(img[0])
            ]
        )

        matching_xrefs = [
            (xref, ib)
            for xref, ib in image_boxes
            if xref > 0 and ib.iou(bbox) >= 0.85
        ]

        if len(matching_xrefs) == 1 and page.parent is not None:
            xref = matching_xrefs[0][0]
            drawings = ctx.drawings if ctx is not None else page.get_drawings()
            has_vector_overlay = False
            if drawings:
                for d in drawings:
                    dr = d.get("rect")
                    if dr is None:
                        continue
                    if dr.width >= page_w * 0.92 or dr.height >= page_h * 0.92:
                        continue
                    if (dr.width >= 2.0 or dr.height >= 2.0) and clip_rect.intersects(dr):
                        has_vector_overlay = True
                        break

            has_text_overlay = False
            if not has_vector_overlay and ctx is not None:
                clipped_words = ctx.clip_words(bbox)
                if clipped_words:
                    has_text_overlay = True

            if not has_vector_overlay and not has_text_overlay:
                img_dict = page.parent.extract_image(xref)
                raw_bytes = img_dict.get("image") if img_dict else None
                ext = (img_dict.get("ext", "") if img_dict else "").lower()
                dest_ext = destination.suffix.lstrip(".").lower() or image_format.lower()
                if raw_bytes:
                    if ext == dest_ext or (ext in ("jpg", "jpeg") and dest_ext in ("jpg", "jpeg")):
                        destination.write_bytes(raw_bytes)
                        return True
                    pix = fitz.Pixmap(page.parent, xref)
                    if pix.alpha or pix.n > 4:
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                    pix.save(str(destination))
                    return True
    except Exception:
        pass

    effective_dpi = target_dpi
    if target_dpi >= 300 and bbox.area > 15000.0 and ctx is not None:
        raw_sub = ctx.clip_rawdict(bbox)
        span_sizes = [
            float(s.get("size", 10.0))
            for b in raw_sub.get("blocks", [])
            for ln in b.get("lines", [])
            for s in ln.get("spans", [])
            if s.get("text", "").strip()
        ]
        if not span_sizes or min(span_sizes) >= 6.5:
            effective_dpi = 200

    return render_crop_300dpi(
        page=page,
        bbox=bbox,
        destination=destination,
        target_dpi=effective_dpi,
        image_format=image_format,
    )


def detect_column_zones(
    line_boxes: List[BoundingBox],
    page_width: float,
    page_height: float,
    min_gutter_width: float = 8.0,
) -> List[Tuple[float, float, float, float]]:
    """
    Detecta medianeras verticales (gutters) entre columnas proyectando las cajas
    de líneas nativas sobre el eje X e identificando valles continuos de densidad cero.
    Soporta maquetaciones de 1, 2 o 3 columnas (simétricas o con barra lateral asimétrica)
    y páginas mixtas (cabecera a 1 columna + cuerpo a 2 columnas).

    Retorna tuplas (x_izq, x_der, y_ini, y_fin): límites horizontales de cada medianera y
    rango vertical de la zona multicolumna en la que es válida.
    """
    if page_width < 360.0 or len(line_boxes) < 4:
        return []

    col_candidates: List[BoundingBox] = []
    for b in line_boxes:
        if b.y1 < 44.0 or b.y0 > (page_height - 42.0):
            continue
        if b.width < 15.0:
            continue
        # Ignorar líneas de ancho completo (títulos, resúmenes o encabezados que cruzan ambas márgenes)
        if b.width >= (page_width * 0.68) or (b.x0 < (page_width * 0.22) and b.x1 > (page_width * 0.62)):
            continue
        col_candidates.append(b)

    if len(col_candidates) < 4:
        return []

    # Sólo las líneas que tienen un "vecino" paralelo (solapamiento vertical y separación
    # horizontal) pertenecen a una zona multicolumna real; esto evita que bloques de una
    # sola columna en páginas mixtas (afiliaciones, cabeceras) tapen la medianera.
    min_col_line_w = page_width * 0.20
    long_lines = [b for b in col_candidates if b.width >= min_col_line_w]
    paired: List[BoundingBox] = []
    for b in long_lines:
        for o in long_lines:
            if o is b:
                continue
            v_overlap = min(b.y1, o.y1) - max(b.y0, o.y0)
            if v_overlap >= min(b.height, o.height) * 0.4 and (o.x0 >= b.x1 + 6.0 or o.x1 <= b.x0 - 6.0):
                paired.append(b)
                break
    if len(paired) < 4:
        return []
    col_candidates = paired

    w_int = int(page_width) + 2
    occ = [0] * w_int
    for b in col_candidates:
        ix0 = max(0, min(w_int - 1, int(b.x0)))
        ix1 = max(0, min(w_int - 1, int(b.x1)))
        for x in range(ix0, ix1 + 1):
            occ[x] += 1

    active_xs = [x for x, count in enumerate(occ) if count > 0]
    if not active_xs:
        return []

    x_min = active_xs[0]
    x_max = active_xs[-1]
    if (x_max - x_min) < 200:
        return []

    search_left = max(int(page_width * 0.16), x_min + 35)
    search_right = min(int(page_width * 0.84), x_max - 35)
    if search_right <= search_left:
        return []

    valleys: List[Tuple[float, float]] = []
    in_valley = False
    v_start = search_left

    for x in range(search_left, search_right + 1):
        if occ[x] == 0:
            if not in_valley:
                in_valley = True
                v_start = x
        else:
            if in_valley:
                if (x - v_start) >= min_gutter_width:
                    valleys.append((float(v_start), float(x - 1)))
                in_valley = False
    if in_valley and (search_right - v_start + 1) >= min_gutter_width:
        valleys.append((float(v_start), float(search_right)))

    valid_zones: List[Tuple[float, float, float, float]] = []
    for g0, g1 in valleys:
        gc = (g0 + g1) * 0.5
        left_lines = [b for b in col_candidates if b.x1 <= (gc + 4.0)]
        right_lines = [b for b in col_candidates if b.x0 >= (gc - 4.0)]
        if len(left_lines) < 2 or len(right_lines) < 2:
            continue
        # Confirmar solapamiento vertical entre ambos lados (columnas paralelas reales)
        l_y0 = min(b.y0 for b in left_lines)
        l_y1 = max(b.y1 for b in left_lines)
        r_y0 = min(b.y0 for b in right_lines)
        r_y1 = max(b.y1 for b in right_lines)
        if min(l_y1, r_y1) - max(l_y0, r_y0) >= 12.0:
            valid_zones.append((g0, g1, min(l_y0, r_y0), max(l_y1, r_y1)))

    if len(valid_zones) > 2:
        valid_zones.sort(key=lambda z: z[1] - z[0], reverse=True)
        valid_zones = sorted(valid_zones[:2], key=lambda z: z[0])

    return valid_zones


def detect_column_gutters(
    line_boxes: List[BoundingBox],
    page_width: float,
    page_height: float,
    min_gutter_width: float = 8.0,
) -> List[Tuple[float, float]]:
    """Versión simplificada de detect_column_zones: retorna sólo (x_izq, x_der) de cada medianera."""
    return [
        (g0, g1)
        for g0, g1, _, _ in detect_column_zones(line_boxes, page_width, page_height, min_gutter_width)
    ]


def column_id_for_bbox(
    bbox: BoundingBox,
    column_zones: List[Tuple[float, float, float, float]],
    zone_pad: float = 12.0,
) -> int:
    """
    Asigna una caja (línea o bloque) a su columna dentro de las zonas multicolumna detectadas.
    Retorna -1 si la caja está fuera de toda zona multicolumna o si cruza una medianera
    (contenido de ancho completo); en caso contrario, el índice 0..N-1 de la columna.
    El margen zone_pad (~1 interlínea) cubre primeras/últimas líneas cortas de cada columna.
    """
    cy = (bbox.y0 + bbox.y1) * 0.5
    active = [
        (g0, g1) for g0, g1, zy0, zy1 in column_zones
        if (zy0 - zone_pad) <= cy <= (zy1 + zone_pad)
    ]
    if not active:
        return -1
    for g0, g1 in active:
        if bbox.x0 < (g0 - 2.0) and bbox.x1 > (g1 + 2.0):
            return -1
    cx = (bbox.x0 + bbox.x1) * 0.5
    return sum(1 for g0, g1 in active if cx > (g0 + g1) * 0.5)


def split_bbox_by_gutters(
    bbox: BoundingBox,
    gutters: List[Tuple[float, float]],
) -> List[BoundingBox]:
    """
    Divide un BoundingBox que cruza una o más medianeras verticales en sub-cajas
    restringidas a cada columna.
    """
    if not gutters:
        return [bbox]

    parts: List[BoundingBox] = []
    cur_x0 = bbox.x0
    for g0, g1 in sorted(gutters, key=lambda g: g[0]):
        if cur_x0 < g0 and bbox.x1 > g1:
            parts.append(BoundingBox(cur_x0, bbox.y0, g0, bbox.y1))
            cur_x0 = g1
    if cur_x0 < bbox.x1:
        parts.append(BoundingBox(cur_x0, bbox.y0, bbox.x1, bbox.y1))
    return parts if parts else [bbox]

