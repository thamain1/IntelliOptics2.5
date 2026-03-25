"""API endpoints for managing deployments to edge hubs."""
from __future__ import annotations

import uuid
import yaml
from typing import List, Optional # Add Optional

from fastapi import APIRouter, Depends, HTTPException, status, Response # Add Response
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..dependencies import get_db, get_current_admin, get_current_user # Add get_current_user


router = APIRouter(prefix="/deployments", tags=["deployments"])

@router.get("", response_model=List[schemas.DeploymentOut])
def list_deployments(
    detector_id: Optional[str] = None,
    hub_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """List all deployments with optional filtering."""
    query = db.query(models.Deployment)
    if detector_id:
        query = query.filter(models.Deployment.detector_id == detector_id)
    if hub_id:
        query = query.filter(models.Deployment.hub_id == hub_id)
    return query.all()


@router.post("", response_model=schemas.DeploymentOut, status_code=status.HTTP_201_CREATED)
def create_deployment(
    payload: schemas.DeploymentCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """
    Creates a record of a deployment and generates the configuration that would be
    pushed to an edge device.
    """
    # Verify that the hub and detector exist
    hub = db.query(models.Hub).filter(models.Hub.id == payload.hub_id).first()
    if not hub:
        raise HTTPException(status_code=404, detail=f"Hub with id {payload.hub_id} not found.")
    
    detector_config = db.query(models.DetectorConfig).options(
        joinedload(models.DetectorConfig.detector)
    ).filter(models.DetectorConfig.detector_id == payload.detector_id).first()
    
    if not detector_config or not detector_config.detector:
        raise HTTPException(status_code=404, detail=f"Detector with id {payload.detector_id} not found.")

    # Generate the YAML config from the database models
    config_dict = {
        "detectors": {
            f"det_{detector_config.detector.name.lower().replace(' ', '_')}": {
                "detector_id": str(detector_config.detector_id),
                "name": detector_config.detector.name,
                "edge_inference_config": "default", # Placeholder
                "confidence_threshold": detector_config.confidence_threshold,
                "patience_time": detector_config.patience_time,
                "mode": detector_config.mode,
                "class_names": detector_config.class_names
            }
        },
        "streams": {
            camera.name.lower().replace(' ', '_'): {
                "name": camera.name,
                "detector_id": f"det_{detector_config.detector.name.lower().replace(' ', '_')}",
                "url": camera.url,
                "sampling_interval_seconds": camera.sampling_interval,
            } for camera in payload.cameras
        }
    }
    
    # In a real scenario, this would trigger a push to the edge hub.
    # For now, we just log the deployment record.
    new_deployment = models.Deployment(
        detector_id=payload.detector_id,
        hub_id=payload.hub_id,
        config=config_dict,
        status="SUCCESS",
        cameras=[c.dict() for c in payload.cameras]
    )
    db.add(new_deployment)
    db.commit()
    db.refresh(new_deployment)
    
    return new_deployment


@router.get("/generate-config", tags=["deployments"])
def generate_edge_config(
    hub_id: str,
    detector_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """
    Generates a preview of the edge-config.yaml for a given hub and detector.
    This is a read-only operation.
    """
    detector_config = db.query(models.DetectorConfig).options(
        joinedload(models.DetectorConfig.detector)
    ).filter(models.DetectorConfig.detector_id == detector_id).first()

    if not detector_config or not detector_config.detector:
        raise HTTPException(status_code=404, detail="Detector not found.")

    config_dict = {
        "detectors": {
            f"det_{detector_config.detector.name.lower().replace(' ', '_')}": {
                "detector_id": str(detector_config.detector_id),
                "name": detector_config.detector.name,
                "edge_inference_config": "default",
                "confidence_threshold": detector_config.confidence_threshold,
                "patience_time": detector_config.patience_time,
                "mode": detector_config.mode,
                "class_names": detector_config.class_names
            }
        },
        "streams": {} # Placeholder for streams as they are not stored in db yet
    }
    
    yaml_content = yaml.dump(config_dict, default_flow_style=False)
    return Response(content=yaml_content, media_type="application/x-yaml")


@router.get("/status", response_model=List[schemas.DeploymentOut])
def get_deployment_status(
    hub_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Get the deployment history and status for a specific hub or all hubs.
    """
    query = db.query(models.Deployment)
    if hub_id:
        query = query.filter(models.Deployment.hub_id == hub_id)
    
    deployments = query.order_by(models.Deployment.deployed_at.desc()).limit(50).all()
    return deployments


@router.post("/redeploy", status_code=status.HTTP_202_ACCEPTED)
def redeploy_detector(
    detector_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """
    Triggers a redeployment of the latest configuration for a detector 
    to all hubs where it is currently deployed.
    """
    # Find all hubs that have this detector deployed
    active_deployments = db.query(models.Deployment).filter(
        models.Deployment.detector_id == detector_id,
        models.Deployment.status == "SUCCESS"
    ).all()
    
    if not active_deployments:
        raise HTTPException(status_code=404, detail="No active deployments found for this detector.")
        
    # In a real scenario, this would loop through and trigger push events.
    # For now we just return the count.
    return {"message": f"Redeployment triggered for {len(active_deployments)} hubs."}
