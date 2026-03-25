"""API endpoints for vehicle identification and search."""
from __future__ import annotations

import base64
import logging
import uuid
from datetime import datetime
from typing import List, Optional

import requests
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from .. import models, schemas
from ..config import get_settings
from ..dependencies import get_db, get_current_user
from ..utils.supabase_storage import upload_blob

router = APIRouter(prefix="/vehicles", tags=["vehicles"])
settings = get_settings()
logger = logging.getLogger(__name__)


@router.get("", response_model=List[schemas.VehicleRecordOut])
def list_vehicles(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """List vehicle records with pagination."""
    return (
        db.query(models.VehicleRecord)
        .order_by(models.VehicleRecord.captured_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get("/search", response_model=List[schemas.VehicleRecordOut])
def search_vehicles(
    plate_text: Optional[str] = Query(None, description="Partial plate text match"),
    vehicle_color: Optional[str] = Query(None),
    vehicle_type: Optional[str] = Query(None),
    camera_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Search vehicle records by plate text, color, type, or camera."""
    query = db.query(models.VehicleRecord)

    if plate_text:
        query = query.filter(models.VehicleRecord.plate_text.ilike(f"%{plate_text}%"))
    if vehicle_color:
        query = query.filter(models.VehicleRecord.vehicle_color.ilike(f"%{vehicle_color}%"))
    if vehicle_type:
        query = query.filter(models.VehicleRecord.vehicle_type.ilike(f"%{vehicle_type}%"))
    if camera_id:
        query = query.filter(models.VehicleRecord.camera_id == camera_id)

    return query.order_by(models.VehicleRecord.captured_at.desc()).offset(offset).limit(limit).all()


@router.get("/{vehicle_id}", response_model=schemas.VehicleRecordOut)
def get_vehicle(
    vehicle_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get a single vehicle record."""
    record = db.query(models.VehicleRecord).filter(models.VehicleRecord.id == vehicle_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Vehicle record not found")
    return record


@router.post("/identify", response_model=List[schemas.VehicleRecordOut])
async def identify_vehicles(
    payload: schemas.VehicleIdentifyRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Submit an image for vehicle identification. Returns identified vehicles."""
    try:
        image_bytes = base64.b64decode(payload.image_data)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 image data")

    # Forward to edge vehicle-id endpoint
    edge_url = getattr(settings, "yoloworld_worker_url", "http://localhost:8001/yoloworld")
    vehicle_url = edge_url.rsplit("/", 1)[0] + "/vehicle-id/identify"

    try:
        response = requests.post(
            vehicle_url,
            files={"image": ("frame.jpg", image_bytes, "image/jpeg")},
            timeout=120,
        )
        response.raise_for_status()
        result = response.json()
    except requests.RequestException as e:
        logger.error(f"Vehicle ID request failed: {e}")
        raise HTTPException(status_code=502, detail=f"Edge vehicle ID service error: {e}")

    # Upload image to storage
    blob_name = f"vehicle-id/{uuid.uuid4()}.jpg"
    try:
        image_url = upload_blob(settings.supabase_storage_bucket, blob_name, image_bytes, "image/jpeg")
    except Exception:
        image_url = None

    # Save vehicle records to DB
    records = []
    for v in result.get("vehicles", []):
        record = models.VehicleRecord(
            detector_id=payload.detector_id,
            plate_text=v.get("plate_text"),
            vehicle_color=v.get("vehicle_color"),
            vehicle_type=v.get("vehicle_type"),
            vehicle_make_model=v.get("vehicle_make_model"),
            confidence=v.get("confidence", 0.0),
            bbox=v.get("bbox"),
            plate_bbox=v.get("plate_bbox"),
            image_url=image_url,
            camera_id=payload.camera_id,
        )
        db.add(record)
        records.append(record)

    db.commit()
    for r in records:
        db.refresh(r)

    return records
