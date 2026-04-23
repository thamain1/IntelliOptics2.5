# Active Learning Loop — Detailed Build Plan

## What exists today
- `feedback` table: every human review saves `label`, `confidence`, `notes`, `reviewer_id`, `query_id`
- `queries` table: `image_blob_path` (Supabase storage), `ground_truth`, `result_label`, `oodd_score`
- `detector_configs` table: `primary_model_blob_path`, `oodd_model_blob_path` — blob paths in Supabase storage
- Edge devices pull models via presigned URLs, check for updates on `refresh_rate` interval
- YOLO → ONNX export already exists at `edge/inference/tools/export_onnx.py`

The gap: feedback accumulates but nothing reads it back. Models never improve.

---

## Phase 1 — Dataset Export
**~2 days | Backend only**

Add `GET /detectors/{id}/export-dataset` endpoint that:
1. Queries all `feedback` records joined to `queries` for the detector where `ground_truth IS NOT NULL` or `feedback.label IS NOT NULL`
2. Downloads each `image_blob_path` from Supabase storage
3. Converts labels to YOLO format: one `.txt` per image with `class_index cx cy w h` normalized rows — derived from `detections_json` bboxes or `ground_truth` label for binary detectors
4. Packages into a zip: `images/train/`, `labels/train/`, `images/val/` (20% holdout), `labels/val/`, `data.yaml`
5. Uploads the zip to Supabase storage and returns a presigned download URL

New DB table: `training_datasets`
```
id, detector_id, created_at, sample_count, val_count,
storage_path, label_distribution (JSONB), triggered_by
```

Minimum viable: 50 labeled samples before export is allowed (enforced in endpoint).

---

## Phase 2 — Retraining Service
**~3 days | New Docker service**

Add a new `cloud/trainer/` service. Runs as a FastAPI app, separate container, GPU-optional.

Key endpoint: `POST /train`
```json
{ "detector_id": "...", "dataset_path": "supabase://...", "base_model": "yolov8s.pt" }
```

Flow:
1. Download dataset zip from Supabase storage
2. Download current model `.pt` file (or use base YOLOv8s if no existing)
3. Run `yolo train model=... data=data.yaml epochs=50 imgsz=640 device=cpu` (GPU if available)
4. On completion: export to ONNX via `export_onnx.py` logic
5. Upload new `.onnx` to Supabase storage at `models/{detector_id}/primary/v{n+1}/model.onnx`
6. POST back to backend `PUT /detectors/{id}/config` with new `primary_model_blob_path` marked as `candidate` (not yet live)

New DB table: `training_runs`
```
id, detector_id, dataset_id, started_at, completed_at, status,
base_model_version, candidate_model_path,
metrics (JSONB: precision, recall, mAP50),
triggered_by, error_log
```

The trainer needs ultralytics — separate requirements.txt, separate Dockerfile. Does NOT go in the inference container (keeps inference Apache 2.0 clean).

---

## Phase 3 — Canary / Shadow Mode
**~2 days | Edge API + backend**

Goal: validate the candidate model on real traffic before promoting, without affecting users.

**Shadow mode** (safest): edge-api runs both the current model AND the candidate model on every image. Results from the candidate are logged but NOT returned to the user. After N frames (configurable, e.g. 500), compare confidence distributions.

Changes:
- `EdgeInferenceManager` grows a `shadow_model_path` per detector — loaded alongside primary
- `run_inference()` fires both; candidate result written to a new `shadow_detections` table with `(detector_id, query_id, candidate_version, label, confidence)`
- New backend endpoint `GET /detectors/{id}/canary-report`: compares shadow vs primary confidence distributions over the last N shadow runs

New DB table: `shadow_detections`
```
id, detector_id, query_id, candidate_model_version,
label, confidence, created_at
```

---

## Phase 4 — Promotion & Rollback
**~1 day | Backend + frontend**

Once a canary report looks good (mAP improved, no regression):

`POST /detectors/{id}/promote-candidate`
1. Moves `candidate_model_path` → `primary_model_blob_path` on `DetectorConfig`
2. Increments model version
3. Clears shadow mode
4. Edge devices pick up on next `refresh_rate` cycle (default 60s)

`POST /detectors/{id}/rollback`
1. Restores previous `primary_model_blob_path` from `training_runs` history
2. Clears candidate

---

## Phase 5 — Frontend
**~2 days | React**

New "Model Training" tab on the Detector detail page:
- **Dataset** section: sample count, label distribution chart, "Export Dataset" + "Trigger Training" buttons
- **Training Runs** table: status, metrics (precision/recall/mAP50), date — with "Deploy as Candidate" button per run
- **Canary Report** section: side-by-side confidence histogram (current vs candidate), "Promote" and "Rollback" buttons
- **Training required indicator**: badge on detector card when `feedback_count_since_last_train > 100`

---

## Phase 6 — Automated Trigger (optional, post-MVP)
A background job (cron via the existing scheduler or a new route) that:
- Checks every detector weekly
- If `new_feedback_count >= 100` AND no training run in progress → auto-triggers Phase 1+2
- Sends email via SendGrid when training completes

---

## DB migrations needed
```sql
CREATE TABLE training_datasets (
    id TEXT PRIMARY KEY,
    detector_id TEXT REFERENCES detectors(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    sample_count INT,
    val_count INT,
    storage_path TEXT,
    label_distribution JSONB,
    triggered_by TEXT
);

CREATE TABLE training_runs (
    id TEXT PRIMARY KEY,
    detector_id TEXT REFERENCES detectors(id),
    dataset_id TEXT REFERENCES training_datasets(id),
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status TEXT DEFAULT 'pending',  -- pending, running, completed, failed
    base_model_version INT,
    candidate_model_path TEXT,
    metrics JSONB,
    triggered_by TEXT,
    error_log TEXT
);

CREATE TABLE shadow_detections (
    id TEXT PRIMARY KEY,
    detector_id TEXT REFERENCES detectors(id),
    query_id TEXT REFERENCES queries(id),
    candidate_model_version INT,
    label TEXT,
    confidence FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE detector_configs ADD COLUMN IF NOT EXISTS candidate_model_path TEXT;
ALTER TABLE detector_configs ADD COLUMN IF NOT EXISTS candidate_model_version INT;
```

---

## Effort summary

| Phase | What | Effort |
|-------|------|--------|
| 1 | Dataset export endpoint | 2 days |
| 2 | Trainer service (new container) | 3 days |
| 3 | Canary/shadow mode at edge | 2 days |
| 4 | Promote/rollback endpoints | 1 day |
| 5 | Frontend training tab | 2 days |
| 6 | Auto-trigger (optional) | 1 day |
| **Total** | | **~11 days** |

## Recommended build order
Phase 1 → Phase 2 → Phase 4 → Phase 5 (MVP usable at this point) → Phase 3 → Phase 6

Phase 3 (canary) can be skipped for early deployments where the operator is comfortable
manually reviewing training metrics before promoting.
