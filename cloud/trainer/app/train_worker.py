"""Background training worker — runs YOLO fine-tune + ONNX export."""
from __future__ import annotations

import io
import logging
import os
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_training(req: dict) -> None:
    """Execute a full training cycle for one TrainRequest dict.

    Called in a background thread.  Writes status updates directly to
    Supabase via PostgREST so the backend can poll training_runs.
    """
    # ── Phase 2: imports inside the worker so FastAPI starts without GPU ──────
    from . import supabase_client as sb

    run_id: str = req["training_run_id"]
    detector_id: str = req["detector_id"]
    dataset_bucket: str = req["dataset_bucket"]
    dataset_blob: str = req["dataset_blob"]
    base_model: str = req.get("base_model", "yolov8s.pt")
    epochs: int = int(req.get("epochs", 50))
    current_version: int = int(req.get("current_model_version", 0))

    def mark(status: str, extra: dict | None = None) -> None:
        payload: dict = {"status": status, "completed_at": _now_iso()} if status in ("completed", "failed") else {"status": status}
        if extra:
            payload.update(extra)
        try:
            sb.db_patch("training_runs", {"id": run_id}, payload)
        except Exception as e:
            logger.warning("Could not update training_runs %s: %s", run_id, e)

    mark("running")
    logger.info("[%s] Training started — detector %s, epochs %d", run_id, detector_id, epochs)

    try:
        # ── 1. Download dataset zip ───────────────────────────────────────────
        logger.info("[%s] Downloading dataset %s/%s", run_id, dataset_bucket, dataset_blob)
        zip_bytes = sb.download_blob(dataset_bucket, dataset_blob)

        with tempfile.TemporaryDirectory(prefix="io_train_") as tmpdir:
            # ── 2. Extract zip ────────────────────────────────────────────────
            zip_path = os.path.join(tmpdir, "dataset.zip")
            with open(zip_path, "wb") as f:
                f.write(zip_bytes)
            del zip_bytes  # free memory

            data_dir = os.path.join(tmpdir, "data")
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(data_dir)

            data_yaml = os.path.join(data_dir, "data.yaml")
            if not os.path.exists(data_yaml):
                raise FileNotFoundError(f"data.yaml missing from dataset zip")

            # ── 3. Detect device ──────────────────────────────────────────────
            try:
                import torch
                device = "0" if torch.cuda.is_available() else "cpu"
            except Exception:
                device = "cpu"
            logger.info("[%s] Training device: %s", run_id, device)

            # ── 4. Run YOLO training ──────────────────────────────────────────
            from ultralytics import YOLO  # type: ignore

            model = YOLO(base_model)
            train_results = model.train(
                data=data_yaml,
                epochs=epochs,
                imgsz=640,
                device=device,
                project=os.path.join(tmpdir, "runs"),
                name="train",
                exist_ok=True,
                verbose=False,
            )

            save_dir = Path(str(train_results.save_dir))
            best_pt = save_dir / "weights" / "best.pt"
            if not best_pt.exists():
                raise FileNotFoundError(f"Training produced no best.pt at {best_pt}")
            logger.info("[%s] Training complete — best weights: %s", run_id, best_pt)

            # ── 5. Validate to collect metrics ────────────────────────────────
            val_model = YOLO(str(best_pt))
            val_result = val_model.val(data=data_yaml, device=device, verbose=False)
            rd = val_result.results_dict if hasattr(val_result, "results_dict") else {}
            metrics = {
                "precision": round(float(rd.get("metrics/precision(B)", 0) or 0), 4),
                "recall": round(float(rd.get("metrics/recall(B)", 0) or 0), 4),
                "mAP50": round(float(rd.get("metrics/mAP50(B)", 0) or 0), 4),
                "mAP50_95": round(float(rd.get("metrics/mAP50-95(B)", 0) or 0), 4),
            }
            logger.info("[%s] Metrics: %s", run_id, metrics)

            # ── 6. Export to ONNX ─────────────────────────────────────────────
            export_model = YOLO(str(best_pt))
            onnx_path_raw = export_model.export(format="onnx", imgsz=640, simplify=True)
            onnx_path = Path(str(onnx_path_raw))
            if not onnx_path.exists():
                # ultralytics may return None in some versions — find the file
                candidates = list(save_dir.glob("weights/*.onnx"))
                if not candidates:
                    raise FileNotFoundError("ONNX export produced no .onnx file")
                onnx_path = candidates[0]
            logger.info("[%s] ONNX exported: %s (%d bytes)", run_id, onnx_path, onnx_path.stat().st_size)

            # ── 7. Upload ONNX to Supabase ────────────────────────────────────
            next_version = current_version + 1
            onnx_blob = f"datasets/{detector_id}/primary/v{next_version}/model.onnx"
            with open(onnx_path, "rb") as f:
                onnx_bytes = f.read()
            candidate_path = sb.upload_blob("models", onnx_blob, onnx_bytes, "application/octet-stream")
            logger.info("[%s] Uploaded ONNX to %s", run_id, candidate_path)

        # ── 8. Update training_runs record ────────────────────────────────────
        mark("completed", {
            "candidate_model_path": candidate_path,
            "metrics": metrics,
        })

        # ── 9. Write candidate back to detector_configs ───────────────────────
        try:
            sb.db_patch(
                "detector_configs",
                {"detector_id": detector_id},
                {
                    "candidate_model_path": candidate_path,
                    "candidate_model_version": next_version,
                },
            )
            logger.info("[%s] detector_configs updated — candidate v%d", run_id, next_version)
        except Exception as e:
            logger.warning("[%s] Could not update detector_configs: %s", run_id, e)

        logger.info("[%s] Training pipeline complete.", run_id)

    except Exception as exc:
        logger.exception("[%s] Training failed: %s", run_id, exc)
        mark("failed", {"error_log": str(exc)[:4000]})
