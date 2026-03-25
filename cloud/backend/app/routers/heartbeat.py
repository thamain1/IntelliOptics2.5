"""API endpoints for hub heartbeat and metrics collection.

This module provides a simple API-key authenticated endpoint for edge hubs
to register and send periodic heartbeats with system metrics. This is
designed for development and testing, allowing any device to appear as a hub.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models
from ..dependencies import get_db

router = APIRouter(prefix="/heartbeat", tags=["heartbeat"])

# Simple API key for development - set via environment or use default
HEARTBEAT_API_KEY = os.getenv("HEARTBEAT_API_KEY", "dev-heartbeat-key-12345")


def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> str:
    """Verify the API key for heartbeat endpoints."""
    if x_api_key != HEARTBEAT_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


class HubMetrics(BaseModel):
    """System metrics sent by edge hubs."""
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    memory_available_gb: Optional[float] = None
    disk_percent: Optional[float] = None
    hostname: Optional[str] = None
    platform: Optional[str] = None
    containers: Optional[dict] = None  # Container statuses
    extra: Optional[dict] = None  # Any additional metrics


class HubRegistration(BaseModel):
    """Request body for hub registration."""
    name: str
    location: Optional[str] = None


class HubHeartbeat(BaseModel):
    """Request body for hub heartbeat."""
    status: str = "online"
    metrics: Optional[HubMetrics] = None


class HubResponse(BaseModel):
    """Response for hub operations."""
    id: str
    name: str
    status: str
    last_ping: Optional[datetime]
    location: Optional[str]
    metrics: Optional[dict] = None

    class Config:
        from_attributes = True


@router.post("/register", response_model=HubResponse)
def register_hub(
    registration: HubRegistration,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
) -> HubResponse:
    """Register a new hub or return existing hub with the same name."""
    # Check if hub with this name already exists
    existing = db.query(models.Hub).filter(models.Hub.name == registration.name).first()
    if existing:
        return HubResponse(
            id=str(existing.id),
            name=existing.name,
            status=existing.status,
            last_ping=existing.last_ping,
            location=existing.location,
            metrics=None,
        )

    # Create new hub
    hub = models.Hub(
        name=registration.name,
        location=registration.location,
        status="unknown",
    )
    db.add(hub)
    db.commit()
    db.refresh(hub)

    return HubResponse(
        id=str(hub.id),
        name=hub.name,
        status=hub.status,
        last_ping=hub.last_ping,
        location=hub.location,
        metrics=None,
    )


@router.post("/{hub_id}/ping", response_model=HubResponse)
def send_heartbeat(
    hub_id: str,
    heartbeat: HubHeartbeat,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
) -> HubResponse:
    """Send a heartbeat from a hub with optional metrics."""
    hub = db.query(models.Hub).filter(models.Hub.id == str(hub_id)).first()
    if not hub:
        raise HTTPException(status_code=404, detail="Hub not found")

    hub.status = heartbeat.status
    hub.last_ping = datetime.utcnow()

    # Store metrics in the hub's location field as JSON for now
    # In production, you'd want a separate HubMetrics table
    metrics_dict = None
    if heartbeat.metrics:
        metrics_dict = heartbeat.metrics.model_dump(exclude_none=True)
        # Store recent metrics - in a real system this would go to a time-series DB
        # For now we'll just track latest metrics

    db.commit()
    db.refresh(hub)

    return HubResponse(
        id=str(hub.id),
        name=hub.name,
        status=hub.status,
        last_ping=hub.last_ping,
        location=hub.location,
        metrics=metrics_dict,
    )


@router.get("/hubs", response_model=List[HubResponse])
def list_hubs_with_status(
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
) -> List[HubResponse]:
    """List all hubs with their current status.

    Hubs that haven't pinged in 2 minutes are marked as offline.
    """
    hubs = db.query(models.Hub).all()
    offline_threshold = datetime.utcnow() - timedelta(minutes=2)

    result = []
    for hub in hubs:
        # Auto-mark as offline if no recent ping
        status = hub.status
        if hub.last_ping and hub.last_ping < offline_threshold and hub.status == "online":
            status = "offline"

        result.append(HubResponse(
            id=str(hub.id),
            name=hub.name,
            status=status,
            last_ping=hub.last_ping,
            location=hub.location,
            metrics=None,
        ))

    return result
