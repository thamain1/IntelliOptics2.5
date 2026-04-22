"""
IntelliOptics 2.5 - YOLOE Open-Vocabulary Inference (Pure ONNX Runtime)

Fixed-vocabulary ONNX detection with prompt-to-vocabulary matching.
No Ultralytics dependency at runtime — model exported via tools/export_onnx.py.
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import onnxruntime as ort

logger = logging.getLogger(__name__)

# Lazy-loaded model reference
_yoloe_model = None

# Default model directory (set via YOLOE_MODEL_DIR env or Docker volume)
DEFAULT_MODEL_DIR = os.getenv("YOLOE_MODEL_DIR", "/models/yoloworld")


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
    """YOLOE open-vocabulary object detection (pure ONNX Runtime).

    Uses a pre-exported ONNX model with a fixed ~300-class vocabulary.
    User prompts are matched to vocabulary entries at runtime via exact
    and fuzzy matching. For truly novel queries, the VLM "smart track"
    handles them separately.
    """

    def __init__(self, model_dir: str = DEFAULT_MODEL_DIR):
        self.model_dir = Path(model_dir)
        self.session: Optional[ort.InferenceSession] = None
        self.vocabulary: list[str] = []
        self.vocab_lower: dict[str, int] = {}  # lowercase vocab -> index
        self.input_name: str = ""
        self.num_classes: int = 0
        self._load_model()

    def _load_model(self) -> None:
        """Load ONNX model and vocabulary."""
        onnx_path = self.model_dir / "yolov8s-worldv2.onnx"
        vocab_path = self.model_dir / "vocabulary.json"

        if not onnx_path.exists():
            raise FileNotFoundError(
                f"ONNX model not found: {onnx_path}. "
                f"Run tools/export_onnx.py or rebuild the Docker image."
            )
        if not vocab_path.exists():
            raise FileNotFoundError(
                f"Vocabulary not found: {vocab_path}. "
                f"Run tools/export_onnx.py or rebuild the Docker image."
            )

        # Load vocabulary
        with open(vocab_path, "r") as f:
            self.vocabulary = json.load(f)
        self.vocab_lower = {v.lower(): i for i, v in enumerate(self.vocabulary)}
        self.num_classes = len(self.vocabulary)
        logger.info(f"Loaded vocabulary: {self.num_classes} classes")

        # Load ONNX session
        providers = ["CPUExecutionProvider"]
        if "CUDAExecutionProvider" in ort.get_available_providers():
            providers.insert(0, "CUDAExecutionProvider")
            logger.info("CUDA available - using GPU inference")

        so = ort.SessionOptions()
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        logger.info(f"Loading ONNX model: {onnx_path}")
        self.session = ort.InferenceSession(str(onnx_path), sess_options=so, providers=providers)
        self.input_name = self.session.get_inputs()[0].name

        # Log model info
        input_shape = self.session.get_inputs()[0].shape
        output_shape = self.session.get_outputs()[0].shape
        file_size_mb = onnx_path.stat().st_size / (1024 * 1024)
        logger.info(
            f"YOLOE model loaded: {file_size_mb:.1f}MB, "
            f"input={input_shape}, output={output_shape}, "
            f"providers={self.session.get_providers()}"
        )

    def _match_prompts(self, prompts: list[str]) -> dict[str, int]:
        """Match user prompts to vocabulary indices.

        Matching priority:
        1. Exact match (case-insensitive)
        2. Vocabulary word is a substring of the prompt ("red car" matches "car")
        3. Prompt is a substring of vocabulary word ("plate" matches "license plate")

        Returns:
            Dict mapping original prompt string -> vocabulary index.
            Prompts with no match are silently skipped (VLM handles novel queries).
        """
        matched: dict[str, int] = {}

        for prompt in prompts:
            p = prompt.lower().strip()
            if not p:
                continue

            # 1. Exact match
            if p in self.vocab_lower:
                matched[prompt] = self.vocab_lower[p]
                continue

            # 2. Find best substring match
            best_match: Optional[tuple[str, int]] = None
            best_len = 0

            for vocab_word, idx in self.vocab_lower.items():
                # Vocab word inside prompt: "red car" contains "car"
                if vocab_word in p and len(vocab_word) > best_len:
                    best_match = (vocab_word, idx)
                    best_len = len(vocab_word)
                # Prompt inside vocab word: "plate" inside "license plate"
                elif p in vocab_word and len(p) > best_len:
                    best_match = (vocab_word, idx)
                    best_len = len(p)

            if best_match:
                matched[prompt] = best_match[1]
                logger.debug(f"Fuzzy match: '{prompt}' -> '{self.vocabulary[best_match[1]]}' (idx {best_match[1]})")
            else:
                logger.warning(f"No vocabulary match for prompt: '{prompt}' (VLM will handle)")

        return matched

    @staticmethod
    def _letterbox(img: np.ndarray, new_shape: int = 640) -> tuple[np.ndarray, float, tuple[int, int]]:
        """Resize image with aspect ratio preservation (letterbox padding).

        Returns:
            resized: Letterboxed image (new_shape x new_shape x 3)
            ratio: Scaling ratio applied
            pad: (pad_w, pad_h) padding added
        """
        h, w = img.shape[:2]
        r = min(new_shape / h, new_shape / w)
        new_w, new_h = int(w * r), int(h * r)

        resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        pad_w = (new_shape - new_w) // 2
        pad_h = (new_shape - new_h) // 2

        # ── Item 7: black (0) padding matches ImageNet-trained model expectations
        padded = np.full((new_shape, new_shape, 3), 0, dtype=np.uint8)
        padded[pad_h : pad_h + new_h, pad_w : pad_w + new_w] = resized

        return padded, r, (pad_w, pad_h)

    def _preprocess(self, image: np.ndarray) -> tuple[np.ndarray, float, tuple[int, int]]:
        """Preprocess image for ONNX inference.

        Args:
            image: Input image (H, W, 3) uint8, RGB or BGR.

        Returns:
            tensor: (1, 3, 640, 640) float32 normalized to [0, 1]
            ratio: Letterbox scaling ratio
            pad: (pad_w, pad_h) letterbox padding
        """
        letterboxed, ratio, pad = self._letterbox(image, 640)

        # Normalize to [0, 1] and convert HWC -> CHW
        tensor = letterboxed.astype(np.float32) / 255.0
        tensor = np.transpose(tensor, (2, 0, 1))  # HWC -> CHW
        tensor = np.expand_dims(tensor, axis=0)  # Add batch dim

        return tensor, ratio, pad

    @staticmethod
    def _iou(box1: list[float], box2: list[float]) -> float:
        """Calculate Intersection over Union between two boxes [x1, y1, x2, y2]."""
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])

        if x2 <= x1 or y2 <= y1:
            return 0.0

        intersection = (x2 - x1) * (y2 - y1)
        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union = area1 + area2 - intersection

        return intersection / union if union > 0 else 0.0

    @staticmethod
    def _nms(detections: list[Detection], iou_threshold: float) -> list[Detection]:
        """Non-Maximum Suppression on Detection objects."""
        if not detections:
            return []

        sorted_dets = sorted(detections, key=lambda d: d.confidence, reverse=True)
        keep: list[Detection] = []

        while sorted_dets:
            best = sorted_dets.pop(0)
            keep.append(best)
            sorted_dets = [
                d for d in sorted_dets
                if YOLOEInference._iou(best.bbox, d.bbox) < iou_threshold
            ]

        return keep

    def _postprocess(
        self,
        output: np.ndarray,
        ratio: float,
        pad: tuple[int, int],
        orig_shape: tuple[int, ...],
        target_indices: dict[str, int],
        prompts: list[str],
        conf: float,
        iou: float,
    ) -> list[Detection]:
        """Postprocess ONNX output to Detection objects.

        Args:
            output: Raw ONNX output, shape (1, 4+N, 8400) or (1, 8400, 4+N)
            ratio: Letterbox scaling ratio
            pad: (pad_w, pad_h)
            orig_shape: Original image shape (H, W, ...)
            target_indices: Dict of prompt -> vocab index (from _match_prompts)
            prompts: Original user prompts
            conf: Confidence threshold
            iou: NMS IoU threshold

        Returns:
            List of Detection objects with pixel-space bboxes.
        """
        orig_h, orig_w = orig_shape[:2]
        pad_w, pad_h = pad

        # Build set of target class indices for filtering
        target_set = set(target_indices.values()) if target_indices else None

        # Build reverse map: vocab_index -> user prompt label
        idx_to_label: dict[int, str] = {}
        for prompt, idx in target_indices.items():
            idx_to_label[idx] = prompt

        # Parse output shape: YOLO-World v2 ONNX outputs (1, 4+N, 8400)
        pred = output[0]  # Remove batch dim -> (4+N, 8400) or (8400, 4+N)

        # Determine if we need to transpose
        # If shape is (4+N, 8400) where 4+N < 8400, transpose to (8400, 4+N)
        if pred.shape[0] < pred.shape[1]:
            pred = pred.T  # -> (8400, 4+N)

        num_boxes = pred.shape[0]
        num_cols = pred.shape[1]
        nc = num_cols - 4  # number of classes

        if nc <= 0:
            logger.warning(f"Unexpected output shape: {output.shape}, nc={nc}")
            return []

        # Extract boxes and scores
        boxes_cxcywh = pred[:, :4]  # (8400, 4) - cx, cy, w, h in 640-space
        scores = pred[:, 4:]  # (8400, N) - per-class confidence

        # Get best class per box
        class_ids = np.argmax(scores, axis=1)  # (8400,)
        max_scores = np.max(scores, axis=1)  # (8400,)

        # Filter by confidence
        conf_mask = max_scores >= conf
        if not np.any(conf_mask):
            return []

        boxes_cxcywh = boxes_cxcywh[conf_mask]
        class_ids = class_ids[conf_mask]
        max_scores = max_scores[conf_mask]

        # Filter by target vocabulary indices (only return requested classes)
        if target_set is not None:
            target_mask = np.array([cid in target_set for cid in class_ids])
            if not np.any(target_mask):
                return []
            boxes_cxcywh = boxes_cxcywh[target_mask]
            class_ids = class_ids[target_mask]
            max_scores = max_scores[target_mask]

        # Convert cx, cy, w, h -> x1, y1, x2, y2 (still in 640-space)
        cx, cy, w, h = boxes_cxcywh[:, 0], boxes_cxcywh[:, 1], boxes_cxcywh[:, 2], boxes_cxcywh[:, 3]
        x1 = cx - w / 2
        y1 = cy - h / 2
        x2 = cx + w / 2
        y2 = cy + h / 2

        # Reverse letterbox: subtract padding, divide by ratio
        x1 = (x1 - pad_w) / ratio
        y1 = (y1 - pad_h) / ratio
        x2 = (x2 - pad_w) / ratio
        y2 = (y2 - pad_h) / ratio

        # Clip to image bounds
        x1 = np.clip(x1, 0, orig_w)
        y1 = np.clip(y1, 0, orig_h)
        x2 = np.clip(x2, 0, orig_w)
        y2 = np.clip(y2, 0, orig_h)

        # Build Detection objects
        detections: list[Detection] = []
        for i in range(len(x1)):
            cid = int(class_ids[i])

            # Use the user's original prompt as label if available,
            # otherwise fall back to vocabulary name
            if cid in idx_to_label:
                label = idx_to_label[cid]
            elif cid < len(self.vocabulary):
                label = self.vocabulary[cid]
            else:
                label = f"class_{cid}"

            detections.append(
                Detection(
                    label=label,
                    confidence=float(max_scores[i]),
                    bbox=[float(x1[i]), float(y1[i]), float(x2[i]), float(y2[i])],
                )
            )

        # Apply NMS
        detections = self._nms(detections, iou)

        return detections

    def detect(
        self,
        image: np.ndarray,
        prompts: list[str],
        conf: float = 0.25,
        iou: float = 0.45,
    ) -> list[Detection]:
        """Run open-vocabulary detection with dynamic text prompts.

        Args:
            image: Input image as numpy array (H, W, 3), BGR or RGB.
            prompts: List of text prompts describing objects to detect.
            conf: Confidence threshold.
            iou: NMS IoU threshold.

        Returns:
            List of Detection objects with labels, confidence, and pixel-space bboxes.
        """
        if self.session is None:
            raise RuntimeError("ONNX model not loaded")

        start = time.perf_counter()

        # Match prompts to vocabulary
        target_indices = self._match_prompts(prompts)

        if not target_indices:
            logger.info(f"No vocabulary matches for prompts {prompts} — returning empty")
            return []

        # Preprocess
        tensor, ratio, pad = self._preprocess(image)

        # Run ONNX inference
        output = self.session.run(None, {self.input_name: tensor})[0]

        # Postprocess
        detections = self._postprocess(
            output, ratio, pad, image.shape,
            target_indices, prompts, conf, iou,
        )

        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(f"YOLOE detected {len(detections)} objects in {elapsed_ms:.0f}ms (prompts: {list(target_indices.keys())})")

        return detections

    def detect_tiled(
        self,
        image: np.ndarray,
        prompts: list[str],
        conf: float = 0.25,
        iou: float = 0.45,
        grid: tuple[int, int] = (2, 2),
    ) -> list[Detection]:
        """Run detect() on a grid of tiles and merge with NMS.
        Improves multi-instance detection in overhead/aerial views.
        """
        h, w = image.shape[:2]
        rows, cols = grid
        tile_h, tile_w = h // rows, w // cols
        all_detections: list[Detection] = []

        for r in range(rows):
            for c in range(cols):
                y1, x1 = r * tile_h, c * tile_w
                y2, x2 = (r + 1) * tile_h, (c + 1) * tile_w
                tile = image[y1:y2, x1:x2]
                tile_dets = self.detect(tile, prompts, conf=conf, iou=iou)
                for d in tile_dets:
                    # Translate bbox back to full-image pixel coordinates
                    all_detections.append(Detection(
                        label=d.label,
                        confidence=d.confidence,
                        bbox=[
                            d.bbox[0] + x1,
                            d.bbox[1] + y1,
                            d.bbox[2] + x1,
                            d.bbox[3] + y1,
                        ],
                    ))

        # Cross-tile NMS — use a lower threshold than intra-tile NMS so that
        # partial views of the same object at tile boundaries are merged.
        return YOLOEInference._nms(all_detections, 0.3)

    def get_vocabulary(self) -> list[str]:
        """Return the full vocabulary list."""
        return list(self.vocabulary)


def get_yoloe_model(model_dir: str = DEFAULT_MODEL_DIR) -> YOLOEInference:
    """Get or create singleton YOLOE inference instance."""
    global _yoloe_model
    if _yoloe_model is None:
        _yoloe_model = YOLOEInference(model_dir=model_dir)
    return _yoloe_model
