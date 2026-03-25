"""
Detector Alerts Router - Manage detector-based alerting

This router handles configuration and history for detector-based alerts.
Examples:
- Person detected in restricted area → Alert security team
- Defect detected → Alert QA team
- Fire detected → Alert safety team
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc
from typing import List, Optional
from datetime import datetime, timedelta

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/detectors", tags=["Detector Alerts"])


@router.get("/{detector_id}/alert-config", response_model=schemas.DetectorAlertConfigOut)
def get_detector_alert_config(
    detector_id: str,
    db: Session = Depends(get_db)
):
    """
    Get alert configuration for a detector.
    Creates default config if not exists.
    """
    # Check detector exists
    detector = db.query(models.Detector).filter(models.Detector.id == detector_id).first()
    if not detector:
        raise HTTPException(404, "Detector not found")

    # Get or create alert config
    config = db.query(models.DetectorAlertConfig).filter(
        models.DetectorAlertConfig.detector_id == detector_id
    ).first()

    if not config:
        # Create default config
        config = models.DetectorAlertConfig(
            detector_id=detector_id,
            enabled=False,
            alert_name=f"Alert for {detector.name}",
            condition_type="LABEL_MATCH",
            condition_value="YES",
            consecutive_count=1,
            time_window_minutes=None,
            confirm_with_cloud=False,
            alert_emails=[],
            alert_phones=[],
            include_image_sms=True,
            alert_webhooks=[],
            webhook_template=None,
            webhook_headers=None,
            severity="warning",
            cooldown_minutes=5,
            include_image=True,
            custom_message=None
        )
        db.add(config)
        db.commit()
        db.refresh(config)

    return schemas.DetectorAlertConfigOut.model_validate(config)


@router.put("/{detector_id}/alert-config", response_model=schemas.DetectorAlertConfigOut)
def update_detector_alert_config(
    detector_id: str,
    config_update: schemas.DetectorAlertConfigUpdate,
    db: Session = Depends(get_db)
):
    """Update alert configuration for a detector."""
    # Check detector exists
    detector = db.query(models.Detector).filter(models.Detector.id == detector_id).first()
    if not detector:
        raise HTTPException(404, "Detector not found")

    # Get or create config
    config = db.query(models.DetectorAlertConfig).filter(
        models.DetectorAlertConfig.detector_id == detector_id
    ).first()

    if not config:
        # Create new config with provided values
        config = models.DetectorAlertConfig(
            detector_id=detector_id,
            enabled=config_update.enabled if config_update.enabled is not None else False,
            alert_name=config_update.alert_name or f"Alert for {detector.name}",
            condition_type=config_update.condition_type or "LABEL_MATCH",
            condition_value=config_update.condition_value,
            consecutive_count=config_update.consecutive_count or 1,
            time_window_minutes=config_update.time_window_minutes,
            confirm_with_cloud=config_update.confirm_with_cloud or False,
            alert_emails=config_update.alert_emails or [],
            alert_phones=config_update.alert_phones or [],
            include_image_sms=config_update.include_image_sms if config_update.include_image_sms is not None else True,
            alert_webhooks=config_update.alert_webhooks or [],
            webhook_template=config_update.webhook_template,
            webhook_headers=config_update.webhook_headers,
            severity=config_update.severity or "warning",
            cooldown_minutes=config_update.cooldown_minutes or 5,
            include_image=config_update.include_image if config_update.include_image is not None else True,
            custom_message=config_update.custom_message
        )
        db.add(config)
    else:
        # Update existing config
        if config_update.enabled is not None:
            config.enabled = config_update.enabled
        if config_update.alert_name is not None:
            config.alert_name = config_update.alert_name
        if config_update.condition_type is not None:
            config.condition_type = config_update.condition_type
        if config_update.condition_value is not None:
            config.condition_value = config_update.condition_value
        if config_update.consecutive_count is not None:
            config.consecutive_count = config_update.consecutive_count
        if config_update.time_window_minutes is not None:
            config.time_window_minutes = config_update.time_window_minutes
        if config_update.confirm_with_cloud is not None:
            config.confirm_with_cloud = config_update.confirm_with_cloud
        if config_update.alert_emails is not None:
            config.alert_emails = config_update.alert_emails
        if config_update.alert_phones is not None:
            config.alert_phones = config_update.alert_phones
        if config_update.include_image_sms is not None:
            config.include_image_sms = config_update.include_image_sms
        if config_update.alert_webhooks is not None:
            config.alert_webhooks = config_update.alert_webhooks
        if config_update.webhook_template is not None:
            config.webhook_template = config_update.webhook_template
        if config_update.webhook_headers is not None:
            config.webhook_headers = config_update.webhook_headers
        if config_update.severity is not None:
            config.severity = config_update.severity
        if config_update.cooldown_minutes is not None:
            config.cooldown_minutes = config_update.cooldown_minutes
        if config_update.include_image is not None:
            config.include_image = config_update.include_image
        if config_update.custom_message is not None:
            config.custom_message = config_update.custom_message

        config.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(config)

    return schemas.DetectorAlertConfigOut.model_validate(config)


@router.get("/{detector_id}/alerts", response_model=List[schemas.DetectorAlertOut])
def get_detector_alerts(
    detector_id: str,
    limit: int = 50,
    acknowledged: Optional[bool] = None,
    severity: Optional[str] = None,
    days: int = 30,
    db: Session = Depends(get_db)
):
    """
    Get alert history for a specific detector.

    Args:
        detector_id: Detector UUID
        limit: Maximum number of alerts to return
        acknowledged: Filter by acknowledged status (true/false/null for all)
        severity: Filter by severity (critical/warning/info)
        days: How many days of history to return (default 30)
    """
    # Check detector exists
    detector = db.query(models.Detector).filter(models.Detector.id == detector_id).first()
    if not detector:
        raise HTTPException(404, "Detector not found")

    cutoff_date = datetime.utcnow() - timedelta(days=days)

    query = db.query(models.DetectorAlert).filter(
        models.DetectorAlert.detector_id == detector_id,
        models.DetectorAlert.created_at >= cutoff_date
    )

    # Apply filters
    if acknowledged is not None:
        query = query.filter(models.DetectorAlert.acknowledged == acknowledged)

    if severity:
        query = query.filter(models.DetectorAlert.severity == severity)

    # Order by most recent first
    query = query.order_by(desc(models.DetectorAlert.created_at))

    # Apply limit
    alerts = query.limit(limit).all()

    return [schemas.DetectorAlertOut.model_validate(alert) for alert in alerts]


# Global detector alerts endpoints
@router.get("/alerts/all", response_model=List[schemas.DetectorAlertOut])
def get_all_detector_alerts(
    limit: int = 100,
    acknowledged: Optional[bool] = None,
    severity: Optional[str] = None,
    detector_id: Optional[str] = None,
    days: int = 7,
    db: Session = Depends(get_db)
):
    """
    Get all detector alerts across all detectors.

    Args:
        limit: Maximum number of alerts to return
        acknowledged: Filter by acknowledged status
        severity: Filter by severity
        detector_id: Filter by specific detector
        days: How many days of history (default 7)
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    query = db.query(models.DetectorAlert).filter(
        models.DetectorAlert.created_at >= cutoff_date
    )

    # Apply filters
    if acknowledged is not None:
        query = query.filter(models.DetectorAlert.acknowledged == acknowledged)

    if severity:
        query = query.filter(models.DetectorAlert.severity == severity)

    if detector_id:
        query = query.filter(models.DetectorAlert.detector_id == detector_id)

    # Order by most recent first
    query = query.order_by(desc(models.DetectorAlert.created_at))

    # Apply limit
    alerts = query.limit(limit).all()

    return [schemas.DetectorAlertOut.model_validate(alert) for alert in alerts]


@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge_detector_alert(
    alert_id: str,
    request: schemas.AcknowledgeAlertRequest,
    db: Session = Depends(get_db)
):
    """Acknowledge a detector alert."""
    alert = db.query(models.DetectorAlert).filter(
        models.DetectorAlert.id == alert_id
    ).first()

    if not alert:
        raise HTTPException(404, "Alert not found")

    if alert.acknowledged:
        return {"message": "Alert already acknowledged"}

    alert.acknowledged = True
    alert.acknowledged_at = datetime.utcnow()
    if request.acknowledged_by:
        alert.acknowledged_by = request.acknowledged_by

    db.commit()

    return {"message": "Alert acknowledged", "alert_id": alert_id}


@router.get("/alerts/summary")
def get_detector_alerts_summary(
    days: int = 7,
    db: Session = Depends(get_db)
):
    """
    Get summary statistics for detector alerts.

    Returns counts by severity, acknowledgment status, and per detector.
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    alerts = db.query(models.DetectorAlert).filter(
        models.DetectorAlert.created_at >= cutoff_date
    ).all()

    # Calculate summary
    total = len(alerts)
    acknowledged = sum(1 for a in alerts if a.acknowledged)
    unacknowledged = total - acknowledged

    by_severity = {
        "critical": sum(1 for a in alerts if a.severity == "critical"),
        "warning": sum(1 for a in alerts if a.severity == "warning"),
        "info": sum(1 for a in alerts if a.severity == "info")
    }

    # Count by detector
    by_detector = {}
    for alert in alerts:
        detector_id = str(alert.detector_id)
        if detector_id not in by_detector:
            by_detector[detector_id] = 0
        by_detector[detector_id] += 1

    return {
        "total": total,
        "acknowledged": acknowledged,
        "unacknowledged": unacknowledged,
        "by_severity": by_severity,
        "by_detector": by_detector,
        "period_days": days
    }
