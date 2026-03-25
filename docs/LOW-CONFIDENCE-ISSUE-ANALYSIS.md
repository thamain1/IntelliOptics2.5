# Low Confidence Issue - Root Cause Analysis & Action Plan

## Issue Summary
Detector `2467f56e-07bb-447e-9122-47595563e34a` (Vehicle Detection Lot A) is returning very low confidence scores (~3-8%) even though the Primary model detects vehicles correctly with high confidence (88.9%).

## Root Cause Analysis

### What's Happening
1. **Primary model detects correctly**: Motorcycle detected with **88.9% confidence** ✅
2. **OODD model marks image as out-of-domain**: `in_domain_score = 0.079` (7.9%) ❌
3. **Confidence adjustment applied**:
   - Formula: `final_confidence = primary_confidence × (oodd_score × 0.5)`
   - Calculation: `0.889 × (0.079 × 0.5) = 0.889 × 0.0395 = 0.035` (3.5%)
4. **Result**: High-quality detection crushed to 3.5% confidence

### Why This Happens
The detector is using **generic pre-trained models** that were NOT trained for parking lot vehicle detection:

| Model | Purpose | Actual Training Data | Problem |
|-------|---------|---------------------|---------|
| **Primary** | Vehicle detection | COCO dataset (80 object classes, general scenes) | Works OK for vehicles but not optimized for parking lots |
| **OODD** | Out-of-domain detection | ImageNet (1000 classes: animals, objects, natural images) | Has NEVER seen a parking lot → marks all parking lot images as out-of-domain |

**Key Insight**: The OODD model thinks parking lot images are "weird" because it was trained on ImageNet (dogs, cats, fruits, furniture), not parking lots. This causes it to drastically reduce confidence scores for perfectly valid detections.

### Evidence from Logs
```
2026-01-13 17:28:22,366 INFO detector-inference OODD result: in_domain=False, score=0.079
2026-01-13 17:28:22,514 INFO detector-inference Sample detection: {'label': 'motorcycle', 'confidence': 0.889283299446106, ...}
```

- Primary model: 88.9% confidence ✅
- OODD: 7.9% in-domain score ❌
- Final result: ~3.5% confidence after adjustment ❌

## Impact Assessment

### What's Working
- ✅ Models download from Azure Blob Storage
- ✅ Primary model detects objects correctly
- ✅ OODD model runs without errors
- ✅ Inference pipeline executes end-to-end
- ✅ Database paths are correct
- ✅ Worker cache is clean

### What's Broken
- ❌ OODD model not trained for parking lot domain
- ❌ Confidence scores unrealistically low
- ❌ All detections would trigger escalation (below 50% threshold)
- ❌ System not production-ready with current models

## Solution Options

### Option 1: Disable OODD Confidence Adjustment (Quick Fix - Recommended for Testing)
**Effort**: 5 minutes
**Risk**: Low (doesn't break anything, just disables one feature)
**Benefit**: Immediate return to normal confidence scores

**How**: Set detector's `oodd_model_blob_path` to `NULL` in database

**Pros**:
- Immediate fix
- Primary model confidence returned as-is
- No code changes needed

**Cons**:
- Loses out-of-domain detection capability
- No protection against novel/unusual images

**Implementation**:
```sql
UPDATE detectors
SET oodd_model_blob_path = NULL
WHERE id = '2467f56e-07bb-447e-9122-47595563e34a';
```

### Option 2: Adjust OODD Threshold (Medium Fix)
**Effort**: 10 minutes
**Risk**: Low
**Benefit**: Keep OODD enabled but reduce its aggressiveness

**How**: Lower the `calibrated_threshold` in OODD inference from 0.444 to 0.05

**Pros**:
- Keep OODD enabled
- More lenient about what's "in-domain"
- Quick fix

**Cons**:
- OODD becomes less effective at catching true out-of-domain cases
- Still not ideal - just masking the problem

**Implementation**: Edit `cloud/worker/detector_inference.py` line 186

### Option 3: Train Detector-Specific OODD Model (Proper Fix - Long Term)
**Effort**: 2-4 hours + training time
**Risk**: Medium (requires retraining)
**Benefit**: OODD actually works correctly for parking lot domain

**How**: Collect 500-1000 parking lot images, train ResNet18 OODD model

**Pros**:
- OODD correctly identifies parking lot images as in-domain
- System works as designed
- Proper solution

**Cons**:
- Requires data collection
- Requires model training infrastructure
- Takes time

**Implementation**: See "OODD Model Training Guide" below

### Option 4: Use YOLOv10n Without OODD (Production Compromise)
**Effort**: 5 minutes
**Risk**: Low
**Benefit**: Production-ready without OODD

**How**: Disable OODD for all detectors using generic models

**Pros**:
- Works immediately
- YOLOv10n is already good for vehicle detection
- No retraining needed

**Cons**:
- No out-of-domain protection
- Missing a key differentiator feature

## Recommended Action Plan

### Phase 1: Immediate Fix (Do Now) ✅
**Goal**: Get system working with normal confidence scores

1. **Disable OODD for this detector** (5 min)
   ```sql
   UPDATE detectors
   SET oodd_model_blob_path = NULL
   WHERE id = '2467f56e-07bb-447e-9122-47595563e34a';
   ```

2. **Test inference** (2 min)
   - Go to Detector Config Page
   - Upload parking lot vehicle image
   - Run Test
   - Verify confidence scores are normal (50-90%)

3. **Document decision** (3 min)
   - Add note to detector description: "OODD disabled - using Primary model only"

### Phase 2: Proper OODD Setup (Next Sprint)
**Goal**: Train detector-specific OODD model

1. **Collect in-domain images** (500-1000 images)
   - Parking lot scenes with vehicles
   - Various lighting conditions
   - Different camera angles
   - Include edge cases (empty lots, crowded lots, night/day)

2. **Collect out-of-domain images** (500-1000 images)
   - Indoor scenes
   - Faces/people close-ups
   - Natural landscapes
   - Non-parking-lot outdoor scenes

3. **Train OODD model**
   - Use ResNet18 architecture
   - Binary classification: in-domain vs out-of-domain
   - Train for 20-50 epochs
   - Validate on hold-out set

4. **Upload trained model**
   - Upload to Azure Blob Storage `models/oodd_parking_lot_v1/resnet18.onnx`
   - Update detector's `oodd_model_blob_path`
   - Clear worker cache
   - Test

### Phase 3: Optimize Primary Model (Future)
**Goal**: Train custom vehicle detector for parking lots

1. **Collect annotated parking lot images**
   - 1000+ images with bounding box annotations
   - Label vehicles: car, truck, bus, motorcycle, bicycle

2. **Fine-tune YOLOv10n**
   - Start from COCO pre-trained weights
   - Fine-tune on parking lot dataset
   - Optimize for parking lot specific scenarios

3. **Deploy custom model**

## CRITICAL: What NOT to Break

### Database Integrity ⚠️
**DO NOT**:
- Delete or modify detectors other than `2467f56e-07bb-447e-9122-47595563e34a`
- Change Primary model paths for other detectors
- Delete any rows from `queries`, `escalations`, or `feedback` tables
- Modify `detector_configs` for other detectors

**ALWAYS**:
- Use `WHERE id = '2467f56e-07bb-447e-9122-47595563e34a'` in UPDATE queries
- Backup database before making changes (see below)
- Test changes on single detector first

### Worker Cache Management ⚠️
**DO NOT**:
- Delete `/app/models/intellioptics-yolov10n.onnx` (used by other detectors)
- Delete cache directories for other detectors
- Delete entire `/app/models/` directory

**ONLY DELETE**:
- `/app/models/2467f56e-07bb-447e-9122-47595563e34a/` (specific detector cache)

### Code Changes ⚠️
**DO NOT**:
- Modify inference pipeline logic in `detector_inference.py` unless necessary
- Change database schema
- Break existing API endpoints

**SAFE TO MODIFY**:
- Detector-specific configuration via API or database
- OODD threshold parameters (if well-documented)
- Add new optional features (don't remove existing)

## Database Backup Procedure

**Before making ANY database changes:**
```bash
# 1. Backup entire database
cd "C:\Dev\IntelliOptics 2.0\cloud"
docker-compose exec postgres pg_dump -U intellioptics -d intellioptics > backup_$(date +%Y%m%d_%H%M%S).sql

# 2. Backup specific detector config
docker-compose exec postgres psql -U intellioptics -d intellioptics -c "
COPY (SELECT * FROM detectors WHERE id = '2467f56e-07bb-447e-9122-47595563e34a')
TO '/tmp/detector_backup.csv' WITH CSV HEADER;
"
docker-compose exec postgres psql -U intellioptics -d intellioptics -c "
COPY (SELECT * FROM detector_configs WHERE detector_id = '2467f56e-07bb-447e-9122-47595563e34a')
TO '/tmp/detector_config_backup.csv' WITH CSV HEADER;
"
```

## Testing Checklist

After implementing fixes, verify:

### ✅ Basic Functionality
- [ ] Detector page loads without errors
- [ ] Model information displays correctly
- [ ] Test image upload works
- [ ] Inference completes without errors
- [ ] Results display in UI

### ✅ Confidence Scores
- [ ] Confidence scores are realistic (50-90% for clear detections)
- [ ] Low confidence for ambiguous images (acceptable)
- [ ] No negative or >100% confidence values

### ✅ Other Detectors Unaffected
- [ ] Test another detector (e.g., Loitering detector)
- [ ] Verify it still works normally
- [ ] Check its confidence scores unchanged

### ✅ Database Integrity
- [ ] Run database integrity check (see below)
- [ ] Verify foreign keys intact
- [ ] Check no orphaned records

### ✅ Worker Health
- [ ] Worker logs show no errors
- [ ] Models load successfully
- [ ] Cache size reasonable (<1GB)

## Database Integrity Check

```sql
-- Check detector exists and has valid paths
SELECT id, name, primary_model_blob_path, oodd_model_blob_path
FROM detectors
WHERE id = '2467f56e-07bb-447e-9122-47595563e34a';

-- Check config exists
SELECT detector_id, mode, confidence_threshold
FROM detector_configs
WHERE detector_id = '2467f56e-07bb-447e-9122-47595563e34a';

-- Check no orphaned configs
SELECT COUNT(*) as orphaned_configs
FROM detector_configs dc
LEFT JOIN detectors d ON dc.detector_id = d.id
WHERE d.id IS NULL;

-- Check queries for this detector
SELECT COUNT(*) as query_count,
       AVG(confidence) as avg_confidence
FROM queries
WHERE detector_id = '2467f56e-07bb-447e-9122-47595563e34a';
```

Expected results:
- Detector row exists with NULL or valid OODD path
- Config row exists with confidence_threshold = 0.5
- 0 orphaned configs
- Query stats show improved average confidence after fix

## Rollback Procedure

If something breaks:

```bash
# 1. Stop services
cd "C:\Dev\IntelliOptics 2.0\cloud"
docker-compose stop worker backend

# 2. Restore database from backup
docker-compose exec postgres psql -U intellioptics -d intellioptics < backup_YYYYMMDD_HHMMSS.sql

# 3. Clear worker cache
docker-compose exec worker rm -rf /app/models/2467f56e-07bb-447e-9122-47595563e34a

# 4. Restart services
docker-compose start worker backend

# 5. Verify restoration
docker-compose exec postgres psql -U intellioptics -d intellioptics -c "
SELECT id, name, primary_model_blob_path, oodd_model_blob_path
FROM detectors
WHERE id = '2467f56e-07bb-447e-9122-47595563e34a';
"
```

## OODD Model Training Guide (For Phase 2)

### Prerequisites
- Python 3.9+
- PyTorch
- 500-1000 in-domain images (parking lot scenes)
- 500-1000 out-of-domain images (non-parking-lot)
- GPU recommended (not required)

### Training Steps

1. **Prepare dataset**
```python
# dataset_structure/
# ├── in_domain/
# │   ├── parking_lot_001.jpg
# │   ├── parking_lot_002.jpg
# │   └── ...
# └── out_of_domain/
#     ├── indoor_001.jpg
#     ├── landscape_001.jpg
#     └── ...
```

2. **Training script** (save as `train_oodd.py`)
```python
import torch
import torch.nn as nn
import torchvision.models as models
import torchvision.transforms as transforms
from torch.utils.data import DataLoader, Dataset
from pathlib import Path

# Custom dataset
class OODDDataset(Dataset):
    def __init__(self, in_domain_dir, out_of_domain_dir, transform=None):
        self.transform = transform
        self.samples = []

        # In-domain (label=1)
        for img_path in Path(in_domain_dir).glob("*.jpg"):
            self.samples.append((str(img_path), 1))
        for img_path in Path(in_domain_dir).glob("*.png"):
            self.samples.append((str(img_path), 1))

        # Out-of-domain (label=0)
        for img_path in Path(out_of_domain_dir).glob("*.jpg"):
            self.samples.append((str(img_path), 0))
        for img_path in Path(out_of_domain_dir).glob("*.png"):
            self.samples.append((str(img_path), 0))

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        img_path, label = self.samples[idx]
        img = Image.open(img_path).convert("RGB")
        if self.transform:
            img = self.transform(img)
        return img, label

# Training
def train_oodd_model():
    # Transforms (same as inference)
    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406],
                           std=[0.229, 0.224, 0.225])
    ])

    # Dataset
    dataset = OODDDataset("dataset_structure/in_domain",
                          "dataset_structure/out_of_domain",
                          transform=transform)
    train_size = int(0.8 * len(dataset))
    val_size = len(dataset) - train_size
    train_dataset, val_dataset = torch.utils.data.random_split(dataset, [train_size, val_size])

    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=32)

    # Model
    model = models.resnet18(pretrained=True)
    model.fc = nn.Linear(model.fc.in_features, 2)  # Binary: in/out

    # Training
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

    for epoch in range(20):
        model.train()
        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

        # Validation
        model.eval()
        correct = 0
        total = 0
        with torch.no_grad():
            for images, labels in val_loader:
                images, labels = images.to(device), labels.to(device)
                outputs = model(images)
                _, predicted = torch.max(outputs, 1)
                total += labels.size(0)
                correct += (predicted == labels).sum().item()

        print(f"Epoch {epoch+1}/20, Val Accuracy: {100 * correct / total:.2f}%")

    # Export to ONNX
    dummy_input = torch.randn(1, 3, 224, 224).to(device)
    torch.onnx.export(model, dummy_input, "oodd_parking_lot_v1.onnx",
                     input_names=["input"], output_names=["output"],
                     dynamic_axes={"input": {0: "batch_size"}})
    print("Model exported to oodd_parking_lot_v1.onnx")

if __name__ == "__main__":
    train_oodd_model()
```

3. **Run training**
```bash
python train_oodd.py
```

4. **Upload trained model**
```bash
# Upload to Azure Blob Storage
az storage blob upload \
    --account-name intelliopticsweb37558 \
    --container-name models \
    --name oodd_parking_lot_v1/resnet18.onnx \
    --file oodd_parking_lot_v1.onnx
```

5. **Update detector**
```sql
UPDATE detectors
SET oodd_model_blob_path = 'models/oodd_parking_lot_v1/resnet18.onnx'
WHERE id = '2467f56e-07bb-447e-9122-47595563e34a';
```

6. **Clear cache and test**
```bash
docker-compose exec worker rm -rf /app/models/2467f56e-07bb-447e-9122-47595563e34a
docker-compose restart worker
```

## Summary

**Current Status**: Models working but confidence scores too low due to mismatched OODD training data

**Immediate Action**: Disable OODD for this detector (5 minutes)

**Long-term Goal**: Train detector-specific OODD model (Phase 2)

**Critical**: Do NOT break existing detectors, database, or cache for other detectors

## Contact & Support

If issues arise during implementation:
1. Check `C:\Dev\IntelliOptics 2.0\docs\DETECTOR-MODEL-PATH-FIX.md` for cache clearing procedures
2. Review worker logs: `docker-compose logs worker --tail=100`
3. Check database integrity using queries above
4. Rollback using backup if needed

## Date
2026-01-13
