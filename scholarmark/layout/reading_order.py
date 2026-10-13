"""
Topological DAG & Recursive XY-Cut Reading Order Solver for ScholarMark v3.0.
Resolves multi-column reading order, isolates footnotes to prevent mid-sentence
column interleaving, groups IEEE author biographies by column, and stitches
cross-page split paragraphs around floating figures/tables.
"""

import re
from typing import List, Tuple

from ..ir.document import Block, PageIR


_SENTENCE_END_RE = re.compile(r'[.!?:;”"\)\]]\s*$')


def _find_vertical_gutter(blocks: List[Block], page_width: float) -> Tuple[bool, float]:
    """
    Detecta si un conjunto de bloques se distribuye en dos columnas separadas por una medianera
    cercana al centro de la página.
    """
    if len(blocks) < 2 or page_width < 420.0:
        return False, page_width / 2.0

    mid = page_width / 2.0
    left_blocks = [b for b in blocks if b.bbox.x1 <= (mid + 18.0)]
    right_blocks = [b for b in blocks if b.bbox.x0 >= (mid - 18.0)]
    crossing = [
        b for b in blocks
        if b.bbox.x0 < (mid - 25.0) and b.bbox.x1 > (mid + 25.0)
    ]

    if left_blocks and right_blocks and len(crossing) == 0:
        gutter_x = (max(b.bbox.x1 for b in left_blocks) + min(b.bbox.x0 for b in right_blocks)) * 0.5
        return True, gutter_x

    return False, mid


def _order_band_blocks(band_blocks: List[Block], page_width: float) -> List[Block]:
    """
    Ordena un grupo de bloques situados entre dos cortes de ancho completo:
    - Si existe medianera vertical de dos columnas, lee íntegramente la columna izquierda
      de arriba hacia abajo y luego la columna derecha de arriba hacia abajo.
    - En caso contrario, ordena por cota vertical y0 y desempata por x0.
    """
    if len(band_blocks) <= 1:
        return list(band_blocks)

    is_two_col, gutter_x = _find_vertical_gutter(band_blocks, page_width)
    if is_two_col:
        left_col = [b for b in band_blocks if ((b.bbox.x0 + b.bbox.x1) * 0.5) < gutter_x]
        right_col = [b for b in band_blocks if ((b.bbox.x0 + b.bbox.x1) * 0.5) >= gutter_x]
        left_col.sort(key=lambda b: (round(b.bbox.y0, 1), round(b.bbox.x0, 1)))
        right_col.sort(key=lambda b: (round(b.bbox.y0, 1), round(b.bbox.x0, 1)))
        return left_col + right_col

    # Verificar si aun con algún elemento ligeramente desplazado la mayoría se divide en 2 columnas
    mid = page_width / 2.0
    left_narrow = [b for b in band_blocks if b.bbox.width < (page_width * 0.56) and ((b.bbox.x0 + b.bbox.x1) * 0.5) < mid]
    right_narrow = [b for b in band_blocks if b.bbox.width < (page_width * 0.56) and ((b.bbox.x0 + b.bbox.x1) * 0.5) >= mid]
    if left_narrow and right_narrow and (len(left_narrow) + len(right_narrow) == len(band_blocks)):
        left_narrow.sort(key=lambda b: (round(b.bbox.y0, 1), round(b.bbox.x0, 1)))
        right_narrow.sort(key=lambda b: (round(b.bbox.y0, 1), round(b.bbox.x0, 1)))
        return left_narrow + right_narrow

    return sorted(band_blocks, key=lambda b: (round(b.bbox.y0, 1), round(b.bbox.x0, 1)))


def order_page_blocks(blocks: List[Block], page_width: float) -> List[Block]:
    """
    Calcula el orden de lectura topológico de una página:
    1. Filtra bloques 'abandon'.
    2. Segrega 'footnote' al final de la página para evitar que se intercalen entre la
       columna izquierda y la columna derecha.
    3. Utiliza bloques de ancho completo (títulos, figuras/tablas de doble columna) como
       barreras horizontales de sincronización, aplicando ordenamiento por columna en cada banda.
    4. Agrupa las biografías de autores ('author_bio') por columna al cierre del cuerpo.
    """
    active = [b for b in blocks if b.kind != "abandon"]
    if not active:
        return []

    footnotes = [b for b in active if b.kind == "footnote"]
    bios = [b for b in active if b.kind == "author_bio"]
    body = [b for b in active if b.kind not in ("footnote", "author_bio")]

    # Ordenar candidatos por y0 para detectar barreras de ancho completo (spanning blocks)
    body_sorted_y = sorted(body, key=lambda b: (round(b.bbox.y0, 1), round(b.bbox.x0, 1)))
    full_width_threshold = page_width * 0.60

    ordered_body: List[Block] = []
    current_band: List[Block] = []

    for b in body_sorted_y:
        is_spanning = (b.bbox.width >= full_width_threshold) or (b.kind == "title")
        if is_spanning:
            if current_band:
                ordered_body.extend(_order_band_blocks(current_band, page_width))
                current_band = []
            ordered_body.append(b)
        else:
            current_band.append(b)

    if current_band:
        ordered_body.extend(_order_band_blocks(current_band, page_width))

    ordered_bios = _order_band_blocks(bios, page_width) if bios else []
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
