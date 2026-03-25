"""Edge API routes for forensic video search (BOLO)."""

import asyncio
import logging
import os
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/forensic-search", tags=["forensic-search"])

# In-memory job tracking (edge-local, not persisted)
_active_jobs: dict[str, dict] = {}


class ForensicSearchRequest(BaseModel):
    query_text: str = Field(..., max_length=500)
    source_url: str = Field(..., max_length=512)
    source_type: str = Field("video_file")
    frame_interval_sec: float = Field(1.0, ge=0.1)
    confidence_threshold: float = Field(0.3, ge=0.0, le=1.0)


@router.post("/start")
async def start_search(payload: ForensicSearchRequest):
    """Start a forensic search job on the edge device."""
    job_id = str(uuid.uuid4())

    _active_jobs[job_id] = {
        "id": job_id,
        "query_text": payload.query_text,
        "source_url": payload.source_url,
        "status": "PENDING",
        "progress_pct": 0.0,
        "frames_scanned": 0,
        "total_frames": 0,
        "matches_found": 0,
        "results": [],
    }

    # Start async search in background
    asyncio.create_task(_run_search(job_id, payload))

    return _active_jobs[job_id]


@router.get("/{job_id}/status")
async def get_search_status(job_id: str):
    """Get progress of a running search job."""
    job = _active_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {k: v for k, v in job.items() if k != "results"}


@router.get("/{job_id}/results")
async def get_search_results(
    job_id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Get matching results from a search job."""
    job = _active_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    results = job.get("results", [])
    return results[offset : offset + limit]


@router.post("/{job_id}/stop")
async def stop_search(job_id: str):
    """Cancel a running search job."""
    job = _active_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    job["status"] = "CANCELLED"
    return job


async def _run_search(job_id: str, payload: ForensicSearchRequest):
    """Background task to run forensic search."""
    job = _active_jobs.get(job_id)
    if not job:
        return

    try:
        from inference.forensic_search import ForensicSearchEngine, ForensicSearchJob
        from inference.yoloe_inference import get_yoloe_model
        from inference.vlm_inference import get_vlm

        yoloe = get_yoloe_model()
        vlm = get_vlm()
        engine = ForensicSearchEngine(yoloe, vlm)

        search_job = ForensicSearchJob(
            id=job_id,
            query_text=payload.query_text,
            source_url=payload.source_url,
            source_type=payload.source_type,
            frame_interval_sec=payload.frame_interval_sec,
            confidence_threshold=payload.confidence_threshold,
        )

        job["status"] = "RUNNING"

        async for result in engine.search(search_job):
            job["frames_scanned"] = search_job.frames_scanned
            job["total_frames"] = search_job.total_frames
            job["progress_pct"] = search_job.progress_pct
            job["matches_found"] = search_job.matches_found
            job["results"].append({
                "id": result.id,
                "timestamp_sec": result.timestamp_sec,
                "confidence": result.confidence,
                "bbox": result.bbox,
                "label": result.label,
            })

        job["status"] = search_job.status
        job["frames_scanned"] = search_job.frames_scanned
        job["progress_pct"] = 100.0

    except Exception as e:
        logger.error(f"Forensic search error: {e}", exc_info=True)
        job["status"] = "ERROR"
