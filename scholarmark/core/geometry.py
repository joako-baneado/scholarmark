"""
Geometry and visual element extraction engine for ScholarMark v3.0.
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
    r"[\(\[][a-zA-Z0-9]{1,2}[\)\]]|"          # (a), (b), [A], (1)
    r"[a-zA-Z][\)\.]|"                         # a), b.
    r"(?:[×xX\*]\s*)?10(?:\^\s*\{?[-−+]?\d+\}?|[⁻⁺]?[⁰¹²³⁴⁵⁶⁷⁸⁹]+|[-−+]\d+)|"  # ×10^-3, 10^{-4}, 10⁻³
    r"[-−+]?\d+(?:[.,]\d+)?(?:[eE][-−+]?\d+)?%?|"  # números de escala / ticks
    r"(?:Hz|kHz|ms|s|mm|cm|m|px|dB|deg|°|rad)"     # unidades cortas en ejes
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

    # Dos pasadas cortas para absorber etiquetas de eje y subpaneles cercanos
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
            # No absorber palabras que pertenecen a un bloque de prosa o leyenda
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
    Incorpora interruptor de seguridad (max_vector_primitives) ante gráficos densos.
    """
    refined_box = figure_bbox
    fig_rect = figure_bbox.to_fitz_rect()

    if drawings is None:
        try:
            drawings = page.get_drawings()
        except Exception:
            drawings = []

    # Interruptor de seguridad B7: si el gráfico o la página supera el límite de primitivas
    # vectoriales (ej. scatter plots densos t-SNE/UMAP), omitir iteración de trazos y usar recorte elástico.
    if len(drawings) <= max_vector_primitives:
        for draw in drawings:
            d_rect = draw.get("rect")
            if d_rect is None:
                continue
            if _rects_within_threshold(fig_rect, d_rect, proximity_threshold):
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
    max_page_primitives: int = 20000
) -> List[BoundingBox]:
    """
    Agrupa trazos vectoriales densos que constituyen gráficos funcionales sin mapas de bits
    (p. ej. matplotlib, TikZ, diagramas de bloques generados por LaTeX).
    Usa Union-Find transitivo con indexación en rejilla y guarda de saturación vectorial.
    """
    page_w = page.rect.width
    page_h = page.rect.height

    # Comprobar densidad vía get_bboxlog() (C nativo ultrarrápido) antes de descomponer dibujos
    if drawings is None:
        try:
            bboxlog = page.get_bboxlog()
            if len(bboxlog) > max_page_primitives:
                return _cluster_dense_bboxlog_grid(
                    bboxlog=bboxlog,
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
        # Ignorar líneas separatorias largas o cajas de página completa
        if r.width >= page_w * 0.92 or r.height >= page_h * 0.92:
            continue
        if r.width < 2.0 and r.height < 2.0:
            continue
        candidate_rects.append(r)

    n = len(candidate_rects)
    if n < min_drawing_count:
        return []

    threshold = 12.0  # puntos tipográficos de separación máxima
    uf = _UnionFind(n)

    # Indexación espacial por celdas para evitar comparaciones cuadráticas innecesarias
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

    # Ordenar determinísticamente de arriba hacia abajo, izquierda a derecha
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
