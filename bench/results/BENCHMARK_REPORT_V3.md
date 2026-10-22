# ScholarMark v4.1.0 — Quantitative Benchmark Report

## 1. Gold Suite Pathologies: `fast` (v2.1 Baseline) vs. `vision` (v4.1 Ultra-Light Pipeline)

| Case ID | Audited Dimension | `fast` Score | `vision` Score | Δ Improvement | `vision` Time (ms) | Notes |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `case1_two_col_footnotes` | Reading Order (Kendall-τ) | 0.9048 | **1.0000** | **+0.0952** | 19.4 ms | 2-column layout with bottom-left footnote segregation |
| `case2_2d_math` | 2D Math Fidelity (1 - NED) | 0.1633 | **0.9355** | **+0.7722** | 2.8 ms | Recovered LaTeX: L = \frac{x_{i}^{n + 1}}{y_{k}} |
| `case3_booktabs_colspan` | Hierarchical Table (TEDS) | 0.4500 | **1.0000** | **+0.5500** | 3.8 ms | Booktabs table with multi-level colspan=2 & rowspan=2 headers |
| `case4_multipanel_1n` | Caption 1:N Matching (F1) | 0.5000 | **1.0000** | **+0.5000** | 45.6 ms | 3 subpanels (a)(b)(c) linked to shared Fig. 1 + standalone Fig. 2 |
| `case5_dense_scatter_guard` | Vector Guard (<2.5s SLA) | 1.0000 | **1.0000** | **+0.0000** | 212.9 ms | 2,704 vector rects processed in 212.9 ms without OOM |
| `case6_algorithm_pseudocode` | Algorithm Indentation Acc. | 0.2500 | **1.0000** | **+0.7500** | 7.3 ms | Algorithm 1 with nested for/if/end + horizontal rules |
| `case7_citations_and_chart_semantics` | Citation Graph & Chart Meta | 0.0000 | **1.0000** | **+1.0000** | 229.8 ms | 3 IEEE refs + [1]-[3] claim link + chart axes/series/values |
| `case8_ieee_author_bios_and_rag_chunks` | RAG Semantic Chunks & Bio Guard | 0.1667 | **1.0000** | **+0.8333** | 5.0 ms | Atomic algorithm chunk + hydrated citation [1] + isolated IEEE Author Biographies |
| **OVERALL MEAN** | **Composite Gold Score** | 0.4294 | **0.9919** | **+0.5626** | — | All quality gates passed |

## 2. Real Scientific Corpus Sample (`Referencias/Original`)

| Paper | Pages | Engine | Status | Characters | Total Time (ms) | Latency (ms/page) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `A Deep Dive Into MediaPipe Pose for Postur` | 20 | `fast` | success | 99,754 | 11664.1 | **583.2 ms/pág** |
| `A Hybrid Approach for Sports Activity Reco` | 23 | `fast` | success | 73,628 | 9950.4 | **432.6 ms/pág** |
| `A Lightweight CNN–TCN–Attention Framework ` | 20 | `fast` | success | 69,638 | 8714.0 | **435.7 ms/pág** |
| `A Deep Dive Into MediaPipe Pose for Postur` | 20 | `vision` | success | 96,553 | 7648.7 | **382.4 ms/pág** |
| `A Hybrid Approach for Sports Activity Reco` | 23 | `vision` | success | 91,836 | 5635.6 | **245.0 ms/pág** |
| `A Lightweight CNN–TCN–Attention Framework ` | 20 | `vision` | success | 72,514 | 2817.8 | **140.9 ms/pág** |
