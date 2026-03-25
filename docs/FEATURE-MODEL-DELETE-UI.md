# Feature: Remove Model from Detector UI

## Overview
Add "Remove Model" functionality to the Detector Config Page, allowing users to **unlink** models from a detector's configuration without manual database edits.

**IMPORTANT**: This does NOT delete the actual model file from Azure Blob Storage. It only removes the reference/path from the detector. Other detectors using the same model are unaffected.

## User Story
**As a user**, I want to remove model references from a detector's configuration via the UI, so that I can:
- Disable OODD without manual SQL commands
- Clear corrupted model references
- Switch between model configurations easily
- Test detectors with/without OODD
- Share models across detectors without fear of deletion

**Note**: The model file remains in Azure Blob Storage and can be re-assigned to any detector anytime.

## Current vs. Proposed UI

### Current (Model Management Section)
```
Model Management
├─ Primary Model
│  └─ [Choose File] [Upload Primary Model]
└─ OODD Model
   └─ [Choose File] [Upload OODD Model]
```

### Proposed (With Delete Buttons)
```
Model Management
├─ Primary Model
│  ├─ Current: intellioptics-yolov10n.onnx
│  ├─ [Choose File] [Upload Primary Model] [🗑️ Remove]
│  └─ (Hover tooltip: "Remove this model from detector configuration")
└─ OODD Model
   ├─ Current: resnet18-v1-7.onnx
   ├─ [Choose File] [Upload OODD Model] [🗑️ Remove]
   └─ (Hover tooltip: "Remove OODD model - detector will use Primary only")
```

## Technical Implementation

### 1. Backend API Endpoint (New)

**File**: `C:\Dev\IntelliOptics 2.0\cloud\backend\app\routers\detectors.py`

**Add after line 121** (after `upload_detector_model` function):

```python
@router.delete("/{detector_id}/model")
def remove_model_from_detector(
    detector_id: uuid.UUID,
    model_type: str = "primary",  # "primary" or "oodd"
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> dict:
    """
    Remove model reference from a detector (sets blob path to NULL).

    IMPORTANT: This does NOT delete the model file from Azure Blob Storage.
    It only removes the path reference from this detector's configuration.
    Other detectors using the same model are unaffected.

    The model file remains in storage and can be re-assigned to this or other detectors.
    """
    det = db.query(models.Detector).get(detector_id)
    if not det:
        raise HTTPException(status_code=404, detail="Detector not found")

    # Validate model_type
    if model_type not in ["primary", "oodd"]:
        raise HTTPException(status_code=400, detail="model_type must be 'primary' or 'oodd'")

    # Prevent removing Primary model (dangerous - detector won't work)
    if model_type == "primary":
        raise HTTPException(
            status_code=400,
            detail="Cannot remove Primary model - detector requires it to function. Upload a different model instead."
        )

    # Remove OODD model reference (safe - detector works without OODD)
    if model_type == "oodd":
        if not det.oodd_model_blob_path:
            raise HTTPException(status_code=400, detail="No OODD model configured for this detector")

        old_path = det.oodd_model_blob_path  # Save for response/logging
        det.oodd_model_blob_path = None
        db.commit()
        db.refresh(det)

        # Note: Worker cache clearing happens automatically on next inference
        # The worker checks database paths and downloads if missing
        # The actual model file remains in Azure Blob Storage unchanged

        return {
            "message": f"OODD model reference removed successfully. Detector will use Primary model only.",
            "detector_id": str(detector_id),
            "model_type": model_type,
            "removed_path": old_path,
            "note": "Model file remains in storage and can be re-assigned anytime."
        }
```

**Alternative (Allow Primary Deletion with Warning)**:
```python
# If you want to allow Primary deletion (more dangerous):
if model_type == "primary":
    if not det.primary_model_blob_path:
        raise HTTPException(status_code=400, detail="No Primary model configured")

    det.primary_model_blob_path = None
    det.model_blob_path = None  # Backward compatibility
    db.commit()
    db.refresh(det)

    return {
        "message": "Primary model removed. WARNING: Detector will not function until new model is uploaded.",
        "detector_id": str(detector_id),
        "model_type": model_type,
        "warning": "Inference will fail until you upload a new Primary model."
    }
```

### 2. Frontend UI Changes

**File**: `C:\Dev\IntelliOptics 2.0\cloud\frontend\src\pages\DetectorConfigPage.tsx`

**Find the Model Management section** (around line 800-900) and update:

#### Add Delete Handler Function
Add this after the model upload handlers (around line 250):

```typescript
const handleRemoveModel = async (modelType: 'primary' | 'oodd') => {
  // Confirmation dialog
  const modelName = modelType === 'primary' ? 'Primary Model' : 'OODD Model';
  const confirmMessage = modelType === 'oodd'
    ? `Remove OODD model reference from this detector?\n\nDetector will use Primary model only (confidence scores may increase).\n\nNote: The model file remains in storage and can be re-assigned.`
    : `Remove Primary model reference from this detector?\n\nWARNING: Detector will stop working until you assign a new model!\n\nNote: The model file remains in storage.`;

  if (!window.confirm(confirmMessage)) {
    return;
  }

  try {
    await axios.delete(`/detectors/${id}/model`, {
      params: { model_type: modelType }
    });

    // Refresh detector data
    fetchDetector();

    // Show success message
    alert(modelType === 'oodd'
      ? 'OODD model removed from this detector. Model file remains in storage and can be re-assigned.'
      : 'Primary model removed from this detector. Please assign a new model immediately.'
    );
  } catch (err: any) {
    console.error(`Failed to remove ${modelName} reference:`, err);
    alert(`Failed to remove ${modelName}: ${err.response?.data?.detail || err.message}`);
  }
};
```

#### Update Model Management JSX
Find the Model Management section and update to:

```tsx
{/* Model Management */}
<div className="bg-gray-800 rounded-lg shadow-md p-6 border border-gray-700">
  <h3 className="text-lg font-bold mb-4 text-white uppercase tracking-wider">Model Management</h3>

  {/* Primary Model */}
  <div className="mb-6">
    <label className="block text-sm font-medium text-gray-400 mb-2">
      Primary Model {detector?.primary_model_blob_path && '✓'}
    </label>

    {detector?.primary_model_blob_path && (
      <div className="mb-2 p-2 bg-gray-900/50 rounded border border-gray-700">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-gray-500">Current Model:</p>
            <p className="text-sm text-green-400 font-mono break-all">
              {detector.primary_model_blob_path.split('/').pop()}
            </p>
            <p className="text-xs text-gray-600 mt-1">
              Full path: {detector.primary_model_blob_path}
            </p>
          </div>
        </div>
      </div>
    )}

    <div className="flex items-center gap-2">
      <input
        type="file"
        accept=".onnx,.pt,.pth"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) setPrimaryModelFile(file);
        }}
        className="text-sm text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-semibold file:bg-blue-600 file:text-white hover:file:bg-blue-500 file:cursor-pointer"
      />
      <button
        onClick={() => handleModelUpload('primary')}
        disabled={!primaryModelFile || uploading}
        className="bg-blue-600 hover:bg-blue-500 text-white font-bold py-2 px-4 rounded transition disabled:bg-gray-600 disabled:cursor-not-allowed"
      >
        {uploading ? 'Uploading...' : 'Upload Primary Model'}
      </button>

      {/* Remove button - only show if model exists */}
      {detector?.primary_model_blob_path && (
        <button
          onClick={() => handleRemoveModel('primary')}
          disabled={uploading}
          title="Remove Primary model reference from this detector (model file remains in storage)"
          className="bg-red-600 hover:bg-red-500 text-white font-bold py-2 px-4 rounded transition disabled:bg-gray-600 disabled:cursor-not-allowed flex items-center gap-2"
        >
          <span>🔗</span> Unlink
        </button>
      )}
    </div>
    <p className="text-xs text-gray-500 mt-2">
      Upload ONNX model file (.onnx) for primary detection
      {detector?.primary_model_blob_path && ' • WARNING: Removing will disable detector'}
    </p>
  </div>

  {/* OODD Model */}
  <div className="mb-4">
    <label className="block text-sm font-medium text-gray-400 mb-2">
      OODD Model (Optional) {detector?.oodd_model_blob_path && '✓'}
    </label>

    {detector?.oodd_model_blob_path && (
      <div className="mb-2 p-2 bg-gray-900/50 rounded border border-gray-700">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-gray-500">Current Model:</p>
            <p className="text-sm text-green-400 font-mono break-all">
              {detector.oodd_model_blob_path.split('/').pop()}
            </p>
            <p className="text-xs text-gray-600 mt-1">
              Full path: {detector.oodd_model_blob_path}
            </p>
          </div>
        </div>
      </div>
    )}

    <div className="flex items-center gap-2">
      <input
        type="file"
        accept=".onnx,.pt,.pth"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) setOoddModelFile(file);
        }}
        className="text-sm text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:text-sm file:font-semibold file:bg-purple-600 file:text-white hover:file:bg-purple-500 file:cursor-pointer"
      />
      <button
        onClick={() => handleModelUpload('oodd')}
        disabled={!ooddModelFile || uploading}
        className="bg-purple-600 hover:bg-purple-500 text-white font-bold py-2 px-4 rounded transition disabled:bg-gray-600 disabled:cursor-not-allowed"
      >
        {uploading ? 'Uploading...' : 'Upload OODD Model'}
      </button>

      {/* Remove button - only show if OODD model exists */}
      {detector?.oodd_model_blob_path && (
        <button
          onClick={() => handleRemoveModel('oodd')}
          disabled={uploading}
          title="Remove OODD model reference from this detector (model file remains in storage)"
          className="bg-orange-600 hover:bg-orange-500 text-white font-bold py-2 px-4 rounded transition disabled:bg-gray-600 disabled:cursor-not-allowed flex items-center gap-2"
        >
          <span>🔗</span> Unlink
        </button>
      )}
    </div>
    <p className="text-xs text-gray-500 mt-2">
      Out-of-Domain Detection model for confidence calibration
      {detector?.oodd_model_blob_path && ' • Removing will use Primary model only (may increase confidence scores)'}
    </p>
  </div>
</div>
```

### 3. Worker Cache Handling

**Current Behavior**: Worker checks database paths on each inference request. If path is NULL, it skips loading that model.

**No code changes needed** - the worker already handles NULL paths gracefully in `detector_inference.py`:

```python
# Line 289-300 (existing code)
oodd_result = None
if oodd_blob_path:  # If NULL, this condition is False
    log.info(f"Loading OODD model for detector {detector_id}")
    try:
        oodd_model_path = download_model_from_blob(oodd_blob_path, detector_id, "oodd")
        oodd_session = load_onnx_model(oodd_model_path, f"{detector_id}_oodd")
    except Exception as e:
        log.warning(f"Failed to load OODD model: {e}, continuing without OODD")
        oodd_session = None
else:
    oodd_session = None  # OODD disabled
```

**Optional Enhancement**: Add explicit cache clearing endpoint (advanced):

```python
@router.post("/{detector_id}/clear-cache")
def clear_detector_cache(
    detector_id: uuid.UUID,
    current_user=Depends(get_current_admin),
) -> dict:
    """
    Signal worker to clear cache for this detector.
    Note: This is a best-effort operation - worker must implement cache clearing.
    """
    # This would require worker to expose a cache management endpoint
    # For now, cache clears automatically on next inference
    return {
        "message": "Cache will be cleared on next inference request",
        "detector_id": str(detector_id)
    }
```

## Shared Model Use Case (Why This Matters)

### Scenario: Multiple Detectors Sharing OODD Model

**Current State**:
```
Azure Blob Storage:
├─ models/
│  ├─ intellioptics-yolov10n.onnx (shared by all detectors)
│  └─ ood_resnet18/resnet18-v1-7.onnx (shared OODD model)

Database:
├─ Detector A (Parking Lot)
│  ├─ primary_model_blob_path: models/intellioptics-yolov10n.onnx
│  └─ oodd_model_blob_path: models/ood_resnet18/resnet18-v1-7.onnx
├─ Detector B (Loitering)
│  ├─ primary_model_blob_path: models/intellioptics-yolov10n.onnx
│  └─ oodd_model_blob_path: models/ood_resnet18/resnet18-v1-7.onnx
└─ Detector C (Vehicle Count)
   ├─ primary_model_blob_path: models/intellioptics-yolov10n.onnx
   └─ oodd_model_blob_path: models/ood_resnet18/resnet18-v1-7.onnx
```

**User Action**: "Unlink" OODD from Detector A (parking lot has low confidence issue)

**After Unlinking**:
```
Azure Blob Storage: (UNCHANGED)
├─ models/
│  ├─ intellioptics-yolov10n.onnx ✅ Still exists
│  └─ ood_resnet18/resnet18-v1-7.onnx ✅ Still exists

Database:
├─ Detector A (Parking Lot)
│  ├─ primary_model_blob_path: models/intellioptics-yolov10n.onnx
│  └─ oodd_model_blob_path: NULL ⬅️ Only this changed
├─ Detector B (Loitering) ✅ Unchanged
│  ├─ primary_model_blob_path: models/intellioptics-yolov10n.onnx
│  └─ oodd_model_blob_path: models/ood_resnet18/resnet18-v1-7.onnx
└─ Detector C (Vehicle Count) ✅ Unchanged
   ├─ primary_model_blob_path: models/intellioptics-yolov10n.onnx
   └─ oodd_model_blob_path: models/ood_resnet18/resnet18-v1-7.onnx
```

**Result**:
- ✅ Detector A: Works without OODD, normal confidence scores
- ✅ Detector B: Still uses OODD, unaffected
- ✅ Detector C: Still uses OODD, unaffected
- ✅ Model files: Safe in storage, can be re-assigned anytime

**Re-assigning Later**:
User can simply select "Upload OODD Model" on Detector A, choose the same file, and it will be re-linked.

Or better yet, add a "Model Library" feature where users can select from existing models in storage without re-uploading (future enhancement).

## Testing Plan

### Test 1: Unlink OODD Model (Happy Path)
1. Go to Detector Config Page for detector with OODD model
2. Click "Unlink" button next to OODD Model (🔗 icon)
3. Read confirmation dialog (mentions model file remains in storage)
4. Confirm
5. **Expected**:
   - Success message: "OODD model removed from this detector. Model file remains in storage..."
   - OODD model section shows "No model uploaded"
   - Primary model still shown
   - Upload OODD button still available
   - Can re-upload same model anytime

### Test 2: Run Inference Without OODD
1. After deleting OODD model
2. Upload test image
3. Click "Run Test"
4. **Expected**:
   - Inference succeeds
   - Confidence scores normal (50-90%)
   - No OODD metrics shown
   - `oodd_metrics: null` in response

### Test 3: Attempt Unlink Primary Model
1. Click "Unlink" button next to Primary Model (🔗 icon)
2. Read warning dialog (mentions detector will stop working)
3. **Option A** (if backend prevents it): Error message "Cannot remove Primary model"
4. **Option B** (if backend allows it): Confirm, model unlinked, inference fails with clear error

### Test 4: Re-upload OODD After Unlinking
1. Unlink OODD model
2. Run test (works without OODD, normal confidence)
3. Upload the same OODD model again (or different one)
4. Run test (OODD re-enabled)
5. **Expected**: Smooth workflow, no errors, can switch back and forth

### Test 5: Verify Model File Still in Storage
1. Note the OODD model path before unlinking (e.g., `models/ood_resnet18/resnet18-v1-7.onnx`)
2. Unlink OODD from Detector A
3. Go to Detector B
4. **Expected**: Detector B still shows the same OODD path, still works
5. **Verify**: Azure Blob Storage still has the file (check via Azure Portal or API)

### Test 6: Other Detectors Unaffected
1. Unlink OODD from Detector A
2. Navigate to Detector B (using same OODD model)
3. Run inference on Detector B
4. **Expected**:
   - Detector B still has its OODD model path
   - Detector B inference still uses OODD
   - No errors or warnings

## User Experience Benefits

### Before (Current)
❌ User sees low confidence (3-8%)
❌ Needs to ask developer for help
❌ Developer runs SQL commands manually
❌ Developer clears worker cache manually
❌ User doesn't understand what happened

### After (With Delete UI)
✅ User sees low confidence (3-8%)
✅ User clicks "Remove OODD Model" button
✅ Reads tooltip: "Remove OODD model - detector will use Primary only"
✅ Confirms action
✅ System automatically handles database + cache
✅ Immediate feedback: "OODD removed, using Primary only"
✅ User runs test again → normal confidence ✅

## Security Considerations

### Authorization
- ✅ Requires admin role (`Depends(get_current_admin)`)
- ✅ Only authenticated users can delete models

### Safety Guards
- ✅ Confirmation dialog in UI
- ✅ Clear warning for Primary model deletion
- ✅ Backend validation (model_type must be 'primary' or 'oodd')
- ✅ 404 if detector doesn't exist
- ✅ 400 if no model configured

### Audit Trail (Optional Enhancement)
```python
# Add to delete_detector_model function
log.info(f"Admin {current_user.email} deleted {model_type} model from detector {detector_id}")

# Or add to database
audit_log = AuditLog(
    user_id=current_user.id,
    action="delete_model",
    resource_type="detector",
    resource_id=str(detector_id),
    details={"model_type": model_type, "old_path": old_path}
)
db.add(audit_log)
```

## Implementation Checklist

### Backend
- [ ] Add DELETE endpoint to `detectors.py`
- [ ] Add input validation (model_type)
- [ ] Add safety checks (prevent Primary deletion OR add strong warning)
- [ ] Test endpoint with curl/Postman
- [ ] Verify database NULL update works
- [ ] Test error cases (detector not found, no model configured)

### Frontend
- [ ] Add `handleDeleteModel` function
- [ ] Add Remove buttons to UI
- [ ] Style buttons (red for Primary, orange for OODD)
- [ ] Add confirmation dialogs
- [ ] Add tooltips with explanations
- [ ] Test button states (disabled when uploading)
- [ ] Test success/error messages
- [ ] Verify page refresh after deletion

### Integration Testing
- [ ] Test full workflow: delete → test inference → re-upload
- [ ] Test both Primary and OODD deletion
- [ ] Verify other detectors unaffected
- [ ] Test edge cases (delete non-existent model)
- [ ] Test with multiple users (admin vs non-admin)

### Documentation
- [ ] Update user guide with model deletion instructions
- [ ] Add tooltips/help text in UI
- [ ] Document API endpoint in Swagger/OpenAPI
- [ ] Add to release notes

## Rollout Strategy

### Phase 1: OODD Only (Safer)
- Implement delete for OODD model only
- Prevent Primary model deletion (backend blocks it)
- Release to production
- Gather user feedback

### Phase 2: Primary with Strong Warnings (Optional)
- Add Primary model deletion with multiple confirmations
- Show warning: "Detector will NOT work until you upload new model"
- Require typing "DELETE" to confirm
- Add banner on detector page: "⚠️ No Primary model - detector disabled"

## Alternative: "Disable OODD" Toggle

Instead of deletion, add a simple toggle:

```tsx
<div className="flex items-center justify-between">
  <div>
    <label className="text-sm font-medium text-gray-400">Enable OODD</label>
    <p className="text-xs text-gray-600">Use OODD for confidence calibration</p>
  </div>
  <input
    type="checkbox"
    checked={detector?.oodd_enabled ?? true}
    onChange={(e) => handleToggleOODD(e.target.checked)}
    className="toggle-checkbox"
  />
</div>
```

**Pros**:
- Non-destructive (model still stored, just not used)
- Can easily re-enable
- Clearer user intent

**Cons**:
- Requires new database column `oodd_enabled`
- Requires worker code changes to check flag

## Recommendation

**Implement the Delete button approach** because:
1. ✅ No database schema changes
2. ✅ No worker code changes
3. ✅ Straightforward implementation
4. ✅ Users can re-upload models anytime
5. ✅ Matches existing upload/remove pattern in UIs

---

**Estimated Effort**: 2-3 hours (backend + frontend + testing)
**Risk Level**: Low (isolated feature, doesn't break existing functionality)
**User Impact**: High (makes OODD management accessible to non-technical users)

**Created**: 2026-01-13
