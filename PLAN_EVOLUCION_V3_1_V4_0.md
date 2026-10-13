# Plan de Implementación Evolutivo: ScholarMark v3.1 $\rightarrow$ v3.2 $\rightarrow$ v4.0

> **Metodología de Ejecución Adaptativa (Iterative Review-and-Adjust Loop):**
> Este documento define la hoja de ruta técnica de las tres prioridades de evolución sobre la base de **ScholarMark v3.0.0**.
> Al finalizar cada Prioridad se ejecuta una **Compuerta de Revisión y Ajuste Adaptativo (`Gate`)**:
> 1. Se ejecutan las pruebas unitarias (`pytest`) y el benchmark comparativo (`python -m bench.run_bench`).
> 2. Se consolida un commit atómico bajo *Conventional Commits*.
> 3. **Se inspeccionan los resultados reales, estructuras de datos y métricas obtenidas en la etapa recién terminada y se actualiza este mismo archivo (`PLAN_EVOLUCION_V3_1_V4_0.md`)**, ajustando contratos de interfaz, umbrales o metadatos de la siguiente Prioridad antes de iniciar su codificación.

```mermaid
flowchart LR
    P1["Prioridad 1 (v3.1)<br/>Fallback Visual Ráster/PUA<br/>+ AlgorithmRecognizer"] --> G1{"Gate 1:<br/>Revisión y Ajuste<br/>del Plan P2"}
    G1 --> P2["Prioridad 2 (v3.2)<br/>Parser Bibliográfico + Grafo<br/>de Citas + Chart-to-Metadata"]
    P2 --> G2{"Gate 2:<br/>Revisión y Ajuste<br/>del Plan P3"}
    G2 --> P3["Prioridad 3 (v4.0)<br/>Semantic RAG Chunker<br/>+ Benchmark Multi-Editorial"]
    P3 --> G3["Gate 3:<br/>Cierre, Docs y Tag v4.0.0"]
```

---

## Prioridad 1 (`v3.1`): Cobertura Visual Ráster/PUA y Reconocedor de Algoritmos

**Estado:** `COMPLETADA (Commit 2cd8473 — 40/40 tests pass, Gold Case 6 = 1.0000)`

### 1.1. Objetivo Arquitectónico
Resolver los dos límites estructurales restantes en el nivel de página individual:
1. **Fórmulas con fuentes corruptas (`PUA` / `Type 1` sin `ToUnicode`) y Tablas 100% Ráster (Imágenes):** Cuando un PDF carece de glifos nativos válidos en una ecuación o incrusta una tabla como mapa de bits (`.png`/`.jpg`), el motor debe activar automáticamente un fallback visual sobre el recorte a 300 DPI sin degradar la velocidad en páginas vectoriales sanas.
2. **Bloques de Algoritmos y Pseudocódigo (`algorithm2e` / `algpseudocode`):** Preservar la estructura jerárquica, numeración de líneas (`1:`, `2:`), sangría horizontal ($\Delta x$) y expresiones matemáticas inline de los bloques de algoritmos habituales en IEEE, ACM y arXiv.

### 1.2. Archivos Creados o Modificados
| Archivo | Acción | Responsabilidad Técnica |
| :--- | :--- | :--- |
| `scholarmark/ir/document.py` | Modificado | Añadido `"algorithm"` a `BlockKind` y soporte de metadatos `fallback_triggered` y `algorithm_lines`. |
| `scholarmark/models/registry.py` | Modificado | Añadido catálogo de especificaciones ONNX (`MODEL_SPECS`), verificación SHA-256 y cargador de sesiones. |
| `scholarmark/recognizers/formula.py` | Modificado | Añadido detector de corrupción `PUA` (`has_corrupted_glyphs`), mapa de reparación `_PUA_GLYPH_MAP` (`sanitize_pua_text`) y telemetría de fallback. |
| `scholarmark/recognizers/table.py` | Modificado | Añadida reconstrucción de tablas ráster/escaneadas (`_reconstruct_raster_table`) mediante OCR selectivo y proyección de perfiles morfológicos 1D. |
| `scholarmark/recognizers/algorithm.py` | **Creado** | Implementado `AlgorithmRecognizer`: prioridad a cierres explícitos (`end for`, `end if`) combinados con paso físico $\Delta x = 12\text{ pt}$. |
| `scholarmark/layout/detector.py` | Modificado | Detección temprana de regiones `algorithm` antes de `_detect_table_regions` para evitar falsos positivos con filetes horizontales `booktabs`. |
| `scholarmark/render/markdown.py` | Modificado | Renderizado de bloques `algorithm` con encabezado en negrita y bloque de código con sangría exacta. |
| `scholarmark/engines/vision.py` | Modificado | Integración de `AlgorithmRecognizer` en Etapa 3C y registro de `fallback_triggered`. |
| `tests/test_priority1_v3_1.py` | **Creado** | Suite de pruebas unitarias e integración para `v3.1`. |
| `bench/gold_suite.py` | Modificado | Añadido **Caso 6 (`case6_algorithm_pseudocode`)** con score `1.0000` (`VisionEngine`) vs `0.2500` (`FastEngine`). |

### 1.3. Criterios de Aceptación (Prioridad 1)
- [x] Bloques `Algorithm 1` conservan el 100% de sus niveles de sangría anidada (`[0, 1, 2, 1, 0, 0]`) y sus variables matemáticas.
- [x] Fórmulas con caracteres `PUA` (`\ue000`–`\uf8ff`) o `\ufffd` activan el fallback y se marcan con trazabilidad en `Block.metadata["fallback_triggered"] = True`.
- [x] Todas las pruebas unitarias (`40 passed`) pasan en verde y se registró el commit atómico `2cd8473`.

### 1.4. Compuerta de Revisión y Ajuste Adaptativo (`Gate 1` $\rightarrow$ Ajustes Aplicados a Prioridad 2)
Tras inspeccionar el comportamiento real de `VisionEngine v3.1`, se identificaron **3 ajustes técnicos clave** que se incorporan inmediatamente al diseño de la **Prioridad 2 (`v3.2`)**:
1. **Ajuste A en `ChartSemanticsExtractor` (`scholarmark/recognizers/chart.py`):**
   - En `span_mapper.py`, los bloques `figure` no almacenan los spans internos en `b.text` (para evitar duplicarlos como prosa), pero `LayoutDetector` ya guarda las etiquetas de subpaneles `(a)`, `(b)` en `b.metadata["subpanel_labels"]`. Por tanto, `ChartSemanticsExtractor` consultará directamente `page.get_text("dict", clip=b.bbox.to_fitz_rect())` y **excluirá explícitamente `b.metadata["subpanel_labels"]`** para no confundir marcadores de subfigura con series de la leyenda (`legend_series`).
2. **Ajuste B en `BibliographyParser` y `CitationLinker` (`scholarmark/core/citations.py`):**
   - En `VisionEngine`, una sección `## References` puede agrupar varias entradas `[1] ... [2] ...` dentro de un mismo bloque `text` o separarlas en múltiples bloques consecutivos. `BibliographyParser` deberá concatenar todos los bloques posteriores al encabezado `References`/`Bibliography` (preservando saltos de línea en `span_mapper.py` cuando estemos en la sección de referencias) y segmentar tanto por `[N]` como por patrones APA `Apellido, I. (Año)`.
   - Además, `CitationLinker` también escaneará títulos de `algorithm` (`b.metadata.get("algorithm_title")`) y leyendas (`caption_text`), no solo bloques `text`.
3. **Ajuste C en `scholarmark/core/manifest.py`:**
   - Para que `scholarmark_manifest.json` aproveche al máximo `chart_semantics`, `algorithms` y `bibliography`, `extract_document_info(md_path)` leerá automáticamente el archivo compañero `md_path.with_suffix(".ir.json")` cuando exista, y usará el parser sobre Markdown (incluyendo comentarios `<!-- sm:chart ... -->`) como respaldo cuando solo exista el `.md`.

---

## Prioridad 2 (`v3.2`): Inteligencia Semántica para Grounding — Parser Bibliográfico, Grafo de Citas y `Chart-to-Metadata`

**Estado:** `EN EJECUCIÓN (Ajustado tras Gate 1)`

### 2.1. Objetivo Arquitectónico
Transformar ScholarMark de un extractor estructural de páginas a un **motor de anclaje evidencial (Evidence Grounding Engine)** para sistemas RAG científicos y validación APA/IEEE:
1. **Parser Estructural de Referencias (`ReferenceEntry`):** Descomponer la sección `## References` en entradas estructuradas (`ref_id`, `authors`, `year`, `title`, `venue`, `doi`, `url`).
2. **Grafo Bidireccional de Citas (`CitationLinker`):** Enlazar cada marcador de cita en el texto (`[1]`, `[3]–[6]`, `(Wang et al., 2024)`) con su entrada bibliográfica canónica y con las métricas cuantitativas (`%`, `ms`, `FPS`, `dB`, `GFLOPs`) presentes en la misma oración.
3. **Extracción Semántica de Gráficos Vectoriales (`Chart-to-Metadata`):** Extraer e indexar los textos nativos contenidos dentro del `bbox` de cada figura (títulos de ejes X/Y, unidades de medida, nombres de series en la leyenda y valores anotados sobre barras/curvas) en `Block.metadata["chart_semantics"]` y en `scholarmark_manifest.json`.

### 2.2. Archivos a Crear o Modificar
| Archivo | Acción | Responsabilidad Técnica |
| :--- | :--- | :--- |
| `scholarmark/core/citations.py` | **Crear** | Implementar `BibliographyParser` (formatos IEEE `[N]` y APA autor-año) y `CitationLinker` (expansión de rangos `[2]–[5]`, mapeo oración $\leftrightarrow$ métrica $\leftrightarrow$ `ref_id`). |
| `scholarmark/recognizers/chart.py` | **Crear** | Implementar `ChartSemanticsExtractor`: clasificación geométrica de spans internos de figuras en `axis_labels`, `legend_series`, `tick_values` y `data_annotations`. |
| `scholarmark/engines/vision.py` | Modificar | Ejecutar `ChartSemanticsExtractor` sobre cada bloque `figure` y `BibliographyParser` + `CitationLinker` sobre el `DocumentIR` ensamblado. |
| `scholarmark/render/markdown.py` | Modificar | Incluir metadatos semánticos de gráficos (ejes y series detectadas) como comentario estructurado/nota bajo las figuras vectoriales cuando estén disponibles. |
| `scholarmark/core/manifest.py` | Modificar | Enriquecer `scholarmark_manifest.json` con `references` (catálogo estructurado), `grounded_claims` (oración + métrica + `ref_ids` + página) y `figures[].chart_semantics`. |
| `tests/test_priority2_v3_2.py` | **Crear** | Pruebas unitarias de parseo de referencias IEEE/APA, expansión de rangos `[1]–[4]`, anclaje oración-métrica-cita y extracción de ejes/leyendas en gráficos. |
| `bench/gold_suite.py` | Modificar | Añadir **Caso 7 (`case7_citations_and_chart_semantics`)** con gráfico de barras vectorial etiquetado, citas en texto y sección `References`. |

### 2.3. Criterios de Aceptación (Prioridad 2)
- [ ] `DocumentIR.meta["bibliography"]` y `scholarmark_manifest.json` contienen la lista estructurada de referencias con `ref_id`, `authors`, `year`, `title` y `doi`.
- [ ] Las citas en rango (ej. `[1]–[3]` o `[1, 4]`) se resuelven a sus identificadores individuales (`["1", "2", "3"]`) y quedan vinculadas al bloque y a las métricas de la oración.
- [ ] Las figuras con texto vectorial interno exponen `chart_semantics` (`axis_labels`, `legend_series`, `numeric_ticks`).
- [ ] Commit atómico: `feat(v3.2): implement bibliography parser, bidirectional citation graph, and chart semantics extractor`.

### 2.4. Compuerta de Revisión y Ajuste Adaptativo (`Gate 2` $\rightarrow$ Ajustes a Prioridad 3)
> *[Se completará automáticamente al finalizar la Prioridad 2 con los hallazgos reales y los ajustes aplicados a la Prioridad 3]*

---

## Prioridad 3 (`v4.0`): Exportación Nativa de Chunks Semánticos para Scientific RAG y Benchmark Multi-Editorial

**Estado:** `PENDIENTE (Sujeto a revisión en Gate 2)`

### 3.1. Objetivo Arquitectónico
Cerrar el ciclo entre extracción documental y recuperación aumentada por generación (Scientific RAG):
1. **Motor de Chunking Semántico Consciente de `DocumentIR` (`scholarmark/rag/chunker.py`):**
   - Generar fragmentos autocontenidos (`SemanticChunk`) que respetan la topología del documento: **nunca parten una tabla, ecuación, algoritmo ni lista**.
   - Inyectar en cada chunk su jerarquía de encabezados (`section_path`: `["2. Methodology", "2.1 Network Architecture"]`), las coordenadas espaciales exactas (`pages`, `bboxes`), las **entradas bibliográficas completas** citadas dentro del fragmento (provenientes de la Prioridad 2) y el **contexto de artefactos referenciados** (si el párrafo menciona *"Table I"*, *"Fig. 2"* o *"Algorithm 1"*, adjunta su resumen estructural / `chart_semantics`).
2. **CLI `scholarmark chunk` y Flag `--chunks` en `extract`:** Exportar directamente archivos `*.chunks.jsonl` listos para indexación vectorial o híbrida (BM25 + Embeddings).
3. **Ampliación Multi-Editorial del Gold Benchmark (`bench/gold_suite.py`):** Incorporar patologías de **Biografías de Autores IEEE con foto lateral** y **Contorneo de Figuras (`Wrap-Text`) estilo Nature**, evaluando de extremo a extremo el pipeline `v4.0`.

### 3.2. Archivos a Crear o Modificar
| Archivo | Acción | Responsabilidad Técnica |
| :--- | :--- | :--- |
| `scholarmark/rag/__init__.py` | **Crear** | Exportar `SemanticChunk`, `SemanticChunker` y `export_chunks_jsonl`. |
| `scholarmark/rag/chunker.py` | **Crear** | Implementar particionamiento jerárquico sobre `DocumentIR` con ventana de tokens configurable (`max_chars=1800`), preservación de bloques atómicos, resolución de referencias cruzadas (`Table N`, `Fig. N`, `Eq. (N)`, `Algorithm N`) y adjunción de citas bibliográficas. |
| `scholarmark/config.py` | Modificar | Añadir `export_chunks: bool = False` y `chunk_max_chars: int = 1800` a `ExtractorConfig`. |
| `scholarmark/extractor.py` | Modificar | Generar `*.chunks.jsonl` automáticamente cuando `config.export_chunks` esté activo. |
| `scholarmark/cli.py` | Modificar | Añadir flag `--chunks` al comando `extract` y nuevo subcomando `scholarmark chunk`. |
| `bench/gold_suite.py` | Modificar | Añadir **Caso 8 (`case8_ieee_author_bios_and_rag_chunks`)** para validar separación de biografías de autores IEEE y calidad de enlace en `SemanticChunker`. |
| `tests/test_priority3_v4_0.py` | **Crear** | Pruebas unitarias de `SemanticChunker` (invarianza atómica de tablas/fórmulas/algoritmos, herencia de `section_path`, enlace de citas y exportación JSONL). |

### 3.3. Criterios de Aceptación (Prioridad 3)
- [ ] Ninguna tabla, ecuación ni algoritmo es fragmentado a mitad por el `SemanticChunker`.
- [ ] Cada chunk exportado en `*.chunks.jsonl` incluye `chunk_id`, `section_path`, `text`, `pages`, `bboxes`, `cited_references` y `linked_elements`.
- [ ] El Gold Benchmark completo (8 escenarios) alcanza un score compuesto $\ge 0.98$ con `VisionEngine`.
- [ ] Commit atómico: `feat(v4.0): add DocumentIR-aware SemanticChunker, JSONL export, and multi-publisher benchmark suite`.

### 3.4. Compuerta Final (`Gate 3` — Cierre del Ciclo)
> *[Se completará al finalizar la Prioridad 3 con la tabla comparativa final `v2.1` vs `v3.0` vs `v4.0` y el tag de versión]*
