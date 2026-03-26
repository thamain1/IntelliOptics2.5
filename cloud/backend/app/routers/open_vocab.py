"""API endpoints for open-vocabulary detection (YOLOE + VLM)."""
from __future__ import annotations

import base64
import logging
import uuid
from datetime import datetime
from typing import List

import requests
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import get_settings
from ..dependencies import get_db, get_current_user
from ..utils.supabase_storage import upload_blob

router = APIRouter(prefix="/open-vocab", tags=["open-vocab"])
settings = get_settings()
logger = logging.getLogger(__name__)


@router.post("/detect", response_model=schemas.OpenVocabResultOut)
async def detect_open_vocab(
    payload: schemas.OpenVocabQueryCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Submit an image + prompts for open-vocabulary object detection via YOLOE."""
    prompt_list = [p.strip() for p in payload.prompts.split(",") if p.strip()]
    if not prompt_list:
        raise HTTPException(status_code=400, detail="No valid prompts provided")

    if not payload.image_data:
        raise HTTPException(status_code=400, detail="image_data is required")

    try:
        image_bytes = base64.b64decode(payload.image_data)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 image data")

    # Forward to edge YOLOE endpoint
    yoloe_url = getattr(settings, "yoloworld_worker_url", "http://localhost:8001/yoloe")
    # Use /yoloe endpoint instead of /yoloworld
    yoloe_url = yoloe_url.replace("/yoloworld", "/yoloe")

    try:
        response = requests.post(
            yoloe_url,
            files={"image": ("frame.jpg", image_bytes, "image/jpeg")},
            params={
                "prompts": ",".join(prompt_list),
                "conf": payload.confidence_threshold,
            },
            timeout=360,
        )
        response.raise_for_status()
        result = response.json()

        detections = [
            schemas.OpenVocabDetectionOut(
                label=d["label"],
                confidence=d["confidence"],
                bbox=d["bbox"],
            )
            for d in result.get("detections", [])
        ]

        return schemas.OpenVocabResultOut(
            detections=detections,
            prompts_used=prompt_list,
            latency_ms=result.get("latency_ms", 0),
        )

    except requests.RequestException as e:
        logger.error(f"YOLOE inference request failed: {e}")
        raise HTTPException(status_code=502, detail=f"Edge inference service error: {e}")


@router.post("/query", response_model=schemas.VLMQueryResultOut)
async def query_vlm(
    payload: schemas.VLMQueryCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Submit an image + natural language question to VLM (Moondream)."""
    if not payload.image_data:
        raise HTTPException(status_code=400, detail="image_data is required")

    try:
        image_bytes = base64.b64decode(payload.image_data)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 image data")

    vlm_url = getattr(settings, "yoloworld_worker_url", "http://localhost:8001/yoloworld")
    vlm_url = vlm_url.rsplit("/", 1)[0] + "/vlm/query"

    try:
        response = requests.post(
            vlm_url,
            files={"image": ("frame.jpg", image_bytes, "image/jpeg")},
            params={"question": payload.question},
            timeout=360,
        )
        response.raise_for_status()
        result = response.json()

        return schemas.VLMQueryResultOut(
            answer=result.get("answer", ""),
            confidence=result.get("confidence", 0.0),
            latency_ms=result.get("latency_ms", 0),
        )

    except requests.RequestException as e:
        logger.error(f"VLM query request failed: {e}")
        raise HTTPException(status_code=502, detail=f"VLM service error: {e}")
