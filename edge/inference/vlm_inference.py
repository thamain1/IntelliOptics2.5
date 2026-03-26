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
        self.tokenizer = None
        self._load_model()

    def _load_model(self) -> None:
        """Load Moondream model via HuggingFace transformers."""
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer

            model_id = self.MODEL_IDS.get(self.model_size, "vikhyatk/moondream2")
            revision = "2024-08-26"
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
            dtype = torch.float16 if use_cuda else torch.float32
            device = "cuda" if use_cuda else "cpu"

            self.tokenizer = AutoTokenizer.from_pretrained(
                model_id, revision=revision, trust_remote_code=True, cache_dir=VLM_CACHE_DIR
            )
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
            enc_image = self.model.encode_image(pil_image)
            answer = self.model.answer_question(enc_image, question, self.tokenizer)
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
        if not self.model:
            return []

        start = time.perf_counter()
        pil_image = self._to_pil(image)

        try:
            enc_image = self.model.encode_image(pil_image)

            # First check if object is present
            presence = self.model.answer_question(
                enc_image,
                f"Is there a {object_desc} in this image? Answer only yes or no.",
                self.tokenizer,
            )

            if "yes" not in presence.lower():
                elapsed_ms = (time.perf_counter() - start) * 1000
                logger.info(f"VLM: no '{object_desc}' found in {elapsed_ms:.0f}ms")
                return []

            # Get bounding box coordinates
            bbox_answer = self.model.answer_question(
                enc_image,
                f"Give the bounding box of the {object_desc} as normalized coordinates [left, top, right, bottom] where each value is between 0.0 and 1.0. Return only the coordinates in format [x1, y1, x2, y2].",
                self.tokenizer,
            )

            elapsed_ms = (time.perf_counter() - start) * 1000

            # Parse bbox from response
            bbox = self._parse_bbox(bbox_answer)

            detections = [
                {
                    "label": object_desc,
                    "confidence": 0.85,
                    "description": f"VLM detected {object_desc}",
                    "bbox": bbox,
                }
            ]

            logger.info(f"VLM detected '{object_desc}' bbox={bbox} in {elapsed_ms:.0f}ms")
            return detections
        except Exception as e:
            logger.error(f"VLM detect failed: {e}")
            return []

    @staticmethod
    def _parse_bbox(text: str) -> list[float]:
        """Parse bounding box coordinates from VLM text response.

        Attempts to extract 4 float values from text like '[0.1, 0.2, 0.8, 0.9]'.
        Falls back to full-frame [0, 0, 1, 1] if parsing fails.
        """
        import re
        numbers = re.findall(r'(\d+\.?\d*)', text)
        if len(numbers) >= 4:
            coords = [float(n) for n in numbers[:4]]
            # Validate: all values should be 0-1 range
            if all(0 <= c <= 1.0 for c in coords):
                # Ensure x1 < x2 and y1 < y2
                x1, y1, x2, y2 = coords
                if x1 > x2:
                    x1, x2 = x2, x1
                if y1 > y2:
                    y1, y2 = y2, y1
                # Ensure box has some area
                if x2 - x1 > 0.01 and y2 - y1 > 0.01:
                    return [x1, y1, x2, y2]
        return [0, 0, 1, 1]

    def ocr(self, image: np.ndarray, region: Optional[list[int]] = None) -> str:
        """Extract text from an image or a specific region.

        Args:
            image: Input image as numpy array (RGB).
            region: Optional [x1, y1, x2, y2] pixel crop region.

        Returns:
            Extracted text string.
        """
        if not self.model:
            return ""

        start = time.perf_counter()

        if region:
            x1, y1, x2, y2 = region
            image = image[y1:y2, x1:x2]

        pil_image = self._to_pil(image)

        try:
            enc_image = self.model.encode_image(pil_image)
            text = self.model.answer_question(
                enc_image,
                "Read all the text in this image. Return only the text, nothing else.",
                self.tokenizer,
            )
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
