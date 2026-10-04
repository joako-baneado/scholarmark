"""
Quickstart example demonstrating ScholarMark Python API usage.
"""

import sys
from pathlib import Path

# Permitir ejecución directa local antes de pip install
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from scholarmark import ScholarExtractor

def main():
    print("Initializing ScholarMark Extractor...")
    extractor = ScholarExtractor(
        extract_images=True,
        dpi=200,
        force=True
    )
    
    # Path to sample paper
    sample_pdf = Path("../Referencias/Original/Accuracy Evaluation of 3D Pose Estimation with MediaPipe Pose for Physical Exercises.pdf")
    output_dir = Path("./example_output")
    
    if sample_pdf.exists():
        print(f"Processing sample: {sample_pdf.name}...")
        result = extractor.convert_file(sample_pdf, output_dir)
        print(f"Status: {result.status}")
        print(f"Output saved to: {result.target_md}")
        print(f"Characters: {result.char_count:,} | Figures: {result.figure_count}")
        print(f"Time: {result.elapsed_seconds:.2f}s")
    else:
        print(f"Sample PDF not found at {sample_pdf}")

if __name__ == "__main__":
    main()
