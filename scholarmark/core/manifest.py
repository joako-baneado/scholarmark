"""
Grounding manifest generator module for ScholarMark v3.0.
Builds a machine-readable JSON index of tables (GFM & semantic HTML), equations,
metrics, and sections specifically tailored for RAG pipelines and LLM citation validators.
"""

import json
import re
from pathlib import Path
from typing import Optional
import yaml

from .. import __version__
from .citations import BibliographyParser, expand_citation_markers


_HTML_TABLE_RE = re.compile(r'<table\b[^>]*>(.*?)</table>', re.IGNORECASE | re.DOTALL)
_HTML_TR_RE = re.compile(r'<tr\b[^>]*>(.*?)</tr>', re.IGNORECASE | re.DOTALL)
_HTML_TH_TD_RE = re.compile(r'<(?:th|td)\b[^>]*>(.*?)</(?:th|td)>', re.IGNORECASE | re.DOTALL)
_HTML_TAG_STRIP_RE = re.compile(r'<[^>]+>')


def _parse_html_tables(text: str, start_idx: int = 1) -> list:
    """Extrae metadatos estructurales de tablas HTML semánticas (con soporte colspan/rowspan)."""
    tables = []
    for offset, match in enumerate(_HTML_TABLE_RE.finditer(text)):
        table_html = match.group(0)
        inner = match.group(1)
        rows = _HTML_TR_RE.findall(inner)
        if not rows:
            continue
        first_row_cells = _HTML_TH_TD_RE.findall(rows[0])
        headers = [
            " ".join(_HTML_TAG_STRIP_RE.sub("", c).split()).strip()
            for c in first_row_cells
        ]
        has_spans = bool(re.search(r'\b(?:colspan|rowspan)\s*=', table_html, re.IGNORECASE))
        tables.append({
            'table_index': start_idx + offset,
            'format': 'html',
            'has_merged_cells': has_spans,
            'headers': headers,
            'rows': max(0, len(rows) - 1),
        })
    return tables


def extract_document_info(md_path: Path) -> dict:
    """
    Extrae metadatos, tablas estructuradas (GFM y HTML), ecuaciones, métricas,
    bibliografía estructurada, afirmaciones ancladas (grounded_claims) y semántica
    de gráficos de un archivo Markdown (y su *.ir.json compañero si existe).
    """
    text = md_path.read_text(encoding='utf-8')

    # 1. Frontmatter YAML
    meta = {}
    if text.startswith('---'):
        parts = text.split('---', 2)
        if len(parts) >= 3:
            try:
                meta = yaml.safe_load(parts[1]) or {}
            except Exception:
                pass

    title = meta.get('title', md_path.stem)
    doi = meta.get('doi', '')
    year = meta.get('year', None)
    engine = meta.get('engine', 'fast')

    # 2. Secciones
    sections = re.findall(r'^##\s+(.+)$', text, re.MULTILINE)

    # 3. Tablas estructuradas (GFM + HTML)
    tables = []
    table_blocks = re.findall(r'(\|[^\n]+\|\n\|[\s\-:|]+\|\n(?:\|[^\n]+\|\n*)+)', text)
    for idx, tb in enumerate(table_blocks):
        lines = [l.strip() for l in tb.strip().splitlines()]
        if len(lines) >= 3:
            headers = [c.strip('* ').strip() for c in lines[0].split('|')[1:-1]]
            row_count = len(lines) - 2
            tables.append({
                'table_index': idx + 1,
                'format': 'gfm',
                'has_merged_cells': False,
                'headers': headers,
                'rows': row_count,
            })

    html_tables = _parse_html_tables(text, start_idx=len(tables) + 1)
    tables.extend(html_tables)

    # 4. Ecuaciones
    block_eqs = len(re.findall(r'\$\$(.*?)\$\$', text, re.DOTALL))
    inline_eqs = len(re.findall(r'(?<!\$)\$([^$\n]+)\$(?!\$)', text))

    # 5. Figuras enlazadas y metadatos internos de gráficos
    fig_links = re.findall(r'!\[(.*?)\]\((.*?)\)', text)
    figures_meta = [
        {"caption": cap, "asset": path}
        for cap, path in fig_links
    ]

    # 6. Métricas factuales para Grounding
    percentages = sorted(set(re.findall(r'\b\d+(?:\.\d+)?\s*%', text)))[:25]
    performances = sorted(set(re.findall(
        r'\b\d+(?:\.\d+)?\s*(?:ms|s|FPS|fps|Hz|kHz|GFLOPs|MFLOPs|MB|GB|params)\b', text
    )))[:25]

    # 7. Bibliografía y citas desde *.ir.json compañero o desde el propio Markdown
    references_list = []
    grounded_claims = []
    algorithms_count = 0

    ir_json_path = md_path.with_suffix(".ir.json")
    if ir_json_path.exists():
        try:
            ir_data = json.loads(ir_json_path.read_text(encoding='utf-8'))
            ir_meta = ir_data.get("meta") or {}
            references_list = ir_meta.get("bibliography") or []
            grounded_claims = ir_meta.get("grounded_claims") or []
            chart_figures = []
            for pg in ir_data.get("pages", []):
                for blk in pg.get("blocks", []):
                    if blk.get("kind") == "algorithm":
                        algorithms_count += 1
                    elif blk.get("kind") == "figure":
                        c_sem = (blk.get("metadata") or {}).get("chart_semantics")
                        chart_figures.append({
                            "page": blk.get("page"),
                            "asset": blk.get("asset"),
                            "caption": blk.get("caption_text") or "",
                            "chart_semantics": c_sem,
                        })
            if chart_figures:
                figures_meta = chart_figures
        except Exception:
            pass

    if not references_list:
        ref_match = re.search(
            r'^##\s+[^\n]*(?:References|Bibliography|Referencias)[^\n]*\n(.+)$',
            text,
            re.IGNORECASE | re.MULTILINE | re.DOTALL,
        )
        if ref_match:
            parsed_refs = BibliographyParser.parse_from_text(ref_match.group(1))
            references_list = [r.to_dict() for r in parsed_refs]

    if not grounded_claims:
        # Extraer oraciones con métricas y citas directamente del Markdown
        body_text = re.split(r'^##\s+[^\n]*(?:References|Bibliography|Referencias)', text, flags=re.IGNORECASE | re.MULTILINE)[0]
        for sent in re.split(r'(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ0-9\[])', body_text):
            s_clean = " ".join(sent.split()).strip()
            if len(s_clean) < 20 or s_clean.startswith(("---", "#", "|", "!")):
                continue
            m_hits = re.findall(r'\b\d+(?:\.\d+)?\s*(?:%|(?:ms|s|FPS|fps|Hz|kHz|GFLOPs|MFLOPs|MB|GB|params|dB|mm)\b)', s_clean)
            c_hits = expand_citation_markers(s_clean)
            if m_hits and c_hits:
                grounded_claims.append({
                    "sentence": s_clean,
                    "metrics": m_hits,
                    "cited_ref_ids": c_hits,
                })
                if len(grounded_claims) >= 35:
                    break

    return {
        'filename': md_path.name,
        'title': title,
        'doi': doi,
        'year': year,
        'engine': engine,
        'total_sections': len(sections),
        'sections_sample': sections[:10],
        'tables_count': len(tables),
        'tables': tables,
        'block_equations_count': block_eqs,
        'inline_equations_count': inline_eqs,
        'figures_count': len(fig_links),
        'figures': figures_meta,
        'algorithms_count': algorithms_count,
        'references_count': len(references_list),
        'references': references_list,
        'grounded_claims': grounded_claims,
        'metrics': {
            'percentages': percentages,
            'performance': performances,
        }
    }


def generate_manifest(target_dir: Path, output_file: Optional[Path] = None) -> dict:
    """Genera el manifiesto integral JSON para todos los documentos Markdown del directorio."""
    target_dir = Path(target_dir)
    if output_file is None:
        output_file = target_dir / "scholarmark_manifest.json"

    md_files = sorted([
        f for f in target_dir.glob("*.md")
        if not f.name.startswith("informe_") and not f.name.startswith("README")
    ])

    manifest_data = {
        'version': __version__,
        'generator': f'ScholarMark High-Precision Extractor v{__version__}',
        'total_papers': len(md_files),
        'documents': {}
    }

    for f in md_files:
        manifest_data['documents'][f.stem] = extract_document_info(f)

    with open(output_file, 'w', encoding='utf-8') as jf:
        json.dump(manifest_data, jf, indent=2, ensure_ascii=False)

    return manifest_data
