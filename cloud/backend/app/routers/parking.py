"""API endpoints for Maven Parking application."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..dependencies import get_db, get_current_user

router = APIRouter(prefix="/parking", tags=["parking"])
logger = logging.getLogger(__name__)


# ==================== Zones ====================

@router.get("/zones", response_model=List[schemas.ParkingZoneOut])
def list_zones(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """List all parking zones with current occupancy."""
    return db.query(models.ParkingZone).order_by(models.ParkingZone.name).all()


@router.post("/zones", response_model=schemas.ParkingZoneOut, status_code=201)
def create_zone(
    payload: schemas.ParkingZoneCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Create a new parking zone."""
    zone = models.ParkingZone(
        name=payload.name,
        camera_id=payload.camera_id,
        max_capacity=payload.max_capacity,
        zone_type=payload.zone_type,
    )
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return zone


@router.get("/zones/{zone_id}", response_model=schemas.ParkingZoneOut)
def get_zone(
    zone_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get a specific parking zone."""
    zone = db.query(models.ParkingZone).filter(models.ParkingZone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    return zone


@router.delete("/zones/{zone_id}", status_code=204)
def delete_zone(
    zone_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Delete a parking zone."""
    zone = db.query(models.ParkingZone).filter(models.ParkingZone.id == zone_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    db.delete(zone)
    db.commit()


# ==================== Events ====================

@router.get("/events", response_model=List[schemas.ParkingEventOut])
def list_events(
    zone_id: str = Query(None),
    event_type: str = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """List parking events with optional filters."""
    query = db.query(models.ParkingEvent)

    if zone_id:
        query = query.filter(models.ParkingEvent.zone_id == zone_id)
    if event_type:
        query = query.filter(models.ParkingEvent.event_type == event_type)

    return query.order_by(models.ParkingEvent.timestamp.desc()).limit(limit).all()


# ==================== Violations ====================

@router.get("/violations", response_model=List[schemas.ParkingViolationOut])
def list_violations(
    resolved: bool = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """List parking violations."""
    query = db.query(models.ParkingViolation)

    if resolved is not None:
        query = query.filter(models.ParkingViolation.resolved == resolved)

    return query.order_by(models.ParkingViolation.created_at.desc()).limit(limit).all()


@router.post("/violations/{violation_id}/resolve", response_model=schemas.ParkingViolationOut)
def resolve_violation(
    violation_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Mark a violation as resolved."""
    violation = db.query(models.ParkingViolation).filter(models.ParkingViolation.id == violation_id).first()
    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found")

    violation.resolved = True
    violation.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(violation)
    return violation


# ==================== Dashboard ====================

@router.get("/dashboard", response_model=schemas.ParkingDashboardOut)
def get_dashboard(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get parking dashboard summary with zone occupancy and recent events."""
    zones = db.query(models.ParkingZone).order_by(models.ParkingZone.name).all()

    total_capacity = sum(z.max_capacity for z in zones)
    total_occupied = sum(z.current_occupancy for z in zones)
    occupancy_pct = (total_occupied / total_capacity * 100) if total_capacity > 0 else 0.0

    recent_events = (
        db.query(models.ParkingEvent)
        .order_by(models.ParkingEvent.timestamp.desc())
        .limit(20)
        .all()
    )

    active_violations = (
        db.query(models.ParkingViolation)
        .filter(models.ParkingViolation.resolved == False)
        .count()
    )

    return schemas.ParkingDashboardOut(
        total_zones=len(zones),
        total_capacity=total_capacity,
        total_occupied=total_occupied,
        occupancy_pct=occupancy_pct,
        zones=zones,
        recent_events=recent_events,
        active_violations=active_violations,
    )
