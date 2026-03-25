# YOLOWorld Feature - Rollback Documentation

**Date**: 2026-01-17
**Feature**: YOLOWorld Open-Vocabulary Detection for Demo Page

## Summary of Changes

The YOLOWorld feature adds open-vocabulary object detection to the demo page, allowing users to detect custom objects by typing text prompts (e.g., "person, car, fire, smoke").

## Files Modified

### Frontend

**File**: `cloud/frontend/src/pages/DemoStreamPage.tsx`
- Added `yoloworldPrompts` state and ref
- Added "YOLOWorld" capture mode button (purple button)
- Added prompt input field for YOLOWorld mode
- Modified `captureWebcamFrame` to call `/submit-yoloworld-frame` endpoint
- Modified session creation to include `yoloworld_prompts`

### Backend

**File**: `cloud/backend/app/schemas.py`
- Added `yoloworld_prompts: Optional[str]` to `DemoSessionCreate`
- Added `yoloworld_prompts: Optional[str]` to `DemoSessionOut`
- Added new schema `YoloWorldFrameSubmit`

**File**: `cloud/backend/app/models.py`
- Added `yoloworld_prompts: str = Column(Text, nullable=True)` to `DemoSession` model

**File**: `cloud/backend/app/routers/demo_streams.py`
- Updated `create_demo_session` to store `yoloworld_prompts`
- Added new endpoint: `POST /sessions/{session_id}/submit-yoloworld-frame`
- Added import for `process_yoloworld_inference`

**File**: `cloud/backend/app/services/yoloworld_inference.py` (NEW FILE)
- Created new service for YOLOWorld inference processing
- Calls inference worker's `/yoloworld` endpoint

### Edge/Inference Worker

**File**: `edge/inference/inference_service.py`
- Added `get_yoloworld_model()` function with lazy loading
- Added `@app.post("/yoloworld")` endpoint
- Updated `/health` endpoint to include `yoloworld_loaded` status

**File**: `edge/inference/yolov8s-worldv2.pt` (NEW FILE)
- YOLOWorld model weights (~50MB)

### Database Migration Required

The `demo_sessions` table needs a new column:
```sql
ALTER TABLE demo_sessions ADD COLUMN yoloworld_prompts TEXT;
```

## Blob Storage Uploads

Uploaded to `https://intelliopticsweb37558.blob.core.windows.net/models/`:
- `yoloworld/yolov8s-worldv2.onnx` (~50 MB)
- `yoloworld/clip-vit-b32.onnx` (~578 MB)

## Rollback Instructions

### Step 1: Restore Frontend

```bash
# Revert DemoStreamPage.tsx to previous version
git checkout HEAD~1 -- cloud/frontend/src/pages/DemoStreamPage.tsx

# Rebuild frontend
cd "C:\dev\IntelliOptics 2.0\cloud"
docker compose build frontend
docker compose up -d frontend
```

### Step 2: Restore Backend

```bash
# Revert backend files
git checkout HEAD~1 -- cloud/backend/app/schemas.py
git checkout HEAD~1 -- cloud/backend/app/models.py
git checkout HEAD~1 -- cloud/backend/app/routers/demo_streams.py

# Remove new service file
rm cloud/backend/app/services/yoloworld_inference.py

# Rebuild backend
cd "C:\dev\IntelliOptics 2.0\cloud"
docker compose build backend
docker compose up -d backend
```

### Step 3: Restore Inference Worker

```bash
# Revert inference service
git checkout HEAD~1 -- edge/inference/inference_service.py

# Remove model file
rm edge/inference/yolov8s-worldv2.pt

# Rebuild inference container
cd "C:\dev\IntelliOptics 2.0\edge"
docker compose build inference
docker compose up -d inference
```

### Step 4: Database Cleanup (Optional)

The `yoloworld_prompts` column can be left in place (nullable, no impact) or removed:
```sql
ALTER TABLE demo_sessions DROP COLUMN yoloworld_prompts;
```

### Step 5: Blob Storage Cleanup (Optional)

Remove uploaded models from Azure Blob Storage:
```bash
az storage blob delete --account-name intelliopticsweb37558 --container-name models --name yoloworld/yolov8s-worldv2.onnx
az storage blob delete --account-name intelliopticsweb37558 --container-name models --name yoloworld/clip-vit-b32.onnx
```

## Quick Rollback (All Services)

If you need to rollback everything quickly:

```bash
# Stop all services
cd "C:\dev\IntelliOptics 2.0\cloud"
docker compose down

cd "C:\dev\IntelliOptics 2.0\edge"
docker compose down

# Git revert all changes
cd "C:\dev\IntelliOptics 2.0"
git checkout HEAD~1 -- cloud/frontend/src/pages/DemoStreamPage.tsx
git checkout HEAD~1 -- cloud/backend/app/schemas.py
git checkout HEAD~1 -- cloud/backend/app/models.py
git checkout HEAD~1 -- cloud/backend/app/routers/demo_streams.py
git checkout HEAD~1 -- edge/inference/inference_service.py
rm cloud/backend/app/services/yoloworld_inference.py
rm edge/inference/yolov8s-worldv2.pt

# Rebuild all
cd "C:\dev\IntelliOptics 2.0\cloud"
docker compose build
docker compose up -d

cd "C:\dev\IntelliOptics 2.0\edge"
docker compose build
docker compose up -d
```

## Configuration Changes

### Environment Variables (No changes required)
The feature uses existing worker URL from settings.

### WORKER_URL Configuration
YOLOWorld uses: `{settings.worker_url}/yoloworld`

## Dependencies Added to Inference Worker

The inference worker Dockerfile/requirements.txt now includes:
- `ultralytics==8.0.206` (includes YOLOWorld support)
- PyTorch and related CUDA libraries

## Testing After Rollback

1. Verify demo page loads without YOLOWorld button
2. Verify existing webcam capture still works
3. Verify inference service health: `curl http://localhost:8001/health`
4. Check that `yoloworld_loaded` field is absent from health response

## Password Change Also Made

During this session, the password for `jmorgan@4wardmotions.com` was changed.

To revert if needed:
```sql
-- Query to check current password hash
SELECT email, hashed_password FROM users WHERE email = 'jmorgan@4wardmotions.com';

-- Note: Original password hash was not preserved. If rollback needed,
-- generate a new hash and update manually.
```

## Contact

For questions about this rollback documentation, refer to the session transcript or contact the development team.
