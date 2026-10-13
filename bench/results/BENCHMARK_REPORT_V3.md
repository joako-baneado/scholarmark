# ScholarMark v4.0.0 — Quantitative Benchmark Report

## 1. Gold Suite Pathologies: `fast` (v2.1 Baseline) vs. `vision` (v3.0 Hybrid Pipeline)

| Case ID | Audited Dimension | `fast` Score | `vision` Score | Δ Improvement | `vision` Time (ms) | Notes |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `case1_two_col_footnotes` | Reading Order (Kendall-τ) | 0.9048 | **1.0000** | **+0.0952** | 176.9 ms | 2-column layout with bottom-left footnote segregation |
| `case2_2d_math` | 2D Math Fidelity (1 - NED) | 0.0938 | **0.9355** | **+0.8417** | 147.8 ms | Recovered LaTeX: L = \frac{x_{i}^{n + 1}}{y_{k}} |
| `case3_booktabs_colspan` | Hierarchical Table (TEDS) | 0.4500 | **1.0000** | **+0.5500** | 871.3 ms | Booktabs table with multi-level colspan=2 & rowspan=2 headers |
| `case4_multipanel_1n` | Caption 1:N Matching (F1) | 0.5000 | **1.0000** | **+0.5000** | 151.9 ms | 3 subpanels (a)(b)(c) linked to shared Fig. 1 + standalone Fig. 2 |
| `case5_dense_scatter_guard` | Vector Guard (<2.5s SLA) | 1.0000 | **1.0000** | **+0.0000** | 427.7 ms | 2,704 vector rects processed in 427.7 ms without OOM |
| `case6_algorithm_pseudocode` | Algorithm Indentation Acc. | 0.2500 | **1.0000** | **+0.7500** | 217.0 ms | Algorithm 1 with nested for/if/end + horizontal rules |
| `case7_citations_and_chart_semantics` | Citation Graph & Chart Meta | 0.0000 | **1.0000** | **+1.0000** | 230.5 ms | 3 IEEE refs + [1]-[3] claim link + chart axes/series/values |
| `case8_ieee_author_bios_and_rag_chunks` | RAG Semantic Chunks & Bio Guard | 0.1667 | **1.0000** | **+0.8333** | 186.7 ms | Atomic algorithm chunk + hydrated citation [1] + isolated IEEE Author Biographies |
| **OVERALL MEAN** | **Composite Gold Score** | 0.4207 | **0.9919** | **+0.5713** | — | All quality gates passed |
