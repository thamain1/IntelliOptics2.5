"""
Detector Alerting Utilities

This module handles the logic for triggering detector-based alerts.
Called after a query result is processed to determine if an alert should be sent.
Supports consecutive count logic (e.g., "YES 2 times in a row"), email, SMS, and webhook alerts.
"""
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from sqlalchemy.orm import Session
from jinja2 import Template

from .. import models
from ..config import get_settings

logger = logging.getLogger(__name__)

# Load email template
TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


def get_email_template() -> str:
    """Load the alert email HTML template."""
    template_path = TEMPLATE_DIR / "alert_email.html"
    if template_path.exists():
        return template_path.read_text()
    # Fallback to simple template
    return """
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #1a1a2e; color: white; padding: 20px;">
        <h2>IntelliOptics Alert</h2>
        <h3>{{ alert_title }}</h3>
        {% if image_url %}<img src="{{ image_url }}" style="max-width: 400px;">{% endif %}
        <p><strong>Detector:</strong> {{ detector_name }}</p>
        <p><strong>Detection:</strong> {{ detection_label }} ({{ confidence }}%)</p>
        <p><strong>Time:</strong> {{ timestamp }}</p>
    </body>
    </html>
    """


def check_consecutive_matches(
    detector_id: str,
    result_label: str,
    required_count: int,
    db: Session
) -> bool:
    """
    Check if the required number of consecutive matches has been reached.

    Args:
        detector_id: UUID of the detector
        result_label: The label to check for consecutive matches
        required_count: Number of consecutive matches required
        db: Database session

    Returns:
        True if consecutive count requirement is met
    """
    if required_count <= 1:
        return True

    # Get the last N queries for this detector
    recent_queries = db.query(models.Query).filter(
        models.Query.detector_id == detector_id
    ).order_by(models.Query.created_at.desc()).limit(required_count).all()

    if len(recent_queries) < required_count:
        return False

    # Check if all have the same label
    for query in recent_queries:
        if query.result != result_label:
            return False

    return True


def check_time_window_matches(
    detector_id: str,
    result_label: str,
    required_count: int,
    time_window_minutes: int,
    db: Session
) -> bool:
    """
    Check if required number of matches occurred within time window.

    Args:
        detector_id: UUID of the detector
        result_label: The label to check for
        required_count: Number of matches required
        time_window_minutes: Time window in minutes
        db: Database session

    Returns:
        True if count requirement is met within time window
    """
    cutoff_time = datetime.utcnow() - timedelta(minutes=time_window_minutes)

    count = db.query(models.Query).filter(
        models.Query.detector_id == detector_id,
        models.Query.result == result_label,
        models.Query.created_at >= cutoff_time
    ).count()

    return count >= required_count


def should_trigger_alert(
    detector_id: str,
    result_label: str,
    confidence: float,
    db: Session
) -> bool:
    """
    Check if alert should be triggered based on detector alert configuration.

    Args:
        detector_id: UUID of the detector
        result_label: Detection result label (e.g., "YES", "Person", "Defect")
        confidence: Detection confidence score (0-1)
        db: Database session

    Returns:
        True if alert should be triggered, False otherwise
    """
    # Get alert config for this detector
    config = db.query(models.DetectorAlertConfig).filter(
        models.DetectorAlertConfig.detector_id == detector_id
    ).first()

    if not config or not config.enabled:
        return False

    # Check base condition
    condition_met = False

    if config.condition_type == "ALWAYS":
        condition_met = True

    elif config.condition_type == "LABEL_MATCH":
        # Alert if label matches the configured value
        if config.condition_value:
            condition_met = result_label.upper() == config.condition_value.upper()

    elif config.condition_type == "CONFIDENCE_ABOVE":
        # Alert if confidence exceeds threshold
        if config.condition_value:
            try:
                threshold = float(config.condition_value)
                condition_met = confidence >= threshold
            except ValueError:
                logger.error(f"Invalid confidence threshold: {config.condition_value}")
                return False

    elif config.condition_type == "CONFIDENCE_BELOW":
        # Alert if confidence is below threshold
        if config.condition_value:
            try:
                threshold = float(config.condition_value)
                condition_met = confidence < threshold
            except ValueError:
                logger.error(f"Invalid confidence threshold: {config.condition_value}")
                return False

    if not condition_met:
        return False

    # Check consecutive count requirement
    consecutive_count = config.consecutive_count or 1
    time_window = getattr(config, 'time_window_minutes', None)

    if time_window and time_window > 0:
        # Use time window mode
        if not check_time_window_matches(
            detector_id, result_label, consecutive_count, time_window, db
        ):
            logger.debug(f"Time window count not met: need {consecutive_count} in {time_window} minutes")
            return False
    elif consecutive_count > 1:
        # Use consecutive mode
        if not check_consecutive_matches(detector_id, result_label, consecutive_count, db):
            logger.debug(f"Consecutive count not met: need {consecutive_count} consecutive")
            return False

    return True


def check_cooldown(
    detector_id: str,
    cooldown_minutes: int,
    db: Session
) -> bool:
    """
    Check if cooldown period has passed since last alert.

    Args:
        detector_id: UUID of the detector
        cooldown_minutes: Cooldown period in minutes
        db: Database session

    Returns:
        True if cooldown has passed (can send alert), False otherwise
    """
    cutoff_time = datetime.utcnow() - timedelta(minutes=cooldown_minutes)

    # Get most recent alert for this detector
    last_alert = db.query(models.DetectorAlert).filter(
        models.DetectorAlert.detector_id == detector_id,
        models.DetectorAlert.created_at > cutoff_time
    ).order_by(models.DetectorAlert.created_at.desc()).first()

    # If no recent alert, cooldown has passed
    return last_alert is None


def create_alert_message(
    detector_name: str,
    result_label: str,
    confidence: float,
    camera_name: Optional[str],
    custom_message: Optional[str]
) -> str:
    """
    Create alert message from template or default format.

    Args:
        detector_name: Name of the detector
        result_label: Detection result label
        confidence: Detection confidence score
        camera_name: Name of the camera (if applicable)
        custom_message: Custom message template (optional)

    Returns:
        Formatted alert message
    """
    if custom_message:
        # Replace placeholders in custom message
        message = custom_message
        message = message.replace("{detector_name}", detector_name)
        message = message.replace("{label}", result_label)
        message = message.replace("{confidence}", f"{confidence:.2%}")
        if camera_name:
            message = message.replace("{camera_name}", camera_name)
        return message

    # Default message format
    base_message = f"Alert: {detector_name} detected '{result_label}' (confidence: {confidence:.2%})"

    if camera_name:
        base_message += f" on camera '{camera_name}'"

    return base_message


def render_email_html(
    alert_title: str,
    detector_name: str,
    detection_label: str,
    confidence: float,
    camera_name: Optional[str] = None,
    location: Optional[str] = None,
    query_id: Optional[str] = None,
    image_url: Optional[str] = None,
    severity: str = "warning",
    custom_message: Optional[str] = None,
    logo_url: Optional[str] = None
) -> str:
    """
    Render the HTML email template with alert data.

    Args:
        alert_title: Main alert title
        detector_name: Name of the detector
        detection_label: Detection result label
        confidence: Confidence score (0-1)
        camera_name: Optional camera name
        location: Optional location string
        query_id: Optional query ID
        image_url: Optional detection image URL
        severity: Alert severity (critical, warning, info)
        custom_message: Optional custom message
        logo_url: Optional logo URL

    Returns:
        Rendered HTML string
    """
    template_str = get_email_template()
    template = Template(template_str)

    # Default logo URL (from Azure Blob Storage)
    if not logo_url:
        logo_url = "https://uwhbbnouxmpounqeudiw.supabase.co/storage/v1/object/public/images/branding/logo.png"

    return template.render(
        alert_title=alert_title,
        detector_name=detector_name,
        detection_label=detection_label,
        confidence=int(confidence * 100),
        camera_name=camera_name,
        location=location,
        query_id=query_id,
        image_url=image_url,
        severity=severity,
        custom_message=custom_message,
        logo_url=logo_url,
        timestamp=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    )


def send_alert_emails(
    recipients: list[str],
    subject: str,
    html_content: str,
) -> bool:
    """
    Send alert emails to recipients using SendGrid.

    Args:
        recipients: List of email addresses
        subject: Email subject
        html_content: HTML email body

    Returns:
        True if email was sent successfully
    """
    if not recipients:
        logger.warning("No recipients configured for alert")
        return False

    settings = get_settings()
    api_key = settings.alert.sendgrid_api_key
    from_email = settings.alert.from_email

    if not api_key:
        logger.warning("SendGrid API key not configured - email not sent")
        return False

    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail, Email, To, Content

        sg = SendGridAPIClient(api_key)

        message = Mail(
            from_email=Email(from_email),
            to_emails=[To(addr) for addr in recipients],
            subject=subject,
            html_content=html_content
        )

        response = sg.send(message)
        logger.info(f"Sent alert email to {recipients}, status: {response.status_code}")
        return response.status_code in [200, 201, 202]

    except ImportError:
        logger.error("SendGrid library not installed")
        return False
    except Exception as e:
        logger.error(f"Failed to send email via SendGrid: {e}")
        return False


def send_alert_sms(
    phone_numbers: list[str],
    message: str,
    image_url: Optional[str] = None,
    include_image: bool = True
) -> bool:
    """
    Send SMS alerts using Twilio.

    Args:
        phone_numbers: List of phone numbers in E.164 format
        message: SMS message text
        image_url: Optional image URL for MMS
        include_image: Whether to include image (MMS)

    Returns:
        True if SMS was sent successfully
    """
    if not phone_numbers:
        return False

    settings = get_settings()
    account_sid = settings.alert.twilio_account_sid
    auth_token = settings.alert.twilio_auth_token
    from_phone = settings.alert.alert_phone_from

    if not all([account_sid, auth_token, from_phone]):
        logger.warning("Twilio credentials not configured - SMS not sent")
        return False

    try:
        from twilio.rest import Client

        client = Client(account_sid, auth_token)

        for phone in phone_numbers:
            kwargs = {
                "from_": from_phone,
                "to": phone,
                "body": message
            }

            # Add image for MMS (US numbers only)
            if include_image and image_url and phone.startswith("+1"):
                kwargs["media_url"] = [image_url]

            client.messages.create(**kwargs)
            logger.info(f"Sent SMS alert to {phone}")

        return True

    except ImportError:
        logger.error("Twilio library not installed")
        return False
    except Exception as e:
        logger.error(f"Failed to send SMS via Twilio: {e}")
        return False


def trigger_detector_alert(
    detector_id: str,
    query_id: str,
    result_label: str,
    confidence: float,
    camera_name: Optional[str],
    image_blob_path: Optional[str],
    db: Session
) -> Optional[str]:
    """
    Main function to trigger a detector alert.

    This function:
    1. Checks if alert should be triggered based on configuration
    2. Checks cooldown period
    3. Creates alert record
    4. Sends email and SMS notifications

    Args:
        detector_id: UUID of the detector
        query_id: UUID of the query that triggered the alert
        result_label: Detection result label
        confidence: Detection confidence score
        camera_name: Name of the camera (if applicable)
        image_blob_path: Path to detection image in blob storage
        db: Database session

    Returns:
        Alert ID if alert was created, None otherwise
    """
    # Get detector
    detector = db.query(models.Detector).filter(
        models.Detector.id == detector_id
    ).first()

    if not detector:
        logger.error(f"Detector not found: {detector_id}")
        return None

    # Get alert config
    config = db.query(models.DetectorAlertConfig).filter(
        models.DetectorAlertConfig.detector_id == detector_id
    ).first()

    if not config or not config.enabled:
        return None

    # Check if alert should be triggered
    if not should_trigger_alert(detector_id, result_label, confidence, db):
        logger.debug(f"Alert conditions not met for detector {detector.name}")
        return None

    # Check cooldown period
    if not check_cooldown(detector_id, config.cooldown_minutes, db):
        logger.info(f"Cooldown period active for detector {detector.name}, skipping alert")
        return None

    # Create alert message
    message = create_alert_message(
        detector_name=detector.name,
        result_label=result_label,
        confidence=confidence,
        camera_name=camera_name,
        custom_message=config.custom_message
    )

    # Generate image URL from blob path
    image_url = None
    if image_blob_path:
        settings = get_settings()
        # Construct public URL (adjust based on your blob storage setup)
        image_url = f"https://uwhbbnouxmpounqeudiw.supabase.co/storage/v1/object/public/images/{image_blob_path}"

    # Create alert record
    sent_to = (config.alert_emails or []) + (config.alert_phones or [])

    alert = models.DetectorAlert(
        detector_id=detector_id,
        query_id=query_id,
        alert_type="DETECTION",
        severity=config.severity,
        message=message,
        detection_label=result_label,
        detection_confidence=confidence,
        camera_name=camera_name,
        image_blob_path=image_blob_path,
        sent_to=sent_to,
        email_sent=False
    )

    db.add(alert)
    db.commit()
    db.refresh(alert)

    logger.info(f"Created alert {alert.id} for detector {detector.name}")

    # Determine alert title
    alert_name = getattr(config, 'alert_name', None) or f"{detector.name} Alert"
    alert_title = f"{result_label} detected" if result_label else alert_name

    # Send email notifications
    if config.alert_emails:
        try:
            subject = f"[{config.severity.upper()}] {alert_name}"

            # Render HTML email
            include_image = getattr(config, 'include_image', True)
            html_content = render_email_html(
                alert_title=alert_title,
                detector_name=detector.name,
                detection_label=result_label,
                confidence=confidence,
                camera_name=camera_name,
                query_id=query_id,
                image_url=image_url if include_image else None,
                severity=config.severity,
                custom_message=config.custom_message
            )

            if send_alert_emails(config.alert_emails, subject, html_content):
                alert.email_sent = True
                alert.email_sent_at = datetime.utcnow()
                db.commit()

        except Exception as e:
            logger.error(f"Failed to send alert emails: {e}")

    # Send SMS notifications
    alert_phones = getattr(config, 'alert_phones', [])
    if alert_phones:
        try:
            sms_message = f"IntelliOptics Alert: {message}"
            include_image_sms = getattr(config, 'include_image_sms', True)

            send_alert_sms(
                phone_numbers=alert_phones,
                message=sms_message,
                image_url=image_url,
                include_image=include_image_sms
            )

        except Exception as e:
            logger.error(f"Failed to send SMS alerts: {e}")

    return str(alert.id)
