# ScholarMark v3.0.0 — Quantitative Benchmark Report

## 1. Gold Suite Pathologies: `fast` (v2.1 Baseline) vs. `vision` (v3.0 Hybrid Pipeline)

| Case ID | Audited Dimension | `fast` Score | `vision` Score | Δ Improvement | `vision` Time (ms) | Notes |
| :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| `case1_two_col_footnotes` | Reading Order (Kendall-τ) | 0.9048 | **1.0000** | **+0.0952** | 145.6 ms | 2-column layout with bottom-left footnote segregation |
| `case2_2d_math` | 2D Math Fidelity (1 - NED) | 0.0938 | **0.9355** | **+0.8417** | 112.4 ms | Recovered LaTeX: L = \frac{x_{i}^{n + 1}}{y_{k}} |
| `case3_booktabs_colspan` | Hierarchical Table (TEDS) | 0.4500 | **1.0000** | **+0.5500** | 682.0 ms | Booktabs table with multi-level colspan=2 & rowspan=2 headers |
| `case4_multipanel_1n` | Caption 1:N Matching (F1) | 0.5000 | **1.0000** | **+0.5000** | 171.3 ms | 3 subpanels (a)(b)(c) linked to shared Fig. 1 + standalone Fig. 2 |
| `case5_dense_scatter_guard` | Vector Guard (<2.5s SLA) | 1.0000 | **1.0000** | **+0.0000** | 372.9 ms | 2,704 vector rects processed in 372.9 ms without OOM |
| **OVERALL MEAN** | **Composite Gold Score** | 0.5897 | **0.9871** | **+0.3974** | — | All quality gates passed |

## 2. Real Scientific Corpus Sample (`Referencias/Original`)

| Paper | Pages | Engine | Status | Characters | Total Time (ms) | Latency (ms/page) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `A Deep Dive Into MediaPipe Pose for Postur` | 20 | `fast` | success | 99,803 | 11854.4 | **592.7 ms/pág** |
| `A Hybrid Approach for Sports Activity Reco` | 23 | `fast` | success | 73,648 | 9010.6 | **391.8 ms/pág** |
| `A Lightweight CNN–TCN–Attention Framework ` | 20 | `fast` | success | 69,644 | 6821.4 | **341.1 ms/pág** |
| `A Deep Dive Into MediaPipe Pose for Postur` | 20 | `vision` | success | 96,437 | 9314.3 | **465.7 ms/pág** |
| `A Hybrid Approach for Sports Activity Reco` | 23 | `vision` | success | 91,227 | 8524.3 | **370.6 ms/pág** |
| `A Lightweight CNN–TCN–Attention Framework ` | 20 | `vision` | success | 71,825 | 5862.1 | **293.1 ms/pág** |
