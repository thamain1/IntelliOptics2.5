"""
IntelliOptics 2.5 - Moondream VLM Inference
Visual Language Model for natural language queries, object detection, and OCR.
Uses HuggingFace transformers to load Moondream2 locally (no cloud API).
"""

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Persist HuggingFace model downloads to the Docker volume so they survive restarts
VLM_CACHE_DIR = os.getenv("VLM_CACHE_DIR", "/vlm-models")
os.environ.setdefault("HF_HOME", VLM_CACHE_DIR)
os.environ.setdefault("TRANSFORMERS_CACHE", os.path.join(VLM_CACHE_DIR, "transformers"))

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

    Uses HuggingFace transformers to load vikhyatk/moondream2 locally.

    Supports:
    - Visual Q&A (ask questions about an image)
    - Object detection with bounding boxes
    - OCR (text extraction from images or regions)
    """

    MODEL_IDS = {
        "0.5B": "vikhyatk/moondream2",
        "2B": "vikhyatk/moondream2",
    }

    def __init__(self, model_size: str = "2B"):
        self.model_size = model_size
        self.model = None
        self._load_model()

    def _load_model(self) -> None:
        """Load Moondream model via HuggingFace transformers."""
        try:
            import torch
            from transformers import AutoModelForCausalLM

            model_id = self.MODEL_IDS.get(self.model_size, "vikhyatk/moondream2")
            revision = "2025-06-21"
            logger.info(f"Loading IO-VLM ({self.model_size}) from {model_id} rev={revision}...")

            # Check CUDA availability AND compute capability (>= 7.0 for modern PyTorch)
            use_cuda = False
            if torch.cuda.is_available():
                try:
                    cap = torch.cuda.get_device_capability(0)
                    use_cuda = cap[0] >= 7
                    if not use_cuda:
                        logger.warning(
                            f"GPU compute capability {cap[0]}.{cap[1]} < 7.0. Falling back to CPU."
                        )
                except Exception:
                    pass
            dtype = torch.bfloat16 if use_cuda else torch.float32
            device = "cuda" if use_cuda else "cpu"

            # Maximize CPU parallelism when running on CPU
            if not use_cuda:
                cpu_threads = os.cpu_count() or 4
                torch.set_num_threads(cpu_threads)
                logger.info(f"VLM will use {cpu_threads} CPU threads (float32)")

            self.model = AutoModelForCausalLM.from_pretrained(
                model_id,
                revision=revision,
                trust_remote_code=True,
                torch_dtype=dtype,
                cache_dir=VLM_CACHE_DIR,
            ).to(device)

            logger.info(f"IO-VLM loaded successfully on {device} ({dtype})")
        except ImportError as e:
            logger.warning(f"transformers not installed, VLM features disabled: {e}")
            self.model = None
        except Exception as e:
            logger.error(f"Failed to load Moondream VLM: {e}")
            self.model = None

    # Moondream internally resizes to 729×729; sending full-res frames just
    # wastes CPU time in the vision encoder preprocessing.  Cap the longest
    # edge so we stay close to native resolution without blowing up latency.
    _MAX_EDGE = 768

    def _to_pil(self, image: np.ndarray) -> Image.Image:
        """Convert numpy array to PIL Image, downscaling if oversized."""
        if image.dtype != np.uint8:
            image = (image * 255).astype(np.uint8)
        pil = Image.fromarray(image)
        w, h = pil.size
        if max(w, h) > self._MAX_EDGE:
            scale = self._MAX_EDGE / max(w, h)
            pil = pil.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        return pil

    def query(self, image: np.ndarray, question: str) -> VLMResult:
        """Ask a natural language question about an image.

        Args:
            image: Input image as numpy array (RGB).
            question: Natural language question.

        Returns:
            VLMResult with answer text.
        """
        if self.model is None:
            return VLMResult(answer="VLM not available", confidence=0.0)

        start = time.perf_counter()
        pil_image = self._to_pil(image)

        try:
            answer = self.model.query(pil_image, question)["answer"]
            elapsed_ms = (time.perf_counter() - start) * 1000

            logger.info(f"VLM query '{question[:50]}...' answered in {elapsed_ms:.0f}ms")
            return VLMResult(answer=answer, confidence=1.0, latency_ms=elapsed_ms)
        except Exception as e:
            logger.error(f"VLM query failed: {e}")
            return VLMResult(answer=f"Error: {e}", confidence=0.0)

    def detect(self, image: np.ndarray, object_desc: str) -> list[dict]:
        """Detect objects matching a description, returning bounding boxes.

        Uses VLM to first confirm presence, then estimate bounding box coordinates.

        Args:
            image: Input image as numpy array (RGB).
            object_desc: Description of object to detect.

        Returns:
            List of detections with normalized bounding boxes [x1, y1, x2, y2] (0-1).
        """
        if self.model is None:
            return []

        start = time.perf_counter()
        pil_image = self._to_pil(image)

        try:
            result = self.model.detect(pil_image, object_desc)
            elapsed_ms = (time.perf_counter() - start) * 1000

            objects = result.get("objects", [])
            if not objects:
                logger.info(f"VLM: no '{object_desc}' found in {elapsed_ms:.0f}ms")
                return []

            detections = []
            for obj in objects:
                bbox = [obj["x_min"], obj["y_min"], obj["x_max"], obj["y_max"]]
                detections.append(
                    {
                        "label": object_desc,
                        "confidence": 0.85,
                        "description": f"VLM detected {object_desc}",
                        "bbox": bbox,
                    }
                )

            logger.info(
                f"VLM detected {len(detections)} '{object_desc}' in {elapsed_ms:.0f}ms"
            )
            return detections
        except Exception as e:
            logger.error(f"VLM detect failed: {e}")
            return []

    def validate_crop(self, image: np.ndarray, label: str, bbox_pixels: list[float]) -> float:
        """Ask VLM whether a YOLOE detection crop actually contains the labeled object.

        Returns ~0.85 if VLM confirms, ~0.1 if VLM rejects, 0.5 (neutral) on error
        or when VLM is unavailable so the caller never drops on a failed check.
        """
        if self.model is None:
            return 0.5

        try:
            x1, y1, x2, y2 = (int(v) for v in bbox_pixels)
            h, w = image.shape[:2]
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)

            if x2 <= x1 or y2 <= y1:
                return 0.5

            crop = image[y1:y2, x1:x2]
            pil_crop = self._to_pil(crop)

            start = time.perf_counter()
            answer = self.model.query(pil_crop, f"Is this a {label}? Answer yes or no.")["answer"]
            elapsed_ms = (time.perf_counter() - start) * 1000

            confirmed = answer.strip().lower().startswith("yes")
            vlm_conf = 0.85 if confirmed else 0.1
            logger.info(f"VLM validate '{label}': '{answer.strip()[:20]}' → {vlm_conf} ({elapsed_ms:.0f}ms)")
            return vlm_conf
        except Exception as e:
            logger.warning(f"VLM validate_crop failed: {e}")
            return 0.5

    def ocr(self, image: np.ndarray, region: Optional[list[int]] = None) -> str:
        """Extract text from an image or a specific region.

        Args:
            image: Input image as numpy array (RGB).
            region: Optional [x1, y1, x2, y2] pixel crop region.

        Returns:
            Extracted text string.
        """
        if self.model is None:
            return ""

        start = time.perf_counter()

        if region:
            x1, y1, x2, y2 = region
            image = image[y1:y2, x1:x2]

        pil_image = self._to_pil(image)

        try:
            text = self.model.query(
                pil_image,
                "Read all the text in this image. Return only the text, nothing else.",
            )["answer"]
            elapsed_ms = (time.perf_counter() - start) * 1000

            logger.info(f"VLM OCR extracted '{text[:50]}...' in {elapsed_ms:.0f}ms")
            return text.strip()
        except Exception as e:
            logger.error(f"VLM OCR failed: {e}")
            return ""


def get_vlm(model_size: str = "2B") -> MoondreamVLM:
    """Get or create singleton VLM instance."""
    global _vlm_instance
    if _vlm_instance is None:
        _vlm_instance = MoondreamVLM(model_size=model_size)
    return _vlm_instance
