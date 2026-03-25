# Quick Fix: Disable OODD for Low Confidence Issue

## Problem
Detector `2467f56e-07bb-447e-9122-47595563e34a` (Vehicle Detection Lot A) returns 3-8% confidence scores because the OODD model incorrectly marks parking lot images as out-of-domain.

## Solution
Disable OODD model for this detector to restore normal confidence scores.

## Implementation Steps

### Step 1: Backup Current Configuration (MANDATORY)
```bash
cd "C:\Dev\IntelliOptics 2.0\cloud"

# Backup detector configuration
docker-compose exec postgres psql -U intellioptics -d intellioptics -c "
SELECT id, name, primary_model_blob_path, oodd_model_blob_path
FROM detectors
WHERE id = '2467f56e-07bb-447e-9122-47595563e34a';
" > detector_backup_before_fix.txt

# Save to timestamped file
echo "Backup created: detector_backup_before_fix.txt at $(date)" >> fix_log.txt
```

### Step 2: Disable OODD Model
```bash
docker-compose exec postgres psql -U intellioptics -d intellioptics -c "
UPDATE detectors
SET oodd_model_blob_path = NULL
WHERE id = '2467f56e-07bb-447e-9122-47595563e34a';
"
```

**Expected output**: `UPDATE 1`

### Step 3: Verify Database Update
```bash
docker-compose exec postgres psql -U intellioptics -d intellioptics -c "
SELECT id, name, primary_model_blob_path, oodd_model_blob_path
FROM detectors
WHERE id = '2467f56e-07bb-447e-9122-47595563e34a';
"
```

**Expected output**:
```
id                                   | name                    | primary_model_blob_path            | oodd_model_blob_path
-------------------------------------|-------------------------|------------------------------------|-----------------------
2467f56e-07bb-447e-9122-47595563e34a | Vehicle Detection Lot A | models/intellioptics-yolov10n.onnx | [NULL]
```

### Step 4: Clear Worker Cache
```bash
# Stop worker to ensure clean state
docker-compose stop worker

# Clear cache for this detector
docker-compose run --rm worker sh -c "rm -rf /app/models/2467f56e-07bb-447e-9122-47595563e34a && ls -la /app/models/"

# Start worker
docker-compose start worker

# Wait for worker to be ready (5 seconds)
sleep 5

# Check worker logs
docker-compose logs worker --tail=20
```

**Expected logs**: Should show "Model present: /app/models/intellioptics-yolov10n.onnx" and "Health+Inference server http://0.0.0.0:8081/infer"

### Step 5: Test Inference

#### Option A: Via UI
1. Go to http://localhost (or your frontend URL)
2. Navigate to Detectors → Vehicle Detection Lot A
3. Upload a test image (parking lot with vehicles)
4. Click "Run Test"
5. **Expected results**:
   - Confidence scores: 50-90% (not 3-8%)
   - Detections appear
   - No "model not found" errors

#### Option B: Via API (Advanced)
```bash
# Save test image as test_image.jpg
curl -X POST http://localhost:8000/detectors/2467f56e-07bb-447e-9122-47595563e34a/test \
  -F "image=@test_image.jpg" \
  -H "Content-Type: multipart/form-data"
```

**Expected response**:
```json
{
  "detections": [
    {
      "class": "car",
      "confidence": 0.75,
      "bbox": {...}
    }
  ],
  "inference_time_ms": 150,
  "would_escalate": false,
  "oodd_metrics": null
}
```

Note: `oodd_metrics` should be `null` (OODD disabled)

### Step 6: Verify Other Detectors Unaffected
```bash
# List all detectors
docker-compose exec postgres psql -U intellioptics -d intellioptics -c "
SELECT id, name, oodd_model_blob_path
FROM detectors
ORDER BY name;
"
```

**Expected**: Only `2467f56e-07bb-447e-9122-47595563e34a` has NULL OODD path, others unchanged.

### Step 7: Document Change
```bash
docker-compose exec postgres psql -U intellioptics -d intellioptics -c "
UPDATE detectors
SET description = COALESCE(description, '') || ' [NOTE: OODD disabled 2026-01-13 - using Primary model only due to domain mismatch]'
WHERE id = '2467f56e-07bb-447e-9122-47595563e34a';
"
```

## Verification Checklist

- [ ] Backup created successfully
- [ ] Database UPDATE returned "UPDATE 1"
- [ ] `oodd_model_blob_path` is NULL for this detector
- [ ] Worker cache cleared
- [ ] Worker restarted successfully
- [ ] Test inference shows 50-90% confidence (not 3-8%)
- [ ] Other detectors unaffected
- [ ] Documentation updated

## Rollback Procedure

If something breaks:

```bash
# 1. Restore OODD model path
docker-compose exec postgres psql -U intellioptics -d intellioptics -c "
UPDATE detectors
SET oodd_model_blob_path = 'models/ood_resnet18/resnet18-v1-7.onnx'
WHERE id = '2467f56e-07bb-447e-9122-47595563e34a';
"

# 2. Restart worker
docker-compose restart worker

# 3. Verify
docker-compose exec postgres psql -U intellioptics -d intellioptics -c "
SELECT id, name, oodd_model_blob_path
FROM detectors
WHERE id = '2467f56e-07bb-447e-9122-47595563e34a';
"
```

## Expected Behavior After Fix

### Before Fix (OODD Enabled)
- Primary model: 88.9% confidence
- OODD: 7.9% in-domain score → applies 0.5x adjustment
- Final confidence: 3.5% ❌

### After Fix (OODD Disabled)
- Primary model: 88.9% confidence
- OODD: Not run (disabled)
- Final confidence: 88.9% ✅

## Troubleshooting

### Issue: "UPDATE 0" (No Rows Updated)
**Cause**: Detector ID typo or doesn't exist
**Fix**: Verify detector ID exists
```bash
docker-compose exec postgres psql -U intellioptics -d intellioptics -c "SELECT id, name FROM detectors;"
```

### Issue: Worker Still Uses OODD
**Cause**: Cache not cleared or database connection pooled
**Fix**:
```bash
docker-compose stop worker backend
docker-compose exec worker rm -rf /app/models/2467f56e-07bb-447e-9122-47595563e34a
docker-compose start worker backend
```

### Issue: Still Low Confidence After Fix
**Cause**: Wrong detector being tested
**Fix**: Double-check detector ID in UI matches `2467f56e-07bb-447e-9122-47595563e34a`

### Issue: Worker Won't Start
**Cause**: Service Bus authentication error (non-critical, worker still functions for HTTP inference)
**Fix**: Ignore Service Bus errors, worker HTTP endpoint still works

## Success Criteria

✅ **Fixed when**:
1. Detector inference returns 50-90% confidence for clear vehicle detections
2. No "model not found" errors
3. Worker logs show no OODD loading for this detector
4. Other detectors still work normally
5. Database backup exists

## Next Steps (Future Work)

This is a **temporary fix**. For proper OODD functionality:
1. Collect 500-1000 parking lot images (in-domain)
2. Collect 500-1000 non-parking-lot images (out-of-domain)
3. Train detector-specific OODD model
4. Re-enable OODD with trained model

See `LOW-CONFIDENCE-ISSUE-ANALYSIS.md` for full details.

## Date
2026-01-13
