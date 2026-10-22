"""
Command Line Interface (CLI) for ScholarMark v4.1 using Rich.
Supports pluggable engines (auto, fast, vision, docling), hardware acceleration selection,
multi-process batch workers, canonical JSON export, and runtime diagnostics ('scholarmark doctor').
"""

import sys
import argparse
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from . import __version__
from .config import ExtractorConfig
from .extractor import ScholarExtractor
from .core.manifest import generate_manifest
from .engines import ENGINE_REGISTRY, get_engine
from .models.registry import get_runtime_diagnostics

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

console = Console(legacy_windows=False)

BANNER = rf"""[bold cyan]
  ____       _           _            __  __            _    
 / ___|  ___| |__   ___ | | __ _ _ __|  \/  | __ _ _ __| | __
 \___ \ / __| '_ \ / _ \| |/ _` | '__| |\/| |/ _` | '__| |/ /
  ___) | (__| | | | (_) | | (_| | |  | |  | | (_| | |  |   < 
 |____/ \___|_| |_|\___/|_|\__,_|_|  |_|  |_|\__,_|_|  |_|\_\
[/bold cyan]
[dim italic]High-Precision Scientific Paper to Markdown & Canonical JSON Extractor v{__version__}[/dim italic]
"""


def print_banner():
    console.print(BANNER)


def _build_config_from_args(args, force_default: bool = False) -> ExtractorConfig:
    return ExtractorConfig(
        extract_images=not getattr(args, "no_images", False),
        extract_vector_graphics=not getattr(args, "no_vectors", False),
        dpi=getattr(args, "dpi", 300),
        force=getattr(args, "force", force_default),
        skip_manifest=getattr(args, "skip_manifest", False),
        engine=getattr(args, "engine", "auto"),
        device=getattr(args, "device", "auto"),
        export_json=getattr(args, "json", False),
        export_chunks=getattr(args, "chunks", False),
        chunk_max_chars=getattr(args, "chunk_max_chars", 1800),
        workers=getattr(args, "workers", 1),
        onnx_model_path=getattr(args, "onnx_model", None),
    )


def cli_batch(args):
    print_banner()
    source_dir = Path(args.source)
    output_dir = Path(args.output)

    if not source_dir.exists():
        console.print(f"[bold red]Error:[/bold red] Source directory '{source_dir}' does not exist.")
        sys.exit(1)

    config = _build_config_from_args(args, force_default=False)
    extractor = ScholarExtractor(config=config)
    active_engine = get_engine(config)
    pdf_files = list(source_dir.glob("*.pdf"))

    if not pdf_files:
        console.print(f"[yellow]No PDF files found in {source_dir}.[/yellow]")
        return

    console.print(Panel(
        f"[bold]Source Directory:[/bold] {source_dir.resolve()}\n"
        f"[bold]Output Directory:[/bold] {output_dir.resolve()}\n"
        f"[bold]PDF Count:[/bold] {len(pdf_files)} papers\n"
        f"[bold]Active Engine:[/bold] {active_engine.name} ({config.device})\n"
        f"[bold]Parallel Workers:[/bold] {config.workers if config.workers > 0 else 'auto'}\n"
        f"[bold]Figure Extraction:[/bold] {'Enabled (' + str(args.dpi) + ' DPI)' if not args.no_images else 'Disabled'}\n"
        f"[bold]Canonical JSON:[/bold] {'Enabled' if config.export_json else 'Disabled'}\n"
        f"[bold]RAG Chunks JSONL:[/bold] {'Enabled' if config.export_chunks else 'Disabled'}\n"
        f"[bold]Force Reconversion:[/bold] {args.force}",
        title=f"[bold green]ScholarMark v{__version__} Configuration[/bold green]",
        border_style="green",
    ))

    table = Table(title="[bold cyan]Extraction Results[/bold cyan]", show_header=True, header_style="bold magenta")
    table.add_column("#", justify="right", style="dim", width=4)
    table.add_column("Paper File", style="white", min_width=35)
    table.add_column("Engine", justify="center", width=8)
    table.add_column("Status", justify="center", width=10)
    table.add_column("Chars", justify="right", width=10)
    table.add_column("Figures", justify="right", width=8)
    table.add_column("Time", justify="right", width=8)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Processing scientific papers...", total=len(pdf_files))

        def on_progress(idx, total, pdf, res):
            if res.status == "success":
                status_str = "[bold green]DONE[/bold green]"
            elif res.status == "skipped":
                status_str = "[yellow]SKIPPED[/yellow]"
            else:
                status_str = "[bold red]ERROR[/bold red]"

            table.add_row(
                str(idx),
                pdf.name[:45] + ("..." if len(pdf.name) > 45 else ""),
                res.engine_used,
                status_str,
                f"{res.char_count:,}" if res.status != "skipped" else "-",
                str(res.figure_count),
                f"{res.elapsed_seconds:.2f}s",
            )
            progress.advance(task)

        results = extractor.convert_batch(source_dir, output_dir, on_progress=on_progress)

    console.print(table)

    success_count = sum(1 for r in results if r.status == "success")
    skipped_count = sum(1 for r in results if r.status == "skipped")
    error_count = sum(1 for r in results if r.status == "error")
    total_figs = sum(r.figure_count for r in results)

    console.print(Panel(
        f"[bold green]✓ Successfully Converted:[/bold green] {success_count}\n"
        f"[yellow]⚡ Skipped (Up-to-date):[/yellow] {skipped_count}\n"
        f"[red]✗ Errors:[/red] {error_count}\n"
        f"[bold cyan]🖼 Total Figures Extracted:[/bold cyan] {total_figs}\n"
        f"[bold blue]📄 Grounding Manifest:[/bold blue] {output_dir / 'scholarmark_manifest.json' if not args.skip_manifest else 'N/A'}",
        title="[bold green]Batch Execution Summary[/bold green]",
        border_style="cyan",
    ))


def cli_single(args):
    print_banner()
    pdf_path = Path(args.file)
    output_dir = Path(args.output)

    if not pdf_path.exists():
        console.print(f"[bold red]Error:[/bold red] File '{pdf_path}' not found.")
        sys.exit(1)

    config = _build_config_from_args(args, force_default=True)
    extractor = ScholarExtractor(config=config)
    console.print(f"[cyan]Converting[/cyan] {pdf_path.name} (engine={config.engine})...")

    res = extractor.convert_file(pdf_path, output_dir)
    if res.status == "success":
        console.print(f"[bold green]✓ Success![/bold green] Saved to {res.target_md}")
        if res.target_json:
            console.print(f"  Canonical JSON: {res.target_json}")
        if res.target_chunks:
            console.print(f"  RAG Chunks JSONL: {res.target_chunks}")
        console.print(
            f"  Engine: {res.engine_used} | Characters: {res.char_count:,} | "
            f"Figures: {res.figure_count} | Time: {res.elapsed_seconds:.2f}s"
        )
    else:
        console.print(f"[bold red]✗ Failed:[/bold red] {res.error_message}")


def cli_manifest(args):
    print_banner()
    target_dir = Path(args.dir)
    console.print(f"[cyan]Generating grounding manifest for[/cyan] {target_dir}...")
    out_file = target_dir / "scholarmark_manifest.json"
    data = generate_manifest(target_dir, out_file)
    console.print("[bold green]✓ Manifest generated successfully![/bold green]")
    console.print(f"  Indexed: {data['total_papers']} papers at {out_file}")


def cli_chunk(args):
    print_banner()
    import json
    from .ir.document import DocumentIR
    from .rag.chunker import export_chunks_jsonl

    target_path = Path(args.target)
    max_chars = getattr(args, "chunk_max_chars", 1800)
    json_files = [target_path] if target_path.is_file() else sorted(target_path.glob("*.scholarmark.json"))
    if not json_files:
        console.print(f"[yellow]No *.scholarmark.json files found in {target_path}.[/yellow]")
        return

    total_chunks = 0
    for jf in json_files:
        raw = json.loads(jf.read_text(encoding="utf-8"))
        ir = DocumentIR.from_dict(raw)
        stem = jf.name.replace(".scholarmark.json", "")
        out_jsonl = jf.parent / f"{stem}.chunks.jsonl"
        chunks = export_chunks_jsonl(ir, out_jsonl, max_chars=max_chars)
        total_chunks += len(chunks)
        console.print(f"[green]✓[/green] {out_jsonl.name}: {len(chunks)} semantic chunks")
    console.print(f"[bold green]✓ Exported {total_chunks} total RAG chunks across {len(json_files)} document(s).[/bold green]")


def cli_doctor(args):
    print_banner()
    diag = get_runtime_diagnostics(device=getattr(args, "device", "auto"))
    eng_table = Table(title="[bold cyan]Pluggable Extraction Engines[/bold cyan]", header_style="bold magenta")
    eng_table.add_column("Engine", style="bold white", width=12)
    eng_table.add_column("Status", width=12)
    eng_table.add_column("Details", style="dim")

    cfg = ExtractorConfig(device=getattr(args, "device", "auto"))
    for name, cls in ENGINE_REGISTRY.items():
        inst = cls(cfg)
        ok, detail = inst.available()
        status = "[bold green]READY[/bold green]" if ok else "[yellow]OPTIONAL[/yellow]"
        eng_table.add_row(name, status, detail)

    console.print(Panel(
        f"[bold]ScholarMark Version:[/bold] {__version__}\n"
        f"[bold]ONNX Runtime Version:[/bold] {diag['onnxruntime_version']}\n"
        f"[bold]Available ORT Providers:[/bold] {', '.join(diag['available_providers']) or 'None'}\n"
        f"[bold]Active Accelerator:[/bold] {diag['active_accelerator']}\n"
        f"[bold]PyMuPDF GNN Layout:[/bold] {'Active' if diag['pymupdf_gnn_layout'] else 'Inactive'}\n"
        f"[bold]Models Cache Dir:[/bold] {diag['models_cache_dir']}\n"
        f"[bold]Cached ONNX Weights:[/bold] {len(diag['cached_onnx_models'])} file(s)",
        title="[bold green]System & Runtime Diagnostics[/bold green]",
        border_style="green",
    ))
    console.print(eng_table)


def _add_common_extraction_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("--no-images", action="store_true", help="Disable figure and image extraction")
    p.add_argument("--no-vectors", action="store_true", help="Disable vector graphics extraction")
    p.add_argument("--dpi", type=int, default=300, help="Image extraction resolution (DPI, default: 300)")
    p.add_argument(
        "--engine",
        type=str,
        default="auto",
        choices=["auto", "fast", "vision", "docling"],
        help="Extraction backend engine (default: auto)",
    )
    p.add_argument(
        "--device",
        type=str,
        default="auto",
        choices=["auto", "cpu", "dml", "cuda"],
        help="Hardware execution target for ONNX Runtime (default: auto)",
    )
    p.add_argument("--json", action="store_true", help="Export canonical DocumentIR JSON alongside Markdown")
    p.add_argument("--chunks", action="store_true", help="Export DocumentIR-aware semantic RAG chunks (*.chunks.jsonl)")
    p.add_argument("--chunk-max-chars", type=int, default=1800, help="Maximum characters per prose RAG chunk (default: 1800)")
    p.add_argument("--onnx-model", type=str, default=None, help="Path to custom layout/formula ONNX model")


def main():
    parser = argparse.ArgumentParser(
        prog="scholarmark",
        description=f"ScholarMark v{__version__}: High-Precision Scientific Paper to Markdown, Canonical JSON & RAG Chunks Extractor.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: batch
    batch_parser = subparsers.add_parser("batch", help="Extract all PDF papers from a folder")
    batch_parser.add_argument("--source", "-s", type=str, default="papers", help="Source folder with PDFs")
    batch_parser.add_argument("--output", "-o", type=str, default="output", help="Output folder for Markdown & figures")
    batch_parser.add_argument("--force", "-f", action="store_true", help="Force reconversion of all files")
    batch_parser.add_argument("--skip-manifest", action="store_true", help="Skip manifest generation")
    batch_parser.add_argument("--workers", "-w", type=int, default=1, help="Number of parallel worker processes (0 for auto)")
    _add_common_extraction_flags(batch_parser)

    # Command: single
    single_parser = subparsers.add_parser("single", help="Extract a single PDF file")
    single_parser.add_argument("file", type=str, help="Path to PDF file")
    single_parser.add_argument("--output", "-o", type=str, default="output", help="Output folder")
    _add_common_extraction_flags(single_parser)

    # Command: manifest
    manifest_parser = subparsers.add_parser("manifest", help="Generate or update JSON grounding manifest")
    manifest_parser.add_argument("dir", type=str, help="Directory containing Markdown files")

    # Command: chunk
    chunk_parser = subparsers.add_parser("chunk", help="Generate *.chunks.jsonl from existing *.scholarmark.json files")
    chunk_parser.add_argument("target", type=str, help="Path to *.scholarmark.json file or directory")
    chunk_parser.add_argument("--chunk-max-chars", type=int, default=1800, help="Maximum characters per prose chunk")

    # Command: doctor
    doctor_parser = subparsers.add_parser("doctor", help="Inspect ONNX providers, engines, and hardware readiness")
    doctor_parser.add_argument("--device", type=str, default="auto", choices=["auto", "cpu", "dml", "cuda"])

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    if sys.argv[1] not in ["batch", "single", "manifest", "chunk", "doctor", "-h", "--help"]:
        sys.argv.insert(1, "batch")

    args = parser.parse_args()
    if args.command == "batch":
        cli_batch(args)
    elif args.command == "single":
        cli_single(args)
    elif args.command == "manifest":
        cli_manifest(args)
    elif args.command == "chunk":
        cli_chunk(args)
    elif args.command == "doctor":
        cli_doctor(args)


if __name__ == "__main__":
    main()
