# Benchmark Papers: Multi-Column Academic Corpus (ScholarMark v5.0)

Colección canónica de 5 artículos científicos representativos utilizados para evaluar y certificar la robustez del motor visual de extracción estructural, el solucionador topológico DAG multicolumna **XY-Cut++**, la reconstrucción jerárquica de tablas multilínea y el grafo bidireccional de citas de **ScholarMark v5.0.0** (*Uncertainty-Gated Micro-Hybrid Architecture*).

Cada artículo incluye su archivo PDF original, su extracción completa a Markdown (`.md`), su catálogo de figuras renderizadas en alta resolución (300 DPI) alojadas en la subcarpeta `assets/`, y la consolidación de metadatos RAG en [`scholarmark_manifest.json`](./scholarmark_manifest.json).

---

## Resumen Global del Benchmark v5.0

| # | Artículo / Editorial | Maquetación | Páginas | Caracteres | Tablas | Figuras | Algoritmos | Referencias / Claims |
|---|----------------------|-------------|---------|------------|--------|---------|------------|----------------------|
| 1 | **IEEE Access** (MediaPipe Pose Posture) | 2 Col. Simétrica | 20 | 112,021 | 11 | 15 | 0 | 75 refs / 50 claims |
| 2 | **PLOS ONE** (ASTM-Net Sports) | Asimétrica (Sidebar + Cuerpo) | 30 | 104,782 | 10 | 12 | 3 | 5 refs / 50 claims |
| 3 | **De Gruyter** (3D Pose Physical Exercises) | 2 Col. Booktabs | 4 | 18,070 | 3 | 5 | 0 | 6 refs / 6 claims |
| 4 | **MDPI** (Pre-Fall Edge Devices) | Mixta (1 Col. Abstract + 2 Col. Cuerpo) | 20 | 68,810 | 7 | 6 | 0 | 2 refs / 45 claims |
| 5 | **IEEE Transactions** (EfficientPose Temporal GCN) | 2 Col. Ecuaciones 2D | 11 | 60,909 | 4 | 5 | 0 | 47 refs / 35 claims |
| **Total** | **Corpus Completo de 5 Papers** | **Diversidad Editorial** | **85 págs** | **364,592** | **35 tablas** | **43 figs** | **3 algs** | **135 refs / 186 claims** |

---

## Índice Detallado de Documentos del Corpus

### 1. IEEE Access — Maquetación de Dos Columnas Simétricas
- **PDF Original:** [`A Deep Dive Into MediaPipe Pose for Postural Assessment_ A Comparative Investigation.pdf`](./A%20Deep%20Dive%20Into%20MediaPipe%20Pose%20for%20Postural%20Assessment_%20A%20Comparative%20Investigation.pdf)
- **Extracción Markdown:** [`A Deep Dive Into MediaPipe Pose for Postural Assessment_ A Comparative Investigation.md`](./A%20Deep%20Dive%20Into%20MediaPipe%20Pose%20for%20Postural%20Assessment_%20A%20Comparative%20Investigation.md)
- **Páginas:** 20 páginas completas.
- **Complejidad de Layout & Mejoras v5.0:**
  - Encabezado `INDEX TERMS` de ancho completo inmediatamente adyacente a la columna izquierda de `I. INTRODUCTION`.
  - Dos columnas paralelas densas con notas al pie en la base de la columna izquierda debidamente segregadas.
  - **15 figuras de alta fidelidad** y **11 tablas complejas** recuperadas con unión proyectada sobre el eje $X$ y fusión de líneas multilínea.
  - Grafo de referencias con 75 entradas canónicas y 50 afirmaciones cuantitativas (*Grounded Claims*) ancladas en $O(1)$.
  - **Resultado v5.0:** $0.0\%$ entretejido (*text weaving*); lectura topológica continua por columna.

---

### 2. PLOS ONE — Maquetación Asimétrica (Barra Lateral + Cuerpo Principal)
- **PDF Original:** [`Lightweight and efficient skeleton-based sports activity recognition with ASTM-Net.pdf`](./Lightweight%20and%20efficient%20skeleton-based%20sports%20activity%20recognition%20with%20ASTM-Net.pdf)
- **Extracción Markdown:** [`Lightweight and efficient skeleton-based sports activity recognition with ASTM-Net.md`](./Lightweight%20and%20efficient%20skeleton-based%20sports%20activity%20recognition%20with%20ASTM-Net.md)
- **Páginas:** 30 páginas completas.
- **Complejidad de Layout & Mejoras v5.0:**
  - Barra lateral izquierda estrecha (~115 pt) con metadatos de autor, filiaciones y fechas de recepción.
  - Columna principal amplia (~375 pt) a la derecha con filetes horizontales decorativos en la cabecera y pie.
  - **10 tablas** recuperadas sin fragmentación de celdas descriptivas; **3 algoritmos** con preservación exacta de sangría.
  - Soporte de citas en superíndice `^{1,3-5}` desambiguadas de variables numéricas.
  - **Resultado v5.0:** Detección de medianera asimétrica en $x \approx 160\text{ pt}$. Cero falsas tablas *booktabs*.

---

### 3. De Gruyter — Dos Columnas con Tablas Booktabs y Figuras Vectoriales
- **PDF Original:** [`Accuracy Evaluation of 3D Pose Estimation with MediaPipe Pose for Physical Exercises.pdf`](./Accuracy%20Evaluation%20of%203D%20Pose%20Estimation%20with%20MediaPipe%20Pose%20for%20Physical%20Exercises.pdf)
- **Extracción Markdown:** [`Accuracy Evaluation of 3D Pose Estimation with MediaPipe Pose for Physical Exercises.md`](./Accuracy%20Evaluation%20of%203D%20Pose%20Estimation%20with%20MediaPipe%20Pose%20for%20Physical%20Exercises.md)
- **Páginas:** 4 páginas completas.
- **Complejidad de Layout & Mejoras v5.0:**
  - Filete tipográfico continuo en el encabezado superior ($y = 72\text{ pt}$) que cruza ambas columnas.
  - Tablas abiertas estilo LaTeX *booktabs* de 2 y 3 filetes sin bordes verticales, recuperadas íntegramente.
  - **Reordenamiento XY-Cut++ jerárquico:** Fig. 3 y Tab. 2 se reinsertan inmediatamente tras su párrafo descriptivo en el texto, eliminando duplicación de leyendas.
  - **Resultado v5.0:** Las figuras vectoriales permanecen acotadas a su columna correspondiente sin ser puenteadas por el filete superior.

---

### 4. MDPI — Maquetación Mixta (1 Columna Título/Abstract + 2 Columnas Cuerpo)
- **PDF Original:** [`A_Lightweight_CNN_TCN_Attention_Pre_Fall_Edge_Devices.pdf`](./A_Lightweight_CNN_TCN_Attention_Pre_Fall_Edge_Devices.pdf)
- **Extracción Markdown:** [`A_Lightweight_CNN_TCN_Attention_Pre_Fall_Edge_Devices.md`](./A_Lightweight_CNN_TCN_Attention_Pre_Fall_Edge_Devices.md)
- **Páginas:** 20 páginas completas.
- **Complejidad de Layout & Mejoras v5.0:**
  - Título, lista de 8 autores, filiaciones y resumen extenso en una sola columna central.
  - Transición inmediata a cuerpo en 2 columnas densas a partir de la sección de Introducción.
  - **7 tablas** y **6 figuras** sincronizadas con el flujo narrativo.
  - Ecuaciones matemáticas 2D con delimitadores y normalización KaTeX.
  - **Resultado v5.0:** Transición topológica XY-Cut limpia en el cambio de 1 columna a 2 columnas.

---

### 5. IEEE Transactions — Dos Columnas con Fórmulas Matemáticas y Grafos
- **PDF Original:** [`Efficient Real-Time Sports Action Pose Estimation via EfficientPose and Temporal Graph Convolution.pdf`](./Efficient%20Real-Time%20Sports%20Action%20Pose%20Estimation%20via%20EfficientPose%20and%20Temporal%20Graph%20Convolution.pdf)
- **Extracción Markdown:** [`Efficient Real-Time Sports Action Pose Estimation via EfficientPose and Temporal Graph Convolution.md`](./Efficient%20Real-Time%20Sports%20Action%20Pose%20Estimation%20via%20EfficientPose%20and%20Temporal%20Graph%20Convolution.md)
- **Páginas:** 11 páginas completas.
- **Complejidad de Layout & Mejoras v5.0:**
  - Dos columnas paralelas estándar de IEEE Transactions con fórmulas matemáticas 2D intercaladas en el texto.
  - Invariante de conectividad radical y matrices con delimitadores.
  - 4 tablas recuperadas (Tablas 1, 2, 3 y 4) y 5 figuras exportadas a 300 DPI.
  - 47 referencias bibliográficas IEEE estructuradas y 35 Grounded Claims cuantitativos.
  - Biografías de autores y fotografías al final del artículo ordenadas por columna.
  - **Resultado v5.0:** Reconstrucción matemática KaTeX de alta fidelidad y aislamiento estricto de biografías.
