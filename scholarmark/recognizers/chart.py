"""
Chart-to-Metadata Semantic Extractor for ScholarMark v4.1.
Extracts and classifies native vector text spans inside scientific figures and plots
into axis_labels, legend_series, data_annotations, and tick_values so RAG pipelines
can query quantitative figure contents without requiring a VLM at search time.
"""

from dataclasses import dataclass, field
import re
from typing import List, Optional, Dict, Any, Set
import fitz

from ..core.caption_matcher import SUBPANEL_TAG_REGEX, CAPTION_REGEX
from ..core.geometry import BoundingBox
from ..core.math_parser import clean_math_glyphs, sanitize_numeric_typography
from ..core.page_context import PageContext


_AXIS_KEYWORD_RE = re.compile(
    r"\b(?:latency|accuracy|precision|recall|f1|map|mpjpe|error|loss|epoch|epochs|"
    r"time|fps|throughput|frequency|wavelength|temperature|voltage|current|power|"
    r"batch\s+size|parameters|flops|gflops|memory|speed|score|rate|ratio|distance)\b"
    r"|\([^)]*(?:%|ms|s|hz|khz|db|mm|cm|m|gb|mb|fps|gflops)[^)]*\)",
    re.IGNORECASE,
)
_NUMERIC_VALUE_RE = re.compile(
    r"^[+\-]?\d+(?:\.\d+)?(?:\s*(?:%|ms|s|FPS|fps|dB|mm|GB|MB|x|×10\^?[+\-]?\d+))?$"
)


@dataclass
class ChartSemantics:
    """Metadatos semánticos extraídos del interior de un gráfico científico vectorial."""
    axis_labels: List[str] = field(default_factory=list)
    legend_series: List[str] = field(default_factory=list)
    data_annotations: List[str] = field(default_factory=list)
    tick_values: List[str] = field(default_factory=list)

    @property
    def has_content(self) -> bool:
        return bool(self.axis_labels or self.legend_series or self.data_annotations)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "axis_labels": self.axis_labels,
            "legend_series": self.legend_series,
            "data_annotations": self.data_annotations,
            "tick_values": self.tick_values,
        }


class ChartSemanticsExtractor:
    """
    Inspector geométrico de texto interno en figuras vectoriales.
    """

    @staticmethod
    def extract_from_figure(
        page: fitz.Page,
        bbox: BoundingBox,
        exclude_subpanels: Optional[List[str]] = None,
        ctx: Optional[PageContext] = None,
    ) -> ChartSemantics:
        if ctx is not None:
            raw = ctx.clip_rawdict(bbox, pad=4.0)
        else:
            clip = bbox.pad(4.0, page.rect).to_fitz_rect()
            raw = page.get_text("dict", clip=clip)

        excluded: Set[str] = {s.strip().lower() for s in (exclude_subpanels or []) if s}
        fig_w = max(1.0, bbox.width)
        fig_h = max(1.0, bbox.height)

        axis_labels: List[str] = []
        legend_series: List[str] = []
        data_annotations: List[str] = []
        tick_values: List[str] = []

        seen: Set[str] = set()

        for b in raw.get("blocks", []):
            if b.get("type") != 0:
                continue
            for ln in b.get("lines", []):
                lb = BoundingBox(*[float(v) for v in ln["bbox"]])
                raw_txt = " ".join(
                    str(s.get("text", "")).strip()
                    for s in ln.get("spans", [])
                    if str(s.get("text", "")).strip()
                ).strip()
                if not raw_txt:
                    continue

                clean_txt = " ".join(clean_math_glyphs(sanitize_numeric_typography(raw_txt)).split()).strip()
                if not clean_txt or len(clean_txt) > 90:
                    continue

                if CAPTION_REGEX.match(clean_txt) or SUBPANEL_TAG_REGEX.fullmatch(clean_txt):
                    continue
                if clean_txt.lower() in excluded:
                    continue

                rel_x = ((lb.x0 + lb.x1) * 0.5 - bbox.x0) / fig_w
                rel_y = ((lb.y0 + lb.y1) * 0.5 - bbox.y0) / fig_h
                near_perimeter = rel_x <= 0.22 or rel_y >= 0.78 or rel_y <= 0.14

                if _NUMERIC_VALUE_RE.match(clean_txt):
                    has_unit_or_decimal = ("." in clean_txt) or any(u in clean_txt.lower() for u in ("%", "ms", "fps", "db", "mm"))
                    if near_perimeter and not has_unit_or_decimal:
                        if clean_txt not in tick_values:
                            tick_values.append(clean_txt)
                    else:
                        if clean_txt not in data_annotations:
                            data_annotations.append(clean_txt)
                    continue

                key_lower = clean_txt.lower()
                if key_lower in seen:
                    continue
                seen.add(key_lower)

                if _AXIS_KEYWORD_RE.search(clean_txt):
                    if len(clean_txt.split()) <= 6:
                        axis_labels.append(clean_txt)
                elif len(clean_txt.split()) <= 4 and len(clean_txt) >= 2:
                    legend_series.append(clean_txt)

        if not axis_labels and not data_annotations and not tick_values:
            legend_series = []

        return ChartSemantics(
            axis_labels=axis_labels[:12],
            legend_series=legend_series[:16],
            data_annotations=data_annotations[:20],
            tick_values=tick_values[:20],
        )
