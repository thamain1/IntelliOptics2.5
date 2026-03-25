"""API endpoints for forensic video search (BOLO)."""
from __future__ import annotations

import base64
import logging
import uuid
from datetime import datetime
from threading import Thread
from typing import List

import requests
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session

from .. import models, schemas
from ..config import get_settings
from ..dependencies import get_db, get_current_user
from ..utils.supabase_storage import upload_blob, generate_signed_url

router = APIRouter(prefix="/forensic-search", tags=["forensic-search"])
logger = logging.getLogger(__name__)
settings = get_settings()

# Edge inference base URL (same host as yoloworld/yoloe workers)
EDGE_INFERENCE_URL = settings.yoloworld_worker_url.rsplit("/", 1)[0]  # strip /yoloworld


def _dispatch_to_edge(job_id: str, query_text: str, source_url: str, source_type: str):
    """Background thread: dispatch search to edge and sync results back."""
    from ..database import SessionLocal

    db = SessionLocal()
    try:
        job = db.query(models.ForensicSearchJob).filter(models.ForensicSearchJob.id == job_id).first()
        if not job:
            logger.error(f"Forensic job {job_id} not found in DB")
            return

        # Start the search on edge inference service
        try:
            resp = requests.post(
                f"{EDGE_INFERENCE_URL}/forensic-search/run",
                json={
                    "job_id": job_id,
                    "query_text": query_text,
                    "source_url": source_url,
                    "source_type": source_type,
                    "frame_interval_sec": 1.0,
                    "confidence_threshold": 0.3,
                },
                timeout=30,
            )
            if resp.status_code != 200:
                logger.error(f"Edge forensic search failed: {resp.text}")
                job.status = "ERROR"
                db.commit()
                return

            job.status = "RUNNING"
            db.commit()
            logger.info(f"Forensic search {job_id} dispatched to edge")

        except requests.RequestException as e:
            logger.error(f"Failed to dispatch forensic search to edge: {e}")
            job.status = "ERROR"
            db.commit()
            return

        # Poll edge for progress until complete
        import time
        while True:
            time.sleep(2)

            try:
                status_resp = requests.get(
                    f"{EDGE_INFERENCE_URL}/forensic-search/{job_id}/status",
                    timeout=10,
                )
                if status_resp.status_code != 200:
                    continue

                status_data = status_resp.json()
                job.progress_pct = status_data.get("progress_pct", 0)
                job.total_frames = status_data.get("total_frames", 0)
                job.frames_scanned = status_data.get("frames_scanned", 0)
                job.matches_found = status_data.get("matches_found", 0)

                edge_status = status_data.get("status", "RUNNING")
                if edge_status in ("COMPLETED", "ERROR", "CANCELLED"):
                    job.status = edge_status
                    db.commit()
                    break

                db.commit()

            except requests.RequestException:
                continue

        # Fetch results from edge and store in cloud DB
        try:
            results_resp = requests.get(
                f"{EDGE_INFERENCE_URL}/forensic-search/{job_id}/results",
                timeout=30,
            )
            if results_resp.status_code == 200:
                edge_results = results_resp.json().get("results", [])
                for r in edge_results:
                    # Upload frame image to Supabase if available
                    frame_url = None
                    frame_b64 = r.get("frame_b64")
                    if frame_b64:
                        try:
                            frame_bytes = base64.b64decode(frame_b64)
                            blob_name = f"forensic/{job_id}/{r['id']}.jpg"
                            upload_blob(
                                settings.supabase_storage_bucket,
                                blob_name,
                                frame_bytes,
                                "image/jpeg",
                            )
                            # Get full public URL for the uploaded image
                            frame_url = generate_signed_url(
                                settings.supabase_storage_bucket,
                                blob_name,
                            )
                        except Exception as e:
                            logger.warning(f"Failed to upload forensic frame: {e}")

                    result_record = models.ForensicSearchResult(
                        id=r["id"],
                        job_id=job_id,
                        timestamp_sec=r.get("timestamp_sec"),
                        confidence=r.get("confidence", 0),
                        bbox=r.get("bbox"),
                        label=r.get("label", ""),
                        description=r.get("description", ""),
                        frame_url=frame_url,
                    )
                    db.add(result_record)

                db.commit()
                logger.info(f"Stored {len(edge_results)} forensic results for job {job_id}")

        except Exception as e:
            logger.error(f"Failed to fetch/store forensic results: {e}")

    except Exception as e:
        logger.error(f"Forensic search dispatch error: {e}", exc_info=True)
    finally:
        db.close()


@router.post("/upload")
def upload_video(
    file: UploadFile = File(...),
    user=Depends(get_current_user),
):
    """Upload a video file to edge for forensic search."""
    try:
        resp = requests.post(
            f"{EDGE_INFERENCE_URL}/forensic-search/upload",
            files={"file": (file.filename, file.file, file.content_type or "video/mp4")},
            timeout=300,
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Edge upload failed: {resp.text}")
        return resp.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Edge upload error: {e}")


@router.post("/jobs", response_model=schemas.ForensicSearchJobOut, status_code=201)
def create_search_job(
    payload: schemas.ForensicSearchJobCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Create a new forensic search (BOLO) job and dispatch to edge."""
    job = models.ForensicSearchJob(
        query_text=payload.query_text,
        source_type=payload.source_type,
        source_url=payload.source_url,
        camera_ids=payload.camera_ids,
        time_range_start=payload.time_range_start,
        time_range_end=payload.time_range_end,
        status="PENDING",
        created_by=user.id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    logger.info(f"Created forensic search job {job.id}: '{payload.query_text}'")

    # Dispatch to edge inference in background thread
    thread = Thread(
        target=_dispatch_to_edge,
        args=(job.id, payload.query_text, payload.source_url, payload.source_type),
        daemon=True,
    )
    thread.start()

    return job


@router.get("/jobs", response_model=List[schemas.ForensicSearchJobOut])
def list_search_jobs(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """List all forensic search jobs."""
    return (
        db.query(models.ForensicSearchJob)
        .order_by(models.ForensicSearchJob.created_at.desc())
        .limit(limit)
        .all()
    )


@router.get("/jobs/{job_id}", response_model=schemas.ForensicSearchJobOut)
def get_search_job(
    job_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get a specific search job with status and progress."""
    job = db.query(models.ForensicSearchJob).filter(models.ForensicSearchJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Search job not found")
    return job


@router.get("/jobs/{job_id}/results", response_model=List[schemas.ForensicSearchResultOut])
def get_search_results(
    job_id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get matching results for a search job."""
    job = db.query(models.ForensicSearchJob).filter(models.ForensicSearchJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Search job not found")

    return (
        db.query(models.ForensicSearchResult)
        .filter(models.ForensicSearchResult.job_id == job_id)
        .order_by(models.ForensicSearchResult.timestamp_sec.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.post("/jobs/{job_id}/stop", response_model=schemas.ForensicSearchJobOut)
def stop_search_job(
    job_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Cancel a running search job."""
    job = db.query(models.ForensicSearchJob).filter(models.ForensicSearchJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Search job not found")

    if job.status not in ("PENDING", "RUNNING"):
        raise HTTPException(status_code=400, detail=f"Cannot stop job in '{job.status}' state")

    # Try to stop on edge too
    try:
        requests.post(
            f"{EDGE_INFERENCE_URL}/forensic-search/{job_id}/stop",
            timeout=5,
        )
    except Exception:
        pass

    job.status = "CANCELLED"
    db.commit()
    db.refresh(job)

    logger.info(f"Cancelled forensic search job {job_id}")
    return job


@router.delete("/jobs/{job_id}", status_code=204)
def delete_search_job(
    job_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Delete a search job and all its results."""
    job = db.query(models.ForensicSearchJob).filter(models.ForensicSearchJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Search job not found")

    # Stop if running
    if job.status in ("PENDING", "RUNNING"):
        try:
            requests.post(f"{EDGE_INFERENCE_URL}/forensic-search/{job_id}/stop", timeout=5)
        except Exception:
            pass

    # Delete results first (cascade should handle this, but be explicit)
    db.query(models.ForensicSearchResult).filter(models.ForensicSearchResult.job_id == job_id).delete()
    db.delete(job)
    db.commit()

    logger.info(f"Deleted forensic search job {job_id}")
