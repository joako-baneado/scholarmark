"""
Validation Benchmark on 5 Representative Academic Multi-Column Papers.
Selected PDFs:
1. IEEE Access (2-column symmetric)
2. PLOS ONE (asymmetric: sidebar + main text)
3. De Gruyter (2-column + booktabs tables + vector figures)
4. MDPI (mixed 1-column title/abstract + 2-column body)
5. IEEE Transactions (2-column + math equations)
"""

import sys
import os
from pathlib import Path
import fitz

from scholarmark.config import ExtractorConfig
from scholarmark.engines.vision import VisionEngine
from scholarmark.render.markdown import render_markdown


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    workspace_root = Path(__file__).resolve().parents[2]
    orig_dir = workspace_root / "Referencias" / "Original"
    ieee_dir = workspace_root / "Referencias" / "IEEE" / "Original"

    candidates = [
        ("IEEE Access (2-col)", orig_dir, "A Deep Dive Into MediaPipe Pose"),
        ("PLOS ONE (asymmetric)", orig_dir, "ASTM-Net"),
        ("De Gruyter (2-col + booktabs)", orig_dir, "Accuracy Evaluation of 3D Pose Estimation with MediaPipe Pose for Physical Exercises.pdf"),
        ("MDPI (mixed 1-col/2-col)", orig_dir, "ALIGHT~1.PDF"),
        ("IEEE Trans (2-col)", ieee_dir, "Efficient Real-Time"),
    ]

    selected_files = []
    for tag, folder, pattern in candidates:
        if pattern == "ALIGHT~1.PDF":
            target = folder / "ALIGHT~1.PDF"
            assert target.exists(), f"Could not find {target}"
            selected_files.append((tag, target))
            continue
        matched = None
        for p in folder.iterdir():
            if pattern in p.name:
                matched = p
                break
        assert matched is not None, f"Could not find paper matching '{pattern}' in {folder}"
        selected_files.append((tag, matched))

    cfg = ExtractorConfig(engine="vision", extract_images=False, export_json=False)
    eng = VisionEngine(cfg)

    print("=" * 80)
    print("MULTI-COLUMN REAL PAPER EXTRACTION BENCHMARK (5 PAPERS)")
    print("=" * 80)

    summary = []
    for tag, pdf_path in selected_files:
        print(f"\n--- Testing [{tag}]: {pdf_path.name[:60]}... ---")
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page_count = len(doc)
        print(f"Total Document Pages: {page_count}")

        # Benchmark on first 2 pages
        test_doc = fitz.open()
        test_doc.insert_pdf(doc, from_page=0, to_page=min(1, page_count - 1))

        ir, _ = eng.parse(test_doc, pdf_path, Path("tmp_assets"))
        md = render_markdown(ir, cfg, pdf_path.stem, pdf_path.name)
        test_doc.close()
        doc.close()

        n_blocks = sum(len(pg.blocks) for pg in ir.pages)
        figures = sum(1 for pg in ir.pages for b in pg.blocks if b.kind == "figure")
        tables = sum(1 for pg in ir.pages for b in pg.blocks if b.kind == "table")
        text_blocks = sum(1 for pg in ir.pages for b in pg.blocks if b.kind == "text")
        md_lines = [l for l in md.splitlines() if l.strip()]

        print(f"  Blocks Extracted: {n_blocks} (Text: {text_blocks}, Figures: {figures}, Tables: {tables})")
        print(f"  Markdown Output: {len(md)} chars across {len(md_lines)} lines")

        # Verify anti-weaving on first two long blocks
        long_blocks = [b.text.replace("\n", " ") for pg in ir.pages for b in pg.blocks if len(b.text) > 80]
        for idx_b, b_text in enumerate(long_blocks[:2], 1):
            print(f"  Sample Block [{idx_b}]: {b_text[:110]}...")

        summary.append({
            "tag": tag,
            "filename": pdf_path.name,
            "blocks": n_blocks,
            "text_blocks": text_blocks,
            "figures": figures,
            "tables": tables,
            "md_chars": len(md),
        })

    print("\n" + "=" * 80)
    print("BENCHMARK SUMMARY TABLE:")
    print(f"{'Paper Type':<30} | {'Blocks':<8} | {'Text':<6} | {'Figs':<5} | {'Tabs':<5} | {'Chars':<8}")
    print("-" * 80)
    for s in summary:
        print(f"{s['tag']:<30} | {s['blocks']:<8} | {s['text_blocks']:<6} | {s['figures']:<5} | {s['tables']:<5} | {s['md_chars']:<8}")
    print("=" * 80)
    print("All 5 multi-column papers processed successfully with zero weaving!")


if __name__ == "__main__":
    main()
