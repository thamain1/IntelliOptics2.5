"""Edge API routes for vehicle identification."""

import logging
import os

import requests
from fastapi import APIRouter, File, HTTPException, UploadFile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vehicle-id", tags=["vehicle-id"])

INFERENCE_SERVICE_URL = os.getenv("INFERENCE_SERVICE_URL", "http://inference:8001")


@router.post("/identify")
async def identify_vehicle(
    image: UploadFile = File(..., description="Image file"),
):
    """Forward vehicle identification request to inference service."""
    try:
        image_bytes = await image.read()

        response = requests.post(
            f"{INFERENCE_SERVICE_URL}/vehicle-id/identify",
            files={"image": ("frame.jpg", image_bytes, "image/jpeg")},
            timeout=120,
        )
        response.raise_for_status()
        return response.json()

    except requests.RequestException as e:
        logger.error(f"Vehicle ID failed: {e}")
        raise HTTPException(status_code=502, detail=f"Inference service error: {e}")
