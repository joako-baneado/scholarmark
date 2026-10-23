"""
Topological DAG & Recursive XY-Cut Reading Order Solver for ScholarMark v4.1.
Resolves generalized N-column reading order (N ∈ {1, 2, 3}), isolates footnotes to prevent mid-sentence
column interleaving, groups IEEE author biographies by column, and stitches
cross-page split paragraphs around floating figures/tables.
"""

import re
from typing import List, Tuple, Dict, Optional

from ..ir.document import Block, PageIR
from ..core.geometry import BoundingBox, detect_column_zones, detect_column_gutters


_SENTENCE_END_RE = re.compile(r'[.!?:;”"\)\]]\s*$')


def _find_band_gutters(
    band_blocks: List[Block],
    page_width: float,
    column_zones: Optional[List[Tuple[float, float, float, float]]] = None,
) -> List[Tuple[float, float]]:
    """
    Identifica las medianeras verticales (gutters) activas para una banda horizontal de bloques.
    Soporta 1, 2 o 3 columnas, simétricas o asimétricas.
    """
    if len(band_blocks) < 2 or page_width < 350.0:
        return []

    band_y0 = min(b.bbox.y0 for b in band_blocks)
    band_y1 = max(b.bbox.y1 for b in band_blocks)

    # 1. Usar column_zones si están disponibles e intersectan verticalmente la banda
    if column_zones:
        active = [
            (g0, g1) for g0, g1, zy0, zy1 in column_zones
            if (zy0 - 15.0) <= band_y1 and (zy1 + 15.0) >= band_y0
        ]
        if active:
            return sorted(active, key=lambda g: g[0])

    # 2. Detección por proyección horizontal directa sobre los bloques de la banda
    gutters = detect_column_gutters(
        [b.bbox for b in band_blocks],
        page_width,
        max(30.0, band_y1 - band_y0),
        min_gutter_width=8.0,
    )
    if gutters:
        return sorted(gutters, key=lambda g: g[0])

    # 3. Heurística de partición bipartita para dos columnas con márgenes asimétricos o espaciados
    mid = page_width / 2.0
    left_cand = [b for b in band_blocks if b.bbox.x1 <= (mid + 20.0)]
    right_cand = [b for b in band_blocks if b.bbox.x0 >= (mid - 20.0)]
    if left_cand and right_cand and (len(left_cand) + len(right_cand) == len(band_blocks)):
        max_left = max(b.bbox.x1 for b in left_cand)
        min_right = min(b.bbox.x0 for b in right_cand)
        if min_right - max_left >= 6.0:
            return [(max_left, min_right)]

    return []


def _order_band_blocks(
    band_blocks: List[Block],
    page_width: float,
    column_zones: Optional[List[Tuple[float, float, float, float]]] = None,
) -> List[Block]:
    """
    Ordena un grupo de bloques situados entre dos cortes de sincronización (spanning blocks).
    Para N columnas, lee íntegramente de arriba a abajo Columna 0, luego Columna 1,
    y sucesivamente hasta Columna N-1. Si no hay columnas, ordena por y0 y desempata por x0.
    """
    if len(band_blocks) <= 1:
        return list(band_blocks)

    gutters = _find_band_gutters(band_blocks, page_width, column_zones)
    if not gutters:
        return sorted(band_blocks, key=lambda b: (round(b.bbox.y0, 1), round(b.bbox.x0, 1)))

    split_xs = [(g0 + g1) * 0.5 for g0, g1 in gutters]
    num_cols = len(split_xs) + 1

    col_groups: Dict[int, List[Block]] = {c: [] for c in range(num_cols)}
    for b in band_blocks:
        cx = (b.bbox.x0 + b.bbox.x1) * 0.5
        cid = sum(1 for sx in split_xs if cx > sx)
        cid = min(cid, num_cols - 1)
        col_groups[cid].append(b)

    ordered: List[Block] = []
    for cid in range(num_cols):
        blocks_in_col = col_groups[cid]
        blocks_in_col.sort(key=lambda b: (round(b.bbox.y0, 1), round(b.bbox.x0, 1)))
        ordered.extend(blocks_in_col)

    return ordered


def order_page_blocks(
    blocks: List[Block],
    page_width: float,
    column_zones: Optional[List[Tuple[float, float, float, float]]] = None,
) -> List[Block]:
    """
    Calcula el orden de lectura topológico DAG de una página:
    1. Filtra bloques 'abandon'.
    2. Segrega 'footnote' al final de la página para evitar que se intercalen entre columnas.
    3. Utiliza bloques de ancho completo o elementos que cruzan medianeras (títulos, figuras/tablas
       de doble columna) como barreras de sincronización XY-Cut, aplicando ordenamiento de N columnas
       en cada banda intermedia.
    4. Agrupa las biografías de autores ('author_bio') por columna al cierre del cuerpo.
    """
    active = [b for b in blocks if b.kind != "abandon"]
    if not active:
        return []

    footnotes = [b for b in active if b.kind == "footnote"]
    bios = [b for b in active if b.kind == "author_bio"]
    body = [b for b in active if b.kind not in ("footnote", "author_bio")]

    # Detectar column_zones si no fueron suministrados
    if not column_zones and body:
        page_h = max((b.bbox.y1 for b in active), default=842.0)
        column_zones = detect_column_zones([b.bbox for b in body], page_width, page_h)

    gutters_all = [(g0, g1) for g0, g1, _, _ in column_zones] if column_zones else []

    # Ordenar candidatos por y0 para detectar barreras de sincronización
    body_sorted_y = sorted(body, key=lambda b: (round(b.bbox.y0, 1), round(b.bbox.x0, 1)))
    full_width_threshold = page_width * 0.58

    ordered_body: List[Block] = []
    current_band: List[Block] = []

    for b in body_sorted_y:
        crosses_gutter = any(
            b.bbox.x0 < (g0 - 4.0) and b.bbox.x1 > (g1 + 4.0)
            for g0, g1 in gutters_all
        )
        is_spanning = (b.bbox.width >= full_width_threshold) or (b.kind == "title") or crosses_gutter
        if is_spanning:
            if current_band:
                ordered_body.extend(_order_band_blocks(current_band, page_width, column_zones))
                current_band = []
            ordered_body.append(b)
        else:
            current_band.append(b)

    if current_band:
        ordered_body.extend(_order_band_blocks(current_band, page_width, column_zones))

    ordered_bios = _order_band_blocks(bios, page_width, column_zones) if bios else []
    ordered_footnotes = sorted(footnotes, key=lambda b: (round(b.bbox.y0, 1), round(b.bbox.x0, 1)))

    return ordered_body + ordered_bios + ordered_footnotes


def stitch_cross_page_paragraphs(pages: List[PageIR]) -> List[str]:
    """
    Construye el orden de lectura global a través de todas las páginas del documento
    y recompone párrafos partidos entre páginas cuando una figura o tabla flotante
    se interpone al inicio de la página siguiente:
    - Si el último bloque 'text' de la página k no finaliza con puntuación terminal y el primer
      bloque 'text' de la página k+1 inicia con minúscula, adelanta la continuación del párrafo
      antes de los flotantes ('figure'/'table') que encabezaban la página k+1.
    """
    global_order: List[str] = []

    for p_idx, page in enumerate(pages):
        ordered = page.ordered_blocks()
        page.reading_order = [b.id for b in ordered]

        if p_idx > 0:
            prev_ordered = pages[p_idx - 1].ordered_blocks()
            prev_texts = [b for b in prev_ordered if b.kind == "text" and b.text.strip()]
            curr_texts = [b for b in ordered if b.kind == "text" and b.text.strip()]

            if prev_texts and curr_texts:
                last_prev = prev_texts[-1]
                first_curr = curr_texts[0]
                prev_unfinished = not bool(_SENTENCE_END_RE.search(last_prev.text.strip()))
                curr_continues = first_curr.text.strip()[0].islower()

                if prev_unfinished and curr_continues:
                    # Si hay figuras/tablas flotantes antes de first_curr en la página actual,
                    # colocar first_curr primero para no partir la frase a la mitad
                    idx_first_text = ordered.index(first_curr)
                    leading_floats = [
                        b for b in ordered[:idx_first_text]
                        if b.kind in ("figure", "figure_caption", "table", "table_caption")
                    ]
                    if leading_floats and len(leading_floats) == idx_first_text:
                        reordered = [first_curr] + leading_floats + ordered[idx_first_text + 1:]
                        page.reading_order = [b.id for b in reordered]
                        ordered = reordered

                    # Fusionar semánticamente la oración partida en last_prev para preservar anáfora en RAG
                    if last_prev.text.endswith("-"):
                        last_prev.text = last_prev.text[:-1] + first_curr.text.lstrip()
                    else:
                        last_prev.text = last_prev.text.rstrip() + " " + first_curr.text.lstrip()
                    first_curr.text = ""
                    first_curr.kind = "abandon"

        for b in ordered:
            if b.kind != "abandon":
                global_order.append(b.id)

    return global_order
