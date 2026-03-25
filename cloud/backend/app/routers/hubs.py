"""API endpoints for hub status management."""
from __future__ import annotations

import uuid
from typing import List, Dict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..dependencies import get_db, get_current_admin, get_current_user
from datetime import datetime


router = APIRouter(prefix="/hubs", tags=["hubs"])


@router.get("", response_model=List[schemas.HubOut])
def list_hubs(db: Session = Depends(get_db), user=Depends(get_current_user)) -> List[models.Hub]:
    return db.query(models.Hub).all()


@router.post("", response_model=schemas.HubOut, status_code=201)
def create_hub(name: str, location: str | None = None, db: Session = Depends(get_db), current_user=Depends(get_current_admin)) -> models.Hub:
    hub = models.Hub(name=name, location=location)
    db.add(hub)
    db.commit()
    db.refresh(hub)
    return hub


@router.post("/{hub_id}/status", response_model=schemas.HubOut)
def update_hub_status(
    hub_id: str,
    status: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> models.Hub:
    hub = db.query(models.Hub).filter(models.Hub.id == hub_id).first()
    if not hub:
        raise HTTPException(status_code=404, detail="Hub not found")
    hub.status = status
    hub.last_ping = datetime.utcnow()
    db.commit()
    db.refresh(hub)
    return hub


@router.get("/{hub_id}/cameras", response_model=List[schemas.CameraOut])
def list_hub_cameras(
    hub_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Fetch all cameras associated with a hub."""
    hub = db.query(models.Hub).filter(models.Hub.id == hub_id).first()
    if not hub:
        raise HTTPException(status_code=404, detail="Hub not found")
    
    # Return cameras from the separate Camera table
    return db.query(models.Camera).filter(models.Camera.hub_id == hub_id).all()


@router.post("/{hub_id}/cameras", response_model=schemas.CameraOut)
def register_camera(
    hub_id: str,
    camera: schemas.CameraCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """Register a new camera to a hub."""
    hub = db.query(models.Hub).filter(models.Hub.id == hub_id).first()
    if not hub:
        raise HTTPException(status_code=404, detail="Hub not found")
        
    new_camera = models.Camera(
        hub_id=hub_id,
        name=camera.name,
        url=camera.url,
        status="active"
    )
    db.add(new_camera)
    db.commit()
    db.refresh(new_camera)
    return new_camera
