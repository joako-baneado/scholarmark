# Benchmark Papers: Multi-Column Academic Corpus (ScholarMark v4.1)

Colección canónica de 5 artículos científicos representativos utilizados para evaluar y validar la robustez del motor visual de extracción estructural y el resolvedor topológico DAG multicolumna de **ScholarMark v4.1**.

Cada artículo incluye su archivo PDF original y su correspondiente extracción completa a Markdown (`.md`), con figuras renderizadas en alta resolución (300 DPI) alojadas en la subcarpeta `assets/`.

---

## Índice de Documentos del Corpus

### 1. IEEE Access — Maquetación de Dos Columnas Simétricas
- **PDF Original:** [`A Deep Dive Into MediaPipe Pose for Postural Assessment_ A Comparative Investigation.pdf`](./A%20Deep%20Dive%20Into%20MediaPipe%20Pose%20for%20Postural%20Assessment_%20A%20Comparative%20Investigation.pdf)
- **Extracción Markdown:** [`A Deep Dive Into MediaPipe Pose for Postural Assessment_ A Comparative Investigation.md`](./A%20Deep%20Dive%20Into%20MediaPipe%20Pose%20for%20Postural%20Assessment_%20A%20Comparative%20Investigation.md)
- **Páginas:** 20 páginas completas.
- **Complejidad de Layout:**
  - Encabezado `INDEX TERMS` de ancho completo inmediatamente adyacente a la columna izquierda de `I. INTRODUCTION`.
  - Dos columnas paralelas densas con notas al pie en la base de la columna izquierda.
  - 15 figuras y 10 tablas intermedias.
  - **Resultado:** 0.0% entretejido (*text weaving*); lectura topológica continua por columna.

---

### 2. PLOS ONE — Maquetación Asimétrica (Barra Lateral + Cuerpo Principal)
- **PDF Original:** [`Lightweight and efficient skeleton-based sports activity recognition with ASTM-Net.pdf`](./Lightweight%20and%20efficient%20skeleton-based%20sports%20activity%20recognition%20with%20ASTM-Net.pdf)
- **Extracción Markdown:** [`Lightweight and efficient skeleton-based sports activity recognition with ASTM-Net.md`](./Lightweight%20and%20efficient%20skeleton-based%20sports%20activity%20recognition%20with%20ASTM-Net.md)
- **Páginas:** 30 páginas completas.
- **Complejidad de Layout:**
  - Barra lateral izquierda estrecha (~115 pt) con metadatos de autor, filiaciones y fechas de recepción.
  - Columna principal amplia (~375 pt) a la derecha.
  - Filetes horizontales decorativos en la parte superior e inferior de la página.
  - **Resultado:** Detección de medianera asimétrica en $x \approx 160\text{ pt}$. Cero falsas tablas *booktabs*.

---

### 3. De Gruyter — Dos Columnas con Tablas Booktabs y Figuras Vectoriales
- **PDF Original:** [`Accuracy Evaluation of 3D Pose Estimation with MediaPipe Pose for Physical Exercises.pdf`](./Accuracy%20Evaluation%20of%203D%20Pose%20Estimation%20with%20MediaPipe%20Pose%20for%20Physical%20Exercises.pdf)
- **Extracción Markdown:** [`Accuracy Evaluation of 3D Pose Estimation with MediaPipe Pose for Physical Exercises.md`](./Accuracy%20Evaluation%20of%203D%20Pose%20Estimation%20with%20MediaPipe%20Pose%20for%20Physical%20Exercises.md)
- **Páginas:** 4 páginas completas.
- **Complejidad de Layout:**
  - Filete tipográfico continuo en el encabezado superior ($y = 72\text{ pt}$) que cruza ambas columnas.
  - Tablas abiertas estilo LaTeX *booktabs* de 2 y 3 filetes sin bordes verticales.
  - Diagramas vectoriales con curvas y texto incrustado.
  - **Resultado:** Las figuras vectoriales permanecen acotadas a su columna correspondiente sin ser puenteadas por el filete superior.

---

### 4. MDPI — Maquetación Mixta (1 Columna Título/Abstract + 2 Columnas Cuerpo)
- **PDF Original:** [`A_Lightweight_CNN_TCN_Attention_Pre_Fall_Edge_Devices.pdf`](./A_Lightweight_CNN_TCN_Attention_Pre_Fall_Edge_Devices.pdf)
- **Extracción Markdown:** [`A_Lightweight_CNN_TCN_Attention_Pre_Fall_Edge_Devices.md`](./A_Lightweight_CNN_TCN_Attention_Pre_Fall_Edge_Devices.md)
- **Páginas:** 20 páginas completas.
- **Complejidad de Layout:**
  - Título, lista de 8 autores, filiaciones y resumen extenso en una sola columna central.
  - Transición inmediata a cuerpo en 2 columnas densas a partir de la sección de Introducción.
  - Ecuaciones matemáticas y diagramas de bloques de red neuronal.
  - **Resultado:** Transición topológica XY-Cut limpia en el cambio de 1 columna a 2 columnas.

---

### 5. IEEE Transactions — Dos Columnas con Fórmulas Matemáticas y Grafos
- **PDF Original:** [`Efficient Real-Time Sports Action Pose Estimation via EfficientPose and Temporal Graph Convolution.pdf`](./Efficient%20Real-Time%20Sports%20Action%20Pose%20Estimation%20via%20EfficientPose%20and%20Temporal%20Graph%20Convolution.pdf)
- **Extracción Markdown:** [`Efficient Real-Time Sports Action Pose Estimation via EfficientPose and Temporal Graph Convolution.md`](./Efficient%20Real-Time%20Sports%20Action%20Pose%20Estimation%20via%20EfficientPose%20and%20Temporal%20Graph%20Convolution.md)
- **Páginas:** 11 páginas completas.
- **Complejidad de Layout:**
  - Dos columnas paralelas estándar de IEEE Transactions con fórmulas matemáticas 2D intercaladas en el texto.
  - Biografías de autores y fotografías al final del artículo.
  - **Resultado:** Reconstrucción perfecta en KaTeX; las biografías de autores se ordenan por columna al pie del documento.
