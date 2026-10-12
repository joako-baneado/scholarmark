"""
Caption matching and spatial correlation engine for ScholarMark.
Associates figures with their respective captions using the Hungarian algorithm
and spatial proximity penalties across single- and multi-column layouts.
"""

import re
from typing import List, Tuple, Optional
import fitz
import numpy as np

from .geometry import BoundingBox, VisualElement

# Expresión regular multilingüe para títulos de figuras y diagramas científicos
CAPTION_REGEX = re.compile(
    r"^(Fig(\.|ure)?|FIG(\.|URE)?|Figura|Figur|Abbildung)\s+([0-9]+|[A-Z])(\.[0-9]+)?(\s*[:\.\-—]|\s*\([a-z]\))",
    re.IGNORECASE
)

# Expresión regular para tablas (para evitar asociar epígrafes de tablas a figuras)
TABLE_CAPTION_REGEX = re.compile(
    r"^(Table|TABLE|Tabla|Tabell|Tabelle)\s+([0-9]+|[A-Z])",
    re.IGNORECASE
)


def extract_captions_from_page(page: fitz.Page) -> List[Tuple[BoundingBox, str]]:
    """
    Detecta bloques de texto en la página que inician con sintaxis de leyendas científicas.
    Retorna pares de (BoundingBox, texto_leyenda).
    """
    captions = []
    blocks = page.get_text("blocks")  # [x0, y0, x1, y1, text, block_no, block_type]

    for b in blocks:
        if b[6] != 0:  # Ignorar bloques no textuales
            continue
        text = b[4].strip()
        if not text:
            continue

        # Si coincide con patrón de figura y NO es una tabla
        if CAPTION_REGEX.search(text) and not TABLE_CAPTION_REGEX.search(text):
            box = BoundingBox(x0=float(b[0]), y0=float(b[1]), x1=float(b[2]), y1=float(b[3]))
            # Normalizar saltos de línea internos en un párrafo continuo
            clean_text = " ".join(text.split())
            captions.append((box, clean_text))

    return captions


def match_figures_to_captions(
    figures: List[VisualElement],
    captions: List[Tuple[BoundingBox, str]],
    page_width: float
) -> None:
    """
    Asigna de forma determinista y biyectiva cada figura a su respectivo pie de página (caption).
    Utiliza una matriz de coste espacial con penalizaciones por desplazamiento vertical,
    horizontal y división de columnas, resuelta mediante el Algoritmo Húngaro.
    """
    if not figures or not captions:
        return

    num_figs = len(figures)
    num_caps = len(captions)
    cost_matrix = np.zeros((num_figs, num_caps), dtype=np.float64)

    is_multi_col = page_width > 500  # Páginas estándar típicamente ~595 o 612 pt
    col_mid = page_width / 2.0

    for i, fig in enumerate(figures):
        f_box = fig.bbox
        f_center_x = (f_box.x0 + f_box.x1) / 2.0
        f_is_wide = f_box.width > (page_width * 0.65)

        for j, (cap_box, cap_text) in enumerate(captions):
            c_center_x = (cap_box.x0 + cap_box.x1) / 2.0

            # 1. Distancia vertical: el pie de foto comúnmente está DEBAJO de la figura
            v_dist = cap_box.y0 - f_box.y1
            if v_dist >= 0:
                # Distancia directa hacia abajo
                v_cost = v_dist * 1.0
            else:
                # Penalización severa si la leyenda se ubica encima de la imagen
                v_cost = abs(v_dist) * 4.5

            # 2. Distancia horizontal entre centroides
            h_cost = abs(c_center_x - f_center_x) * 1.2

            # 3. Penalización de columna: si están en columnas opuestas y la figura no es de ancho completo
            col_penalty = 0.0
            if is_multi_col and not f_is_wide:
                fig_col = 0 if f_center_x < col_mid else 1
                cap_col = 0 if c_center_x < col_mid else 1
                if fig_col != cap_col:
                    col_penalty = 400.0  # Fuerte barrera entre columnas adyacentes

            # 4. Bonificación léxica si la leyenda inicia explícitamente con Fig/Figure
            regex_bonus = -60.0 if CAPTION_REGEX.search(cap_text) else 0.0

            cost_matrix[i, j] = v_cost + h_cost + col_penalty + regex_bonus

    # Intentar resolver mediante SciPy (Algoritmo Húngaro O(N^3))
    try:
        from scipy.optimize import linear_sum_assignment
        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        for r, c in zip(row_ind, col_ind):
            # Asignar solo si el coste no es absurdamente alto (p. ej. otra columna sin relación)
            if cost_matrix[r, c] < 800.0:
                figures[r].caption_text = captions[c][1]
    except ImportError:
        # Fallback Greedy si SciPy no estuviera disponible en el entorno
        assigned_caps = set()
        for i in range(num_figs):
            best_j = None
            min_c = float('inf')
            for j in range(num_caps):
                if j not in assigned_caps and cost_matrix[i, j] < min_c:
                    min_c = cost_matrix[i, j]
                    best_j = j
            if best_j is not None and min_c < 800.0:
                figures[i].caption_text = captions[best_j][1]
                assigned_caps.add(best_j)
