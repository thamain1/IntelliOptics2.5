"""API endpoints for managing global settings."""
from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field # Added for local TestAlertPayload

from .. import models, schemas
from ..dependencies import get_db, get_current_admin
from ..utils.alerts import SendGridAlertService


router = APIRouter(prefix="/settings", tags=["settings"])

# Local Pydantic model for the test alert request
class TestAlertPayload(BaseModel):
    recipient_email: str = Field(..., description="Email address to send the test alert to")
    template_name: str = Field(..., description="Name of the alert template to test (e.g., 'low_confidence', 'camera_health')")


@router.get("/alerts", response_model=schemas.AlertSettingsOut)
def get_alert_settings(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """
    Retrieve the global alert settings.
    If no settings exist, a default one is created and returned.
    """
    settings_db = db.query(models.AlertSettings).first()
    if not settings_db:
        settings_db = models.AlertSettings()
        db.add(settings_db)
        db.commit()
        db.refresh(settings_db)
    return settings_db


@router.put("/alerts", response_model=schemas.AlertSettingsOut)
def update_alert_settings(
    alert_settings_update: schemas.AlertSettingsUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """
    Update the global alert settings.
    If no settings exist, a new one is created.
    """
    settings_db = db.query(models.AlertSettings).first()
    if not settings_db:
        settings_db = models.AlertSettings()
        db.add(settings_db)

    update_data = alert_settings_update.dict(exclude_unset=True)
    
    # Manually update JSONB fields to ensure correct merging or replacement
    if 'recipients' in update_data:
        settings_db.recipients = update_data.pop('recipients')
    if 'triggers' in update_data:
        settings_db.triggers = update_data.pop('triggers')
    if 'batching' in update_data:
        settings_db.batching = update_data.pop('batching')
    if 'rate_limiting' in update_data:
        settings_db.rate_limiting = update_data.pop('rate_limiting')

    for key, value in update_data.items():
        setattr(settings_db, key, value)

    db.commit()
    db.refresh(settings_db)
    return settings_db


@router.post("/alerts/test", status_code=status.HTTP_200_OK)
def test_send_alert(
    test_request: TestAlertPayload, # Changed to use local payload
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """
    Send a test alert email to verify SendGrid configuration.
    """
    alert_settings = db.query(models.AlertSettings).first()
    if not alert_settings or not alert_settings.sendgrid_api_key or not alert_settings.from_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SendGrid API key and 'From' email must be configured in alert settings."
        )

    alert_service = SendGridAlertService(
        api_key=alert_settings.sendgrid_api_key,
        from_email=alert_settings.from_email
    )

    # Simplified test logic: just send a basic email
    try:
        response = alert_service.send_email(
            to_emails=[test_request.recipient_email],
            subject=f"IntelliOptics Test Alert: {test_request.template_name}",
            html_content=f"<p>This is a test alert for template: {test_request.template_name}</p><p>If you received this, your SendGrid integration is working!</p>"
        )
        if response and response.status_code == 202:
            return {"message": "Test alert sent successfully!", "status_code": response.status_code}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to send test alert: {response.body.decode() if response else 'Unknown error'}"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error sending test alert: {str(e)}"
        )
