"""API endpoints for data retention management, storage stats, and training data export."""
from __future__ import annotations

import io
import json
import logging
import uuid
import zipfile
from datetime import datetime, timedelta
from typing import List, Dict

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..dependencies import get_db, get_current_user
from ..utils.supabase_storage import delete_blob, download_blob
from ..config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/data", tags=["data-management"])
settings = get_settings()


def get_or_create_settings(db: Session) -> models.DataRetentionSettings:
    """Get existing settings or create default ones."""
    settings_obj = db.query(models.DataRetentionSettings).first()
    if not settings_obj:
        settings_obj = models.DataRetentionSettings()
        db.add(settings_obj)
        db.commit()
        db.refresh(settings_obj)
    return settings_obj


@router.get("/retention-settings", response_model=schemas.DataRetentionSettingsOut)
def get_retention_settings(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get current data retention settings."""
    return get_or_create_settings(db)


@router.put("/retention-settings", response_model=schemas.DataRetentionSettingsOut)
def update_retention_settings(
    payload: schemas.DataRetentionSettingsUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Update data retention settings."""
    settings_obj = get_or_create_settings(db)

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(settings_obj, key, value)

    settings_obj.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(settings_obj)
    return settings_obj


@router.get("/storage-stats", response_model=schemas.StorageStatsOut)
def get_storage_stats(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get storage statistics for queries and images."""
    now = datetime.utcnow()

    # Total counts
    total_queries = db.query(func.count(models.Query.id)).scalar()
    total_with_images = db.query(func.count(models.Query.id)).filter(
        models.Query.image_blob_path.isnot(None)
    ).scalar()
    verified_queries = db.query(func.count(models.Query.id)).filter(
        models.Query.ground_truth.isnot(None)
    ).scalar()
    unverified_queries = total_queries - verified_queries

    # Estimate size (assume ~100KB per image)
    estimated_size_mb = (total_with_images * 100) / 1024

    # Queries by age
    day_7 = now - timedelta(days=7)
    day_30 = now - timedelta(days=30)

    queries_lt_7 = db.query(func.count(models.Query.id)).filter(
        models.Query.created_at > day_7
    ).scalar()
    queries_7_30 = db.query(func.count(models.Query.id)).filter(
        models.Query.created_at <= day_7,
        models.Query.created_at > day_30
    ).scalar()
    queries_gt_30 = db.query(func.count(models.Query.id)).filter(
        models.Query.created_at <= day_30
    ).scalar()

    queries_by_age = {
        "< 7 days": queries_lt_7,
        "7-30 days": queries_7_30,
        "> 30 days": queries_gt_30,
    }

    # Queries by label (top 20)
    label_counts = db.query(
        models.Query.result_label,
        func.count(models.Query.id)
    ).group_by(models.Query.result_label).order_by(
        func.count(models.Query.id).desc()
    ).limit(20).all()

    queries_by_label = {label or "None": count for label, count in label_counts}

    # Date range
    oldest = db.query(func.min(models.Query.created_at)).scalar()
    newest = db.query(func.max(models.Query.created_at)).scalar()

    return schemas.StorageStatsOut(
        total_queries=total_queries,
        total_with_images=total_with_images,
        verified_queries=verified_queries,
        unverified_queries=unverified_queries,
        estimated_size_mb=estimated_size_mb,
        queries_by_age=queries_by_age,
        queries_by_label=queries_by_label,
        oldest_query_date=oldest,
        newest_query_date=newest,
    )


def _run_purge(record_ids: list[str], blob_paths: list[str | None], db_factory):
    """Background task: delete blobs from Supabase and DB records."""
    from ..database import SessionLocal
    db = db_factory()
    try:
        blob_delete_count = 0
        for blob_path in blob_paths:
            if blob_path:
                try:
                    container, blob_name = blob_path.split("/", 1)
                    if delete_blob(container, blob_name):
                        blob_delete_count += 1
                except Exception as e:
                    logger.warning(f"Failed to delete blob {blob_path}: {e}")

        for rid in record_ids:
            db.query(models.Escalation).filter(models.Escalation.query_id == rid).delete()
            db.query(models.Feedback).filter(models.Feedback.query_id == rid).delete()
            db.query(models.ImageAnnotation).filter(models.ImageAnnotation.query_id == rid).delete()
            db.query(models.Query).filter(models.Query.id == rid).delete()

        settings_obj = get_or_create_settings(db)
        settings_obj.last_cleanup_at = datetime.utcnow()
        settings_obj.last_cleanup_count = len(record_ids)
        db.commit()
        logger.info(f"Purge complete: {len(record_ids)} queries, {blob_delete_count} blobs deleted")
    except Exception as e:
        logger.error(f"Purge background task failed: {e}")
        db.rollback()
    finally:
        db.close()


@router.post("/purge", response_model=schemas.PurgeResponse)
def purge_old_data(
    payload: schemas.PurgeRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Purge old queries and their associated blob images."""
    cutoff_date = datetime.utcnow() - timedelta(days=payload.older_than_days)

    # Build query for records to delete
    query = db.query(models.Query).filter(models.Query.created_at < cutoff_date)

    if payload.exclude_verified:
        query = query.filter(models.Query.ground_truth.is_(None))

    if payload.label_filter:
        query = query.filter(models.Query.result_label == payload.label_filter)

    # Get records to delete
    records_to_delete = query.all()
    count = len(records_to_delete)

    if payload.dry_run:
        return schemas.PurgeResponse(
            deleted_count=count,
            deleted_blob_count=count,
            dry_run=True,
            message=f"Dry run: Would delete {count} queries and their images."
        )

    # Collect IDs and blob paths, then run deletion in background
    record_ids = [r.id for r in records_to_delete]
    blob_paths = [r.image_blob_path for r in records_to_delete]

    from ..database import SessionLocal
    background_tasks.add_task(_run_purge, record_ids, blob_paths, SessionLocal)

    return schemas.PurgeResponse(
        deleted_count=count,
        deleted_blob_count=count,
        dry_run=False,
        message=f"Purging {count} queries and their images in the background."
    )


@router.post("/export-training", response_model=schemas.TrainingExportResponse)
async def export_training_data(
    payload: schemas.TrainingExportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Export a sample of query data for model training."""
    # Build base query
    query = db.query(models.Query).filter(models.Query.image_blob_path.isnot(None))

    if payload.verified_only:
        query = query.filter(models.Query.ground_truth.isnot(None))

    if payload.label_filter:
        query = query.filter(models.Query.result_label.in_(payload.label_filter))

    if payload.min_confidence is not None:
        query = query.filter(models.Query.confidence >= payload.min_confidence)

    if payload.max_confidence is not None:
        query = query.filter(models.Query.confidence <= payload.max_confidence)

    # Get all matching records
    all_records = query.all()

    if not all_records:
        raise HTTPException(status_code=404, detail="No matching queries found for export")

    # Calculate sample size
    sample_size = int(len(all_records) * (payload.sample_percentage / 100))
    sample_size = max(1, sample_size)

    # Stratified or random sampling
    if payload.stratify_by_label:
        # Group by label
        by_label: Dict[str, List[models.Query]] = {}
        for record in all_records:
            label = record.result_label or "unknown"
            if label not in by_label:
                by_label[label] = []
            by_label[label].append(record)

        # Sample proportionally from each label
        import random
        sampled = []
        samples_per_label = max(1, sample_size // len(by_label))

        for label, records in by_label.items():
            n = min(samples_per_label, len(records))
            sampled.extend(random.sample(records, n))

        # Trim to exact sample size
        if len(sampled) > sample_size:
            sampled = random.sample(sampled, sample_size)
    else:
        import random
        sampled = random.sample(all_records, min(sample_size, len(all_records)))

    # Count by label
    samples_by_label: Dict[str, int] = {}
    for record in sampled:
        label = record.result_label or "unknown"
        samples_by_label[label] = samples_by_label.get(label, 0) + 1

    export_id = str(uuid.uuid4())[:8]

    return schemas.TrainingExportResponse(
        total_samples=len(sampled),
        samples_by_label=samples_by_label,
        download_url=f"/admin/data/export-training/{export_id}/download?ids={','.join([r.id for r in sampled])}",
        export_id=export_id,
        message=f"Export ready with {len(sampled)} samples. Use the download URL to get the ZIP file."
    )


@router.get("/export-training/{export_id}/download")
async def download_training_export(
    export_id: str,
    ids: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Download the training data export as a ZIP file."""
    query_ids = ids.split(",")

    # Get the queries
    queries = db.query(models.Query).filter(models.Query.id.in_(query_ids)).all()

    if not queries:
        raise HTTPException(status_code=404, detail="No queries found for export")

    # Create ZIP in memory
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Create metadata JSON
        metadata = {
            "export_id": export_id,
            "export_date": datetime.utcnow().isoformat(),
            "total_images": len(queries),
            "images": []
        }

        for i, query in enumerate(queries):
            if not query.image_blob_path:
                continue

            try:
                # Download image from blob storage
                container, blob_name = query.image_blob_path.split("/", 1)
                image_data = download_blob(container, blob_name)

                # Determine filename
                ext = blob_name.split(".")[-1] if "." in blob_name else "jpg"
                filename = f"images/{query.result_label or 'unknown'}_{i:04d}.{ext}"

                # Add to ZIP
                zip_file.writestr(filename, image_data)

                # Add to metadata
                image_meta = {
                    "filename": filename,
                    "query_id": query.id,
                    "label": query.result_label,
                    "ground_truth": query.ground_truth,
                    "confidence": query.confidence,
                    "is_correct": query.is_correct,
                    "created_at": query.created_at.isoformat() if query.created_at else None,
                    "detections": query.detections_json,
                }
                metadata["images"].append(image_meta)

            except Exception as e:
                print(f"Failed to download image {query.image_blob_path}: {e}")
                continue

        # Add metadata.json to ZIP
        zip_file.writestr("metadata.json", json.dumps(metadata, indent=2))

    # Seek to beginning of buffer
    zip_buffer.seek(0)

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=training_export_{export_id}.zip"
        }
    )
