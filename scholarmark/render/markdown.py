"""
Markdown renderer for ScholarMark v3.0 DocumentIR.
Emits clean Markdown with KaTeX math, semantic HTML for complex tables (colspan/rowspan),
GFM for simple tables, contextualized figure links, and segregated footnotes.
"""

import re
from typing import List, Set

from ..config import ExtractorConfig
from ..core.academic import format_academic
from ..core.math_parser import parse_math, clean_math_glyphs, format_inline_expressions, sanitize_numeric_typography
from ..ir.document import DocumentIR, Block
from ..utils.paths import sanitize_slug


def _format_inline_text(text: str, enable_math: bool = True) -> str:
    if not text:
        return ""
    if not enable_math:
        return text
    t = sanitize_numeric_typography(text)
    t = clean_math_glyphs(t)
    t = format_inline_expressions(t)
    return t


def _has_merged_cells(html: str) -> bool:
    return bool(re.search(r'\b(?:colspan|rowspan)\s*=\s*["\']?[2-9]', html or "", re.IGNORECASE))


def render_markdown(ir: DocumentIR, config: ExtractorConfig, paper_stem: str, pdf_filename: str) -> str:
    """
    Serializa un DocumentIR hacia Markdown enriquecido listo para RAG.
    Si el motor suministró markdown_override (ej. FastEngine), aplica el pipeline de post-procesado.
    """
    if ir.markdown_override is not None:
        md = ir.markdown_override
        if config.math_to_latex:
            md = parse_math(md)
        if config.normalize_headings or config.inject_yaml_frontmatter:
            md = format_academic(md, pdf_filename, preserve_heading_text=config.preserve_heading_text)
        return md

    slug = sanitize_slug(paper_stem)
    blocks = ir.all_blocks_ordered()
    consumed_caption_ids: Set[str] = {
        b.caption_id for b in blocks if b.caption_id and b.kind in ("figure", "table", "formula")
    }

    chunks: List[str] = []
    footnotes: List[Block] = []

    for b in blocks:
        if b.kind == "abandon":
            continue
        if b.id in consumed_caption_ids and b.kind in ("figure_caption", "table_caption", "formula_caption"):
            continue
        if b.kind == "footnote":
            footnotes.append(b)
            continue

        if b.kind == "title":
            title_txt = _format_inline_text(b.text.strip(), config.math_to_latex)
            if title_txt:
                chunks.append(f"# {title_txt}")

        elif b.kind == "section_header":
            lvl = max(2, min(4, b.heading_level))
            hdr_txt = _format_inline_text(b.text.strip(), config.math_to_latex)
            if hdr_txt:
                chunks.append(f"{'#' * lvl} {hdr_txt}")

        elif b.kind == "formula":
            latex_body = (b.latex or b.text or "").strip()
            tag = b.metadata.get("tag")
            if tag and r"\tag{" not in latex_body:
                latex_body = f"{latex_body} \\tag{{{tag}}}"
            eq_block = f"$$\n{latex_body}\n$$"
            if b.confidence < 0.5 and b.text and b.latex and b.text.strip() != b.latex.strip():
                safe_native = b.text.strip().replace("-->", "--")
                eq_block += f"\n<!-- sm:native {safe_native} -->"
            chunks.append(eq_block)

        elif b.kind == "table":
            parts: List[str] = []
            if b.caption_text:
                parts.append(f"**{b.caption_text.strip()}**")
            if b.html and (config.html_complex_tables and (_has_merged_cells(b.html) or not b.gfm)):
                parts.append(b.html.strip())
            elif b.gfm:
                parts.append(b.gfm.strip())
            elif b.html:
                parts.append(b.html.strip())
            elif b.text:
                parts.append(_format_inline_text(b.text.strip(), config.math_to_latex))
            if parts:
                chunks.append("\n\n".join(parts))

        elif b.kind == "figure":
            cap = (b.caption_text or b.text or f"Figure p.{b.page}").strip()
            if b.asset:
                fig_md = f"![{cap}](assets/{slug}/{b.asset})"
                if b.caption_text:
                    fig_md += f"\n\n*{b.caption_text.strip()}*"
                chunks.append(fig_md)
            elif b.caption_text:
                chunks.append(f"*{b.caption_text.strip()}*")

        elif b.kind in ("figure_caption", "table_caption"):
            if b.text.strip():
                chunks.append(f"*{_format_inline_text(b.text.strip(), config.math_to_latex)}*")

        elif b.kind == "algorithm":
            if b.gfm and b.gfm.strip():
                chunks.append(b.gfm.strip())
            elif b.text and b.text.strip():
                chunks.append(f"```text\n{b.text.strip()}\n```")

        elif b.kind == "list":
            txt = _format_inline_text(b.text.strip(), config.math_to_latex)
            if txt:
                chunks.append(txt)

        else:
            # text, author_bio, etc.
            txt = _format_inline_text(b.text.strip(), config.math_to_latex)
            if txt:
                chunks.append(txt)

    if footnotes:
        fn_lines = ["## Footnotes"]
        for idx, fn in enumerate(footnotes, 1):
            fn_txt = _format_inline_text(fn.text.strip(), config.math_to_latex)
            if fn_txt:
                fn_lines.append(f"- **[p.{fn.page}.{idx}]** {fn_txt}")
        if len(fn_lines) > 1:
            chunks.append("\n".join(fn_lines))

    assembled = "\n\n".join(chunks)
    if config.normalize_headings or config.inject_yaml_frontmatter:
        assembled = format_academic(
            assembled,
            pdf_filename,
            preserve_heading_text=config.preserve_heading_text
        )
    return assembled
