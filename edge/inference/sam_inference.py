"""
IntelliOptics 2.5 - SAM Segment Enrichment
Wraps MobileSAM to produce pixel-precise mask polygons for YOLOE detections.

Pipeline:
    YOLOE detection (bbox) → SAMInference.segment_from_bboxes() → mask polygon
    → enriched Detection.mask_polygon → GeoJSON-ready polygon for Eagle Eye

MobileSAM (~10MB checkpoint, CPU-capable, ~40ms/frame) is the default.
Swap SAM_MODEL_TYPE="vit_b" + a SAM ViT-B checkpoint for higher-accuracy deployments.
"""

import logging
import os
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

SAM_MODEL_DIR = os.getenv("SAM_MODEL_DIR", "/models/sam")
SAM_MODEL_TYPE = os.getenv("SAM_MODEL_TYPE", "vit_t")    # vit_t = MobileSAM tiny
SAM_CHECKPOINT = os.getenv("SAM_CHECKPOINT", "mobile_sam.pt")
SAM_POLY_EPSILON = float(os.getenv("SAM_POLY_EPSILON", "0.005"))  # Douglas-Peucker tolerance

_sam_instance: Optional["SAMInference"] = None


class SAMInference:
    """MobileSAM predictor — segments objects from bbox prompts."""

    def __init__(self, checkpoint_path: str, model_type: str = "vit_t"):
        self.checkpoint_path = checkpoint_path
        self.model_type = model_type
        self.predictor = None
        self._loaded = False

    def load(self) -> bool:
        try:
            from mobile_sam import SamPredictor, sam_model_registry
            sam = sam_model_registry[self.model_type](checkpoint=self.checkpoint_path)
            sam.eval()
            self.predictor = SamPredictor(sam)
            self._loaded = True
            logger.info(f"SAM loaded: type={self.model_type} ckpt={self.checkpoint_path}")
            return True
        except ImportError:
            logger.warning("mobile-sam not installed — SAM enrichment disabled. pip install mobile-sam")
        except FileNotFoundError:
            logger.warning(f"SAM checkpoint not found at {self.checkpoint_path} — enrichment disabled")
        except Exception as e:
            logger.error(f"SAM load failed: {e}", exc_info=True)
        self._loaded = False
        return False

    @property
    def loaded(self) -> bool:
        return self._loaded

    def segment_from_bboxes(
        self,
        image_np: np.ndarray,
        bboxes: list[list[float]],
    ) -> list[list[list[float]]]:
        """
        Segment each bbox region and return a simplified polygon contour per bbox.

        Args:
            image_np: RGB image as HxWx3 uint8 numpy array.
            bboxes:   List of [x1, y1, x2, y2] in pixel coordinates.

        Returns:
            List of polygons — one per input bbox.
            Each polygon: [[x, y], ...] normalized to [0, 1].
            Returns [] for any bbox that fails.
        """
        if not self._loaded or self.predictor is None:
            return [[] for _ in bboxes]

        try:
            self.predictor.set_image(image_np)
        except Exception as e:
            logger.warning(f"SAM set_image failed: {e}")
            return [[] for _ in bboxes]

        h, w = image_np.shape[:2]
        polygons: list[list[list[float]]] = []

        for bbox in bboxes:
            try:
                x1, y1, x2, y2 = [float(v) for v in bbox]
                # Clamp to image bounds
                x1 = max(0.0, min(x1, w - 1))
                y1 = max(0.0, min(y1, h - 1))
                x2 = max(x1 + 1, min(x2, w))
                y2 = max(y1 + 1, min(y2, h))

                input_box = np.array([[x1, y1, x2, y2]])
                masks, scores, _ = self.predictor.predict(
                    box=input_box,
                    multimask_output=True,
                )
                # multimask_output=True returns 3 masks; pick highest-score
                best_idx = int(np.argmax(scores))
                mask = masks[best_idx]
                polygon = _mask_to_polygon(mask, w, h, SAM_POLY_EPSILON)
                polygons.append(polygon)
            except Exception as e:
                logger.warning(f"SAM segment failed for bbox {bbox}: {e}")
                polygons.append([])

        return polygons


def _mask_to_polygon(
    mask: np.ndarray,
    img_w: int,
    img_h: int,
    epsilon_ratio: float = 0.005,
) -> list[list[float]]:
    """
    Convert binary mask → largest contour → simplified polygon → normalized [[x,y],...].

    epsilon_ratio controls Douglas-Peucker simplification:
        0.005 = 0.5% of perimeter (keeps moderate detail)
        0.02  = 2% (very coarse, few vertices)
    """
    mask_u8 = (mask.astype(np.uint8)) * 255
    contours, _ = cv2.findContours(mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return []

    contour = max(contours, key=cv2.contourArea)
    epsilon = epsilon_ratio * cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, epsilon, True)

    return [
        [float(pt[0][0]) / img_w, float(pt[0][1]) / img_h]
        for pt in approx
    ]


def get_sam_model() -> Optional[SAMInference]:
    """Lazy global loader — returns None if SAM unavailable (non-fatal)."""
    global _sam_instance
    if _sam_instance is not None:
        return _sam_instance if _sam_instance.loaded else None

    checkpoint = _find_checkpoint()
    if not checkpoint:
        logger.info("SAM checkpoint not found — segment enrichment disabled")
        _sam_instance = SAMInference("", SAM_MODEL_TYPE)  # marks as not loaded
        return None

    _sam_instance = SAMInference(checkpoint, SAM_MODEL_TYPE)
    _sam_instance.load()
    return _sam_instance if _sam_instance.loaded else None


def _find_checkpoint() -> Optional[str]:
    """Search SAM_MODEL_DIR for a known checkpoint filename."""
    model_dir = Path(SAM_MODEL_DIR)
    candidates = [
        SAM_CHECKPOINT,          # env-configurable, default mobile_sam.pt
        "mobile_sam.pt",
        "sam_vit_t.pth",
        "sam_vit_b_01ec64.pth",  # SAM ViT-B fallback
    ]
    for name in candidates:
        p = model_dir / name
        if p.exists():
            logger.info(f"SAM checkpoint found: {p}")
            return str(p)
    return None
