"""Active learning — training lifecycle endpoints.

Phase 2: trigger retraining from a labeled dataset, list/get run status.
"""
from __future__ import annotations

import uuid
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models
from ..config import get_settings
from ..dependencies import get_db, get_current_admin, get_current_user

router = APIRouter(tags=["training"])
settings = get_settings()


# ── Phase 2: Trigger Training ─────────────────────────────────────────────────

@router.post("/detectors/{detector_id}/trigger-training")
def trigger_training(
    detector_id: str,
    dataset_id: str,
    epochs: int = 50,
    base_model: str = "yolov8s.pt",
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
):
    """Kick off YOLO fine-tuning from an existing labeled dataset.

    Creates a training_runs record (status=pending) then POSTs to the
    cloud-trainer service.  Returns immediately — poll GET /training-runs/{id}
    for status.

    Args:
        dataset_id: ID of a training_datasets record for this detector.
        epochs:     Training epochs (default 50).
        base_model: Base checkpoint name (default yolov8s.pt).
    """
    detector = db.query(models.Detector).filter(models.Detector.id == detector_id).first()
    if not detector:
        raise HTTPException(status_code=404, detail="Detector not found")

    dataset = db.query(models.TrainingDataset).filter(
        models.TrainingDataset.id == dataset_id,
        models.TrainingDataset.detector_id == detector_id,
    ).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Training dataset not found for this detector")

    # Refuse to start if a run is already active
    active = db.query(models.TrainingRun).filter(
        models.TrainingRun.detector_id == detector_id,
        models.TrainingRun.status.in_(["pending", "running"]),
    ).first()
    if active:
        raise HTTPException(
            status_code=409,
            detail=f"Training already in progress (run_id={active.id}, status={active.status})",
        )

    # Determine current model version
    config = db.query(models.DetectorConfig).filter(
        models.DetectorConfig.detector_id == detector_id
    ).first()
    current_version: int = (config.candidate_model_version or 0) if config else 0

    # Create the training run record
    run = models.TrainingRun(
        id=str(uuid.uuid4()),
        detector_id=detector_id,
        dataset_id=dataset_id,
        status="pending",
        base_model_version=current_version,
        triggered_by=getattr(current_user, "email", str(current_user)),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # Split dataset storage_path into bucket + blob
    storage_path: str = dataset.storage_path or ""
    parts = storage_path.split("/", 1)
    bucket = parts[0] if len(parts) == 2 else "models"
    blob = parts[1] if len(parts) == 2 else storage_path

    payload = {
        "training_run_id": run.id,
        "detector_id": detector_id,
        "dataset_bucket": bucket,
        "dataset_blob": blob,
        "base_model": base_model,
        "epochs": epochs,
        "current_model_version": current_version,
    }

    try:
        resp = httpx.post(settings.trainer_url, json=payload, timeout=10.0)
        if resp.status_code not in (200, 201, 202):
            run.status = "failed"
            run.error_log = f"Trainer rejected request: HTTP {resp.status_code} — {resp.text[:500]}"
            db.commit()
            raise HTTPException(status_code=502, detail="Trainer service rejected the request")
    except httpx.ConnectError:
        run.status = "failed"
        run.error_log = "Trainer service unreachable"
        db.commit()
        raise HTTPException(status_code=503, detail="Trainer service unavailable")

    return {
        "training_run_id": run.id,
        "status": run.status,
        "detector_id": detector_id,
        "dataset_id": dataset_id,
        "epochs": epochs,
        "base_model": base_model,
    }


# ── Phase 2: List Training Runs ───────────────────────────────────────────────

@router.get("/detectors/{detector_id}/training-runs")
def list_training_runs(
    detector_id: str,
    limit: int = 20,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """List all training runs for a detector, newest first."""
    detector = db.query(models.Detector).filter(models.Detector.id == detector_id).first()
    if not detector:
        raise HTTPException(status_code=404, detail="Detector not found")

    runs = (
        db.query(models.TrainingRun)
        .filter(models.TrainingRun.detector_id == detector_id)
        .order_by(models.TrainingRun.started_at.desc())
        .limit(limit)
        .all()
    )
    return [_run_to_dict(r) for r in runs]


@router.get("/training-runs/{run_id}")
def get_training_run(
    run_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get a single training run by ID."""
    run = db.query(models.TrainingRun).filter(models.TrainingRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Training run not found")
    return _run_to_dict(run)


def _run_to_dict(run: models.TrainingRun) -> dict:
    return {
        "id": run.id,
        "detector_id": run.detector_id,
        "dataset_id": run.dataset_id,
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "base_model_version": run.base_model_version,
        "candidate_model_path": run.candidate_model_path,
        "metrics": run.metrics,
        "triggered_by": run.triggered_by,
        "error_log": run.error_log,
    }
