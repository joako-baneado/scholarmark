"""
Grounding manifest generator module for ScholarMark.
Builds a machine-readable JSON index of tables, equations, metrics, and sections
specifically tailored for RAG pipelines and LLM citation validators.
"""

import json
import re
from pathlib import Path
import yaml

def extract_document_info(md_path: Path) -> dict:
    """Extrae metadatos, tablas estructuradas, ecuaciones y métricas de un archivo Markdown."""
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
    
    # 2. Secciones
    sections = re.findall(r'^##\s+(.+)$', text, re.MULTILINE)
    
    # 3. Tablas estructuradas
    tables = []
    table_blocks = re.findall(r'(\|[^\n]+\|\n\|[\s\-:|]+\|\n(?:\|[^\n]+\|\n*)+)', text)
    for idx, tb in enumerate(table_blocks):
        lines = [l.strip() for l in tb.strip().splitlines()]
        if len(lines) >= 3:
            headers = [c.strip('* ').strip() for c in lines[0].split('|')[1:-1]]
            row_count = len(lines) - 2
            tables.append({
                'table_index': idx + 1,
                'headers': headers,
                'rows': row_count
            })
            
    # 4. Ecuaciones
    block_eqs = len(re.findall(r'\$\$(.*?)\$\$', text, re.DOTALL))
    inline_eqs = len(re.findall(r'(?<!\$)\$([^$\n]+)\$(?!\$)', text))
    
    # 5. Figuras enlazadas
    fig_links = re.findall(r'!\[(.*?)\]\((.*?)\)', text)
    
    # 6. Métricas factuales para Grounding
    percentages = list(set(re.findall(r'\b\d+(?:\.\d+)?\s*%', text)))[:20]
    performances = list(set(re.findall(r'\b\d+(?:\.\d+)?\s*(?:ms|FPS|fps|Hz|GFLOPs|MFLOPs)\b', text)))[:20]
    
    return {
        'filename': md_path.name,
        'title': title,
        'doi': doi,
        'year': year,
        'total_sections': len(sections),
        'sections_sample': sections[:10],
        'tables_count': len(tables),
        'tables': tables,
        'block_equations_count': block_eqs,
        'inline_equations_count': inline_eqs,
        'figures_count': len(fig_links),
        'metrics': {
            'percentages': percentages,
            'performance': performances
        }
    }

def generate_manifest(target_dir: Path, output_file: Path = None) -> dict:
    """Genera el manifiesto integral JSON para todos los documentos Markdown del directorio."""
    if output_file is None:
        output_file = target_dir / "scholarmark_manifest.json"
        
    md_files = sorted([f for f in target_dir.glob("*.md") if not f.name.startswith("informe_") and not f.name.startswith("README")])
    
    manifest_data = {
        'version': '2.0.0',
        'generator': 'ScholarMark High-Precision Extractor',
        'total_papers': len(md_files),
        'documents': {}
    }
    
    for f in md_files:
        manifest_data['documents'][f.stem] = extract_document_info(f)
        
    with open(output_file, 'w', encoding='utf-8') as jf:
        json.dump(manifest_data, jf, indent=2, ensure_ascii=False)
        
    return manifest_data
