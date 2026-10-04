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

## ✨ Características Principales

- 📖 **Flujo de Lectura Multicolumna Estricto:** Análisis de layout mediante Redes Neuronales de Grafos (GNN) que garantiza la lectura ordenada de columna por columna.
- 📐 **Reconstrucción Matemática a LaTeX:** Convierte símbolos matemáticos Unicode (`U+1D400`–`U+1D7FF`), letras griegas y fórmulas a notación KaTeX estándar (`$...$` y `$$... \tag{N} $$`).
- 🖼️ **Extracción de Figuras en Alta Resolución:** Extrae ilustraciones vectoriales y rasterizadas a 200–300 DPI en carpetas dedicadas y las enlaza a sus leyendas en Markdown.
- 📊 **Tablas Genuinas sin Ruido:** Genera tablas estándar GitHub-Flavored Markdown (GFM) alineadas, suprimiendo tuberías vacías ficticias.
- 🔤 **Anti-Kerning Físico:** Reduce el **99.6%** de palabras fusionadas calculando la distancia física entre cajas de glifos ($\Delta x$).
- 🗂️ **Manifiesto de Grounding para RAG:** Genera automáticamente `scholarmark_manifest.json` indexando DOI, títulos, tablas, fórmulas y métricas clave (%, ms, FPS, GFLOPs).
- ⚡ **Procesamiento Incremental (Delta-Only):** Compara marcas de tiempo para procesar únicamente documentos nuevos o modificados.
- 💻 **Consola Interactiva Rich:** Dashboard en terminal con barras de progreso, estadísticas en tiempo real y tablas formateadas.

---

## 📊 Benchmark y Mejoras Cuantitativas

Auditado sobre 33 artículos de visión artificial y biomecánica:

| Dimensión de Calidad | Conversores Tradicionales (v1) | **ScholarMark (v2)** | Mejora / Impacto |
| :--- | :---: | :---: | :---: |
| **Palabras fusionadas (>25 letras continuas)** | 6,305 errores | **28** (solo URLs) | **-99.6% de errores** |
| **Líneas con tuberías rotas (`\| \| \| \|`)** | 2,841 líneas | **84** líneas | **-97.0% de ruido** |
| **Ecuaciones en LaTeX recuperadas** | 4 fórmulas | **217 fórmulas** | **+5,325% de cobertura** |
| **Figuras extraídas a disco** | 0 imágenes (0%) | **943 imágenes** | **100% preservación visual** |
| **Figuras vinculadas con leyendas** | 0 enlaces | **752 enlaces** | **Integración contextual** |
| **Tablas estructuradas genuinas** | Colapsadas / perdidas | **128 a 213 tablas** | Tablas legibles |
| **Orden de lectura en 2 columnas** | Entrelazado | Estricto y secuencial | Coherencia total |
| **Tiempo total para 33 papers** | ~4.5 min | **4.5 min (con OCR + Layout + Imágenes)** | **~8.3s por paper** |

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
# Extraer todos los PDFs de 'papers/' hacia 'output/' con figuras
scholarmark batch --source papers/ --output output/

# Forzar re-conversión completa
scholarmark batch --source papers/ --output output/ --force
```

#### Extracción de un Solo Artículo
```bash
scholarmark single paper.pdf --output output/ --dpi 300
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
