"""API endpoints for managing detectors."""
from __future__ import annotations

import json
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..dependencies import get_db, get_current_admin, get_current_user
from ..utils.supabase_storage import upload_blob
from ..config import get_settings


router = APIRouter(prefix="/detectors", tags=["detectors"])
settings = get_settings()


@router.get("/groups", response_model=List[str])
def list_detector_groups(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> List[str]:
    """Return a list of all unique detector group names (excludes deleted detectors)."""
    groups = db.query(models.Detector.group_name).filter(
        models.Detector.group_name.isnot(None),
        models.Detector.deleted_at.is_(None)
    ).distinct().all()
    return [g[0] for g in groups if g[0]]


@router.get("", response_model=List[schemas.DetectorOut])
def list_detectors(
    group_name: Optional[str] = None,
    include_deleted: bool = False,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> List[models.Detector]:
    """Return all detectors, optionally filtered by group. Deleted detectors excluded by default."""
    query = db.query(models.Detector)
    if not include_deleted:
        query = query.filter(models.Detector.deleted_at.is_(None))
    if group_name:
        query = query.filter(models.Detector.group_name == group_name)
    return query.all()


@router.post("", response_model=schemas.DetectorOut, status_code=201)
def create_detector(
    payload: schemas.DetectorCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> models.Detector:
    """Create a new detector and its configuration."""
    # 1. Create the detector
    det = models.Detector(
        name=payload.name,
        description=payload.description,
        query_text=payload.query_text,
        group_name=payload.group_name,
        detector_metadata_serialized=payload.detector_metadata_serialized
    )
    db.add(det)
    db.commit()
    db.refresh(det)

    # 2. Create the detailed configuration
    edge_inference_config = {
        "profile": payload.edge_inference_profile or "default",
        "min_time_between_escalations": payload.min_time_between_escalations or 2.0,
    }

    # Add mode_configuration and pipeline_config if provided
    if payload.mode_configuration:
        edge_inference_config["mode_configuration"] = payload.mode_configuration
    if payload.pipeline_config:
        edge_inference_config["pipeline_config"] = payload.pipeline_config

    new_config = models.DetectorConfig(
        detector_id=det.id,
        mode=payload.mode,
        class_names=payload.class_names,
        confidence_threshold=payload.confidence_threshold,
        patience_time=payload.patience_time or 30.0,
        edge_inference_config=edge_inference_config
    )
    db.add(new_config)
    db.commit()
    db.refresh(det) # Refresh to load the new relationship

    return det


@router.get("/{detector_id}", response_model=schemas.DetectorOut)
def get_detector(detector_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)) -> models.Detector:
    det = db.query(models.Detector).filter(models.Detector.id == detector_id).first()
    if not det:
        raise HTTPException(status_code=404, detail="Detector not found")
    return det


@router.put("/{detector_id}", response_model=schemas.DetectorOut)
def update_detector(
    detector_id: str,
    payload: schemas.DetectorUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> models.Detector:
    """Update a detector's basic information."""
    det = db.query(models.Detector).filter(models.Detector.id == detector_id).first()
    if not det:
        raise HTTPException(status_code=404, detail="Detector not found")

    update_data = payload.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(det, key, value)

    db.commit()
    db.refresh(det)
    return det


@router.delete("/{detector_id}")
def delete_detector(
    detector_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """
    Soft delete a detector. The detector and all its historical data (queries,
    escalations, etc.) are preserved but the detector is hidden from normal listings.
    Use include_deleted=true on list endpoint to see deleted detectors.
    Use POST /{detector_id}/restore to restore a deleted detector.
    """
    from datetime import datetime

    det = db.query(models.Detector).filter(models.Detector.id == detector_id).first()
    if not det:
        raise HTTPException(status_code=404, detail="Detector not found")

    if det.deleted_at is not None:
        raise HTTPException(status_code=400, detail="Detector is already deleted")

    det.deleted_at = datetime.utcnow()
    db.commit()

    return {
        "message": "Detector deleted successfully",
        "id": detector_id,
        "deleted_at": det.deleted_at.isoformat(),
        "note": "Historical data (queries, escalations) preserved. Use /restore to undo."
    }


@router.post("/{detector_id}/restore")
def restore_detector(
    detector_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """
    Restore a soft-deleted detector, making it visible again in listings.
    """
    det = db.query(models.Detector).filter(models.Detector.id == detector_id).first()
    if not det:
        raise HTTPException(status_code=404, detail="Detector not found")

    if det.deleted_at is None:
        raise HTTPException(status_code=400, detail="Detector is not deleted")

    det.deleted_at = None
    db.commit()

    return {
        "message": "Detector restored successfully",
        "id": detector_id
    }


@router.post("/{detector_id}/model", response_model=schemas.DetectorOut)
def upload_detector_model(
    detector_id: str,
    file: UploadFile = File(...),
    model_type: str = "primary",
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> models.Detector:
    """Upload a model file for a detector (primary or oodd)."""
    det = db.query(models.Detector).filter(models.Detector.id == detector_id).first()
    if not det:
        raise HTTPException(status_code=404, detail="Detector not found")
    
    data = file.file.read()
    # Upload to "models" container, not "images" container
    blob_name = f"{detector_id}/{model_type}/{file.filename}"
    path = upload_blob("models", blob_name, data, file.content_type or "application/octet-stream")
    
    if model_type == "oodd":
        det.oodd_model_blob_path = path
    else:
        det.primary_model_blob_path = path
        det.model_blob_path = path # Backward compatibility
        
    # Sync to config
    config = db.query(models.DetectorConfig).filter(models.DetectorConfig.detector_id == detector_id).first()
    if config:
        if model_type == "oodd":
            config.oodd_model_blob_path = path
        else:
            config.primary_model_blob_path = path
        db.add(config)

    db.commit()
    db.refresh(det)
    return det


@router.delete("/{detector_id}/model")
def remove_model_from_detector(
    detector_id: str,
    model_type: str = "primary",  # "primary" or "oodd"
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> dict:
    """
    Remove model reference from a detector (sets blob path to NULL).

    IMPORTANT: This does NOT delete the model file from Azure Blob Storage.
    It only removes the path reference from this detector's configuration.
    Other detectors using the same model are unaffected.

    The model file remains in storage and can be re-assigned to this or other detectors.
    """
    det = db.query(models.Detector).filter(models.Detector.id == detector_id).first()
    if not det:
        raise HTTPException(status_code=404, detail="Detector not found")

    # Validate model_type
    if model_type not in ["primary", "oodd"]:
        raise HTTPException(status_code=400, detail="model_type must be 'primary' or 'oodd'")

    # Remove Primary model reference
    if model_type == "primary":
        if not det.primary_model_blob_path:
            raise HTTPException(status_code=400, detail="No Primary model configured")

        old_path = det.primary_model_blob_path
        det.primary_model_blob_path = None
        det.model_blob_path = None  # Backward compatibility
        db.commit()
        db.refresh(det)

        return {
            "message": "Primary model removed. WARNING: Detector will not function until new model is uploaded.",
            "detector_id": str(detector_id),
            "model_type": model_type,
            "removed_path": old_path,
            "warning": "Inference will fail until you upload a new Primary model."
        }

    # Remove OODD model reference
    if model_type == "oodd":
        if not det.oodd_model_blob_path:
            raise HTTPException(status_code=400, detail="No OODD model configured for this detector")

        old_path = det.oodd_model_blob_path
        det.oodd_model_blob_path = None
        db.commit()
        db.refresh(det)

        return {
            "message": "OODD model reference removed successfully. Detector will use Primary model only.",
            "detector_id": str(detector_id),
            "model_type": model_type,
            "removed_path": old_path,
            "note": "Model file remains in storage and can be re-assigned anytime."
        }


# --- New Configuration Endpoints ---

@router.get("/{detector_id}/config", response_model=schemas.DetectorConfigOut)
def get_detector_config(
    detector_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Get the detailed configuration for a specific detector.
    If no configuration exists, a default one is created and returned.
    """
    config = db.query(models.DetectorConfig).filter(models.DetectorConfig.detector_id == detector_id).first()
    if not config:
        # Check if the detector itself exists
        detector = db.query(models.Detector).filter(models.Detector.id == detector_id).first()
        if not detector:
            raise HTTPException(status_code=404, detail="Detector not found")
        # Create and return a default config if one doesn't exist
        config = models.DetectorConfig(detector_id=detector_id)
        db.add(config)
        db.commit()
        db.refresh(config)
    
    # Ensure fields are not None for Pydantic validation
    if config.edge_inference_config is None:
        config.edge_inference_config = {}
    if config.model_input_config is None:
        config.model_input_config = {}
    if config.model_output_config is None:
        config.model_output_config = {}
    if config.detection_params is None:
        config.detection_params = {}
    if config.per_class_thresholds is None:
        config.per_class_thresholds = {}
        
    return config


@router.put("/{detector_id}/config", response_model=schemas.DetectorConfigOut)
def update_detector_config(
    detector_id: str,
    config_update: schemas.DetectorConfigUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """
    Update (or create) the detailed configuration for a detector.
    """
    config = db.query(models.DetectorConfig).filter(models.DetectorConfig.detector_id == detector_id).first()
    if not config:
        # Check if the detector itself exists before creating a config for it
        detector = db.query(models.Detector).filter(models.Detector.id == detector_id).first()
        if not detector:
            raise HTTPException(status_code=404, detail="Detector not found")
        config = models.DetectorConfig(detector_id=detector_id)
        db.add(config)

    update_data = config_update.dict(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(config, key, value)

    db.commit()
    db.refresh(config)
    return config

# --- Test Endpoint ---

import io
import httpx

from ..services.inference_service import InferenceService

@router.post("/{detector_id}/test")
async def test_detector(
    detector_id: str,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Test detector with a sample image.
    Returns inference results without saving to database.
    Calls the cloud worker for real ONNX inference via InferenceService.
    """
    detector = db.query(models.Detector).filter(models.Detector.id == detector_id).first()
    if not detector:
        raise HTTPException(status_code=404, detail="Detector not found")

    config = db.query(models.DetectorConfig).filter(models.DetectorConfig.detector_id == detector_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Detector config not found")

    # Read image bytes
    image_bytes = await image.read()

    if not image_bytes:
        raise HTTPException(status_code=400, detail="No image data received")

    try:
        # Call InferenceService for real inference
        result = await InferenceService.run_inference(
            detector_id=detector_id,
            image_bytes=image_bytes,
            detector_config=config,
            primary_model_blob_path=config.primary_model_blob_path or detector.primary_model_blob_path,
            oodd_model_blob_path=config.oodd_model_blob_path or detector.oodd_model_blob_path
        )

    except Exception as e:
        import traceback
        error_detail = f"Inference error: {str(e)}\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=str(e))

    # Extract detections from worker response
    detections = result.get("detections", [])
    inference_time_ms = result.get("latency_ms", 0)
    oodd_result = result.get("oodd_result")
    model_info = result.get("model_info")

    # Transform worker output to match expected format
    formatted_detections = []
    for det in detections:
        formatted_det = {
            "class": det.get("label", "unknown"),
            "confidence": det.get("confidence", 0.0)
        }

        if "bbox" in det and isinstance(det["bbox"], list) and len(det["bbox"]) >= 4:
            bbox_list = det["bbox"]
            formatted_det["bbox"] = {
                "x1": int(bbox_list[0]),
                "y1": int(bbox_list[1]),
                "x2": int(bbox_list[2]),
                "y2": int(bbox_list[3])
            }

        formatted_detections.append(formatted_det)

    # Determine if would escalate based on confidence threshold
    max_confidence = max([d.get("confidence", 0) for d in formatted_detections], default=0.0)
    would_escalate = max_confidence < config.confidence_threshold

    response = {
        "detections": formatted_detections,
        "inference_time_ms": inference_time_ms,
        "would_escalate": would_escalate,
        "annotated_image_url": None,
        "message": "Real inference from cloud worker"
    }

    if oodd_result:
        response["oodd_metrics"] = {
            "in_domain_score": oodd_result.get("in_domain_score"),
            "is_in_domain": oodd_result.get("is_in_domain"),
            "confidence_adjustment": oodd_result.get("confidence_adjustment"),
            "calibrated_threshold": oodd_result.get("calibrated_threshold")
        }

    if model_info:
        response["model_info"] = model_info

    return response


@router.get("/{detector_id}/metrics", response_model=schemas.DetectorMetricsOut)
def get_detector_metrics(
    detector_id: str,
    time_range: str = "7d",  # Options: 1d, 7d, 30d, all
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Calculate detector performance metrics based on ground truth labels.
    """
    detector = db.query(models.Detector).filter(models.Detector.id == detector_id).first()
    if not detector:
        raise HTTPException(status_code=404, detail="Detector not found")

    # Calculate time cutoff
    from datetime import datetime, timedelta, timezone
    if time_range == "1d":
        cutoff = datetime.now(timezone.utc) - timedelta(days=1)
    elif time_range == "7d":
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    elif time_range == "30d":
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    else:
        cutoff = None  # All time

    # Query all queries with ground truth labels
    query = db.query(models.Query).filter(
        models.Query.detector_id == detector_id,
        models.Query.ground_truth.isnot(None)  # Only queries with ground truth
    )

    if cutoff:
        query = query.filter(models.Query.created_at >= cutoff)

    queries_list = query.all()

    if not queries_list:
        # No ground truth data available
        return {
            "detector_id": detector_id,
            "balanced_accuracy": None,
            "sensitivity": None,
            "specificity": None,
            "true_positives": 0,
            "true_negatives": 0,
            "false_positives": 0,
            "false_negatives": 0,
            "total_queries": 0,
            "message": "No ground truth labels available for this detector"
        }

    # Calculate confusion matrix
    tp = 0  # Predicted YES, Actual YES
    tn = 0  # Predicted NO, Actual NO
    fp = 0  # Predicted YES, Actual NO
    fn = 0  # Predicted NO, Actual YES

    positive_labels = ["yes", "defect", "detected", "true", "ok"]

    for q in queries_list:
        predicted = q.result_label  # Detector prediction
        actual = q.ground_truth  # Human-verified label

        if not predicted or not actual:
            continue

        predicted_positive = predicted.lower() in positive_labels
        actual_positive = actual.lower() in positive_labels

        if predicted_positive and actual_positive:
            tp += 1
        elif not predicted_positive and not actual_positive:
            tn += 1
        elif predicted_positive and not actual_positive:
            fp += 1
        else:  # not predicted_positive and actual_positive
            fn += 1

    # Calculate metrics
    total = tp + tn + fp + fn

    if total == 0:
        return {
            "detector_id": detector_id,
            "balanced_accuracy": None,
            "sensitivity": None,
            "specificity": None,
            "true_positives": 0,
            "true_negatives": 0,
            "false_positives": 0,
            "false_negatives": 0,
            "total_queries": 0,
            "message": "No valid labels found in the selected range"
        }

    # Sensitivity (Recall, True Positive Rate, Accuracy for YES)
    sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0.0

    # Specificity (True Negative Rate, Accuracy for NO)
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0

    # Balanced Accuracy
    balanced_accuracy = (sensitivity + specificity) / 2.0

    return {
        "detector_id": detector_id,
        "balanced_accuracy": balanced_accuracy,
        "sensitivity": sensitivity,
        "specificity": specificity,
        "true_positives": tp,
        "true_negatives": tn,
        "false_positives": fp,
        "false_negatives": fn,
        "total_queries": total,
        "time_range": time_range
    }
