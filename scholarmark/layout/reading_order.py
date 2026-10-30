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
    Calcula el orden de lectura topológico DAG de una página con XY-Cut++ y enmascaramiento jerárquico:
    1. Filtra bloques 'abandon'.
    2. Segrega 'footnote' al final de la página para evitar que se intercalen entre columnas.
    3. Identifica elementos flotantes enmascarables (figuras, tablas, algoritmos, recuadros enmarcados)
       que invaden parcialmente medianeras o rompen la continuidad Manhattan.
    4. Aplica ordenamiento columnar estricto por bandas sobre la prosa remanente.
    5. Reinserta determinísticamente los flotantes enmascarados inmediatamente después del primer
       bloque de prosa que los referencia explícitamente (Fig. X, Table Y, Box Z, Algorithm K),
       o en el punto de corte de banda más cercano a su centroide vertical cy.
    6. Agrupa las biografías de autores ('author_bio') por columna al cierre del cuerpo.
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

    # Enmascaramiento jerárquico XY-Cut++:
    caption_map: Dict[str, Block] = {}
    for b in body:
        if b.kind in ("figure_caption", "table_caption"):
            parent_id = b.metadata.get("parent_figure_id") or b.metadata.get("parent_table_id")
            if parent_id:
                caption_map[str(parent_id)] = b

    full_width_threshold = page_width * 0.58
    masked_groups: List[Tuple[Block, List[Block], Optional[str]]] = []
    unmasked_body: List[Block] = []
    handled_ids = set()

    for b in body:
        if b.id in handled_ids:
            continue
        is_framed_box = bool(b.metadata.get("is_framed_box", False))
        is_float = b.kind in ("figure", "table", "algorithm") or is_framed_box

        crosses_gutter = any(
            b.bbox.x0 < (g0 - 4.0) and b.bbox.x1 > (g1 + 4.0)
            for g0, g1 in gutters_all
        )
        is_spanning_barrier = (b.bbox.width >= full_width_threshold) or (b.kind == "title")

        if is_float and not is_spanning_barrier and (crosses_gutter or is_framed_box or (b.bbox.width >= (page_width * 0.35) and gutters_all)):
            ref_label: Optional[str] = None
            assoc: List[Block] = [b]
            handled_ids.add(b.id)

            cap = caption_map.get(b.id)
            if cap and cap.id not in handled_ids:
                assoc.append(cap)
                handled_ids.add(cap.id)

            cap_text = cap.text if cap else (b.caption_text or b.text or "")
            m_fig = re.search(r"\b(Fig(?:ure)?\.?\s*\d+[a-zA-Z]?)\b", cap_text, re.I)
            m_tab = re.search(r"\b(Tab(?:le)?\.?\s*\d+[a-zA-Z]?)\b", cap_text, re.I)
            m_alg = re.search(r"\b(Algorithm\s*\d+)\b", cap_text, re.I)
            m_box = re.search(r"\b(Box\s*\d+)\b", cap_text, re.I)

            if m_fig:
                ref_label = m_fig.group(1)
            elif m_tab:
                ref_label = m_tab.group(1)
            elif m_alg:
                ref_label = m_alg.group(1)
            elif m_box:
                ref_label = m_box.group(1)

            masked_groups.append((b, assoc, ref_label))
        elif b.kind in ("figure_caption", "table_caption") and b.id in {blk.id for _, blist, _ in masked_groups for blk in blist}:
            continue
        else:
            unmasked_body.append(b)

    # Ordenar candidatos no enmascarados por y0 para detectar barreras de sincronización
    body_sorted_y = sorted(unmasked_body, key=lambda b: (round(b.bbox.y0, 1), round(b.bbox.x0, 1)))
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

    # Reinsertar determinísticamente cada grupo flotante enmascarado
    for main_b, assoc_blocks, ref_label in masked_groups:
        inserted = False
        if ref_label and ordered_body:
            m_num = re.search(r"\d+", ref_label)
            if m_num:
                num_str = m_num.group(0)
                if "fig" in ref_label.lower():
                    pat = re.compile(rf"\b(?:Fig\.?|Figure)\s*{num_str}\b", re.I)
                elif "tab" in ref_label.lower():
                    pat = re.compile(rf"\b(?:Tab\.?|Table)\s*{num_str}\b", re.I)
                elif "box" in ref_label.lower():
                    pat = re.compile(rf"\bBox\s*{num_str}\b", re.I)
                elif "alg" in ref_label.lower():
                    pat = re.compile(rf"\bAlgorithm\s*{num_str}\b", re.I)
                else:
                    pat = re.compile(rf"\b{re.escape(ref_label)}\b", re.I)
            else:
                pat = re.compile(rf"\b{re.escape(ref_label)}\b", re.I)

            for idx, ob in enumerate(ordered_body):
                if ob.kind in ("text", "paragraph", "list") and ob.text and pat.search(ob.text):
                    ordered_body[idx + 1:idx + 1] = assoc_blocks
                    inserted = True
                    break

        if not inserted:
            target_cy = (main_b.bbox.y0 + main_b.bbox.y1) * 0.5
            best_idx = len(ordered_body)
            for idx, ob in enumerate(ordered_body):
                ob_cy = (ob.bbox.y0 + ob.bbox.y1) * 0.5
                if ob_cy >= target_cy:
                    best_idx = idx
                    break
            ordered_body[best_idx:best_idx] = assoc_blocks

    ordered_bios = _order_band_blocks(bios, page_width, column_zones) if bios else []
    ordered_footnotes = sorted(footnotes, key=lambda b: (round(b.bbox.y0, 1), round(b.bbox.x0, 1)))

    return ordered_body + ordered_bios + ordered_footnotes


def stitch_cross_page_paragraphs(pages: List[PageIR]) -> List[str]:
    """
    Construye el orden de lectura global a través de todas las páginas del documento
    y recompone párrafos partidos entre páginas con horizonte multi-salto (Δp ∈ {1, 2}):
    - Si la página k termina con oración inconclusa y la página k+1 carece de bloques 'text'
      porque está ocupada exclusivamente por figuras o tablas, busca la continuación en la página k+2.
    """
    global_order: List[str] = []

    # Actualizar reading_order inicial por página
    for page in pages:
        ordered = page.ordered_blocks()
        page.reading_order = [b.id for b in ordered]

    for p_idx in range(len(pages)):
        page_k = pages[p_idx]
        ordered_k = page_k.ordered_blocks()
        prev_texts = [b for b in ordered_k if b.kind == "text" and b.text.strip()]
        if not prev_texts:
            continue
        last_prev = prev_texts[-1]
        prev_unfinished = not bool(_SENTENCE_END_RE.search(last_prev.text.strip()))
        if not prev_unfinished:
            continue

        # Probar horizonte multi-salto Δp ∈ {1, 2}
        for delta_p in (1, 2):
            next_idx = p_idx + delta_p
            if next_idx >= len(pages):
                break

            target_page = pages[next_idx]
            target_ordered = target_page.ordered_blocks()
            target_texts = [b for b in target_ordered if b.kind == "text" and b.text.strip()]

            if not target_texts:
                # La página intermedia carece de prosa; continuar a delta_p == 2
                continue

            first_curr = target_texts[0]
            curr_continues = first_curr.text.strip()[0].islower()

            if curr_continues:
                idx_first_text = target_ordered.index(first_curr)
                leading_floats = [
                    b for b in target_ordered[:idx_first_text]
                    if b.kind in ("figure", "figure_caption", "table", "table_caption")
                ]
                if leading_floats and len(leading_floats) == idx_first_text:
                    reordered = [first_curr] + leading_floats + target_ordered[idx_first_text + 1:]
                    target_page.reading_order = [b.id for b in reordered]

                if last_prev.text.endswith("-"):
                    last_prev.text = last_prev.text[:-1] + first_curr.text.lstrip()
                else:
                    last_prev.text = last_prev.text.rstrip() + " " + first_curr.text.lstrip()
                first_curr.text = ""
                first_curr.kind = "abandon"
                break

    for page in pages:
        for b in page.ordered_blocks():
            if b.kind != "abandon":
                global_order.append(b.id)

    return global_order
