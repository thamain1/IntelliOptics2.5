# Detector Model Path Fix

## Issue
Detector `2467f56e-07bb-447e-9122-47595563e34a` (Vehicle Detection Lot A) was showing "no model detected" error when running inference tests.

## Root Cause
The detector's model paths in the database were pointing to detector-specific folders that don't exist in Azure Blob Storage:

**Incorrect paths:**
```
primary_model_blob_path: models/2467f56e-07bb-447e-9122-47595563e34a/primary/intellioptics-yolov10n.onnx
oodd_model_blob_path: models/2467f56e-07bb-447e-9122-47595563e34a/oodd/resnet18-v1-7.onnx
```

These detector-specific folders were never created when the models were uploaded. The actual models exist in global paths.

## Fix Applied
Updated the database to use the correct global model paths:

```sql
UPDATE detectors
SET
    primary_model_blob_path = 'models/intellioptics-yolov10n.onnx',
    oodd_model_blob_path = 'models/ood_resnet18/resnet18-v1-7.onnx'
WHERE id = '2467f56e-07bb-447e-9122-47595563e34a';
```

**Correct paths:**
```
primary_model_blob_path: models/intellioptics-yolov10n.onnx
oodd_model_blob_path: models/ood_resnet18/resnet18-v1-7.onnx
```

## Root Cause Analysis - Cached Corrupted Model

After the database update, the error persisted because:
1. The worker had **cached the corrupted model file** locally at `/app/models/2467f56e-07bb-447e-9122-47595563e34a/primary/model.onnx`
2. The download logic checks if model already exists in cache before downloading
3. Worker log showed: `Model already cached` → tried to load corrupted file → `ModelProto does not have a graph` error

**Key insight:** Database updates alone don't clear the worker's local file cache!

## Complete Fix Applied

### Step 1: Update Database Paths ✅
```sql
UPDATE detectors
SET
    primary_model_blob_path = 'models/intellioptics-yolov10n.onnx',
    oodd_model_blob_path = 'models/ood_resnet18/resnet18-v1-7.onnx'
WHERE id = '2467f56e-07bb-447e-9122-47595563e34a';
```

### Step 2: Clear Corrupted Cache ✅
```bash
docker-compose exec worker rm -rf /app/models/2467f56e-07bb-447e-9122-47595563e34a
```

### Step 3: Restart Worker ✅
```bash
docker-compose restart worker
```

## Verification Status
- ✅ Database paths updated (1 row affected)
- ✅ Corrupted cache directory removed
- ✅ Worker service restarted
- ✅ Worker loading global model successfully

## Next Steps

### 1. Test the Detector
Go to the Detector Config Page for "Vehicle Detection Lot A" and run a test inference:
1. Upload a test image
2. Click "Run Test"
3. Verify inference completes without "no model detected" error
4. Check that results show confidence scores and OODD metrics

### 2. Check Other Detectors
Run this query to find any other detectors with similar path issues:

```sql
SELECT id, name, primary_model_blob_path, oodd_model_blob_path
FROM detectors
WHERE primary_model_blob_path LIKE '%/%/%/%'
   OR oodd_model_blob_path LIKE '%/%/%/%';
```

If any detectors have deep paths (more than 2 levels), they may have the same issue.

### 3. Fix Any Other Affected Detectors
For each detector with incorrect paths, update to use global model paths:

```sql
UPDATE detectors
SET
    primary_model_blob_path = 'models/intellioptics-yolov10n.onnx',
    oodd_model_blob_path = 'models/ood_resnet18/resnet18-v1-7.onnx'
WHERE id = '<detector_id>';
```

### 4. Prevent Corrupted Cache Issues

**IMPORTANT:** If you ever update model paths in the database, you MUST clear the worker's cached models:

```bash
# Clear cache for specific detector
docker-compose exec worker rm -rf /app/models/<detector_id>

# OR: Clear all cached models
docker-compose exec worker rm -rf /app/models/*

# Then restart worker
docker-compose restart worker
```

**Why this matters:**
- The worker caches downloaded models locally in `/app/models/`
- If a model path changes, the old cached file becomes stale/invalid
- The worker doesn't automatically detect database path changes
- You must manually clear the cache to force re-download

### 5. Model Upload Process Review
**Future uploads should follow this pattern:**

When uploading models via the UI:
- The file upload endpoint (`POST /detectors/{id}/model`) currently stores models with detector-specific paths
- This is correct IF the models are detector-specific
- However, if you're using shared models (like the global YOLOv10n), you should manually set the paths to global locations after upload

**Recommended approach:**
1. Upload model to Azure Blob Storage `models/` container
2. Manually update detector's blob paths in database to point to correct location
3. **Clear worker cache** for that detector
4. Restart worker
5. OR: Modify the upload endpoint to support "shared" vs "detector-specific" models

### 6. Long-term Solution
Consider implementing a model management system that:
- Tracks which detectors use which models (many-to-many relationship)
- Allows model versioning and rollback
- Automatically handles shared vs. detector-specific models
- Validates model paths before saving to database

## Files Modified
- Database: `detectors` table, detector ID `2467f56e-07bb-447e-9122-47595563e34a`

## Related Files
- `C:\Dev\IntelliOptics 2.0\cloud\backend\app\routers\detectors.py` (line 95-121: model upload endpoint)
- `C:\Dev\IntelliOptics 2.0\cloud\worker\detector_inference.py` (line 65-122: model download logic)

## Date
2026-01-13
