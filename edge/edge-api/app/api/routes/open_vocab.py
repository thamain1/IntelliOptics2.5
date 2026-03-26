"""Edge API routes for open-vocabulary detection (YOLOE) and VLM queries."""

import logging
import os
from typing import Optional

import requests
from fastapi import APIRouter, File, HTTPException, Query, UploadFile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/open-vocab", tags=["open-vocab"])

INFERENCE_SERVICE_URL = os.getenv("INFERENCE_SERVICE_URL", "http://inference:8001")


@router.post("/detect")
async def detect_open_vocab(
    image: UploadFile = File(..., description="Image file"),
    prompts: str = Query(..., description="Comma-separated detection prompts"),
    conf: float = Query(0.25, description="Confidence threshold"),
):
    """Forward open-vocab detection request to YOLOE inference service."""
    try:
        image_bytes = await image.read()

        response = requests.post(
            f"{INFERENCE_SERVICE_URL}/yoloe",
            files={"image": ("frame.jpg", image_bytes, "image/jpeg")},
            params={"prompts": prompts, "conf": conf},
            timeout=180,
        )
        response.raise_for_status()
        return response.json()

    except requests.RequestException as e:
        logger.error(f"YOLOE inference failed: {e}")
        raise HTTPException(status_code=502, detail=f"Inference service error: {e}")


@router.post("/query")
async def vlm_query(
    image: UploadFile = File(..., description="Image file"),
    question: str = Query(..., description="Natural language question"),
):
    """Forward VLM query to inference service."""
    try:
        image_bytes = await image.read()

        response = requests.post(
            f"{INFERENCE_SERVICE_URL}/vlm/query",
            files={"image": ("frame.jpg", image_bytes, "image/jpeg")},
            params={"question": question},
            timeout=180,
        )
        response.raise_for_status()
        return response.json()

    except requests.RequestException as e:
        logger.error(f"VLM query failed: {e}")
        raise HTTPException(status_code=502, detail=f"VLM service error: {e}")
