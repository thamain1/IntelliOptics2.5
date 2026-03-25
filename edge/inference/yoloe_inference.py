"""
IntelliOptics 2.0 - YOLOE Open-Vocabulary Inference
Dynamic text prompt object detection without custom training.
"""

import logging
import os
import time
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Persist Ultralytics model downloads to Docker volume
os.environ.setdefault("YOLO_CONFIG_DIR", "/models/ultralytics")

# Lazy-loaded model reference
_yoloe_model = None


class Detection:
    """Single detection result."""

    def __init__(self, label: str, confidence: float, bbox: list[float]):
        self.label = label
        self.confidence = confidence
        self.bbox = bbox  # [x1, y1, x2, y2] pixel coords

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "confidence": self.confidence,
            "bbox": self.bbox,
        }

    def to_normalized(self, img_width: int, img_height: int) -> dict:
        """Return bbox in normalized 0-1 coordinates."""
        x1, y1, x2, y2 = self.bbox
        return {
            "label": self.label,
            "confidence": self.confidence,
            "bbox": [
                x1 / img_width,
                y1 / img_height,
                x2 / img_width,
                y2 / img_height,
            ],
        }


class YOLOEInference:
    """YOLOE open-vocabulary object detection.

    Accepts dynamic text prompts per-request — no re-training needed.
    Uses Ultralytics YOLOE under the hood.
    """

    def __init__(self, model_path: str = "yolov8s-worldv2.pt"):
        self.model_path = model_path
        self.model = None
        self._load_model()

    def _load_model(self) -> None:
        """Load YOLOE model via Ultralytics."""
        try:
            import torch

            # Patch torch.load for PyTorch 2.6+ compat
            original_torch_load = torch.load

            def patched_torch_load(*args, **kwargs):
                kwargs["weights_only"] = False
                return original_torch_load(*args, **kwargs)

            torch.load = patched_torch_load

            from ultralytics import YOLO

            # Check CUDA availability AND compute capability compatibility
            self.device = "cpu"
            if torch.cuda.is_available():
                try:
                    cap = torch.cuda.get_device_capability(0)
                    if cap[0] >= 7:
                        self.device = "cuda"
                    else:
                        logger.warning(
                            f"GPU compute capability {cap[0]}.{cap[1]} < 7.0 required by PyTorch. Falling back to CPU."
                        )
                except Exception:
                    logger.warning("Could not check GPU capability. Falling back to CPU.")
            logger.info(f"Loading YOLOE model: {self.model_path} on {self.device}")
            self.model = YOLO(self.model_path)
            self.model.to(self.device)
            logger.info("YOLOE model loaded successfully")

            torch.load = original_torch_load
        except Exception as e:
            logger.error(f"Failed to load YOLOE model: {e}")
            raise

    def detect(
        self,
        image: np.ndarray,
        prompts: list[str],
        conf: float = 0.25,
        iou: float = 0.45,
    ) -> list[Detection]:
        """Run open-vocabulary detection with dynamic text prompts.

        Args:
            image: Input image as numpy array (BGR or RGB).
            prompts: List of text prompts describing objects to detect.
            conf: Confidence threshold.
            iou: NMS IoU threshold.

        Returns:
            List of Detection objects with labels, confidence, and bounding boxes.
        """
        if not self.model:
            raise RuntimeError("YOLOE model not loaded")

        start = time.perf_counter()

        # Set classes from prompts (ensure CLIP text tokens land on same device as model)
        self.model.set_classes(prompts)

        # Run inference on the model's device
        results = self.model.predict(image, conf=conf, iou=iou, verbose=False, device=self.device)

        detections: list[Detection] = []
        for result in results:
            boxes = result.boxes
            if boxes is not None:
                for i in range(len(boxes)):
                    box = boxes[i]
                    cls_id = int(box.cls[0])
                    confidence = float(box.conf[0])
                    xyxy = box.xyxy[0].tolist()

                    label = prompts[cls_id] if cls_id < len(prompts) else f"class_{cls_id}"
                    detections.append(Detection(label=label, confidence=confidence, bbox=xyxy))

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(f"YOLOE detected {len(detections)} objects in {elapsed_ms:.0f}ms")

        return detections


def get_yoloe_model(model_path: str = "yolov8s-worldv2.pt") -> YOLOEInference:
    """Get or create singleton YOLOE inference instance."""
    global _yoloe_model
    if _yoloe_model is None:
        _yoloe_model = YOLOEInference(model_path=model_path)
    return _yoloe_model
