"""API endpoints for creating and retrieving image queries."""
from __future__ import annotations

import uuid
import random
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .. import models, schemas
from ..dependencies import get_db, get_current_user, get_current_reviewer
from ..utils.supabase_storage import upload_blob, generate_signed_url, send_service_bus_message, delete_blob
from ..utils.alerts import send_alert_via_function
from ..utils.detector_alerting import trigger_detector_alert
from ..auth import create_fallback_token
from ..config import get_settings


router = APIRouter(prefix="/queries", tags=["queries"])
settings = get_settings()


@router.get("", response_model=schemas.QueryListResponse)
def list_queries(
    skip: int = 0,
    limit: int = 20,
    show_verified: bool = False,
    label_filter: str = None,
    max_confidence: float = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Return paginated queries with signed image URLs.

    Args:
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return (default 20, max 100)
        show_verified: If False, only return queries without ground_truth
        label_filter: Filter by result_label (case-insensitive contains)
        max_confidence: Only return queries with confidence below this threshold
    """
    limit = min(limit, 100)  # Cap at 100

    # Build base query
    base_query = db.query(models.Query)
    if not show_verified:
        base_query = base_query.filter(models.Query.ground_truth.is_(None))
    if label_filter:
        base_query = base_query.filter(models.Query.result_label.ilike(f"%{label_filter}%"))
    if max_confidence is not None and max_confidence < 1.0:
        base_query = base_query.filter(models.Query.confidence <= max_confidence)

    # Get total count
    total = base_query.count()

    # Get paginated results
    queries = base_query.order_by(models.Query.created_at.desc()).offset(skip).limit(limit).all()

    # Generate signed URLs for images
    result = []
    for q in queries:
        image_url = None
        if q.image_blob_path:
            try:
                container, blob_name = q.image_blob_path.split("/", 1)
                image_url = generate_signed_url(container, blob_name)
            except Exception:
                pass

        result.append(schemas.QueryOut(
            id=q.id,
            detector_id=q.detector_id,
            created_at=q.created_at,
            image_blob_path=q.image_blob_path,
            image_url=image_url,
            result_label=q.result_label,
            confidence=q.confidence,
            status=q.status,
            local_inference=q.local_inference,
            escalated=q.escalated,
            ground_truth=q.ground_truth,
            is_correct=q.is_correct,
            detections_json=q.detections_json,
        ))

    return schemas.QueryListResponse(
        queries=result,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=schemas.QueryOut, status_code=201)
async def create_query(
    detector_id: str = Form(...),
    confidence_threshold: float = Form(0.9),
    want_async: bool = Form(False),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> models.Query:
    """Create a new image query.

    The uploaded image is stored in Blob Storage.  A Query record is
    created with status pending.  Local inference is simulated by
    generating a random label and confidence.  If the confidence is
    below the provided threshold, an escalation is created and a
    fallback job is posted to Service Bus.  A fallback token is
    generated to authorise the edge device when contacting the cloud
    inference service.
    """
    # Verify detector exists
    det = db.query(models.Detector).filter(models.Detector.id == detector_id).first()
    if not det:
        raise HTTPException(status_code=404, detail="Detector not found")
    # Save the image to blob storage
    data = await image.read()
    blob_name = f"queries/{detector_id}/{datetime.utcnow().isoformat()}_{image.filename}"
    blob_path = upload_blob(settings.supabase_storage_bucket, blob_name, data, image.content_type or "image/jpeg")
    # Create query record
    q = models.Query(
        detector_id=detector_id,
        image_blob_path=blob_path,
        status="PENDING",
        local_inference=False,
        escalated=False,
    )
    db.add(q)
    db.commit()
    db.refresh(q)
    if want_async:
        # Asynchronous mode: send directly to fallback without local inference
        q.status = "PENDING"
        payload = {
            "query_id": str(q.id),
            "detector_id": str(detector_id),
            "blob_path": blob_path,
            "fallback_token": create_fallback_token(str(detector_id)),
        }
        try:
            send_service_bus_message("inference-jobs", payload)
        except Exception:
            pass
    else:
        # Perform real inference via worker
        try:
            from ..services.inference_service import InferenceService
            config = db.query(models.DetectorConfig).filter(models.DetectorConfig.detector_id == str(detector_id)).first()
            
            result = await InferenceService.run_inference(
                detector_id=str(detector_id),
                image_bytes=data,
                detector_config=config,
                primary_model_blob_path=det.primary_model_blob_path,
                oodd_model_blob_path=det.oodd_model_blob_path
            )
            
            # Extract all detections with bounding boxes
            detections = result.get("detections", [])
            if detections:
                # Store all detections with their bboxes
                q.detections_json = detections
                # Use the detection with highest confidence as the primary result
                top_det = max(detections, key=lambda x: x.get("confidence", 0.0))
                label = top_det.get("label", "unknown")
                confidence = top_det.get("confidence", 0.0)
            else:
                label = "nothing"
                confidence = 1.0
                q.detections_json = []

            q.result_label = label
            q.confidence = confidence
            q.status = "DONE"
            q.local_inference = True

            # ── Phase 3: Save shadow/canary result if candidate model ran ──
            shadow_data = result.get("shadow_result")
            if shadow_data:
                try:
                    shadow_rec = models.ShadowDetection(
                        id=str(uuid.uuid4()),
                        detector_id=str(detector_id),
                        query_id=str(q.id),
                        primary_label=label,
                        primary_confidence=confidence,
                        shadow_label=shadow_data.get("top_label"),
                        shadow_confidence=shadow_data.get("top_confidence"),
                        primary_detections_json=detections,
                        shadow_detections_json=shadow_data.get("detections", []),
                        agreed=(label == shadow_data.get("top_label")),
                    )
                    db.add(shadow_rec)
                except Exception as shadow_save_err:
                    logger.warning(f"Failed to save shadow detection record: {shadow_save_err}")

        except Exception as e:
            logger.error(f"Inference failed: {e}")
            # Fallback to pending/error or simulation if worker is down
            q.status = "ERROR"
            db.commit()
            raise HTTPException(status_code=500, detail=f"Inference worker error: {str(e)}")

        # Determine if escalation is needed
        if confidence < confidence_threshold:
            # create escalation
            esc = models.Escalation(query_id=q.id, created_at=datetime.utcnow(), reason="Low confidence")
            db.add(esc)
            q.escalated = True
            q.status = "ESCALATED"
            # Send fallback job to Service Bus
            payload = {
                "query_id": str(q.id),
                "detector_id": str(detector_id),
                "blob_path": blob_path,
                "fallback_token": create_fallback_token(str(detector_id)),
            }
            try:
                send_service_bus_message("inference-jobs", payload)
            except Exception:
                pass
            # Send alert via email and SMS
            # Compose alert subject and body
            subject = f"Escalation for query {q.id}"
            body = f"Query {q.id} for detector {detector_id} has been escalated due to low confidence ({confidence:.2f})."
            emails: list[str] = []
            phones: list[str] = []
            if settings.alert.alert_email_to:
                emails = [addr.strip() for addr in settings.alert.alert_email_to.split(',') if addr.strip()]
            if settings.alert.alert_phone_to:
                phones = [settings.alert.alert_phone_to]
            # If an Azure Function URL is configured, call it asynchronously
            try:
                await send_alert_via_function(subject=subject, body=body, emails=emails, phones=phones)
            except Exception:
                # Fall back to direct SendGrid/Twilio alerts
                try:
                    from ..utils.alerts import send_email_alert, send_sms_alert
                    if emails:
                        send_email_alert(emails, subject, body)
                    for phone in phones:
                        send_sms_alert(phone, body)
                except Exception:
                    pass
    db.commit()
    db.refresh(q)

    # Trigger detector-based alert if conditions are met
    if q.result_label and q.confidence is not None:
        try:
            trigger_detector_alert(
                detector_id=str(detector_id),
                query_id=str(q.id),
                result_label=q.result_label,
                confidence=q.confidence,
                camera_name=None,  # TODO: Add camera context if available
                image_blob_path=blob_path,
                db=db
            )
        except Exception as e:
            # Don't fail query processing if alert fails
            print(f"Failed to trigger detector alert: {e}")
    return q


@router.get("/{query_id}", response_model=schemas.QueryOut)
def get_query(query_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    q = db.query(models.Query).filter(models.Query.id == query_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Query not found")

    # Generate signed image URL if image exists
    image_url = None
    if q.image_blob_path:
        try:
            container, blob_name = q.image_blob_path.split("/", 1)
            image_url = generate_signed_url(container, blob_name)
        except Exception:
            pass  # Image URL generation failed, leave as None

    return schemas.QueryOut(
        id=q.id,
        detector_id=q.detector_id,
        created_at=q.created_at,
        image_blob_path=q.image_blob_path,
        image_url=image_url,
        result_label=q.result_label,
        confidence=q.confidence,
        status=q.status,
        local_inference=q.local_inference,
        escalated=q.escalated,
    )


@router.get("/{query_id}/image")
def get_query_image(query_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)) -> dict[str, str]:
    """Return a signed URL for the query image."""
    q = db.query(models.Query).filter(models.Query.id == query_id).first()
    if not q or not q.image_blob_path:
        raise HTTPException(status_code=404, detail="Query or image not found")
    container, blob_name = q.image_blob_path.split("/", 1)
    url = generate_signed_url(container, blob_name)
    return {"url": url}


@router.post("/{query_id}/feedback", response_model=schemas.FeedbackOut)
def submit_feedback(
    query_id: str,
    payload: schemas.FeedbackCreate,
    db: Session = Depends(get_db),
    reviewer=Depends(get_current_reviewer),
) -> models.Feedback:
    """Persist human feedback for a query and update its status.

    Reviewers can supply a label (YES/NO/UNCLEAR), optional confidence, notes and
    count.  A Feedback record is created and the query's label and confidence
    fields are updated accordingly.  Escalation resolution must be handled via
    the escalations API.
    """
    q = db.query(models.Query).filter(models.Query.id == query_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Query not found")
    # Create feedback record
    fb = models.Feedback(
        query_id=query_id,
        reviewer_id=reviewer.id if reviewer.id else None,
        label=payload.label,
        confidence=payload.confidence,
        notes=payload.notes,
        count=payload.count,
    )
    db.add(fb)
    # Update query with human result
    q.result_label = payload.label
    if payload.confidence is not None:
        q.confidence = payload.confidence
    q.status = "DONE"
    q.escalated = False
    db.commit()
    db.refresh(fb)
    return fb


@router.patch("/{query_id}", response_model=schemas.QueryOut)
def update_query_ground_truth(
    query_id: str,
    payload: schemas.QueryGroundTruthUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Update ground truth label for a query."""
    query = db.query(models.Query).filter(models.Query.id == query_id).first()
    if not query:
        raise HTTPException(status_code=404, detail="Query not found")

    query.ground_truth = payload.ground_truth
    query.reviewed_by = current_user.id
    query.reviewed_at = datetime.utcnow()
    # Check if detector prediction was correct
    if query.result_label:
        query.is_correct = (query.result_label.lower() == payload.ground_truth.lower())

    db.commit()
    db.refresh(query)
    return query


@router.delete("/{query_id}", status_code=204)
def delete_query(
    query_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Delete a query and its associated blob image.

    This permanently removes the query record and its image from blob storage.
    Related records (escalations, feedback, annotations) are also deleted.
    """
    query = db.query(models.Query).filter(models.Query.id == query_id).first()
    if not query:
        raise HTTPException(status_code=404, detail="Query not found")

    # Delete blob if exists
    if query.image_blob_path:
        try:
            container, blob_name = query.image_blob_path.split("/", 1)
            delete_blob(container, blob_name)
        except Exception as e:
            # Log but don't fail if blob deletion fails
            print(f"Failed to delete blob {query.image_blob_path}: {e}")

    # Delete related records
    db.query(models.Escalation).filter(models.Escalation.query_id == query_id).delete()
    db.query(models.Feedback).filter(models.Feedback.query_id == query_id).delete()
    db.query(models.ImageAnnotation).filter(models.ImageAnnotation.query_id == query_id).delete()

    # Delete the query
    db.delete(query)
    db.commit()

    return None
