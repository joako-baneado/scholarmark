"""
Local Lightweight ONNX OCR Engine for ScholarMark v4.1.
Provides 100% offline, CPU-friendly optical character recognition using
miniature ONNX models (RapidOCR / PP-OCRv4) under selective gating.
"""

from typing import List, Tuple, Optional, Any
import numpy as np
import fitz
from ..core.geometry import BoundingBox


class LocalOCREngine:
    """
    Singleton perezoso para OCR local con RapidOCR en ONNX.
    Solo inicializa el modelo cuando una compuerta de visión lo requiere.
    """
    _instance: Optional["LocalOCREngine"] = None
    _engine: Optional[Any] = None
    _initialized: bool = False

    def __new__(cls) -> "LocalOCREngine":
        if cls._instance is None:
            cls._instance = super(LocalOCREngine, cls).__new__(cls)
        return cls._instance

    @classmethod
    def is_available(cls) -> bool:
        """Verifica si rapidocr_onnxruntime está instalado y listo para usarse."""
        try:
            import rapidocr_onnxruntime
            return True
        except ImportError:
            return False

    def _get_engine(self) -> Optional[Any]:
        if not self._initialized:
            try:
                from rapidocr_onnxruntime import RapidOCR
                self._engine = RapidOCR()
            except Exception:
                self._engine = None
            self._initialized = True
        return self._engine

    def extract_words_from_pixmap(
        self,
        pix: fitz.Pixmap,
        clip_bbox: BoundingBox,
        dpi: int = 200,
    ) -> List[Tuple[BoundingBox, str, float]]:
        """
        Ejecuta OCR sobre un Pixmap recortado y proyecta las coordenadas de vuelta
        al sistema de referencia del documento PDF (en puntos tipográficos 72 DPI).

        Retorna lista de: (BoundingBox_pdf, texto, confianza).
        """
        engine = self._get_engine()
        if engine is None or pix is None or pix.width < 4 or pix.height < 4:
            return []

        try:
            arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, pix.n))
            if pix.n == 4:
                import cv2
                img = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
            elif pix.n == 3:
                import cv2
                img = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            elif pix.n == 1:
                import cv2
                img = cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
            else:
                img = arr

            results, _ = engine(img)
            if not results:
                return []

            scale = 72.0 / float(dpi)
            words: List[Tuple[BoundingBox, str, float]] = []

            for box_pts, txt, score in results:
                txt_clean = str(txt).strip()
                if not txt_clean:
                    continue
                px0 = min(pt[0] for pt in box_pts)
                py0 = min(pt[1] for pt in box_pts)
                px1 = max(pt[0] for pt in box_pts)
                py1 = max(pt[1] for pt in box_pts)

                pdf_x0 = clip_bbox.x0 + px0 * scale
                pdf_y0 = clip_bbox.y0 + py0 * scale
                pdf_x1 = clip_bbox.x0 + px1 * scale
                pdf_y1 = clip_bbox.y0 + py1 * scale

                box = BoundingBox(pdf_x0, pdf_y0, pdf_x1, pdf_y1)
                words.append((box, txt_clean, float(score)))

            return words
        except Exception:
            return []

    def extract_words_from_region(
        self,
        page: fitz.Page,
        bbox: BoundingBox,
        dpi: int = 200,
        pad: float = 2.0,
    ) -> List[Tuple[BoundingBox, str, float]]:
        """Recorta un Pixmap de la región dada en la página y extrae palabras proyectadas a PDF."""
        clip_rect = bbox.pad(pad, page.rect).to_fitz_rect()
        pix = page.get_pixmap(clip=clip_rect, dpi=dpi)
        padded_bbox = BoundingBox.from_fitz_rect(clip_rect)
        return self.extract_words_from_pixmap(pix, padded_bbox, dpi=dpi)
