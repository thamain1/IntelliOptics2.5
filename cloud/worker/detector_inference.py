#!/usr/bin/env python3
"""
Detector-Aware Inference System for IntelliOptics
Handles per-detector model caching, Primary + OODD inference, and detector-specific configuration
"""
import os
import json
import logging
import hashlib
from typing import Dict, Any, Optional, Tuple
from pathlib import Path

import numpy as np
import onnxruntime as ort
import cv2
try:
    from azure.storage.blob import BlobServiceClient
    HAS_AZURE_BLOB = True
except ImportError:
    HAS_AZURE_BLOB = False

log = logging.getLogger("detector-inference")

# Model cache directory
MODEL_CACHE_DIR = Path(os.getenv("MODEL_CACHE_DIR", "/app/models"))
MODEL_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Azure connection
AZ_CONN_STR = os.getenv("AZURE_STORAGE_CONNECTION_STRING")


class ModelCache:
    """
    LRU cache for ONNX models per detector
    Keeps models in memory to avoid reloading from disk
    """
    def __init__(self, max_models=5):
        self.cache: Dict[str, ort.InferenceSession] = {}
        self.access_count: Dict[str, int] = {}
        self.max_models = max_models

    def get(self, key: str) -> Optional[ort.InferenceSession]:
        """Get model from cache"""
        if key in self.cache:
            self.access_count[key] += 1
            log.debug(f"Model cache HIT for {key}")
            return self.cache[key]
        log.debug(f"Model cache MISS for {key}")
        return None

    def put(self, key: str, session: ort.InferenceSession):
        """Add model to cache with LRU eviction"""
        # Evict least recently used if cache is full
        if len(self.cache) >= self.max_models and key not in self.cache:
            lru_key = min(self.access_count, key=self.access_count.get)
            log.info(f"Evicting model from cache: {lru_key}")
            del self.cache[lru_key]
            del self.access_count[lru_key]

        self.cache[key] = session
        self.access_count[key] = 1
        log.info(f"Added model to cache: {key} (cache size: {len(self.cache)})")


# Global model cache
_model_cache = ModelCache(max_models=10)  # Can cache 5 detectors (Primary + OODD each)


def download_model_from_blob(blob_path: str, detector_id: str, model_type: str) -> Path:
    """
    Download model from Azure Blob Storage and cache locally

    Args:
        blob_path: Path in blob storage (e.g., "models/detector_123/primary/1/model.onnx")
        detector_id: Detector UUID
        model_type: "primary" or "oodd"

    Returns:
        Path to downloaded model file
    """
    if not AZ_CONN_STR:
        raise ValueError("AZURE_STORAGE_CONNECTION_STRING not configured")

    # Create local cache path: /app/models/{detector_id}/{model_type}/model.onnx
    local_dir = MODEL_CACHE_DIR / detector_id / model_type
    local_dir.mkdir(parents=True, exist_ok=True)
    local_path = local_dir / "model.onnx"

    # Check if already cached AND file is not empty (empty = failed download)
    if local_path.exists():
        file_size = local_path.stat().st_size
        if file_size > 0:
            log.info(f"Model already cached: {local_path} ({file_size / (1024*1024):.2f} MB)")
            return local_path
        else:
            log.warning(f"Found empty/corrupt model cache, re-downloading: {local_path}")
            local_path.unlink()  # Delete empty file

    log.info(f"Downloading model from blob: {blob_path}")

    # Download to temp file first, then move on success
    temp_path = local_path.with_suffix(".onnx.tmp")

    try:
        # Parse blob path to get container and blob name
        container_name = "models"
        blob_name = blob_path.replace("models/", "", 1) if blob_path.startswith("models/") else blob_path

        # Try Supabase Storage via HTTP first
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        if supabase_url and supabase_key:
            import httpx
            dl_url = f"{supabase_url}/storage/v1/object/{container_name}/{blob_name}"
            headers = {"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"}
            resp = httpx.get(dl_url, headers=headers, timeout=60.0)
            resp.raise_for_status()
            with open(temp_path, "wb") as f:
                f.write(resp.content)
        elif HAS_AZURE_BLOB and AZ_CONN_STR and AZ_CONN_STR != "DISABLED":
            # Azure fallback
            if blob_path.startswith("http"):
                from azure.storage.blob import BlobClient
                blob_client = BlobClient.from_connection_string(
                    AZ_CONN_STR, container_name=container_name,
                    blob_name=blob_path.split("/models/")[-1] if "/models/" in blob_path else blob_path
                )
            else:
                blob_service = BlobServiceClient.from_connection_string(AZ_CONN_STR)
                blob_client = blob_service.get_blob_client(container=container_name, blob=blob_name)
            with open(temp_path, "wb") as f:
                download_stream = blob_client.download_blob()
                f.write(download_stream.readall())
        else:
            raise RuntimeError("No storage backend configured (set SUPABASE_URL + SUPABASE_SERVICE_KEY)")

        # Verify download succeeded (non-empty file)
        file_size = temp_path.stat().st_size
        if file_size == 0:
            temp_path.unlink()
            raise ValueError(f"Downloaded file is empty - model may not exist in blob storage: {blob_path}")

        # Move temp to final location
        temp_path.rename(local_path)

        file_size_mb = file_size / (1024 * 1024)
        log.info(f"Downloaded model: {local_path} ({file_size_mb:.2f} MB)")
        return local_path

    except Exception as e:
        # Clean up temp file on failure
        if temp_path.exists():
            temp_path.unlink()
        log.error(f"Failed to download model from {blob_path}: {e}")
        raise


def load_onnx_model(model_path: Path, cache_key: str) -> ort.InferenceSession:
    """
    Load ONNX model from path with caching

    Args:
        model_path: Path to ONNX model file
        cache_key: Unique key for caching (e.g., "{detector_id}_primary")

    Returns:
        ONNX Runtime inference session
    """
    # Check cache first
    cached = _model_cache.get(cache_key)
    if cached:
        return cached

    # Load from disk
    log.info(f"Loading ONNX model: {model_path}")
    so = ort.SessionOptions()
    so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

    providers = ["CPUExecutionProvider"]
    # Try GPU if available
    if "CUDAExecutionProvider" in ort.get_available_providers():
        providers.insert(0, "CUDAExecutionProvider")

    session = ort.InferenceSession(str(model_path), sess_options=so, providers=providers)

    # Cache the session
    _model_cache.put(cache_key, session)

    return session


def letterbox(img: np.ndarray, new_shape: int = 640) -> Tuple[np.ndarray, float, Tuple[int, int]]:
    """
    Resize image with aspect ratio preservation (letterbox padding)

    Returns:
        resized_img: Letterboxed image
        ratio: Scaling ratio
        pad: (pad_w, pad_h) padding added
    """
    h, w = img.shape[:2]
    r = min(new_shape / h, new_shape / w)
    new_w, new_h = int(w * r), int(h * r)

    resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    # Add padding
    pad_w = (new_shape - new_w) // 2
    pad_h = (new_shape - new_h) // 2

    # ── Item 7: black (0) padding matches ImageNet-trained model expectations
    padded = np.full((new_shape, new_shape, 3), 0, dtype=np.uint8)
    padded[pad_h:pad_h + new_h, pad_w:pad_w + new_w] = resized

    return padded, r, (pad_w, pad_h)


def run_oodd_inference(
    session: ort.InferenceSession,
    rgb_image: np.ndarray,
    calibrated_threshold: float = 0.444
) -> Dict[str, Any]:
    """
    Run OODD (Out-of-Domain Detection) inference

    Returns:
        {
            "in_domain_score": float,  # 0.0 to 1.0
            "is_in_domain": bool,
            "confidence_adjustment": float  # Multiplier for primary confidence
        }
    """
    # Preprocess for ResNet (OODD model is ResNet18)
    # Resize to 224x224 (standard ImageNet size)
    img = cv2.resize(rgb_image, (224, 224))

    # Normalize (ImageNet stats)
    img = img.astype(np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    img = (img - mean) / std

    # NCHW format
    img = np.transpose(img, (2, 0, 1))[None, ...]

    # Run inference
    input_name = session.get_inputs()[0].name
    outputs = session.run(None, {input_name: img})

    # OODD output: ResNet models output raw logits, not probabilities
    # Need to apply softmax/sigmoid to convert to [0, 1] range
    output = outputs[0][0]

    if len(output) == 2:
        # Binary classification: [OOD, in-domain] - apply softmax
        # Softmax: exp(x) / sum(exp(x))
        exp_output = np.exp(output - np.max(output))  # Subtract max for numerical stability
        softmax_output = exp_output / np.sum(exp_output)
        in_domain_score = float(softmax_output[1])
    else:
        # Single value (logit) - apply sigmoid: 1 / (1 + exp(-x))
        in_domain_score = float(1.0 / (1.0 + np.exp(-output[0])))

    # Clamp to [0, 1] range just in case
    in_domain_score = max(0.0, min(1.0, in_domain_score))

    is_in_domain = in_domain_score >= calibrated_threshold

    # Confidence adjustment: reduce primary confidence if out-of-domain
    # in_domain_score is now guaranteed to be in [0, 1]
    confidence_adjustment = in_domain_score if is_in_domain else in_domain_score * 0.5

    return {
        "in_domain_score": in_domain_score,
        "is_in_domain": is_in_domain,
        "confidence_adjustment": confidence_adjustment,
        "calibrated_threshold": calibrated_threshold
    }


def run_detector_inference(
    detector_id: str,
    detector_config: Dict[str, Any],
    image_bytes: bytes
) -> Dict[str, Any]:
    """
    Run full detector inference with Primary + OODD models and detector-specific configuration

    Args:
        detector_id: Detector UUID
        detector_config: Full detector configuration from database
        image_bytes: Raw image bytes

    Returns:
        {
            "detections": [...],
            "latency_ms": int,
            "oodd_result": {...},
            "model_info": {...}
        }
    """
    import time
    start_time = time.perf_counter()

    # Extract configuration
    primary_blob_path = detector_config.get("primary_model_blob_path")
    oodd_blob_path = detector_config.get("oodd_model_blob_path")
    model_input_config = detector_config.get("model_input_config") or {}
    model_output_config = detector_config.get("model_output_config") or {}
    detection_params = detector_config.get("detection_params") or {}
    class_names = detector_config.get("class_names") or []
    confidence_threshold = detector_config.get("confidence_threshold", 0.5)
    per_class_thresholds = detector_config.get("per_class_thresholds") or {}
    mode = detector_config.get("mode", "BOUNDING_BOX")
    # ── Item 6: OODD Per-Detector Threshold ─────────────────────────────────
    # Falls back to 0.444 if not set — preserves existing behaviour for
    # detectors that haven't been individually calibrated yet.
    oodd_calibrated_threshold = float(detector_config.get("oodd_calibrated_threshold") or 0.444)

    if not primary_blob_path:
        raise ValueError(f"No primary_model_blob_path configured for detector {detector_id}")

    # Download and load Primary model
    log.info(f"Loading Primary model for detector {detector_id}")
    primary_model_path = download_model_from_blob(primary_blob_path, detector_id, "primary")
    primary_session = load_onnx_model(primary_model_path, f"{detector_id}_primary")

    # Download and load OODD model (if configured)
    oodd_result = None
    if oodd_blob_path:
        log.info(f"Loading OODD model for detector {detector_id}")
        try:
            oodd_model_path = download_model_from_blob(oodd_blob_path, detector_id, "oodd")
            oodd_session = load_onnx_model(oodd_model_path, f"{detector_id}_oodd")
        except Exception as e:
            log.warning(f"Failed to load OODD model: {e}, continuing without OODD")
            oodd_session = None
    else:
        oodd_session = None

    # Decode image
    img_array = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Failed to decode image")

    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    orig_h, orig_w = rgb.shape[:2]

    # Run OODD inference first (if available)
    if oodd_session:
        # ── Item 6: pass per-detector threshold instead of hardcoded 0.444 ──
        oodd_result = run_oodd_inference(oodd_session, rgb, calibrated_threshold=oodd_calibrated_threshold)
        log.info(f"OODD result: in_domain={oodd_result['is_in_domain']}, score={oodd_result['in_domain_score']:.3f}, threshold={oodd_calibrated_threshold}")

    # Preprocess using model_input_config
    input_size = model_input_config.get("input_width", 640)  # Default to 640
    letterboxed, ratio, pad = letterbox(rgb, input_size)

    # Normalize
    x = letterboxed.astype(np.float32) / 255.0
    x = np.transpose(x, (2, 0, 1))[None, ...]  # NCHW

    # Run Primary inference
    input_name = primary_session.get_inputs()[0].name
    outputs = primary_session.run(None, {input_name: x})
    pred = outputs[0]

    # Post-process detections (YOLO format)
    # Use a lower detection threshold (default 0.25) to allow model to return all reasonable detections
    # The confidence_threshold is for escalation decisions, not detection filtering
    detection_conf_thresh = detection_params.get("min_score_threshold", 0.25)
    log.info(f"Running YOLO post-processing with conf_thresh={detection_conf_thresh}")

    detections = postprocess_yolo(
        pred, ratio, pad, (orig_w, orig_h),
        conf_thresh=detection_conf_thresh,
        iou_thresh=detection_params.get("iou_threshold", 0.45),
        max_det=detection_params.get("max_detections", 100),
        custom_class_names=class_names if class_names else None
    )

    log.info(f"Raw detections from model: {len(detections)}")

    # Apply OODD confidence adjustment
    if oodd_result and not oodd_result["is_in_domain"]:
        for det in detections:
            det["confidence"] *= oodd_result["confidence_adjustment"]
            det["oodd_adjusted"] = True

    # Filter by class names (if specified)
    if class_names:
        log.info(f"Filtering by class_names={class_names}")
        before_count = len(detections)
        detections = [d for d in detections if d.get("label") in class_names]
        log.info(f"After class filtering: {len(detections)}/{before_count} detections kept")
    else:
        log.info(f"No class filtering applied (class_names is empty)")

    # Apply per-class thresholds
    if per_class_thresholds:
        filtered = []
        for det in detections:
            class_label = det.get("label")
            threshold = per_class_thresholds.get(class_label, confidence_threshold)
            if det["confidence"] >= threshold:
                filtered.append(det)
        detections = filtered

    latency_ms = int((time.perf_counter() - start_time) * 1000)

    # ── Item 6: surface oodd_score at top level for drift tracking ──────────
    oodd_score = oodd_result.get("in_domain_score") if oodd_result else None

    return {
        "detections": detections,
        "latency_ms": latency_ms,
        "oodd_result": oodd_result,
        "oodd_score": oodd_score,
        "model_info": {
            "primary_model": primary_blob_path,
            "oodd_model": oodd_blob_path,
            "mode": mode,
            "input_size": input_size
        }
    }


def postprocess_yolo(
    pred: np.ndarray,
    ratio: float,
    pad: Tuple[int, int],
    original_size: Tuple[int, int],
    conf_thresh: float = 0.5,
    iou_thresh: float = 0.45,
    max_det: int = 100,
    custom_class_names: list = None
) -> list:
    """
    Post-process YOLO output with NMS

    Args:
        pred: YOLO output tensor
        ratio: Letterbox scaling ratio
        pad: (pad_w, pad_h)
        original_size: (width, height) of original image
        conf_thresh: Confidence threshold
        iou_thresh: IoU threshold for NMS
        max_det: Maximum detections to keep

    Returns:
        List of detections: [{"label": str, "confidence": float, "bbox": [x1,y1,x2,y2]}, ...]
    """
    # YOLO output formats:
    # Format 1: (1, N, 85) where 85 = [x, y, w, h, obj_conf, cls1, cls2, ..., cls80]
    # Format 2: (1, N, 6) where 6 = [x1, y1, x2, y2, conf, class_id]
    # Format 3: (1, 84, N) or (1, 4+nc, N)

    if len(pred.shape) == 3:
        if pred.shape[2] == 6:
            # Format 2: [x1, y1, x2, y2, conf, class_id]
            boxes = pred[0]
        elif pred.shape[1] in [84, 85]:
            # Format 3: Need to transpose
            boxes = pred[0].T
        else:
            # Format 1: [x, y, w, h, obj, cls...]
            boxes = pred[0]
    else:
        boxes = pred

    # Use custom class names if provided, otherwise fall back to COCO
    COCO_CLASSES = [
        "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
        "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
        "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack",
        "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball",
        "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket",
        "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
        "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair",
        "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote",
        "keyboard", "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator", "book",
        "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush"
    ]

    # Use custom class names for non-COCO models (e.g., fire detection)
    class_names_to_use = custom_class_names if custom_class_names else COCO_CLASSES
    log.info(f"Using class names: {class_names_to_use[:5]}{'...' if len(class_names_to_use) > 5 else ''}")

    detections = []
    total_boxes = len(boxes)
    log.info(f"YOLO post-processing: pred shape={pred.shape}, boxes shape={boxes.shape}, total boxes={total_boxes}")

    filtered_count = 0
    for box in boxes:
        if len(box) == 6:
            # [x1, y1, x2, y2, conf, class_id]
            x1, y1, x2, y2, conf, cls_id = box
            if conf < conf_thresh:
                filtered_count += 1
                continue
            label = class_names_to_use[int(cls_id)] if int(cls_id) < len(class_names_to_use) else f"class_{int(cls_id)}"
        else:
            # [x, y, w, h, obj_conf, cls1, cls2, ...]
            if len(box) < 85:
                continue
            x, y, w, h, obj_conf = box[:5]
            class_confs = box[5:]
            cls_id = int(np.argmax(class_confs))
            cls_conf = class_confs[cls_id]
            conf = obj_conf * cls_conf

            if conf < conf_thresh:
                filtered_count += 1
                continue

            # Convert xywh to xyxy
            x1 = x - w / 2
            y1 = y - h / 2
            x2 = x + w / 2
            y2 = y + h / 2

            label = class_names_to_use[cls_id] if cls_id < len(class_names_to_use) else f"class_{cls_id}"

        # Reverse letterbox transformation
        pad_w, pad_h = pad
        x1 = (x1 - pad_w) / ratio
        y1 = (y1 - pad_h) / ratio
        x2 = (x2 - pad_w) / ratio
        y2 = (y2 - pad_h) / ratio

        # Clip to image bounds
        orig_w, orig_h = original_size
        x1 = max(0, min(x1, orig_w))
        y1 = max(0, min(y1, orig_h))
        x2 = max(0, min(x2, orig_w))
        y2 = max(0, min(y2, orig_h))

        detections.append({
            "label": label,
            "confidence": float(conf),
            "bbox": [float(x1), float(y1), float(x2), float(y2)],
            "oodd_adjusted": False
        })

    # Apply NMS
    if len(detections) > 0:
        detections = nms(detections, iou_thresh)

    # Limit to max_det
    detections = detections[:max_det]

    log.info(f"YOLO post-processing complete: {len(detections)} detections kept, {filtered_count} filtered by confidence < {conf_thresh}")
    if detections:
        log.info(f"Sample detection: {detections[0]}")

    return detections


def nms(detections: list, iou_threshold: float = 0.45) -> list:
    """Non-Maximum Suppression"""
    if not detections:
        return []

    # Sort by confidence
    detections = sorted(detections, key=lambda x: x["confidence"], reverse=True)

    keep = []
    while detections:
        best = detections.pop(0)
        keep.append(best)

        # Remove overlapping boxes
        detections = [
            d for d in detections
            if iou(best["bbox"], d["bbox"]) < iou_threshold
        ]

    return keep


def iou(box1: list, box2: list) -> float:
    """Calculate Intersection over Union"""
    x1_min, y1_min, x1_max, y1_max = box1
    x2_min, y2_min, x2_max, y2_max = box2

    # Intersection
    xi_min = max(x1_min, x2_min)
    yi_min = max(y1_min, y2_min)
    xi_max = min(x1_max, x2_max)
    yi_max = min(y1_max, y2_max)

    if xi_max <= xi_min or yi_max <= yi_min:
        return 0.0

    intersection = (xi_max - xi_min) * (yi_max - yi_min)

    # Union
    area1 = (x1_max - x1_min) * (y1_max - y1_min)
    area2 = (x2_max - x2_min) * (y2_max - y2_min)
    union = area1 + area2 - intersection

    return intersection / union if union > 0 else 0.0
