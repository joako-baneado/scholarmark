<div align="center">

# ⚡ ScholarMark (Español)

### Extractor de Papers Científicos a Markdown de Alta Precisión y Motor de Grounding para RAG

[![Python 3.10+](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)]()
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

*Convierte PDFs científicos complejos de doble columna (IEEE, ACM, Springer, Elsevier, MDPI) en documentos Markdown impecables para LLMs con ecuaciones LaTeX nativas, figuras en alta resolución, tablas estructuradas y manifiesto de grounding para sistemas RAG.*

[English Version](README.md) • [Características](#-características-principales) • [Benchmarks](#-benchmark-y-mejoras) • [Inicio Rápido](#-inicio-rápido) • [API Python](#-api-en-python) • [Referencia CLI](#-referencia-de-comandos)

</div>

---

## 💡 El Problema de los Conversores Tradicionales de PDF

Al procesar artículos de investigación para LLMs o sistemas RAG, los extractores convencionales presentan fallas graves:
1. **Entrelazado de Doble Columna:** Las oraciones de la columna izquierda y derecha se leen horizontalmente de forma intercalada, destrozando la coherencia sintáctica.
2. **Destrucción de Fórmulas Matemáticas:** Ecuaciones centradas con numeración (ej. $V_t = P_{t+1} - P_t \quad (2)$) son interpretadas como **tablas vacías de 16 columnas** (`| | | | ... |`), tragándose además el texto adyacente.
3. **Pérdida Total de Figuras (0% extraídas):** Se pierden esquemas de arquitectura neuronal, matrices de confusión y diagramas experimentales.
4. **Palabras Pegadas por Kerning:** Fuentes sin glifo explícito de espacio ASCII generan cadenas ilegibles de decenas de caracteres.
5. **Símbolos Corruptos:** Letras griegas ($\alpha, \beta, \theta$) y operadores matemáticos se transforman en `??`.

**ScholarMark** resuelve integralmente estos problemas mediante un pipeline de 4 capas de alta velocidad que se ejecuta en **segundos por paper** en CPU estándar o GPU.

---

## ✨ Características Principales (Arquitectura v4.0)

- 🔌 **Motores de Extracción Intercambiables (`--engine auto|fast|vision|docling`):**
  - `fast`: Pipeline de baja latencia con layout GNN de PyMuPDF4LLM y clustering vectorial transitivo Union-Find.
  - `vision`: Pipeline modular híbrido asimétrico con `LayoutDetector`, `SpanMapper` nativo (0% alucinación textual), **Grafo DAG de Orden de Lectura**, **FormulaRecognizer 2D** (con reparación PUA), **TableRecognizer HTML Jerárquico** (con fallback OCR ráster), **AlgorithmRecognizer**, **ChartSemanticsExtractor**, **CitationLinker** y **SemanticChunker**.
  - `docling`: Adaptador opcional de referencia hacia IBM Docling.
- 📖 **Flujo de Lectura Multicolumna DAG:** Garantiza lectura columna por columna, segrega notas al pie al cierre para no cortar frases, aísla biografías IEEE no rectangulares y une párrafos divididos entre páginas alrededor de figuras flotantes.
- 📐 **Reconstrucción Matemática 2D a LaTeX y Reparación PUA:** Recupera fracciones vectoriales (`\frac{num}{den}`), subíndices y superíndices anidados ($x_{i_k}^{n+1}$), límites de sumatorias/integrales, matrices (`\begin{pmatrix}...\end{pmatrix}`) y glifos matemáticos en Private Use Area (`PUA`).
- 📊 **Tablas Jerárquicas en HTML Semántico, Booktabs y Ráster:** Recupera tablas abiertas estilo LaTeX `booktabs`, encabezados multinivel (`colspan` y `rowspan`), páginas rotadas (`/Rotate 90`) y tablas 100% imagen mediante proyección morfológica 1D y OCR selectivo.
- 💻 **Reconocedor de Algoritmos y Pseudocódigo (`AlgorithmRecognizer`):** Preserva bloques `Algorithm N` (`algorithm2e` / `algpseudocode`) con niveles de sangría anidada ($\Delta x$), numeración de líneas y especificaciones `Require:`/`Ensure:`.
- 🔗 **Grafo Bidireccional de Citas y Semántica de Gráficos (`v3.2`):** Parsea referencias IEEE `[N]` y APA autor-año, vincula rangos de citas (`[1]–[3]`) con métricas cuantitativas (`%`, `ms`, `FPS`), y extrae ejes, leyendas y valores internos de gráficos vectoriales (`ChartSemanticsExtractor`).
- 🧩 **Chunking Semántico Consciente de `DocumentIR` (`--chunks` / `scholarmark chunk`):** Exporta `<paper>.chunks.jsonl` con bloques atómicos (tablas, figuras, algoritmos, fórmulas), ruta jerárquica de secciones (`section_path`), hidratación $O(1)$ de citas bibliográficas y enlace cruzado a artefactos (`Fig. N`, `Table N`, `Algorithm N`, `Eq. (N)`).

---

## 📊 Benchmark y Mejoras Cuantitativas

### Gold Suite v4.0: `fast` (Base v2.1) vs. `vision` (Pipeline Híbrido v4.0)

| Caso de Prueba | Dimensión Auditada | Puntaje `fast` | Puntaje `vision` (v4.0) | Mejora Δ | Latencia `vision` |
| :--- | :--- | :---: | :---: | :---: | :---: |
| `case1_two_col_footnotes` | Orden de Lectura (Kendall-τ) | 0.9048 | **1.0000** | **+0.0952** | 176.9 ms |
| `case2_2d_math` | Fidelidad Matemática 2D (1 - NED) | 0.0938 | **0.9355** | **+0.8417** | 147.8 ms |
| `case3_booktabs_colspan` | Tabla Jerárquica (TEDS) | 0.4500 | **1.0000** | **+0.5500** | 871.3 ms |
| `case4_multipanel_1n` | Leyendas Multipanel 1:N (F1) | 0.5000 | **1.0000** | **+0.5000** | 151.9 ms |
| `case5_dense_scatter_guard` | Guarda Vectorial (<2.5s SLA) | 1.0000 | **1.0000** | **+0.0000** | 427.7 ms |
| `case6_algorithm_pseudocode` | Sangría de Algoritmos (`v3.1`) | 0.2500 | **1.0000** | **+0.7500** | 217.0 ms |
| `case7_citations_and_chart_semantics` | Grafo de Citas y Gráficos (`v3.2`) | 0.0000 | **1.0000** | **+1.0000** | 230.5 ms |
| `case8_ieee_author_bios_and_rag_chunks` | Chunks Semánticos RAG y Bio Guard (`v4.0`) | 0.1667 | **1.0000** | **+0.8333** | 186.7 ms |
| **PROMEDIO GLOBAL** | **Puntaje Compuesto Gold (8 Casos)** | **0.4207** | **0.9919** | **+0.5713** | **~301 ms/caso** |

---

## 🚀 Inicio Rápido

### 1. Instalación

```bash
git clone https://github.com/joako-baneado/scholarmark.git
cd scholarmark
pip install -e .
```

### 2. Uso desde la Línea de Comandos (CLI)

#### Extracción en Lote (Carpeta de PDFs)
```bash
# Extraer todos los PDFs con el motor híbrido v3.0 y exportar JSON canónico
scholarmark batch --source papers/ --output output/ --engine vision --json

# Forzar re-conversión completa
scholarmark batch --source papers/ --output output/ --force
```

#### Extracción de un Solo Artículo
```bash
scholarmark single paper.pdf --output output/ --engine vision --dpi 300 --json
```

#### Diagnóstico del Entorno y Motores
```bash
scholarmark doctor
```

#### Generar Manifiesto de Grounding
```bash
scholarmark manifest output/
```

---

## 🐍 API en Python

```python
from pathlib import Path
from scholarmark import ScholarExtractor

# Inicializar extractor
extractor = ScholarExtractor(extract_images=True, dpi=200)

# Convertir un archivo
res = extractor.convert_file(
    pdf_path=Path("papers/mi_articulo.pdf"),
    output_dir=Path("output/")
)

print(f"Estado: {res.status}")
print(f"Figuras extraídas: {res.figure_count}")
print(f"Archivo guardado en: {res.target_md}")
```

---

## 📄 Licencia

Distribuido bajo la Licencia MIT. Consulta el archivo `LICENSE` para más información.
