"""
Academic formatting, metadata extraction and heading normalization module for ScholarMark v3.0.
"""

import re
import yaml


def purge_ocr_artifacts(text: str) -> str:
    """Elimina fragmentos ruidosos de OCR generados dentro de bloques de imágenes."""
    text = re.sub(r'<!-- Start of picture text -->.*?<!-- End of picture text -->', '', text, flags=re.DOTALL)
    return text


def purge_page_numbers(text: str) -> str:
    """
    Elimina números de página sueltos en bordes de sección/página sin borrar
    números dentro de bloques matemáticos ($$...$$), bloques de código o tablas.
    """
    lines = text.splitlines()
    cleaned = []
    page_re = re.compile(r'^\s*\d{1,3}\s*$')
    in_math_block = False
    in_code_block = False

    n = len(lines)
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            cleaned.append(line)
            continue

        if stripped.startswith("$$"):
            # Si abre y cierra en la misma línea (ej. $$ x = 1 $$), no cambia el estado
            if stripped == "$$" or stripped.count("$$") == 1:
                in_math_block = not in_math_block
            cleaned.append(line)
            continue

        if in_math_block or in_code_block:
            cleaned.append(line)
            continue

        if page_re.match(stripped):
            prev_blank = (idx == 0) or (lines[idx - 1].strip() == "") or lines[idx - 1].strip().startswith("----")
            next_blank = (idx == n - 1) or (lines[idx + 1].strip() == "") or lines[idx + 1].strip().startswith("#")
            if prev_blank and next_blank:
                continue

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


# Patrones de secciones principales (números arábigos o romanos, o palabras clave de nivel 1)
_MAIN_SECTION_RE = re.compile(
    r'^\s*(?:#+\s*)?\*{0,2}('
    r'(?:[1-9]|1[0-5]|[I]{1,3}|IV|V|VI{0,3}|IX|X)\.\s+[A-ZÁÉÍÓÚÑ][^\n]{2,100}|'
    r'(?:ABSTRACT|RESUMEN|INTRODUCTION|INTRODUCCIÓN|RELATED\s+WORK|METHODOLOGY|METHODS|'
    r'EXPERIMENTS(?:\s+AND\s+RESULTS)?|RESULTS(?:\s+AND\s+DISCUSSION)?|DISCUSSION|'
    r'CONCLUSION|CONCLUSIONS|CONCLUSIONES|ACKNOWLEDGMENTS|ACKNOWLEDGEMENTS|REFERENCES|BIBLIOGRAPHY|REFERENCIAS)'
    r')\*{0,2}\s*$',
    re.IGNORECASE
)

_SUB_SECTION_RE = re.compile(
    r'^\s*(?:#+\s*)?\*{0,2}(\d+\.\d+(?:\.\d+)?\.?\s+[A-Za-zÁÉÍÓÚÑáéíóúñ][^\n]{1,120})\*{0,2}\s*$'
)


def standardize_headings(text: str, preserve_heading_text: bool = True) -> str:
    """
    Normaliza el nivel jerárquico de encabezados científicos (## y ###).
    Cuando preserve_heading_text=True (por defecto en v3.0), conserva el título original
    exacto del autor sin sobrescribirlo con etiquetas genéricas.
    """
    lines = text.splitlines()
    res = []

    legacy_patterns = [
        (r'^\s*(?:#+\s*)?(?:1\.?|I\.?)\s*(?:INTRODUCTION|Introducción)\s*$', '## 1. Introduction'),
        (r'^\s*(?:#+\s*)?(?:2\.?|II\.?)\s*(?:RELATED WORK|BACKGROUND|Trabajo Relacionado)\s*$', '## 2. Related Work'),
        (r'^\s*(?:#+\s*)?(?:3\.?|III\.?)\s*(?:METHODOLOGY|PROPOSED METHOD|METHODS|Metodología)\s*$', '## 3. Methodology'),
        (r'^\s*(?:#+\s*)?(?:4\.?|IV\.?)\s*(?:EXPERIMENTS|RESULTS|Experimentos|Resultados)\s*$', '## 4. Experiments and Results'),
        (r'^\s*(?:#+\s*)?(?:5\.?|V\.?)\s*(?:DISCUSSION|Discusión)\s*$', '## 5. Discussion'),
        (r'^\s*(?:#+\s*)?(?:6\.?|VI\.?)\s*(?:CONCLUSION|CONCLUSIONS|Conclusiones)\s*$', '## 6. Conclusion'),
        (r'^\s*(?:#+\s*)?(?:REFERENCES|BIBLIOGRAPHY|Referencias)\s*$', '## References'),
        (r'^\s*(?:#+\s*)?(?:ABSTRACT|Resumen)\s*$', '## Abstract'),
    ]

    for line in lines:
        stripped = line.strip()
        if not stripped:
            res.append(line)
            continue

        if not preserve_heading_text:
            matched = False
            for pat, rep in legacy_patterns:
                if re.match(pat, stripped, re.IGNORECASE):
                    res.append(rep)
                    matched = True
                    break
            if matched:
                continue

        # Subsección 1.1 o 1.1.1
        sub_m = _SUB_SECTION_RE.match(stripped)
        if sub_m:
            clean_heading = sub_m.group(1).strip().strip('*').strip()
            prefix = "####" if re.match(r'^\d+\.\d+\.\d+', clean_heading) else "###"
            res.append(f"{prefix} {clean_heading}")
            continue

        # Sección principal numerada o canónica
        main_m = _MAIN_SECTION_RE.match(stripped)
        if main_m and len(stripped) < 120:
            clean_heading = main_m.group(1).strip().strip('*').strip()
            res.append(f"## {clean_heading}")
            continue

        res.append(line)

    return '\n'.join(res)


def format_academic(text: str, filename: str, preserve_heading_text: bool = True) -> str:
    """Aplica el pipeline completo de formateo académico."""
    t = purge_ocr_artifacts(text)
    t = purge_page_numbers(t)
    t = standardize_headings(t, preserve_heading_text=preserve_heading_text)
    meta = parse_academic_metadata(t, filename)
    t = inject_frontmatter(t, meta)
    return t
