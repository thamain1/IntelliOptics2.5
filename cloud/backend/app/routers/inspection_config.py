"""
Inspection configuration endpoints for camera health monitoring system.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/inspection-config", tags=["Inspection Config"])


@router.get("", response_model=schemas.InspectionConfigOut)
def get_inspection_config(
    organization_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get current inspection configuration.
    If no config exists, returns default configuration.
    """
    query = db.query(models.InspectionConfig)

    if organization_id:
        query = query.filter(models.InspectionConfig.organization_id == organization_id)

    config = query.first()

    if not config:
        # Return default configuration
        config = models.InspectionConfig(
            inspection_interval_minutes=60,
            offline_threshold_minutes=5,
            fps_drop_threshold_pct=0.5,
            latency_threshold_ms=1000,
            view_change_threshold=0.7,
            alert_emails=[],
            dashboard_retention_days=30,
            database_retention_days=90
        )
        db.add(config)
        db.commit()
        db.refresh(config)

    return config


@router.put("", response_model=schemas.InspectionConfigOut)
def update_inspection_config(
    config_update: schemas.InspectionConfigUpdate,
    organization_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Update inspection configuration."""
    query = db.query(models.InspectionConfig)

    if organization_id:
        query = query.filter(models.InspectionConfig.organization_id == organization_id)

    config = query.first()

    if not config:
        # Create new configuration
        config_data = config_update.model_dump(exclude_unset=True)
        if organization_id:
            config_data["organization_id"] = organization_id

        config = models.InspectionConfig(**config_data)
        db.add(config)
    else:
        # Update existing configuration
        for key, value in config_update.model_dump(exclude_unset=True).items():
            setattr(config, key, value)

    db.commit()
    db.refresh(config)
    return config
