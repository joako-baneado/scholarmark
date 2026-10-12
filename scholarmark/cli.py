"""
Command Line Interface (CLI) for ScholarMark using Rich.
"""

import sys
import argparse
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from .config import ExtractorConfig
from .extractor import ScholarExtractor
from .core.manifest import generate_manifest

if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

console = Console(legacy_windows=False)

BANNER = r"""[bold cyan]
  ____       _           _            __  __            _    
 / ___|  ___| |__   ___ | | __ _ _ __|  \/  | __ _ _ __| | __
 \___ \ / __| '_ \ / _ \| |/ _` | '__| |\/| |/ _` | '__| |/ /
  ___) | (__| | | | (_) | | (_| | |  | |  | | (_| | |  |   < 
 |____/ \___|_| |_|\___/|_|\__,_|_|  |_|  |_|\__,_|_|  |_|\_\
[/bold cyan]
[dim italic]High-Precision Scientific Paper to Markdown Extractor & Grounding Engine v2.0[/dim italic]
"""

def print_banner():
    console.print(BANNER)

def cli_batch(args):
    print_banner()
    source_dir = Path(args.source)
    output_dir = Path(args.output)
    
    if not source_dir.exists():
        console.print(f"[bold red]Error:[/bold red] Source directory '{source_dir}' does not exist.")
        sys.exit(1)
        
    config = ExtractorConfig(
        extract_images=not args.no_images,
        extract_vector_graphics=not getattr(args, "no_vectors", False),
        dpi=args.dpi,
        force=args.force,
        skip_manifest=args.skip_manifest,
        onnx_model_path=getattr(args, "onnx_model", None)
    )
    
    extractor = ScholarExtractor(config=config)
    pdf_files = list(source_dir.glob("*.pdf"))
    
    if not pdf_files:
        console.print(f"[yellow]No PDF files found in {source_dir}.[/yellow]")
        return
        
    console.print(Panel(
        f"[bold]Source Directory:[/bold] {source_dir.resolve()}\n"
        f"[bold]Output Directory:[/bold] {output_dir.resolve()}\n"
        f"[bold]PDF Count:[/bold] {len(pdf_files)} papers\n"
        f"[bold]Figure Extraction:[/bold] {'Enabled (' + str(args.dpi) + ' DPI)' if not args.no_images else 'Disabled'}\n"
        f"[bold]Force Reconversion:[/bold] {args.force}",
        title="[bold green]Configuration[/bold green]",
        border_style="green"
    ))
    
    table = Table(title="[bold cyan]Extraction Results[/bold cyan]", show_header=True, header_style="bold magenta")
    table.add_column("#", justify="right", style="dim", width=4)
    table.add_column("Paper File", style="white", min_width=35)
    table.add_column("Status", justify="center", width=10)
    table.add_column("Chars", justify="right", width=10)
    table.add_column("Figures", justify="right", width=8)
    table.add_column("Time", justify="right", width=8)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console
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
                status_str,
                f"{res.char_count:,}" if res.status != "skipped" else "-",
                str(res.figure_count),
                f"{res.elapsed_seconds:.2f}s"
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
        border_style="cyan"
    ))

def cli_single(args):
    print_banner()
    pdf_path = Path(args.file)
    output_dir = Path(args.output)
    
    if not pdf_path.exists():
        console.print(f"[bold red]Error:[/bold red] File '{pdf_path}' not found.")
        sys.exit(1)
        
    config = ExtractorConfig(
        extract_images=not args.no_images,
        extract_vector_graphics=not getattr(args, "no_vectors", False),
        dpi=args.dpi,
        force=True,
        onnx_model_path=getattr(args, "onnx_model", None)
    )
    
    extractor = ScholarExtractor(config=config)
    console.print(f"[cyan]Converting[/cyan] {pdf_path.name}...")
    
    res = extractor.convert_file(pdf_path, output_dir)
    if res.status == "success":
        console.print(f"[bold green]✓ Success![/bold green] Saved to {res.target_md}")
        console.print(f"  Characters: {res.char_count:,} | Figures: {res.figure_count} | Time: {res.elapsed_seconds:.2f}s")
    else:
        console.print(f"[bold red]✗ Failed:[/bold red] {res.error_message}")

def cli_manifest(args):
    print_banner()
    target_dir = Path(args.dir)
    console.print(f"[cyan]Generating grounding manifest for[/cyan] {target_dir}...")
    out_file = target_dir / "scholarmark_manifest.json"
    data = generate_manifest(target_dir, out_file)
    console.print(f"[bold green]✓ Manifest generated successfully![/bold green]")
    console.print(f"  Indexed: {data['total_papers']} papers at {out_file}")

def main():
    parser = argparse.ArgumentParser(
        prog="scholarmark",
        description="ScholarMark: High-Precision Scientific Paper to Markdown Extractor & RAG Grounding Engine."
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: batch
    batch_parser = subparsers.add_parser("batch", help="Extract all PDF papers from a folder")
    batch_parser.add_argument("--source", "-s", type=str, default="papers", help="Source folder with PDFs")
    batch_parser.add_argument("--output", "-o", type=str, default="output", help="Output folder for Markdown & figures")
    batch_parser.add_argument("--force", "-f", action="store_true", help="Force reconversion of all files")
    batch_parser.add_argument("--no-images", action="store_true", help="Disable figure and image extraction")
    batch_parser.add_argument("--no-vectors", action="store_true", help="Disable vector graphics extraction")
    batch_parser.add_argument("--dpi", type=int, default=300, help="Image extraction resolution (DPI, default: 300)")
    batch_parser.add_argument("--skip-manifest", action="store_true", help="Skip manifest generation")
    batch_parser.add_argument("--onnx-model", type=str, default=None, help="Path to custom layout detection ONNX model")

    # Command: single
    single_parser = subparsers.add_parser("single", help="Extract a single PDF file")
    single_parser.add_argument("file", type=str, help="Path to PDF file")
    single_parser.add_argument("--output", "-o", type=str, default="output", help="Output folder")
    single_parser.add_argument("--no-images", action="store_true", help="Disable image extraction")
    single_parser.add_argument("--no-vectors", action="store_true", help="Disable vector graphics extraction")
    single_parser.add_argument("--dpi", type=int, default=300, help="DPI resolution (default: 300)")
    single_parser.add_argument("--onnx-model", type=str, default=None, help="Path to custom layout detection ONNX model")

    # Command: manifest
    manifest_parser = subparsers.add_parser("manifest", help="Generate or update JSON grounding manifest")
    manifest_parser.add_argument("dir", type=str, help="Directory containing Markdown files")

    # Fallback to batch if called without subcommands but with args
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    # Si se pasa directamente --source o -s sin subcommand, redirigir a batch
    if sys.argv[1] not in ["batch", "single", "manifest", "-h", "--help"]:
        # Insertar 'batch' como subcommand implícito
        sys.argv.insert(1, "batch")

    args = parser.parse_args()
    if args.command == "batch":
        cli_batch(args)
    elif args.command == "single":
        cli_single(args)
    elif args.command == "manifest":
        cli_manifest(args)

if __name__ == "__main__":
    main()
