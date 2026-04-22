"""IntelliOptics Trainer Service — FastAPI entry point.

Receives POST /train from the cloud backend, runs YOLO fine-tuning in a
background thread, and posts results back to Supabase via PostgREST.
"""
from __future__ import annotations

import logging

from fastapi import BackgroundTasks, FastAPI
from pydantic import BaseModel

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:     %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="IntelliOptics Trainer", version="1.0.0")


class TrainRequest(BaseModel):
    training_run_id: str
    detector_id: str
    dataset_bucket: str           # Supabase bucket, e.g. "models"
    dataset_blob: str             # Path within bucket, e.g. "datasets/.../dataset.zip"
    base_model: str = "yolov8s.pt"
    epochs: int = 50
    current_model_version: int = 0


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/train", status_code=202)
def start_training(req: TrainRequest, background_tasks: BackgroundTasks) -> dict:
    """Kick off YOLO fine-tune in a background thread.

    Returns immediately with 202 Accepted.  The caller should poll
    GET /training-runs/{id} on the backend for status.
    """
    logger.info("Training request received — run %s, detector %s", req.training_run_id, req.detector_id)
    from .train_worker import run_training
    background_tasks.add_task(run_training, req.model_dump())
    return {"training_run_id": req.training_run_id, "status": "started"}
