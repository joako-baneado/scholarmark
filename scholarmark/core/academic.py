"""
Academic formatting, metadata extraction and heading normalization module for ScholarMark.
"""

import re
import yaml

def purge_ocr_artifacts(text: str) -> str:
    """Elimina fragmentos ruidosos de OCR generados dentro de bloques de imágenes."""
    text = re.sub(r'<!-- Start of picture text -->.*?<!-- End of picture text -->', '', text, flags=re.DOTALL)
    return text

def purge_page_numbers(text: str) -> str:
    """Elimina números de página sueltos al pie del documento."""
    lines = text.splitlines()
    cleaned = []
    page_re = re.compile(r'^\s*\d{1,3}\s*$')
    for line in lines:
        if not page_re.match(line.strip()):
            cleaned.append(line)
    return '\n'.join(cleaned)

def parse_academic_metadata(text: str, filename: str) -> dict:
    """Detecta metadatos clave como DOI, Título y Año de publicación."""
    meta = {
        'title': '',
        'doi': '',
        'year': None,
        'source_pdf': filename
    }
    
    # DOI
    doi_match = re.search(r'(?:https?://doi\.org/|doi:\s*)(10\.\d{4,9}/[^\s"\'<>]+)', text, re.IGNORECASE)
    if doi_match:
        meta['doi'] = doi_match.group(1).rstrip('.')
        
    # Título
    title_match = re.search(r'#+\s*\*{0,2}(.*?)\*{0,2}\s*$', text, re.MULTILINE)
    if title_match and len(title_match.group(1).strip()) > 10:
        meta['title'] = title_match.group(1).strip()
    else:
        meta['title'] = re.sub(r'[_\-]+', ' ', filename).replace('.pdf', '')
        
    # Año
    year_match = re.search(r'\b(20[0-2][0-9])\b', text[:2500])
    if year_match:
        meta['year'] = int(year_match.group(1))
        
    return meta

def inject_frontmatter(text: str, metadata: dict) -> str:
    """Inyecta metadatos en formato YAML Frontmatter estándar."""
    clean_meta = {k: v for k, v in metadata.items() if v}
    yaml_header = yaml.dump(clean_meta, allow_unicode=True, default_flow_style=False, sort_keys=False)
    
    if text.startswith('---'):
        parts = text.split('---', 2)
        if len(parts) >= 3:
            text = parts[2].lstrip()
            
    return f"---\n{yaml_header}---\n\n{text}"

def standardize_headings(text: str) -> str:
    """Estandariza encabezados de secciones científicas (## 1. Introduction, etc.)."""
    lines = text.splitlines()
    res = []
    
    patterns = [
        (r'^\s*(?:#+\s*)?(?:1\.?|I\.?)\s*(?:INTRODUCTION|Introducción)\b', '## 1. Introduction'),
        (r'^\s*(?:#+\s*)?(?:2\.?|II\.?)\s*(?:RELATED WORK|BACKGROUND|Trabajo Relacionado)\b', '## 2. Related Work'),
        (r'^\s*(?:#+\s*)?(?:3\.?|III\.?)\s*(?:METHODOLOGY|PROPOSED METHOD|METHODS|Metodología)\b', '## 3. Methodology'),
        (r'^\s*(?:#+\s*)?(?:4\.?|IV\.?)\s*(?:EXPERIMENTS|RESULTS|Experimentos|Resultados)\b', '## 4. Experiments and Results'),
        (r'^\s*(?:#+\s*)?(?:5\.?|V\.?)\s*(?:DISCUSSION|Discusión)\b', '## 5. Discussion'),
        (r'^\s*(?:#+\s*)?(?:6\.?|VI\.?)\s*(?:CONCLUSION|CONCLUSIONS|Conclusiones)\b', '## 6. Conclusion'),
        (r'^\s*(?:#+\s*)?(?:REFERENCES|BIBLIOGRAPHY|Referencias)\b', '## References'),
        (r'^\s*(?:#+\s*)?(?:ABSTRACT|Resumen)\b', '## Abstract'),
    ]
    
    for line in lines:
        matched = False
        for pat, rep in patterns:
            if re.match(pat, line.strip(), re.IGNORECASE):
                res.append(rep)
                matched = True
                break
        if not matched:
            sub = re.match(r'^\s*(?:#+\s*)?(\d+\.\d+\.?\s+[A-Za-z].*)$', line.strip())
            if sub and not line.strip().startswith('###'):
                res.append(f"### {sub.group(1)}")
            else:
                res.append(line)
                
    return '\n'.join(res)

def format_academic(text: str, filename: str) -> str:
    """Aplica el pipeline completo de formateo académico."""
    t = purge_ocr_artifacts(text)
    t = purge_page_numbers(t)
    t = standardize_headings(t)
    meta = parse_academic_metadata(t, filename)
    t = inject_frontmatter(t, meta)
    return t
