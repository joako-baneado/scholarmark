"""
Geometry and visual element extraction engine for ScholarMark.
Handles multimodal bounding box fusion, vector drawings clustering, and high-DPI rendering.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
import fitz  # PyMuPDF


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

    def to_fitz_rect(self) -> fitz.Rect:
        return fitz.Rect(self.x0, self.y0, self.x1, self.y1)

    @classmethod
    def from_fitz_rect(cls, rect: fitz.Rect) -> "BoundingBox":
        return cls(x0=float(rect.x0), y0=float(rect.y0), x1=float(rect.x1), y1=float(rect.y1))

    def pad(self, padding: float, page_rect: Optional[fitz.Rect] = None) -> "BoundingBox":
        """Añade margen de guarda (bleed padding) sin exceder los límites de la página."""
        max_w = float(page_rect.width) if page_rect else float('inf')
        max_h = float(page_rect.height) if page_rect else float('inf')
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


def expand_figure_bbox(
    page: fitz.Page,
    figure_bbox: BoundingBox,
    proximity_threshold: float = 10.0,
    bleed_padding: float = 4.0
) -> BoundingBox:
    """
    Fusiona la caja base de una figura con primitivas vectoriales (ejes, marcas, curvas)
    y notaciones adyacentes para evitar truncamientos de escalas o etiquetas cartesianas.
    """
    refined_box = figure_bbox
    fig_rect = figure_bbox.to_fitz_rect()
    
    # 1. Fusión de trazos vectoriales circundantes (get_drawings)
    drawings = page.get_drawings()
    for draw in drawings:
        d_rect = draw["rect"]
        # Si interseca o está a distancia vertical/horizontal menor al umbral
        if fig_rect.intersects(d_rect) or (
            abs(fig_rect.y1 - d_rect.y0) <= proximity_threshold
            and fig_rect.x0 <= d_rect.x1
            and fig_rect.x1 >= d_rect.x0
        ) or (
            abs(fig_rect.x0 - d_rect.x1) <= proximity_threshold
            and fig_rect.y0 <= d_rect.y1
            and fig_rect.y1 >= d_rect.y0
        ):
            # Filtrar fondos gigantescos de página completa para no colapsar el bbox
            if d_rect.width < (page.rect.width * 0.95) and d_rect.height < (page.rect.height * 0.95):
                refined_box = refined_box.union(d_rect)

    # 2. Inclusión de notaciones de subpaneles ((a), (b), (c)) cercanas a las esquinas
    try:
        words = page.get_text("words")  # [x0, y0, x1, y1, word, block_no, line_no, word_no]
        for w in words:
            w_rect = fitz.Rect(w[0], w[1], w[2], w[3])
            text = str(w[4]).strip()
            # Identificar subpaneles típicos: (a), (b), (c), (A), [a], etc.
            if len(text) in [3, 4] and text.startswith(("(", "[")) and text.endswith((")", "]")):
                # Verificar proximidad directa al cuadro actual
                if (abs(refined_box.x0 - w_rect.x1) < 15.0 and refined_box.y0 <= w_rect.y1 and refined_box.y1 >= w_rect.y0) or \
                   (abs(refined_box.y0 - w_rect.y1) < 15.0 and refined_box.x0 <= w_rect.x1 and refined_box.x1 >= w_rect.x0):
                    refined_box = refined_box.union(w_rect)
    except Exception:
        pass

    # 3. Aplicar margen de guarda (bleed padding)
    return refined_box.pad(bleed_padding, page.rect)


def cluster_vector_drawings(
    page: fitz.Page,
    min_drawing_count: int = 8,
    min_area: float = 3500.0
) -> List[BoundingBox]:
    """
    Agrupa trazos vectoriales densos que constituyen gráficos funcionales sin mapas de bits
    (p. ej. matplotlib, TikZ, diagramas de bloques generados por LaTeX).
    """
    drawings = page.get_drawings()
    if not drawings:
        return []

    page_w = page.rect.width
    page_h = page.rect.height
    candidate_rects = []

    for d in drawings:
        r = d["rect"]
        # Ignorar líneas separatorias largas o cajas de página completa
        if r.width >= page_w * 0.92 or r.height >= page_h * 0.92:
            continue
        if r.width < 2.0 and r.height < 2.0:
            continue
        candidate_rects.append(r)

    if len(candidate_rects) < min_drawing_count:
        return []

    # Clustering voraz por proximidad euclidiana de rectángulos
    clusters: List[List[fitz.Rect]] = []
    threshold = 12.0  # puntos tipográficos de separación máxima

    for r in candidate_rects:
        merged = False
        for c in clusters:
            # Comprobar si r está cerca de alguno de los elementos del cluster
            for existing in c:
                if existing.intersects(r) or (
                    abs(existing.x0 - r.x1) < threshold or abs(r.x0 - existing.x1) < threshold
                ) and (
                    abs(existing.y0 - r.y1) < threshold or abs(r.y0 - existing.y1) < threshold
                ):
                    c.append(r)
                    merged = True
                    break
            if merged:
                break
        if not merged:
            clusters.append([r])

    result_boxes: List[BoundingBox] = []
    for c in clusters:
        if len(c) < min_drawing_count:
            continue
        
        # Calcular envolvente convexa del cluster
        u = c[0]
        for item in c[1:]:
            u = u | item
            
        area = u.width * u.height
        # Descartar elementos microscópicos o la página entera
        if area >= min_area and u.width < page_w * 0.95 and u.height < page_h * 0.95:
            box = BoundingBox.from_fitz_rect(u)
            result_boxes.append(box)

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

        # Renderizar pixmap de alta fidelidad contra fondo blanco opaco
        pix = page.get_pixmap(matrix=affine_matrix, clip=clip_rect, alpha=False)
        pix.save(str(destination))
        return True
    except Exception as e:
        return False
