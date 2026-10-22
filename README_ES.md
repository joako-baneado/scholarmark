<div align="center">

# ⚡ ScholarMark (Español)

### Extractor de Papers Científicos a Markdown de Alta Precisión y Motor de Grounding para RAG (v4.1.0)

[![Python 3.10+](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen.svg)]()
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

*Convierte PDFs científicos complejos de doble columna (IEEE, ACM, Springer, Elsevier, MDPI) en documentos Markdown impecables para LLMs con ecuaciones LaTeX nativas, figuras en alta resolución, tablas estructuradas jerárquicas y manifiesto de grounding para sistemas RAG.*

[English Version](README.md) • [Características](#-características-principales-arquitectura-v41) • [Benchmarks](#-benchmark-y-mejoras-cuantitativas) • [Inicio Rápido](#-inicio-rápido) • [API Python](#-api-en-python) • [Referencia CLI](#-referencia-de-comandos)

</div>

---

## 💡 El Problema de los Conversores Tradicionales de PDF

Al procesar artículos de investigación para LLMs o sistemas RAG, los extractores convencionales presentan fallas graves:
1. **Entrelazado de Doble Columna:** Las oraciones de la columna izquierda y derecha se leen horizontalmente de forma intercalada, destrozando la coherencia sintáctica.
2. **Destrucción de Fórmulas Matemáticas:** Ecuaciones centradas con numeración (ej. $V_t = P_{t+1} - P_t \quad (2)$) son interpretadas como **tablas vacías de 16 columnas** (`| | | | ... |`), tragándose además el texto adyacente.
3. **Pérdida Total de Figuras (0% extraídas):** Se pierden esquemas de arquitectura neuronal, matrices de confusión y diagramas experimentales.
4. **Palabras Pegadas por Kerning:** Fuentes sin glifo explícito de espacio ASCII generan cadenas ilegibles de decenas de caracteres.
5. **Símbolos Corruptos:** Letras griegas ($\alpha, \beta, \theta$) y operadores matemáticos se transforman en `??`.

**ScholarMark** resuelve integralmente estos problemas mediante un pipeline ultra-ligero nativo en CPU (0 MB VRAM) que se ejecuta en **2–4 segundos por paper** con complejidad de memoria estricta $O(N)$.

---

## ✨ Características Principales (Arquitectura v4.1)

- 🔌 **Motores de Extracción Intercambiables (`--engine auto|fast|vision|docling`):**
  - `auto` (**Por Defecto:** `VisionEngine`): Pipeline modular híbrido asimétrico con paso único en memoria `PageContext`.
  - `fast`: Pipeline de baja latencia con layout GNN de PyMuPDF4LLM y clustering vectorial transitivo Union-Find.
  - `vision`: Pipeline multimodal con `SpanMapper` nativo (0% alucinación textual), **Grafo DAG de Orden de Lectura**, **FormulaRecognizer 2D y Multilínea**, **TableRecognizer HTML Jerárquico**, **AlgorithmRecognizer**, **ChartSemanticsExtractor** y **CitationLinker**.
  - `docling`: Adaptador opcional de referencia hacia IBM Docling.
- ⚡ **Paso Único en Memoria `PageContext`:** Ejecuta un único pase de `rawdict` y `bboxlog` por página en toda la ejecución, eliminando llamadas redundantes a la API de C de PyMuPDF y acelerando el triaje global.
- 🚀 **Pool Multiproceso de Alta Velocidad (`--workers N` / `-w`):** Soporta `ProcessPoolExecutor` para procesamiento en paralelo sobre procesadores multinúcleo, con sincronización segura sin colisiones en `DeltaCache` y generación de manifiesto en RAM.
- 📖 **Flujo de Lectura Multicolumna DAG:** Garantiza lectura columna por columna, segrega notas al pie al cierre para no cortar frases, aísla biografías IEEE no rectangulares y une párrafos divididos entre páginas alrededor de figuras flotantes.
- 📐 **Reconstrucción Matemática 2D y Multilínea (`FormulaRecognizer`):** Recupera fracciones vectoriales (`\frac{num}{den}`), subíndices y superíndices anidados ($x_{i}^{n+1}$), sistemas de ecuaciones multilínea (`\begin{aligned} ... \end{aligned}`), matrices (`\begin{pmatrix}`), sub/superíndices en línea por desplazamiento $\Delta y$ (`x_{i}^{2}`, `L_{total}`) y glifos matemáticos en Private Use Area (`PUA`).
- 📊 **Tablas Jerárquicas en HTML Semántico y Booktabs (`TableRecognizer`):** Recupera tablas abiertas estilo LaTeX `booktabs`, encabezados multinivel (`colspan` y `rowspan`) y páginas rotadas (`/Rotate 90`). Protege `page.find_tables()` tras compuertas geométricas reduciendo la latencia de tablas de 871 ms a **3.8 ms** ($229\times$ más rápido).
- 🖼️ **Volcado XREF Directo y DPI Adaptativo:** Extrae streams ráster directamente de los objetos XREF del PDF sin recodificación, y escala a 200 DPI para figuras vectoriales amplias y 300 DPI para micro-gráficos para un balance óptimo de nitidez y peso.
- 💻 **Reconocedor de Algoritmos y Pseudocódigo (`AlgorithmRecognizer`):** Preserva bloques `Algorithm N` (`algorithm2e` / `algpseudocode`) con niveles de sangría anidada ($\Delta x$), numeración de líneas y especificaciones `Require:`/`Ensure:`.
- 🔗 **Grafo Bidireccional de Citas y Semántica de Gráficos:** Parsea referencias IEEE `[N]` y APA autor-año, vincula rangos de citas (`[1]–[3]`) con métricas cuantitativas (`%`, `ms`, `FPS`), y extrae ejes, leyendas y valores internos de gráficos vectoriales.
- 🧩 **Chunking Semántico Consciente de `DocumentIR` (`--chunks` / `scholarmark chunk`):** Exporta `<paper>.chunks.jsonl` con bloques atómicos (tablas, figuras, algoritmos, fórmulas), ruta jerárquica de secciones (`section_path`), hidratación $O(1)$ de citas bibliográficas y enlace cruzado a artefactos (`Fig. N`, `Table N`, `Algorithm N`, `Eq. (N)`).

---

## 📊 Benchmark y Mejoras Cuantitativas

### 1. Gold Suite v4.1: `fast` (Base v2.1) vs. `vision` (Pipeline v4.1.0)

| Caso de Prueba | Dimensión Auditada | Puntaje `fast` | Puntaje `vision` (v4.1) | Mejora Δ | Latencia `vision` | Notas |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `case1_two_col_footnotes` | Orden de Lectura (Kendall-τ) | 0.9048 | **1.0000** | **+0.0952** | **19.4 ms** | Doble columna con segregación de pie de página inferior izquierdo |
| `case2_2d_math` | Fidelidad Matemática 2D (1 - NED) | 0.1633 | **0.9355** | **+0.7722** | **2.8 ms** | LaTeX recuperado: `L = \frac{x_{i}^{n+1}}{y_{k}}` |
| `case3_booktabs_colspan` | Tabla Jerárquica (TEDS) | 0.4500 | **1.0000** | **+0.5500** | **3.8 ms** | Tabla booktabs con colspan=2 y rowspan=2 ($229\times$ más veloz) |
| `case4_multipanel_1n` | Leyendas Multipanel 1:N (F1) | 0.5000 | **1.0000** | **+0.5000** | **45.6 ms** | 3 subpaneles (a)(b)(c) ligados a Fig. 1 compartida + Fig. 2 |
| `case5_dense_scatter_guard` | Guarda Vectorial (<2.5s SLA) | 1.0000 | **1.0000** | **+0.0000** | **212.9 ms** | 2,704 rectángulos vectoriales procesados sin desbordamiento |
| `case6_algorithm_pseudocode` | Sangría de Algoritmos | 0.2500 | **1.0000** | **+0.7500** | **7.3 ms** | Algoritmo 1 con bucles for/if anidados y líneas divisorias |
| `case7_citations_and_chart_semantics` | Grafo de Citas y Gráficos | 0.0000 | **1.0000** | **+1.0000** | **229.8 ms** | 3 refs IEEE + afirmación anclada [1]-[3] + metadatos de ejes |
| `case8_ieee_author_bios_and_rag_chunks` | Chunks Semánticos RAG y Bio Guard | 0.1667 | **1.0000** | **+0.8333** | **5.0 ms** | Chunk de algoritmo atómico + cita [1] hidratada + bio IEEE aislada |
| **PROMEDIO GLOBAL** | **Puntaje Compuesto Gold** | **0.4294** | **0.9919** | **+0.5626** | **~65.8 ms/caso** | **Todos los quality gates aprobados ($4.0\times$ más rápido)** |

---

### 2. Rendimiento en Artículos Reales de Producción (IEEE y MDPI)

En papers reales de investigación de 20 a 23 páginas, el motor `vision` de v4.1.0 es **más rápido que `fast` (PyMuPDF4LLM)** manteniendo calidad SOTA:

| Archivo del Paper | Páginas | Latencia `fast` (PyMuPDF4LLM) | Latencia `vision` (v4.1.0) | Ventaja de Velocidad |
| :--- | :---: | :---: | :---: | :---: |
| `A Deep Dive Into MediaPipe Pose for Postural Assessment...` | 20 | 583.2 ms/pág | **382.4 ms/pág** | **$-34.4\%$ tiempo** |
| `A Hybrid Approach for Sports Activity Recognition...` | 23 | 432.6 ms/pág | **245.0 ms/pág** | **$-43.4\%$ tiempo** |
| `A Lightweight CNN–TCN–Attention Framework for Low-Latency...` | 20 | 435.7 ms/pág | **140.9 ms/pág** | **$-67.7\%$ tiempo ($3.09\times$ más veloz)** |

---

## 🚀 Inicio Rápido

### 1. Instalación

```bash
git clone https://github.com/joako-baneado/scholarmark.git
cd scholarmark

# Instalación base (nativa en CPU, 0 MB VRAM)
pip install -e .

# Opcional: dependencias extendidas para modelos ONNX de visión y benchmarks
pip install -e ".[vision,bench]"
```

### 2. Uso desde la Línea de Comandos (CLI)

#### Extracción en Paralelo por Lotes
```bash
# Extraer carpeta de PDFs con 4 procesos paralelos (VisionEngine por defecto)
scholarmark batch --source papers/ --output output/ --workers 4

# Incluir JSON canónico y chunks semánticos RAG
scholarmark batch --source papers/ --output output/ --workers 4 --json --chunks

# Forzar re-conversión completa
scholarmark batch --source papers/ --output output/ -w 4 --force
```

#### Extracción de un Solo Artículo
```bash
scholarmark single paper.pdf --output output/ --dpi 300 --json --chunks
```

#### Diagnóstico del Entorno y Hardware
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
from scholarmark import ScholarExtractor, ExtractorConfig

# Configurar el extractor
config = ExtractorConfig(
    engine="auto",
    workers=4,
    extract_images=True,
    dpi=300,
    export_json=True,
    export_chunks=True,
)
extractor = ScholarExtractor(config=config)

# 1. Convertir un archivo
res = extractor.convert_file(
    pdf_path=Path("papers/mi_articulo.pdf"),
    output_dir=Path("output/")
)
print(f"Estado: {res.status}")
print(f"Figuras extraídas: {res.figure_count} en {res.elapsed_seconds:.2f}s")
print(f"Archivo guardado en: {res.target_md}")

# 2. Convertir un lote de archivos con pool paralelo
results = extractor.convert_batch(
    source_dir=Path("papers/"),
    output_dir=Path("output/")
)
for r in results:
    print(f"[{r.status.upper()}] {r.source_pdf}: {r.char_count:,} chars ({r.elapsed_seconds:.2f}s)")
```

---

## ⚙️ Referencia de Comandos CLI

| Comando / Bandera | Alias | Por Defecto | Descripción |
| :--- | :---: | :---: | :--- |
| `--source` | `-s` | `papers` | Directorio fuente que contiene los archivos PDF |
| `--output` | `-o` | `output` | Directorio destino para `.md`, `.scholarmark.json` y `assets/` |
| `--engine` | | `auto` | Motor: `auto` (`VisionEngine` por defecto), `vision`, `fast`, o `docling` |
| `--workers` | `-w` | `1` | Número de procesos paralelos en modo batch (`0` para auto según núcleos CPU) |
| `--device` | | `auto` | Dispositivo de hardware para ONNX Runtime: `auto`, `cpu`, `dml`, `cuda` |
| `--json` | | `False` | Exporta el IR canónico en formato JSON (`*.scholarmark.json`) |
| `--chunks` | | `False` | Exporta chunks semánticos conscientes de la jerarquía RAG (`*.chunks.jsonl`) |
| `--chunk-max-chars` | | `1800` | Máximo número de caracteres por chunk semántico de prosa |
| `--force` | `-f` | `False` | Fuerza la re-extracción ignorando la caché delta |
| `--no-images` | | `False` | Desactiva la extracción de figuras y diagramas |
| `--dpi` | | `300` | Resolución objetivo para figuras (con escalado vectorial adaptativo) |
| `--skip-manifest`| | `False` | Omite la generación del archivo `scholarmark_manifest.json` |
| `scholarmark doctor` | | — | Inspecciona proveedores ONNX, motores disponibles y aceleradores |

---

## 📄 Licencia

Distribuido bajo la Licencia MIT. Consulta el archivo `LICENSE` para más información.
