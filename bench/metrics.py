"""
Quantitative evaluation metrics for ScholarMark v3.0 Benchmark Harness:
- Normalized Edit Distance (NED) & Text Fidelity (1 - NED)
- Kendall's Tau rank correlation for Reading Order
- Tree/Structural HTML Table Similarity (TEDS / TEDS-Struct proxy)
- Normalized LaTeX Formula Similarity
- Precision, Recall & F1 for 1:N Figure/Table Caption Matching
"""

from html.parser import HTMLParser
import re
from typing import List, Tuple, Set


def levenshtein_distance(s1: List[str], s2: List[str]) -> int:
    """Distancia de edición de programación dinámica O(N*M) sobre secuencias de tokens o caracteres."""
    if len(s1) < len(s2):
        s1, s2 = s2, s1
    if not s2:
        return len(s1)

    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


def normalized_edit_distance(pred: str, gold: str) -> float:
    """Calcula Normalized Edit Distance (NED) en [0.0, 1.0]. Menor es mejor."""
    p = " ".join(pred.split())
    g = " ".join(gold.split())
    if not p and not g:
        return 0.0
    max_len = max(len(p), len(g))
    if max_len == 0:
        return 0.0
    try:
        from rapidfuzz.distance import Levenshtein
        dist = Levenshtein.distance(p, g)
    except ImportError:
        dist = levenshtein_distance(list(p), list(g))
    return float(dist) / float(max_len)


def text_fidelity_score(pred: str, gold: str) -> float:
    """Retorna 1.0 - NED en [0.0, 1.0]. Mayor es mejor."""
    return max(0.0, 1.0 - normalized_edit_distance(pred, gold))


def kendall_tau_order(pred_seq: List[str], gold_seq: List[str]) -> float:
    """
    Calcula la correlación de orden de lectura de Kendall-τ normalizada a [0.0, 1.0]
    sobre los bloques presentes en gold_seq.
    1.0 indica orden de lectura idéntico; 0.0 indica inversión total.
    """
    common = [x for x in pred_seq if x in set(gold_seq)]
    n = len(gold_seq)
    if n <= 1:
        return 1.0
    if len(common) <= 1:
        return 0.0

    gold_rank = {item: idx for idx, item in enumerate(gold_seq)}
    ranks = [gold_rank[item] for item in common]

    concordant = 0
    discordant = 0
    m = len(ranks)
    for i in range(m):
        for j in range(i + 1, m):
            if ranks[i] < ranks[j]:
                concordant += 1
            elif ranks[i] > ranks[j]:
                discordant += 1

    total_pairs = m * (m - 1) / 2.0
    tau = (concordant - discordant) / total_pairs if total_pairs > 0 else 1.0
    coverage = len(common) / float(n)
    return max(0.0, ((tau + 1.0) * 0.5) * coverage)


class _TableDOMParser(HTMLParser):
    """Extrae la secuencia linealizada de nodos estructurales y textos de una tabla HTML."""

    def __init__(self):
        super().__init__()
        self.struct_tokens: List[str] = []
        self.cell_tokens: List[str] = []
        self._in_cell = False
        self._cur_text: List[str] = []
        self._cur_tag = ""

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str]]):
        t = tag.lower()
        if t in ("table", "thead", "tbody", "tr", "th", "td"):
            attr_dict = {k.lower(): v for k, v in attrs if k.lower() in ("colspan", "rowspan")}
            span_sig = "".join(f"[{k}={v}]" for k, v in sorted(attr_dict.items()))
            self.struct_tokens.append(f"<{t}{span_sig}>")
            if t in ("th", "td"):
                self._in_cell = True
                self._cur_tag = f"{t}{span_sig}"
                self._cur_text = []

    def handle_endtag(self, tag: str):
        t = tag.lower()
        if t in ("table", "thead", "tbody", "tr", "th", "td"):
            self.struct_tokens.append(f"</{t}>")
            if t in ("th", "td") and self._in_cell:
                txt = " ".join("".join(self._cur_text).split())
                self.cell_tokens.append(f"{self._cur_tag}:{txt}")
                self._in_cell = False

    def handle_data(self, data: str):
        if self._in_cell:
            self._cur_text.append(data)


def teds_table_score(pred_html: str, gold_html: str, structure_only: bool = False) -> float:
    """
    Calcula la similitud estructural y de contenido de tablas HTML (TEDS / TEDS-Struct).
    Evalúa tanto la topología de etiquetas (tr, th, td, colspan, rowspan) como el contenido de cada celda.
    """
    p_parser = _TableDOMParser()
    g_parser = _TableDOMParser()
    p_parser.feed(pred_html or "")
    g_parser.feed(gold_html or "")

    if not g_parser.struct_tokens:
        return 1.0 if not p_parser.struct_tokens else 0.0
    if not p_parser.struct_tokens:
        return 0.0

    struct_dist = levenshtein_distance(p_parser.struct_tokens, g_parser.struct_tokens)
    struct_max = max(len(p_parser.struct_tokens), len(g_parser.struct_tokens))
    struct_sim = max(0.0, 1.0 - (struct_dist / float(struct_max)))

    if structure_only:
        return struct_sim

    cell_dist = levenshtein_distance(p_parser.cell_tokens, g_parser.cell_tokens)
    cell_max = max(1, len(p_parser.cell_tokens), len(g_parser.cell_tokens))
    cell_sim = max(0.0, 1.0 - (cell_dist / float(cell_max)))

    return 0.5 * struct_sim + 0.5 * cell_sim


def normalize_latex_tokens(latex: str) -> str:
    """Normaliza espacios y comandos equivalentes en LaTeX para comparación justa."""
    s = (latex or "").strip()
    s = re.sub(r"^\$\$|\$\$$", "", s).strip()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("{ ", "{").replace(" }", "}")
    return s


def latex_formula_similarity(pred_latex: str, gold_latex: str) -> float:
    """Retorna 1 - NED sobre cadenas LaTeX normalizadas."""
    p = normalize_latex_tokens(pred_latex)
    g = normalize_latex_tokens(gold_latex)
    return text_fidelity_score(p, g)


def caption_matching_f1(
    pred_pairs: Set[Tuple[str, str]],
    gold_pairs: Set[Tuple[str, str]]
) -> Tuple[float, float, float]:
    """Calcula (Precision, Recall, F1) sobre pares (id_elemento, texto_leyenda)."""
    if not gold_pairs and not pred_pairs:
        return 1.0, 1.0, 1.0
    if not gold_pairs or not pred_pairs:
        return 0.0, 0.0, 0.0

    tp = len(pred_pairs & gold_pairs)
    prec = tp / float(len(pred_pairs))
    rec = tp / float(len(gold_pairs))
    f1 = (2.0 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
    return prec, rec, f1
