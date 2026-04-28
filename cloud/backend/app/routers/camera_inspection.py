"""
Camera inspection endpoints for health monitoring dashboard and alerts.
"""
import base64
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List, Optional
from datetime import datetime, timedelta

from .. import models, schemas
from ..database import get_db
from ..utils.frame_capture import capture_single_frame
from ..utils.supabase_storage import upload_blob
from ..config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/camera-inspection", tags=["Camera Inspection"])


class TestUrlRequest(BaseModel):
    url: str


class TestUrlResponse(BaseModel):
    ok: bool
    frame_base64: Optional[str] = None
    error: Optional[str] = None


@router.post("/cameras/test-url", response_model=TestUrlResponse)
def test_camera_url(payload: TestUrlRequest):
    """Try to grab one frame from `url` and return it as a base64-encoded JPEG.

    Used by the Add Camera modal's "Test Connection" button so the operator
    can confirm the URL/credentials are correct before saving the camera.
    Never raises — returns ok=false with an error string on failure so the
    UI can show a friendly message.
    """
    if not payload.url or not payload.url.strip():
        return TestUrlResponse(ok=False, error="URL is required")

    try:
        jpeg = capture_single_frame(payload.url.strip(), timeout_ms=8000)
    except Exception as e:
        logger.error(f"test-url capture exception: {e}", exc_info=True)
        return TestUrlResponse(ok=False, error=f"Capture error: {e}")

    if jpeg is None:
        return TestUrlResponse(
            ok=False,
            error="Could not retrieve a frame. Verify the URL, credentials, and that the demo machine can reach the camera.",
        )

    return TestUrlResponse(ok=True, frame_base64=base64.b64encode(jpeg).decode("ascii"))


@router.get("/dashboard", response_model=schemas.InspectionDashboard)
def get_inspection_dashboard(
    hub_id: Optional[str] = None,
    status_filter: Optional[str] = None,  # healthy, warning, failed
    days: int = 30,
    db: Session = Depends(get_db)
):
    """
    Get inspection dashboard data for last N days.
    Shows all cameras with their latest health status and active alerts.
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    # Get all cameras with hub information
    query = db.query(models.Camera).join(models.Hub)

    if hub_id:
        query = query.filter(models.Camera.hub_id == hub_id)

    cameras = query.all()

    # Build dashboard data
    dashboard_data = []
    for camera in cameras:
        # Get latest health record
        latest_health = db.query(models.CameraHealth).filter(
            models.CameraHealth.camera_id == camera.id,
            models.CameraHealth.timestamp >= cutoff_date
        ).order_by(models.CameraHealth.timestamp.desc()).first()

        # Get active alerts (not acknowledged, not muted)
        active_alerts = db.query(models.CameraAlert).filter(
            models.CameraAlert.camera_id == camera.id,
            models.CameraAlert.acknowledged == False,
            or_(
                models.CameraAlert.muted_until == None,
                models.CameraAlert.muted_until < datetime.utcnow()
            )
        ).order_by(models.CameraAlert.created_at.desc()).all()

        # Create camera with health data
        camera_data = schemas.InspectionDashboardCamera(
            camera=schemas.CameraWithHealthOut.model_validate(camera),
            hub_name=camera.hub.name,
            health=schemas.CameraHealthOut.model_validate(latest_health) if latest_health else None,
            alerts=[schemas.CameraAlertOut.model_validate(alert) for alert in active_alerts]
        )

        dashboard_data.append(camera_data)

    # Apply status filter
    if status_filter:
        dashboard_data = [
            d for d in dashboard_data
            if d.health and d.health.status == status_filter
        ]

    # Calculate summary stats
    total = len(dashboard_data)
    healthy = sum(1 for d in dashboard_data if d.health and d.health.status == "connected")
    warning = sum(1 for d in dashboard_data if d.health and d.health.status == "degraded")
    failed = sum(1 for d in dashboard_data if d.health and d.health.status == "offline")

    summary = schemas.InspectionDashboardSummary(
        total=total,
        healthy=healthy,
        warning=warning,
        failed=failed
    )

    return schemas.InspectionDashboard(
        summary=summary,
        cameras=dashboard_data,
        last_updated=datetime.utcnow()
    )


@router.get("/cameras/{camera_id}/history")
def get_camera_inspection_history(
    camera_id: str,
    days: int = 30,
    db: Session = Depends(get_db)
):
    """Get inspection history for a specific camera."""
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    camera = db.query(models.Camera).filter(models.Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(404, "Camera not found")

    # Get health history
    health_history = db.query(models.CameraHealth).filter(
        models.CameraHealth.camera_id == camera_id,
        models.CameraHealth.timestamp >= cutoff_date
    ).order_by(models.CameraHealth.timestamp.asc()).all()

    # Get alert history
    alert_history = db.query(models.CameraAlert).filter(
        models.CameraAlert.camera_id == camera_id,
        models.CameraAlert.created_at >= cutoff_date
    ).order_by(models.CameraAlert.created_at.desc()).all()

    return {
        "camera_id": camera_id,
        "camera_name": camera.name,
        "hub_name": camera.hub.name,
        "health_history": [schemas.CameraHealthOut.model_validate(h) for h in health_history],
        "alerts": [schemas.CameraAlertOut.model_validate(a) for a in alert_history]
    }


@router.post("/cameras/{camera_id}/mute-alerts")
def mute_camera_alerts(
    camera_id: str,
    request: schemas.MuteAlertsRequest,
    db: Session = Depends(get_db)
):
    """Mute alerts for a specific camera (1-30 days)."""
    camera = db.query(models.Camera).filter(models.Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(404, "Camera not found")

    mute_until = datetime.utcnow() + timedelta(days=request.mute_days)

    # Update all active (non-acknowledged) alerts
    updated_count = db.query(models.CameraAlert).filter(
        models.CameraAlert.camera_id == camera_id,
        models.CameraAlert.acknowledged == False
    ).update({
        "muted_until": mute_until
    })

    db.commit()

    return {
        "message": f"Alerts muted until {mute_until.isoformat()}",
        "muted_until": mute_until,
        "alerts_muted": updated_count
    }


@router.post("/cameras/{camera_id}/unmute-alerts")
def unmute_camera_alerts(
    camera_id: str,
    db: Session = Depends(get_db)
):
    """Unmute all alerts for a specific camera."""
    camera = db.query(models.Camera).filter(models.Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(404, "Camera not found")

    updated_count = db.query(models.CameraAlert).filter(
        models.CameraAlert.camera_id == camera_id
    ).update({"muted_until": None})

    db.commit()

    return {
        "message": "Alerts unmuted",
        "alerts_unmuted": updated_count
    }


@router.post("/cameras/{camera_id}/acknowledge-alert/{alert_id}")
def acknowledge_alert(
    camera_id: str,
    alert_id: str,
    db: Session = Depends(get_db)
):
    """Acknowledge a specific alert."""
    alert = db.query(models.CameraAlert).filter(
        models.CameraAlert.id == alert_id,
        models.CameraAlert.camera_id == camera_id
    ).first()

    if not alert:
        raise HTTPException(404, "Alert not found")

    alert.acknowledged = True
    alert.acknowledged_at = datetime.utcnow()
    # Note: acknowledged_by would require auth/current_user

    db.commit()

    return {"message": "Alert acknowledged"}


@router.post("/cameras/{camera_id}/update-baseline")
async def update_baseline_image(
    camera_id: str,
    db: Session = Depends(get_db)
):
    """
    Capture a fresh frame from the camera, upload it to Supabase Storage,
    and store the path on the Camera row. The inspection worker reads this
    baseline to detect view drift on subsequent runs.
    """
    camera = db.query(models.Camera).filter(models.Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(404, "Camera not found")

    if not camera.url:
        raise HTTPException(400, "Camera has no URL configured")

    jpeg = capture_single_frame(camera.url, timeout_ms=10000)
    if jpeg is None:
        raise HTTPException(
            502,
            "Could not capture a frame from the camera. Confirm the camera is reachable and the URL/credentials are correct.",
        )

    settings = get_settings()
    bucket = settings.supabase_storage_bucket or "images"
    blob_name = f"camera-baselines/{camera_id}/{uuid.uuid4().hex}.jpg"
    try:
        path = upload_blob(bucket, blob_name, jpeg, content_type="image/jpeg")
    except Exception as e:
        logger.error(f"baseline upload failed: {e}", exc_info=True)
        raise HTTPException(502, f"Storage upload failed: {e}")

    camera.baseline_image_path = path
    camera.baseline_image_updated_at = datetime.utcnow()
    camera.view_change_detected = False
    camera.view_change_detected_at = None
    db.commit()

    return {
        "message": "Baseline image captured and stored",
        "camera_id": camera_id,
        "baseline_image_path": path,
        "frame_size_bytes": len(jpeg),
    }


@router.get("/runs", response_model=List[schemas.InspectionRunOut])
def get_inspection_runs(
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """Get recent inspection runs."""
    runs = db.query(models.InspectionRun).order_by(
        models.InspectionRun.started_at.desc()
    ).limit(limit).all()

    return [schemas.InspectionRunOut.model_validate(run) for run in runs]


@router.post("/runs", response_model=schemas.InspectionRunOut)
def create_inspection_run(db: Session = Depends(get_db)):
    """Create a new inspection run (used by worker)."""
    run = models.InspectionRun(
        started_at=datetime.utcnow(),
        status="running"
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    return schemas.InspectionRunOut.model_validate(run)


@router.put("/runs/{run_id}", response_model=schemas.InspectionRunOut)
def update_inspection_run(
    run_id: str,
    total_cameras: Optional[int] = None,
    cameras_inspected: Optional[int] = None,
    cameras_healthy: Optional[int] = None,
    cameras_warning: Optional[int] = None,
    cameras_failed: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Update inspection run (used by worker to mark as completed)."""
    run = db.query(models.InspectionRun).filter(models.InspectionRun.id == run_id).first()
    if not run:
        raise HTTPException(404, "Inspection run not found")

    if total_cameras is not None:
        run.total_cameras = total_cameras
    if cameras_inspected is not None:
        run.cameras_inspected = cameras_inspected
    if cameras_healthy is not None:
        run.cameras_healthy = cameras_healthy
    if cameras_warning is not None:
        run.cameras_warning = cameras_warning
    if cameras_failed is not None:
        run.cameras_failed = cameras_failed
    if status is not None:
        run.status = status
        if status == "completed":
            run.completed_at = datetime.utcnow()

    db.commit()
    db.refresh(run)

    return schemas.InspectionRunOut.model_validate(run)


@router.post("/runs/{run_id}/stop", response_model=schemas.InspectionRunOut)
def stop_inspection_run(
    run_id: str,
    db: Session = Depends(get_db)
):
    """Stop a running inspection run."""
    run = db.query(models.InspectionRun).filter(models.InspectionRun.id == run_id).first()
    if not run:
        raise HTTPException(404, "Inspection run not found")

    if run.status != "running":
        raise HTTPException(400, f"Run is not running (status: {run.status})")

    run.status = "stopped"
    run.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(run)

    return schemas.InspectionRunOut.model_validate(run)


@router.delete("/runs/{run_id}")
def delete_inspection_run(
    run_id: str,
    db: Session = Depends(get_db)
):
    """Delete an inspection run."""
    run = db.query(models.InspectionRun).filter(models.InspectionRun.id == run_id).first()
    if not run:
        raise HTTPException(404, "Inspection run not found")

    db.delete(run)
    db.commit()

    return {"message": "Inspection run deleted"}


@router.post("/cameras/{camera_id}/health")
def create_health_record(
    camera_id: str,
    health_data: dict,  # Accept raw dict from worker
    db: Session = Depends(get_db)
):
    """Create health record for a camera (used by worker)."""
    camera = db.query(models.Camera).filter(models.Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(404, "Camera not found")

    # Create health record
    health = models.CameraHealth(
        camera_id=camera_id,
        **health_data
    )
    db.add(health)

    # Update camera's current status and health score
    camera.current_status = health_data.get("status", "unknown")
    camera.last_health_check = datetime.utcnow()

    # Calculate simple health score (0-100)
    if health_data.get("status") == "connected":
        camera.health_score = 100.0
    elif health_data.get("status") == "degraded":
        camera.health_score = 50.0
    else:
        camera.health_score = 0.0

    db.commit()

    return {"message": "Health record created", "id": str(health.id)}


@router.post("/alerts")
def create_alert(
    alert_data: dict,  # Accept raw dict from worker
    db: Session = Depends(get_db)
):
    """Create alert (used by worker)."""
    alert = models.CameraAlert(**alert_data)
    db.add(alert)
    db.commit()
    db.refresh(alert)

    return {"message": "Alert created", "id": str(alert.id)}
