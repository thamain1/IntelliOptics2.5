"""
IntelliOptics 2.0 - Inference Service
Multi-detector ONNX inference with Primary + OODD ground truth models
"""

import os
import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, Optional, Tuple
from cachetools import LRUCache

import numpy as np
import onnxruntime as ort
from fastapi import FastAPI, File, UploadFile, Query, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
from PIL import Image
import io
from yoloe_inference import Detection

# Configuration
MODEL_REPOSITORY = os.getenv("MODEL_REPOSITORY", "/models")
CACHE_MAX_MODELS = 5
IMG_SIZE = int(os.getenv("IO_IMG_SIZE", "640"))
CONF_THRESH = float(os.getenv("IO_CONF_THRESH", "0.5"))
NMS_IOU = float(os.getenv("IO_NMS_IOU", "0.45"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
HEALTH_PORT = int(os.getenv("HEALTH_PORT", "8081"))

# Setup logging
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

# Model cache (LRU - keeps 5 most recently used models)
model_cache: LRUCache = LRUCache(maxsize=CACHE_MAX_MODELS)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-load YOLOE and VLM at startup to avoid cold-start latency on first request."""
    logger.info("Pre-loading inference models at startup...")
    loop = asyncio.get_event_loop()
    await asyncio.gather(
        loop.run_in_executor(None, get_yoloe),
        loop.run_in_executor(None, get_vlm),
    )
    logger.info("Models pre-loaded — inference service ready.")
    yield


app = FastAPI(title="IntelliOptics Inference Service", version="2.0", lifespan=lifespan)

# ====================
# Model Loading
# ====================

def load_onnx_model(model_path: str) -> ort.InferenceSession:
    """Load ONNX model with CPU/GPU support"""
    providers = ["CPUExecutionProvider"]

    # Check for CUDA
    if "CUDAExecutionProvider" in ort.get_available_providers():
        providers.insert(0, "CUDAExecutionProvider")
        logger.info("CUDA available - using GPU inference")

    session = ort.InferenceSession(model_path, providers=providers)
    logger.info(f"Loaded model: {model_path} with providers: {providers}")
    return session


def get_model_paths(detector_id: str) -> Tuple[Optional[Path], Optional[Path]]:
    """Get paths to Primary and OODD models for a detector"""
    base_path = Path(MODEL_REPOSITORY) / detector_id

    # Find latest version for Primary model
    primary_path = base_path / "primary"
    primary_model = None
    if primary_path.exists():
        versions = sorted([d for d in primary_path.iterdir() if d.is_dir()], reverse=True)
        if versions:
            model_file = versions[0] / "model.buf"
            if model_file.exists():
                primary_model = model_file

    # Find latest version for OODD model
    oodd_path = base_path / "oodd"
    oodd_model = None
    if oodd_path.exists():
        versions = sorted([d for d in oodd_path.iterdir() if d.is_dir()], reverse=True)
        if versions:
            model_file = versions[0] / "model.buf"
            if model_file.exists():
                oodd_model = model_file

    return primary_model, oodd_model


def load_detector_models(detector_id: str) -> Tuple[Optional[ort.InferenceSession], Optional[ort.InferenceSession]]:
    """Load Primary and OODD models for a detector (with caching)"""
    cache_key = detector_id

    if cache_key in model_cache:
        logger.debug(f"Cache hit for detector: {detector_id}")
        return model_cache[cache_key]

    primary_path, oodd_path = get_model_paths(detector_id)

    primary_session = None
    oodd_session = None

    if primary_path:
        try:
            primary_session = load_onnx_model(str(primary_path))
        except Exception as e:
            logger.error(f"Failed to load primary model for {detector_id}: {e}")

    if oodd_path:
        try:
            oodd_session = load_onnx_model(str(oodd_path))
        except Exception as e:
            logger.error(f"Failed to load OODD model for {detector_id}: {e}")

    # Cache the models
    model_cache[cache_key] = (primary_session, oodd_session)

    return primary_session, oodd_session


# ====================
# Image Preprocessing
# ====================

def preprocess_image(image_bytes: bytes) -> np.ndarray:
    """Preprocess image for ONNX model input"""
    # Load image
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    # Resize to model input size
    image = image.resize((IMG_SIZE, IMG_SIZE))

    # Convert to numpy array (CHW format)
    image_array = np.array(image).astype(np.float32)
    image_array = image_array.transpose(2, 0, 1)  # HWC -> CHW

    # Normalize (0-255 -> 0-1)
    image_array /= 255.0

    # Add batch dimension
    image_array = np.expand_dims(image_array, axis=0)

    return image_array


# ====================
# Inference
# ====================

def run_primary_inference(session: ort.InferenceSession, image: np.ndarray) -> Dict:
    """Run primary model inference"""
    # Get input name
    input_name = session.get_inputs()[0].name

    # Run inference
    outputs = session.run(None, {input_name: image})

    # Parse output (assumes YOLO-style output)
    # TODO: Adapt based on your actual model output format
    predictions = outputs[0]  # Shape: (batch, num_detections, 5+num_classes)

    # Extract best prediction
    if len(predictions.shape) == 3:
        predictions = predictions[0]  # Remove batch dimension

    if len(predictions) > 0:
        # Get highest confidence detection
        best_idx = np.argmax(predictions[:, 4])  # Confidence score at index 4
        best_detection = predictions[best_idx]

        confidence = float(best_detection[4])
        class_id = int(np.argmax(best_detection[5:]))  # Class scores start at index 5

        return {
            "label": class_id,
            "confidence": confidence,
            "bbox": best_detection[:4].tolist() if len(best_detection) >= 4 else None
        }
    else:
        return {"label": 0, "confidence": 0.0, "bbox": None}


def run_oodd_inference(session: ort.InferenceSession, image: np.ndarray) -> float:
    """Run OODD model inference to get in-domain score"""
    input_name = session.get_inputs()[0].name
    outputs = session.run(None, {input_name: image})

    # OODD output is in-domain confidence (0.0 to 1.0)
    in_domain_score = float(outputs[0][0])  # Assumes single output value

    return in_domain_score


# ====================
# API Endpoints
# ====================

@app.post("/infer")
async def infer(
    detector_id: str = Query(..., description="Detector ID"),
    image: UploadFile = File(..., description="Image file"),
    class_names: str = Query(None, description="Comma-separated class names for label mapping")
):
    """
    Run inference for a detector with Primary + OODD ground truth check

    Returns:
        - label: Detection class (name if class_names provided, otherwise numeric ID)
        - confidence: Final confidence (Primary × OODD in-domain score)
        - raw_primary_confidence: Original Primary model confidence
        - oodd_in_domain_score: OODD ground truth score
        - is_out_of_domain: True if OODD score < 0.5
    """
    try:
        # Load models
        primary_session, oodd_session = load_detector_models(detector_id)

        if not primary_session:
            raise HTTPException(status_code=404, detail=f"Primary model not found for detector: {detector_id}")

        # Read image
        image_bytes = await image.read()

        # Preprocess
        preprocessed_image = preprocess_image(image_bytes)

        # Run Primary model
        primary_result = run_primary_inference(primary_session, preprocessed_image)
        raw_confidence = primary_result["confidence"]
        class_id = primary_result["label"]

        # Map class_id to class name if class_names provided
        if class_names:
            names_list = [n.strip() for n in class_names.split(',')]
            label = names_list[class_id] if class_id < len(names_list) else f"class_{class_id}"
        else:
            label = f"class_{class_id}"

        # Run OODD model (ground truth check)
        oodd_in_domain_score = 1.0  # Default to in-domain if no OODD model
        if oodd_session:
            oodd_in_domain_score = run_oodd_inference(oodd_session, preprocessed_image)
        else:
            logger.warning(f"No OODD model for detector: {detector_id}")

        # Adjust confidence based on OODD ground truth
        final_confidence = raw_confidence * oodd_in_domain_score

        logger.info(f"🎯 Detector {detector_id}: {label} ({final_confidence:.2%})")

        return JSONResponse({
            "label": label,
            "class_id": class_id,
            "confidence": final_confidence,
            "raw_primary_confidence": raw_confidence,
            "oodd_in_domain_score": oodd_in_domain_score,
            "is_out_of_domain": oodd_in_domain_score < 0.5,
            "bbox": primary_result.get("bbox")
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Inference error for {detector_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ====================
# YOLOWorld Open-Vocabulary Detection (delegates to YOLOE ONNX)
# ====================

@app.post("/yoloworld")
async def yoloworld_inference(
    image: UploadFile = File(..., description="Image file"),
    prompts: str = Query(..., description="Comma-separated list of objects to detect")
):
    """
    Run YOLOWorld open-vocabulary detection (delegates to YOLOE ONNX model).
    Kept for backwards compatibility — identical to /yoloe.
    """
    import time
    try:
        prompt_list = [p.strip() for p in prompts.split(',') if p.strip()]
        if not prompt_list:
            raise HTTPException(status_code=400, detail="No valid prompts provided")

        logger.info(f"YOLOWorld inference (via YOLOE ONNX) with prompts: {prompt_list}")

        model = get_yoloe()
        image_bytes = await image.read()

        pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        image_np = np.array(pil_image)

        start = time.perf_counter()
        detections = model.detect(image_np, prompt_list, conf=CONF_THRESH, iou=NMS_IOU)
        latency_ms = (time.perf_counter() - start) * 1000

        logger.info(f"YOLOWorld detected {len(detections)} objects via YOLOE ONNX")

        return JSONResponse({
            "detections": [d.to_normalized(pil_image.width, pil_image.height) for d in detections],
            "prompts_used": prompt_list,
            "latency_ms": int(latency_ms),
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"YOLOWorld inference error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ====================
# YOLOE Open-Vocabulary Detection
# ====================

yoloe_instance = None
vlm_instance = None


def get_yoloe():
    """Load YOLOE model (lazy initialization)"""
    global yoloe_instance
    if yoloe_instance is None:
        from yoloe_inference import get_yoloe_model
        yoloe_instance = get_yoloe_model()
    return yoloe_instance


def get_vlm():
    """Load VLM model (lazy initialization)"""
    global vlm_instance
    if vlm_instance is None:
        from vlm_inference import get_vlm as _get_vlm
        vlm_instance = _get_vlm()
    return vlm_instance


@app.post("/yoloe")
async def yoloe_inference(
    image: UploadFile = File(..., description="Image file"),
    prompts: str = Query(..., description="Comma-separated list of objects to detect"),
    conf: float = Query(0.25, description="Confidence threshold"),
):
    """
    Run YOLOE open-vocabulary detection with dynamic text prompts.

    Args:
        image: Image file to analyze
        prompts: Comma-separated list of things to detect (e.g., "person, car, fire")
        conf: Confidence threshold (0-1)

    Returns:
        - detections: List of detected objects with labels, confidence, and bounding boxes
        - latency_ms: Inference time in milliseconds
    """
    import time
    try:
        prompt_list = [p.strip() for p in prompts.split(',') if p.strip()]
        if not prompt_list:
            raise HTTPException(status_code=400, detail="No valid prompts provided")

        logger.info(f"YOLOE inference with prompts: {prompt_list}")

        model = get_yoloe()
        image_bytes = await image.read()

        # Convert to numpy
        pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        image_np = np.array(pil_image)

        start = time.perf_counter()
        detections = model.detect(image_np, prompt_list, conf=conf)
        latency_ms = (time.perf_counter() - start) * 1000

        # VLM fallback: for any prompt that YOLOE missed, escalate to VLM
        vlm_used = False
        detected_labels = {d.label.lower() for d in detections}
        missed_prompts = [p for p in prompt_list if p.lower() not in detected_labels]

        if missed_prompts:
            try:
                vlm = get_vlm()
                if vlm.model is not None:
                    logger.info(f"YOLOE missed prompts {missed_prompts}, escalating to VLM")
                    vlm_start = time.perf_counter()
                    for prompt in missed_prompts:
                        vlm_dets = vlm.detect(image_np, prompt)
                        for vd in vlm_dets:
                            detections.append(Detection(
                                label=vd["label"],
                                confidence=vd["confidence"],
                                bbox=[
                                    vd["bbox"][0] * pil_image.width,
                                    vd["bbox"][1] * pil_image.height,
                                    vd["bbox"][2] * pil_image.width,
                                    vd["bbox"][3] * pil_image.height,
                                ],
                            ))
                    vlm_ms = (time.perf_counter() - vlm_start) * 1000
                    latency_ms += vlm_ms
                    vlm_used = True
                    logger.info(f"VLM fallback found {len(detections) - len(detected_labels)} additional detections in {vlm_ms:.0f}ms")
            except Exception as vlm_err:
                logger.warning(f"VLM fallback failed: {vlm_err}")

        return JSONResponse({
            "detections": [d.to_normalized(pil_image.width, pil_image.height) for d in detections],
            "prompts_used": prompt_list,
            "latency_ms": int(latency_ms),
            "vlm_fallback": vlm_used,
        })

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"YOLOE inference error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ====================
# Moondream VLM Endpoints
# ====================

@app.post("/vlm/query")
async def vlm_query(
    image: UploadFile = File(..., description="Image file"),
    question: str = Query(..., description="Natural language question about the image"),
):
    """Ask a natural language question about an image using Moondream VLM."""
    try:
        vlm = get_vlm()
        image_bytes = await image.read()
        pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        image_np = np.array(pil_image)

        result = vlm.query(image_np, question)

        return JSONResponse({
            "answer": result.answer,
            "confidence": result.confidence,
            "latency_ms": int(result.latency_ms),
        })

    except Exception as e:
        logger.error(f"VLM query error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/vlm/detect")
async def vlm_detect(
    image: UploadFile = File(..., description="Image file"),
    object_desc: str = Query(..., description="Description of object to detect"),
):
    """Detect objects matching a description using Moondream VLM (returns bounding boxes)."""
    try:
        vlm = get_vlm()
        image_bytes = await image.read()
        pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        image_np = np.array(pil_image)

        detections = vlm.detect(image_np, object_desc)

        return JSONResponse({
            "detections": detections,
            "object_description": object_desc,
        })

    except Exception as e:
        logger.error(f"VLM detect error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/vlm/ocr")
async def vlm_ocr(
    image: UploadFile = File(..., description="Image file"),
):
    """Extract text from an image using Moondream VLM OCR."""
    try:
        vlm = get_vlm()
        image_bytes = await image.read()
        pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        image_np = np.array(pil_image)

        text = vlm.ocr(image_np)

        return JSONResponse({"text": text})

    except Exception as e:
        logger.error(f"VLM OCR error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ====================
# Vehicle ID Endpoint
# ====================

@app.post("/vehicle-id/identify")
async def vehicle_id_identify(
    image: UploadFile = File(..., description="Image file"),
):
    """Run full vehicle identification pipeline: plate OCR + color + type + spatial matching."""
    try:
        from vehicle_id import VehicleIdentifier

        yoloe = get_yoloe()
        vlm = get_vlm()
        identifier = VehicleIdentifier(yoloe, vlm)

        image_bytes = await image.read()
        pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        image_np = np.array(pil_image)

        records = identifier.identify(image_np)

        return JSONResponse({
            "vehicles": [
                {
                    "plate_text": r.plate_text,
                    "vehicle_color": r.vehicle_color,
                    "vehicle_type": r.vehicle_type,
                    "vehicle_make_model": r.vehicle_make_model,
                    "confidence": r.confidence,
                    "bbox": r.bbox,
                    "plate_bbox": r.plate_bbox,
                    "latency_ms": int(r.latency_ms),
                }
                for r in records
            ]
        })

    except Exception as e:
        logger.error(f"Vehicle ID error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "cached_models": len(model_cache),
        "yoloe_loaded": yoloe_instance is not None,
        "vlm_loaded": vlm_instance is not None,
    }


@app.get("/models")
async def list_models():
    """List available models"""
    model_repo = Path(MODEL_REPOSITORY)
    if not model_repo.exists():
        return {"models": []}

    detectors = []
    for detector_dir in model_repo.iterdir():
        if detector_dir.is_dir():
            primary_path, oodd_path = get_model_paths(detector_dir.name)
            detectors.append({
                "detector_id": detector_dir.name,
                "has_primary": primary_path is not None,
                "has_oodd": oodd_path is not None,
                "cached": detector_dir.name in model_cache
            })

    return {"models": detectors}


# ====================
# Forensic Search (BOLO) Endpoints
# ====================

forensic_engine = None
forensic_results: dict[str, list] = {}  # job_id -> list of result dicts


def get_forensic_engine():
    """Load forensic search engine (lazy initialization)."""
    global forensic_engine
    if forensic_engine is None:
        from forensic_search import ForensicSearchEngine
        forensic_engine = ForensicSearchEngine(get_yoloe(), get_vlm())
    return forensic_engine


@app.post("/forensic-search/run")
async def forensic_search_run(payload: dict):
    """Start a forensic search job. Returns immediately with job_id.

    Payload: {query_text, source_url, source_type?, frame_interval_sec?, confidence_threshold?}
    """
    import asyncio
    from forensic_search import ForensicSearchJob

    engine = get_forensic_engine()

    # Normalize source_url to container path
    source_url = payload["source_url"]
    # Map Windows host paths or bare filenames to /videos/ mount
    import re
    if re.match(r'^[a-zA-Z]:\\', source_url) or re.match(r'^[a-zA-Z]:/', source_url):
        # Windows absolute path — extract filename after last slash/backslash
        filename = source_url.replace('\\', '/').split('/')[-1]
        source_url = f"/videos/{filename}"
        logger.info(f"Mapped Windows path to container path: {source_url}")
    elif not source_url.startswith('/'):
        # Bare filename or relative path — prepend /videos/
        source_url = f"/videos/{source_url}"
        logger.info(f"Mapped relative path to container path: {source_url}")

    job = ForensicSearchJob(
        id=payload.get("job_id", str(uuid.uuid4())),
        query_text=payload["query_text"],
        source_url=source_url,
        source_type=payload.get("source_type", "video_file"),
        frame_interval_sec=payload.get("frame_interval_sec", 1.0),
        confidence_threshold=payload.get("confidence_threshold", 0.3),
    )

    forensic_results[job.id] = []

    async def _run():
        try:
            async for result in engine.search(job):
                # Store result (without frame_data for status polling — frame_data fetched separately)
                frame_bytes = result.frame_data
                result_dict = {
                    "id": result.id,
                    "job_id": result.job_id,
                    "timestamp_sec": result.timestamp_sec,
                    "confidence": result.confidence,
                    "bbox": result.bbox,
                    "label": result.label,
                    "description": result.description,
                    "has_frame": frame_bytes is not None,
                }
                # Encode frame as base64 for retrieval
                if frame_bytes:
                    import base64
                    result_dict["frame_b64"] = base64.b64encode(frame_bytes).decode()
                forensic_results.get(job.id, []).append(result_dict)
        except Exception as e:
            logger.error(f"Forensic search error: {e}", exc_info=True)
            job.status = "ERROR"

    asyncio.create_task(_run())

    return JSONResponse({
        "job_id": job.id,
        "status": job.status,
        "message": f"Search started for: {job.query_text}",
    })


@app.get("/forensic-search/{job_id}/status")
async def forensic_search_status(job_id: str):
    """Get progress of a forensic search job."""
    engine = get_forensic_engine()
    job = engine.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JSONResponse({
        "job_id": job.id,
        "status": job.status,
        "progress_pct": job.progress_pct,
        "total_frames": job.total_frames,
        "frames_scanned": job.frames_scanned,
        "matches_found": job.matches_found,
    })


@app.get("/forensic-search/{job_id}/results")
async def forensic_search_results(job_id: str):
    """Get search results for a job."""
    results = forensic_results.get(job_id, [])
    # Return results without large frame data (fetch frames individually if needed)
    lightweight = []
    for r in results:
        lightweight.append({
            "id": r["id"],
            "job_id": r["job_id"],
            "timestamp_sec": r["timestamp_sec"],
            "confidence": r["confidence"],
            "bbox": r["bbox"],
            "label": r["label"],
            "frame_b64": r.get("frame_b64"),
        })
    return JSONResponse({"results": lightweight})


@app.post("/forensic-search/{job_id}/stop")
async def forensic_search_stop(job_id: str):
    """Cancel a running forensic search job."""
    engine = get_forensic_engine()
    if engine.stop(job_id):
        return JSONResponse({"message": "Job cancelled", "job_id": job_id})
    raise HTTPException(status_code=404, detail="Job not found or already finished")


@app.post("/forensic-search/upload")
async def forensic_search_upload(file: UploadFile = File(...)):
    """Upload a video file for forensic search. Saves to /videos/ directory."""
    import os
    import re

    # Sanitize filename
    filename = re.sub(r'[^\w\-.]', '_', file.filename or "upload.mp4")
    save_path = f"/videos/{filename}"

    # Avoid overwriting — append suffix if exists
    base, ext = os.path.splitext(save_path)
    counter = 1
    while os.path.exists(save_path):
        save_path = f"{base}_{counter}{ext}"
        counter += 1

    os.makedirs("/videos", exist_ok=True)
    with open(save_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            f.write(chunk)

    final_filename = os.path.basename(save_path)
    logger.info(f"Uploaded video: {save_path} ({os.path.getsize(save_path)} bytes)")

    return JSONResponse({
        "filename": final_filename,
        "path": save_path,
        "size": os.path.getsize(save_path),
    })


# ====================
# Main
# ====================

if __name__ == "__main__":
    # Run main inference service
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level=LOG_LEVEL.lower()
    )
