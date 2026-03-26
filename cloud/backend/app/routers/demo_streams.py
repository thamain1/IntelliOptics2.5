"""API endpoints for YouTube demo stream functionality."""
from __future__ import annotations

import uuid
import random
import re
import base64
import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import Response
from sqlalchemy.orm import Session

from .. import models, schemas
from ..dependencies import get_db, get_current_user
from ..utils.supabase_storage import upload_blob
from ..config import get_settings
from ..services.demo_session_manager import session_manager

router = APIRouter(prefix="/demo-streams", tags=["demo-streams"])
settings = get_settings()
logger = logging.getLogger(__name__)


# ==================== Helper Functions ====================

def extract_youtube_id(url: str) -> str:
    """Extract YouTube video ID from URL."""
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\n?#]+)',
        r'youtube\.com\/embed\/([^&\n?#]+)',
        r'youtube\.com\/v\/([^&\n?#]+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


async def process_demo_query(query_id: str, result_id: str, db: Session):
    """Background task to process demo query (real inference)."""
    from ..services.inference_service import InferenceService
    from ..utils.supabase_storage import download_blob
    
    query = db.query(models.Query).filter(models.Query.id == query_id).first()
    result = db.query(models.DemoDetectionResult).filter(models.DemoDetectionResult.id == result_id).first()
    
    if not query or not result:
        return

    try:
        # 1. Get image bytes from blob
        container, blob_name = query.image_blob_path.split("/", 1)
        image_bytes = download_blob(container, blob_name)
        
        # 2. Get detector and config
        det = query.detector
        config = db.query(models.DetectorConfig).filter(models.DetectorConfig.detector_id == det.id).first()
        
        # 3. Run real inference
        inference_result = await InferenceService.run_inference(
            detector_id=det.id,
            image_bytes=image_bytes,
            detector_config=config,
            primary_model_blob_path=det.primary_model_blob_path,
            oodd_model_blob_path=det.oodd_model_blob_path
        )
        
        # 4. Extract results
        detections = inference_result.get("detections", [])
        if detections:
            top_det = max(detections, key=lambda x: x.get("confidence", 0.0) if "confidence" in x else x.get("conf", 0.0))
            label = top_det.get("label", "unknown")
            confidence = top_det.get("confidence", 0.0) if "confidence" in top_det else top_det.get("conf", 0.0)
        else:
            label = "nothing"
            confidence = 1.0

        # 5. Update records
        query.result_label = label
        query.confidence = confidence
        query.status = "DONE"

        result.result_label = label
        result.confidence = confidence
        result.status = "DONE"
        result.completed_at = datetime.utcnow()

        # Update session stats
        session = result.session
        if session:
            session.total_detections += 1

    except Exception as e:
        logger.error(f"Demo inference failed for query {query_id}: {e}")
        query.status = "ERROR"
        result.status = "ERROR"
        
    db.commit()


# ==================== Stream Configs (Presets) ====================

@router.get("/configs", response_model=List[schemas.DemoStreamConfigOut])
def list_stream_configs(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
) -> List[models.DemoStreamConfig]:
    """List all saved stream preset configurations."""
    return db.query(models.DemoStreamConfig).filter(
        models.DemoStreamConfig.created_by == user.id
    ).order_by(models.DemoStreamConfig.updated_at.desc()).all()


@router.post("/configs", response_model=schemas.DemoStreamConfigOut, status_code=201)
def create_stream_config(
    payload: schemas.DemoStreamConfigCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
) -> models.DemoStreamConfig:
    """Create a new stream preset configuration."""
    # Extract YouTube video ID from URL
    video_id = extract_youtube_id(payload.youtube_url)

    config = models.DemoStreamConfig(
        name=payload.name,
        description=payload.description,
        youtube_url=payload.youtube_url,
        youtube_video_id=video_id,
        capture_mode=payload.capture_mode,
        polling_interval_ms=payload.polling_interval_ms,
        motion_threshold=payload.motion_threshold,
        detector_ids=payload.detector_ids,
        created_by=user.id
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


@router.get("/configs/{config_id}", response_model=schemas.DemoStreamConfigOut)
def get_stream_config(
    config_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
) -> models.DemoStreamConfig:
    """Get a specific stream configuration."""
    config = db.query(models.DemoStreamConfig).filter(models.DemoStreamConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    return config


@router.put("/configs/{config_id}", response_model=schemas.DemoStreamConfigOut)
def update_stream_config(
    config_id: str,
    payload: schemas.DemoStreamConfigUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
) -> models.DemoStreamConfig:
    """Update a stream configuration."""
    config = db.query(models.DemoStreamConfig).filter(models.DemoStreamConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")

    for key, value in payload.dict(exclude_unset=True).items():
        setattr(config, key, value)

    # Update video ID if URL changed
    if payload.youtube_url:
        config.youtube_video_id = extract_youtube_id(payload.youtube_url)

    db.commit()
    db.refresh(config)
    return config


@router.delete("/configs/{config_id}", status_code=204)
def delete_stream_config(
    config_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Delete a stream configuration."""
    config = db.query(models.DemoStreamConfig).filter(models.DemoStreamConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    db.delete(config)
    db.commit()


# ==================== Demo Sessions ====================

@router.get("/sessions", response_model=List[schemas.DemoSessionOut])
def list_sessions(
    limit: int = 50,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
) -> List[models.DemoSession]:
    """List recent demo sessions."""
    return db.query(models.DemoSession).filter(
        models.DemoSession.created_by == user.id
    ).order_by(models.DemoSession.started_at.desc()).limit(limit).all()


@router.post("/sessions", response_model=schemas.DemoSessionOut, status_code=201)
def start_demo_session(
    payload: schemas.DemoSessionCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
) -> models.DemoSession:
    """Start a new demo session with server-side capture."""
    # Generate session name if not provided
    name = payload.name or f"Demo {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"

    # Extract YouTube video ID
    video_id = extract_youtube_id(payload.youtube_url)

    # Generate appropriate name for YOLOWorld sessions
    if payload.yoloworld_prompts:
        name = payload.name or f"YOLOWorld Demo {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"

    session = models.DemoSession(
        config_id=payload.config_id,
        name=name,
        youtube_url=payload.youtube_url,
        youtube_video_id=video_id,
        capture_mode=payload.capture_mode,
        polling_interval_ms=payload.polling_interval_ms,
        motion_threshold=payload.motion_threshold,
        detector_ids=payload.detector_ids,
        yoloworld_prompts=payload.yoloworld_prompts,
        status="active",
        created_by=user.id
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # Debug logging
    logger.info(f"Session created: {session.id}")
    logger.info(f"Payload capture_mode: '{payload.capture_mode}'")
    logger.info(f"Session capture_mode: '{session.capture_mode}'")
    logger.info(f"YOLOWorld prompts: '{payload.yoloworld_prompts}'")
    logger.info(f"YouTube URL: '{payload.youtube_url}'")

    # Determine if we should start server-side capture
    # Start for: polling/motion modes, OR yoloworld with a real stream URL (not webcam)
    is_polling_or_motion = payload.capture_mode in ['polling', 'motion']
    is_yoloworld_with_stream = (
        payload.yoloworld_prompts and
        payload.youtube_url and
        not payload.youtube_url.startswith('webcam://')
    )

    if is_polling_or_motion or is_yoloworld_with_stream:
        mode_desc = "YOLOWorld stream" if is_yoloworld_with_stream else payload.capture_mode
        logger.info(f"Attempting to start {mode_desc} capture for session {session.id}")
        logger.info(f"YouTube URL: {payload.youtube_url}")
        logger.info(f"Detector IDs: {payload.detector_ids}")
        if is_yoloworld_with_stream:
            logger.info(f"🌍 YOLOWorld prompts: {payload.yoloworld_prompts}")
        try:
            session_manager.start_session(
                session_id=session.id,
                youtube_url=payload.youtube_url,
                capture_mode=payload.capture_mode if is_polling_or_motion else 'polling',
                detector_ids=payload.detector_ids,
                db=db,
                polling_interval_ms=payload.polling_interval_ms or 2000,
                motion_threshold=payload.motion_threshold or 500.0,
                yoloworld_prompts=payload.yoloworld_prompts if is_yoloworld_with_stream else None,
            )
            logger.info(f"✓ Started server-side capture for session {session.id}")
        except Exception as e:
            logger.error(f"✗ Failed to start server-side capture: {e}", exc_info=True)
            session.status = "error"
            db.commit()
            raise HTTPException(status_code=500, detail=f"Failed to start video capture: {str(e)}")

    return session


@router.get("/sessions/{session_id}", response_model=schemas.DemoSessionOut)
def get_session(
    session_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
) -> models.DemoSession:
    """Get a specific demo session."""
    session = db.query(models.DemoSession).filter(models.DemoSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Check if capture thread is actually running
    is_active = session_manager.is_session_active(session.id)
    if session.status == 'active' and not is_active:
        # If DB says active but manager doesn't have it, it might have crashed
        # (Don't update DB here, just return current state)
        pass
        
    return session


@router.post("/sessions/{session_id}/stop", response_model=schemas.DemoSessionOut)
def stop_demo_session(
    session_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
) -> models.DemoSession:
    """Stop an active demo session."""
    session = db.query(models.DemoSession).filter(models.DemoSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Stop server-side capture if running
    if session_manager.is_session_active(session_id):
        session_manager.stop_session(session_id)
        logger.info(f"Stopped server-side capture for session {session_id}")

    session.status = "stopped"
    session.stopped_at = datetime.utcnow()
    db.commit()
    db.refresh(session)
    return session


# ==================== Frame Submission ====================

@router.post("/sessions/{session_id}/submit-frame", response_model=schemas.DemoDetectionResultOut)
async def submit_frame(
    session_id: str,
    payload: schemas.FrameSubmit,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
) -> models.DemoDetectionResult:
    """
    Submit a frame for detection during a demo session.

    This endpoint receives:
    - session_id: Active demo session
    - detector_id: Which detector to use
    - image_data: Base64 encoded image
    - capture_method: polling, motion, manual
    """
    session = db.query(models.DemoSession).filter(models.DemoSession.id == session_id).first()
    if not session or session.status != "active":
        raise HTTPException(status_code=400, detail="Session not active")

    # Decode image from base64
    try:
        image_bytes = base64.b64decode(payload.image_data)
        logger.info(f"📸 Received manual frame submission for session {session_id}, size: {len(image_bytes)} bytes")
    except Exception as e:
        logger.error(f"❌ Failed to decode base64 image: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid base64 image data: {e}")

    # Store latest frame for live preview polling
    session_manager._latest_frames[session_id] = image_bytes

    # Submit to blob storage
    blob_name = f"demo-sessions/{session_id}/{uuid.uuid4()}.jpg"
    try:
        blob_path = upload_blob(
            settings.supabase_storage_bucket,
            blob_name,
            image_bytes,
            "image/jpeg"
        )
        logger.info(f"☁️ Uploaded frame to blob: {blob_path}")
    except Exception as e:
        logger.error(f"❌ Failed to upload frame to blob: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload image to storage")

    # Create query
    query = models.Query(
        detector_id=payload.detector_id,
        image_blob_path=blob_path,
        status="PENDING",
        local_inference=False,
        escalated=False,
    )
    db.add(query)
    db.flush()

    # Create detection result
    result = models.DemoDetectionResult(
        session_id=session_id,
        query_id=query.id,
        detector_id=payload.detector_id,
        frame_number=session.total_frames_captured + 1,
        capture_method=payload.capture_method,
        status="PENDING"
    )
    db.add(result)

    # Update session stats
    session.total_frames_captured += 1

    db.commit()
    db.refresh(result)

    # Process query using local inference (same as server-side capture)
    from threading import Thread
    from ..services.demo_session_manager import _process_inference_local
    thread = Thread(
        target=_process_inference_local,
        args=(query.id, result.id, image_bytes, payload.detector_id),
        daemon=True
    )
    thread.start()

    return result


@router.post("/sessions/{session_id}/submit-yoloworld-frame", response_model=schemas.DemoDetectionResultOut)
async def submit_yoloworld_frame(
    session_id: str,
    payload: schemas.YoloWorldFrameSubmit,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
) -> models.DemoDetectionResult:
    """
    Submit a frame for YOLOWorld open-vocabulary detection.

    This endpoint receives:
    - session_id: Active demo session
    - image_data: Base64 encoded image
    - prompts: Comma-separated list of things to detect
    """
    session = db.query(models.DemoSession).filter(models.DemoSession.id == session_id).first()
    if not session or session.status != "active":
        raise HTTPException(status_code=400, detail="Session not active")

    # Decode image from base64
    try:
        image_bytes = base64.b64decode(payload.image_data)
        logger.info(f"🌍 YOLOWorld frame received for session {session_id}, size: {len(image_bytes)} bytes")
        logger.info(f"🎯 Prompts: {payload.prompts}")
    except Exception as e:
        logger.error(f"❌ Failed to decode base64 image: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid base64 image data: {e}")

    # Upload to blob storage
    blob_name = f"demo-sessions/{session_id}/yoloworld/{uuid.uuid4()}.jpg"
    try:
        blob_path = upload_blob(
            settings.supabase_storage_bucket,
            blob_name,
            image_bytes,
            "image/jpeg"
        )
        logger.info(f"☁️ Uploaded YOLOWorld frame to blob: {blob_path}")
    except Exception as e:
        logger.error(f"❌ Failed to upload frame to blob: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload image to storage")

    # Create a placeholder query (no specific detector)
    query = models.Query(
        detector_id=None,  # YOLOWorld doesn't use a specific detector
        image_blob_path=blob_path,
        status="PENDING",
        local_inference=True,
        escalated=False,
    )
    db.add(query)
    db.flush()

    # Create detection result
    result = models.DemoDetectionResult(
        session_id=session_id,
        query_id=query.id,
        detector_id=None,  # YOLOWorld mode
        frame_number=session.total_frames_captured + 1,
        capture_method="yoloworld",
        status="PENDING"
    )
    db.add(result)

    # Update session stats
    session.total_frames_captured += 1

    db.commit()
    db.refresh(result)

    # Process YOLOWorld inference
    from threading import Thread
    from ..services.yoloworld_inference import process_yoloworld_inference
    thread = Thread(
        target=process_yoloworld_inference,
        args=(query.id, result.id, image_bytes, payload.prompts),
        daemon=True
    )
    thread.start()

    return result


@router.post("/sessions/{session_id}/submit-yoloe-frame", response_model=schemas.DemoDetectionResultOut)
async def submit_yoloe_frame(
    session_id: str,
    payload: schemas.YoloeFrameSubmit,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> models.DemoDetectionResult:
    """Submit a frame for YOLOE open-vocabulary detection.

    Similar to submit_yoloworld_frame but uses the YOLOE endpoint which supports
    dynamic per-request text prompts and stores bbox detections for LiveBboxOverlay.
    """
    session = db.query(models.DemoSession).filter(models.DemoSession.id == session_id).first()
    if not session or session.status != "active":
        raise HTTPException(status_code=400, detail="Session not active")

    try:
        image_bytes = base64.b64decode(payload.image_data)
        logger.info(f"[YOLOE] Frame received for session {session_id}, size: {len(image_bytes)} bytes")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid base64 image data: {e}")

    blob_name = f"demo-sessions/{session_id}/yoloe/{uuid.uuid4()}.jpg"
    try:
        blob_path = upload_blob(
            settings.supabase_storage_bucket, blob_name, image_bytes, "image/jpeg"
        )
    except Exception as e:
        logger.error(f"[YOLOE] Failed to upload frame: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload image to storage")

    query = models.Query(
        detector_id=None,
        image_blob_path=blob_path,
        status="PENDING",
        local_inference=True,
        escalated=False,
    )
    db.add(query)
    db.flush()

    result = models.DemoDetectionResult(
        session_id=session_id,
        query_id=query.id,
        detector_id=None,
        frame_number=session.total_frames_captured + 1,
        capture_method="yoloe",
        status="PENDING",
    )
    db.add(result)

    session.total_frames_captured += 1
    db.commit()
    db.refresh(result)

    from threading import Thread
    from ..services.yoloworld_inference import process_yoloe_inference

    thread = Thread(
        target=process_yoloe_inference,
        args=(query.id, result.id, image_bytes, payload.prompts, payload.confidence_threshold),
        daemon=True,
    )
    thread.start()

    return result


@router.get("/sessions/{session_id}/results", response_model=List[schemas.DemoDetectionResultOut])
def get_session_results(
    session_id: str,
    limit: int = 100,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
) -> List[models.DemoDetectionResult]:
    """Get detection results for a demo session."""
    return db.query(models.DemoDetectionResult).filter(
        models.DemoDetectionResult.session_id == session_id
    ).order_by(models.DemoDetectionResult.created_at.desc()).limit(limit).all()


@router.get("/sessions/{session_id}/latest-detections")
def get_latest_detections(
    session_id: str,
    limit: int = 1,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get the most recent detection results with normalized bbox coords (for live overlay).

    Returns lightweight response (no image data, just detections array).
    """
    session = db.query(models.DemoSession).filter(models.DemoSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get the single most recent completed result that has detection data
    results = (
        db.query(models.DemoDetectionResult)
        .filter(
            models.DemoDetectionResult.session_id == session_id,
            models.DemoDetectionResult.status == "DONE",
        )
        .order_by(models.DemoDetectionResult.created_at.desc())
        .limit(limit * 5)
        .all()
    )

    # Return detections from the FIRST result that has bbox data (most recent frame)
    detections = []
    for result in results:
        if result.query_id:
            query = db.query(models.Query).filter(models.Query.id == result.query_id).first()
            if query and query.detections_json:
                for det in query.detections_json:
                    detections.append({
                        "label": det.get("label", result.result_label),
                        "confidence": det.get("confidence", det.get("conf", result.confidence)),
                        "bbox": det.get("bbox", []),
                    })
                break  # Only use the most recent frame's detections
            elif result.result_label:
                detections.append({
                    "label": result.result_label,
                    "confidence": result.confidence or 0.0,
                    "bbox": [],
                })
                break  # Only use the most recent frame's detections

    return {
        "session_id": session_id,
        "detections": detections[:50],
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.put("/sessions/{session_id}/prompts")
def update_session_prompts(
    session_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Update detection prompts for an active server-side capture session."""
    prompts = payload.get("prompts", "").strip()
    if not prompts:
        raise HTTPException(status_code=400, detail="Prompts cannot be empty")

    session = db.query(models.DemoSession).filter(models.DemoSession.id == session_id).first()
    if not session or session.status != "active":
        raise HTTPException(status_code=400, detail="Session not active")

    if session_manager.update_prompts(session_id, prompts):
        # Also update the session record
        session.yoloworld_prompts = prompts
        db.commit()
        return {"message": f"Prompts updated to: {prompts}", "prompts": prompts}

    raise HTTPException(status_code=404, detail="Session not found in active captures")


@router.get("/sessions/{session_id}/latest-frame")
def get_latest_frame(
    session_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
) -> Response:
    """Get the latest captured frame as JPEG for live preview."""
    session = db.query(models.DemoSession).filter(models.DemoSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    frame_bytes = session_manager.get_latest_frame(session_id)
    if not frame_bytes:
        raise HTTPException(status_code=404, detail="No frame available yet")

    return Response(
        content=frame_bytes,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
    )
