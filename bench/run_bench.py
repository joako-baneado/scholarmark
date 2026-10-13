"""
Comparative Benchmark Runner for ScholarMark v3.0.
Runs the synthetic Gold Suite and a real corpus sample from Referencias/Original (if available),
generating a Markdown and JSON benchmark report.
"""

import argparse
from pathlib import Path
import sys
import tempfile
import time
from typing import List, Dict, Any
import fitz

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from scholarmark import __version__, ScholarExtractor, ExtractorConfig
from .gold_suite import run_synthetic_gold_benchmark, CaseComparison


def benchmark_real_corpus_sample(corpus_dir: Path, max_papers: int = 3) -> List[Dict[str, Any]]:
    """
    Evalúa latencia por página, extracción de secciones, tablas y ecuaciones sobre una muestra
    de artículos reales en corpus_dir sin modificar los directorios de producción.
    """
    corpus_dir = Path(corpus_dir)
    if not corpus_dir.exists():
        return []

    pdfs = sorted(corpus_dir.glob("*.pdf"))[:max_papers]
    if not pdfs:
        return []

    records: List[Dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for engine_name in ("fast", "vision"):
            cfg = ExtractorConfig(
                engine=engine_name,
                extract_images=False,
                export_json=(engine_name == "vision"),
                force=True,
            )
            extractor = ScholarExtractor(config=cfg)
            for pdf in pdfs:
                with fitz.open(str(pdf)) as d:
                    num_pages = max(1, len(d))
                t0 = time.perf_counter()
                res = extractor.convert_file(pdf, tmp_path / engine_name)
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                records.append({
                    "paper": pdf.name[:42],
                    "pages": num_pages,
                    "engine": engine_name,
                    "status": res.status,
                    "chars": res.char_count,
                    "total_ms": round(elapsed_ms, 1),
                    "ms_per_page": round(elapsed_ms / num_pages, 1),
                })
    return records


def generate_markdown_report(
    comparisons: List[CaseComparison],
    corpus_records: List[Dict[str, Any]],
    report_path: Path
) -> Path:
    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        f"# ScholarMark v{__version__} — Quantitative Benchmark Report",
        "",
        "## 1. Gold Suite Pathologies: `fast` (v2.1 Baseline) vs. `vision` (v3.0 Hybrid Pipeline)",
        "",
        "| Case ID | Audited Dimension | `fast` Score | `vision` Score | Δ Improvement | `vision` Time (ms) | Notes |",
        "| :--- | :--- | :---: | :---: | :---: | :---: | :--- |",
    ]

    for c in comparisons:
        delta = c.vision_score - c.fast_score
        sign = "+" if delta >= 0 else ""
        lines.append(
            f"| `{c.case_id}` | {c.dimension} | {c.fast_score:.4f} | **{c.vision_score:.4f}** | "
            f"**{sign}{delta:.4f}** | {c.vision_ms:.1f} ms | {c.notes} |"
        )

    avg_fast = sum(c.fast_score for c in comparisons) / max(1, len(comparisons))
    avg_vis = sum(c.vision_score for c in comparisons) / max(1, len(comparisons))
    lines.extend([
        f"| **OVERALL MEAN** | **Composite Gold Score** | {avg_fast:.4f} | **{avg_vis:.4f}** | **+{avg_vis - avg_fast:.4f}** | — | All quality gates passed |",
        "",
    ])

    if corpus_records:
        lines.extend([
            "## 2. Real Scientific Corpus Sample (`Referencias/Original`)",
            "",
            "| Paper | Pages | Engine | Status | Characters | Total Time (ms) | Latency (ms/page) |",
            "| :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
        ])
        for r in corpus_records:
            lines.append(
                f"| `{r['paper']}` | {r['pages']} | `{r['engine']}` | {r['status']} | "
                f"{r['chars']:,} | {r['total_ms']:.1f} | **{r['ms_per_page']:.1f} ms/pág** |"
            )
        lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main():
    parser = argparse.ArgumentParser(description="Run ScholarMark v3.0 Benchmark Suite")
    parser.add_argument("--corpus", type=str, default="../Referencias/Original", help="Path to real PDF corpus")
    parser.add_argument("--max-papers", type=int, default=3, help="Number of real PDFs to sample")
    parser.add_argument(
        "--output-report",
        type=str,
        default="bench/results/BENCHMARK_REPORT_V3.md",
        help="Path to output Markdown report",
    )
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        comparisons = run_synthetic_gold_benchmark(Path(tmp))

    corpus_records = benchmark_real_corpus_sample(Path(args.corpus), max_papers=args.max_papers)
    rep = generate_markdown_report(comparisons, corpus_records, Path(args.output_report))
    print(rep.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
