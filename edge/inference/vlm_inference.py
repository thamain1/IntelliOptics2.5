"""
IntelliOptics 2.5 - Moondream VLM Inference (Pure ONNX Runtime)

Visual Language Model for natural language queries, object detection, and OCR.
Uses the official moondream pip package (ONNX Runtime internally) — no PyTorch,
no HuggingFace transformers at runtime.
"""

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Model path (set via VLM_MODEL_PATH env or Docker volume)
VLM_MODEL_PATH = os.getenv("VLM_MODEL_PATH", "/vlm-models/moondream-0_5b-int4.mf.gz")

_vlm_instance: Optional["MoondreamVLM"] = None


@dataclass
class VLMResult:
    """Result from a VLM query."""

    answer: str
    confidence: float = 1.0
    bboxes: list[dict] = field(default_factory=list)
    latency_ms: float = 0.0


class MoondreamVLM:
    """Moondream Visual Language Model for image understanding.

    Uses the official moondream pip package (ONNX Runtime backend).
    Model: moondream-0_5b-int4.mf.gz (~442MB) from vikhyatk/moondream2.

    Supports:
    - Visual Q&A (ask questions about an image)
    - Object detection with bounding boxes
    - OCR (text extraction from images or regions)
    """

    def __init__(self, model_path: str = VLM_MODEL_PATH):
        self.model_path = model_path
        self.model = None
        self._load_model()

    def _load_model(self) -> None:
        """Load Moondream model via official moondream package."""
        try:
            import moondream as md

            logger.info(f"Loading Moondream VLM from {self.model_path}...")
            self.model = md.vl(model=self.model_path)
            logger.info("Moondream VLM loaded successfully (ONNX Runtime)")
        except FileNotFoundError:
            logger.error(f"Moondream model not found: {self.model_path}")
            self.model = None
        except Exception as e:
            logger.error(f"Failed to load Moondream VLM: {e}")
            self.model = None

    def _to_pil(self, image: np.ndarray) -> Image.Image:
        """Convert numpy array to PIL Image."""
        if image.dtype != np.uint8:
            image = (image * 255).astype(np.uint8)
        return Image.fromarray(image)

    def query(self, image: np.ndarray, question: str) -> VLMResult:
        """Ask a natural language question about an image.

        Args:
            image: Input image as numpy array (RGB).
            question: Natural language question.

        Returns:
            VLMResult with answer text.
        """
        if not self.model:
            return VLMResult(answer="VLM not available", confidence=0.0)

        start = time.perf_counter()
        pil_image = self._to_pil(image)

        try:
            encoded = self.model.encode_image(pil_image)
            answer = self.model.query(encoded, question)["answer"]
            elapsed_ms = (time.perf_counter() - start) * 1000

            logger.info(f"VLM query '{question[:50]}...' answered in {elapsed_ms:.0f}ms")
            return VLMResult(answer=answer, confidence=1.0, latency_ms=elapsed_ms)
        except Exception as e:
            logger.error(f"VLM query failed: {e}")
            return VLMResult(answer=f"Error: {e}", confidence=0.0)

    def detect(self, image: np.ndarray, object_desc: str) -> list[dict]:
        """Detect objects matching a description, returning bounding boxes.

        Args:
            image: Input image as numpy array (RGB).
            object_desc: Description of object to detect.

        Returns:
            List of detections with bounding boxes (normalized 0-1 coordinates).
        """
        if not self.model:
            return []

        start = time.perf_counter()
        pil_image = self._to_pil(image)

        try:
            encoded = self.model.encode_image(pil_image)
            result = self.model.detect(encoded, object_desc)
            elapsed_ms = (time.perf_counter() - start) * 1000

            detections = []
            for obj in result.get("objects", []):
                detections.append({
                    "label": object_desc,
                    "confidence": 1.0,
                    "description": object_desc,
                    "bbox": [
                        obj["x_min"],
                        obj["y_min"],
                        obj["x_max"],
                        obj["y_max"],
                    ],
                })

            logger.info(f"VLM detected {len(detections)} '{object_desc}' in {elapsed_ms:.0f}ms")
            return detections
        except Exception as e:
            logger.error(f"VLM detect failed: {e}")
            return []

    def ocr(self, image: np.ndarray, region: Optional[list[int]] = None) -> str:
        """Extract text from an image or a specific region.

        Uses VLM query since the moondream package has no dedicated OCR method.

        Args:
            image: Input image as numpy array (RGB).
            region: Optional [x1, y1, x2, y2] pixel crop region.

        Returns:
            Extracted text string.
        """
        if not self.model:
            return ""

        start = time.perf_counter()

        # Crop to region if specified
        if region:
            x1, y1, x2, y2 = region
            image = image[y1:y2, x1:x2]

        pil_image = self._to_pil(image)

        try:
            encoded = self.model.encode_image(pil_image)
            result = self.model.query(
                encoded,
                "Read all the text in this image. Return only the text, nothing else.",
            )
            text = result["answer"]
            elapsed_ms = (time.perf_counter() - start) * 1000

            logger.info(f"VLM OCR extracted '{text[:50]}...' in {elapsed_ms:.0f}ms")
            return text.strip()
        except Exception as e:
            logger.error(f"VLM OCR failed: {e}")
            return ""


def get_vlm(model_path: str = VLM_MODEL_PATH) -> MoondreamVLM:
    """Get or create singleton VLM instance."""
    global _vlm_instance
    if _vlm_instance is None:
        _vlm_instance = MoondreamVLM(model_path=model_path)
    return _vlm_instance
