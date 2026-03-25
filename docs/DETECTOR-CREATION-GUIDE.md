# IntelliOptics Detector Creation Guide

## What is a Detector?

A **detector** is the core control object in IntelliOptics that defines:
- **What to detect** (vehicle, defect, person, etc.)
- **How to detect it** (which AI model to use)
- **When to escalate** (confidence threshold for human review)
- **Where to run** (edge-first with cloud fallback)

**Detectors are detector-centric**: They control all aspects of AI engagement across your deployment.

---

## Detector Lifecycle

```
┌──────────────────────────────────────────────────────────────┐
│ 1. CREATE DETECTOR                                           │
│    Create via Web UI or API                                  │
│    Define: name, description, mode, thresholds               │
│    Result: Detector ID (UUID)                                │
└──────────────────────────────────────────────────────────────┘
         ↓
┌──────────────────────────────────────────────────────────────┐
│ 2. UPLOAD MODEL (Optional - can happen later)                │
│    Upload ONNX model file                                    │
│    Model stored in Azure Blob Storage                        │
│    Result: model_blob_path populated                         │
└──────────────────────────────────────────────────────────────┘
         ↓
┌──────────────────────────────────────────────────────────────┐
│ 3. CONFIGURE EDGE                                            │
│    Add detector to edge-config.yaml                          │
│    Set confidence threshold, mode, class names               │
│    Configure edge inference profile (default/offline)        │
└──────────────────────────────────────────────────────────────┘
         ↓
┌──────────────────────────────────────────────────────────────┐
│ 4. EDGE DEVICES FETCH CONFIGURATION                          │
│    Edge API calls: GET /detectors/{detector_id}              │
│    Downloads detector metadata and configuration             │
│    Result: Detector available on edge                        │
└──────────────────────────────────────────────────────────────┘
         ↓
┌──────────────────────────────────────────────────────────────┐
│ 5. EDGE DEVICES DOWNLOAD MODEL                               │
│    Edge API calls: GET /edge-api/v1/fetch-model-urls         │
│    Downloads ONNX model from blob storage                    │
│    Caches locally in /opt/intellioptics/models/              │
│    Result: Ready for inference                               │
└──────────────────────────────────────────────────────────────┘
         ↓
┌──────────────────────────────────────────────────────────────┐
│ 6. INFERENCE & ESCALATION                                    │
│    Edge runs inference with Primary + OODD models            │
│    High confidence → Return result immediately               │
│    Low confidence → Escalate to cloud for review             │
│    Human labels → Retrain model → Deploy new version         │
└──────────────────────────────────────────────────────────────┘
```

---

## Method 1: Create Detector via Web UI

**URL**: http://localhost:3000/detectors

### Step 1: Navigate to Detectors Page

1. Open browser: `http://localhost:3000`
2. Click **"Detectors"** in navigation menu

### Step 2: Fill Out Form

**Required fields**:
- **Name**: Descriptive name for the detector
  - Examples: "Vehicle Detection - Parking Lot", "Defect Detection - Line A"

**Optional fields**:
- **Description**: Detailed explanation of what this detector does
  - Examples: "Detects vehicles in parking lot for occupancy monitoring", "Inspects welds for cracks and defects"

- **Model File**: Upload ONNX model (can be done later)
  - File format: `.onnx`
  - Max size: Depends on Azure Blob Storage limits

### Step 3: Create Detector

Click **"Create Detector"** button

**Result**:
- Detector appears in table
- Unique ID (UUID) generated
- Status: Ready for configuration

### Example: Quality Inspection Detector

```
Name: Weld Quality Inspector - Line 3
Description: Detects cracks, porosity, and incomplete fusion in welds. Trained on 5000+ labeled weld images.
Model File: weld_inspector_v1.onnx (optional - can upload later)
```

Click **"Create Detector"** → Detector ID: `abc123...`

---

## Method 2: Create Detector via API

**Endpoint**: `POST http://localhost:8000/detectors/`

### Step 1: Prepare Request

**Important**: The request body must be wrapped in a `"payload"` object (FastAPI parameter structure).

**Request format**:
```json
{
  "payload": {
    "name": "Detector Name",
    "description": "Optional description"
  }
}
```

### Step 2: Send API Request

#### Using curl:

```bash
curl -X POST http://localhost:8000/detectors/ \
  -H "Content-Type: application/json" \
  -d '{
    "payload": {
      "name": "Vehicle Detection - Parking Lot",
      "description": "Detects vehicles in parking lot for occupancy monitoring"
    }
  }'
```

#### Using Python:

```python
import requests

response = requests.post(
    "http://localhost:8000/detectors/",
    json={
        "payload": {
            "name": "Vehicle Detection - Parking Lot",
            "description": "Detects vehicles in parking lot for occupancy monitoring"
        }
    }
)

detector = response.json()
print(f"Created detector: {detector['id']}")
print(f"Name: {detector['name']}")
```

#### Using PowerShell:

```powershell
$body = @{
    payload = @{
        name = "Vehicle Detection - Parking Lot"
        description = "Detects vehicles in parking lot for occupancy monitoring"
    }
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/detectors/" `
    -Method Post `
    -ContentType "application/json" `
    -Body $body
```

### Step 3: Verify Response

**Expected response** (HTTP 200):
```json
{
  "id": "5b69c510-f84a-4a3c-b9bf-aa73ff368401",
  "name": "Vehicle Detection - Parking Lot",
  "description": "Detects vehicles in parking lot for occupancy monitoring",
  "model_blob_path": null,
  "created_at": "2026-01-10T12:34:54.880926"
}
```

**Save the detector ID** - you'll need it for:
- Uploading models
- Configuring edge devices
- Referencing in API calls

---

## Step 3: Upload Model (Optional)

Once detector is created, you can upload an ONNX model file.

**Endpoint**: `POST http://localhost:8000/detectors/{detector_id}/model`

### Using curl:

```bash
curl -X POST http://localhost:8000/detectors/5b69c510-f84a-4a3c-b9bf-aa73ff368401/model \
  -F "file=@/path/to/model.onnx"
```

### Using Python:

```python
import requests

detector_id = "5b69c510-f84a-4a3c-b9bf-aa73ff368401"

with open("/path/to/model.onnx", "rb") as f:
    files = {"file": f}
    response = requests.post(
        f"http://localhost:8000/detectors/{detector_id}/model",
        files=files
    )

print(f"Model uploaded: {response.json()}")
```

### Using Web UI:

1. Go to **Detectors** page
2. Find your detector in the table
3. Click **"Upload Model"** button
4. Select `.onnx` file
5. Click **"Upload"**

**Result**:
- Model stored in Azure Blob Storage
- `model_blob_path` updated in database
- Edge devices will download on next refresh (60s)

---

## Step 4: Configure Edge Device

Add detector configuration to `edge/config/edge-config.yaml`

### Minimal Configuration

```yaml
detectors:
  det_vehicle_parking:
    detector_id: 5b69c510-f84a-4a3c-b9bf-aa73ff368401  # From API response
    edge_inference_config: default  # Use default profile
```

### Full Configuration

```yaml
detectors:
  det_vehicle_parking:
    # Detector identification
    detector_id: 5b69c510-f84a-4a3c-b9bf-aa73ff368401
    name: "Vehicle Detection - Parking Lot"

    # Inference profile (default, offline, aggressive)
    edge_inference_config: default

    # Confidence threshold for escalation
    confidence_threshold: 0.85  # Escalate if confidence < 0.85

    # Patience time before escalating same area again
    patience_time: 30.0  # seconds

    # Detection mode
    mode: BINARY  # BINARY, MULTICLASS, COUNTING, BOUNDING_BOX, TEXT

    # Class names (for BINARY or MULTICLASS modes)
    class_names: ["no_vehicle", "vehicle"]

    # HRM reasoning (future feature)
    hrm_enabled: false
```

### Configuration Options

#### `edge_inference_config` Profiles:

**`default`** (recommended):
```yaml
edge_inference_configs:
  default:
    enabled: true
    always_return_edge_prediction: false  # Escalate low confidence
    disable_cloud_escalation: false
    min_time_between_escalations: 2.0
```

**`offline`** (no cloud dependency):
```yaml
edge_inference_configs:
  offline:
    enabled: true
    always_return_edge_prediction: true  # Return all results
    disable_cloud_escalation: true  # Never escalate
    min_time_between_escalations: 0
```

**`aggressive`** (frequent escalation):
```yaml
edge_inference_configs:
  aggressive:
    enabled: true
    always_return_edge_prediction: false
    disable_cloud_escalation: false
    min_time_between_escalations: 0.5  # More frequent escalations
```

#### Detection Modes:

| Mode | Use Case | Example |
|------|----------|---------|
| **BINARY** | Yes/No detection | Defect present? Vehicle detected? |
| **MULTICLASS** | Classification | Defect type: crack, scratch, dent |
| **COUNTING** | Count objects | Number of vehicles in frame |
| **BOUNDING_BOX** | Object location | Draw boxes around defects |
| **TEXT** | OCR/Text extraction | Read serial numbers, labels |

---

## Step 5: Assign Detector to Camera Stream

Configure RTSP camera to use the detector:

**File**: `edge/config/edge-config.yaml`

```yaml
streams:
  camera_parking_lot:
    name: "Parking Lot Camera - East Entrance"
    detector_id: det_vehicle_parking  # Reference to detector config above
    url: "rtsp://192.168.1.100:554/stream1"
    sampling_interval_seconds: 2.0  # Capture every 2 seconds
    reconnect_delay_seconds: 5.0
    backend: "auto"
    encoding: "jpeg"
    submission_method: "edge"  # Run inference locally

    credentials:
      username_env: "RTSP_USER"
      password_env: "RTSP_PASS"

    # Camera health monitoring (optional)
    camera_health:
      enabled: true
      check_tampering: true
      log_health_status: true
      skip_unhealthy_frames: true
      health_check_interval_seconds: 10.0
```

**Result**: Camera feeds frames → Health check → Inference with detector → Results

---

## Complete Example: Quality Inspection Detector

### Scenario

**Goal**: Create a detector for weld quality inspection on production line

**Requirements**:
- Detect 3 types of defects: crack, porosity, incomplete_fusion
- High accuracy required (confidence threshold: 0.90)
- Offline-capable (no cloud dependency during production)
- Camera monitors welds every 3 seconds

### Step 1: Create Detector (API)

```bash
curl -X POST http://localhost:8000/detectors/ \
  -H "Content-Type: application/json" \
  -d '{
    "payload": {
      "name": "Weld Quality Inspector - Line 3",
      "description": "Detects cracks, porosity, and incomplete fusion in welds. Trained on 5000+ labeled images from Line 3."
    }
  }'
```

**Response**:
```json
{
  "id": "abc123-def456-ghi789",
  "name": "Weld Quality Inspector - Line 3",
  "description": "Detects cracks, porosity, and incomplete fusion in welds...",
  "model_blob_path": null,
  "created_at": "2026-01-10T14:23:10"
}
```

### Step 2: Upload Trained Model

```bash
curl -X POST http://localhost:8000/detectors/abc123-def456-ghi789/model \
  -F "file=@weld_inspector_line3_v1.onnx"
```

### Step 3: Configure Edge Device

**File**: `edge/config/edge-config.yaml`

```yaml
detectors:
  det_weld_quality_line3:
    detector_id: abc123-def456-ghi789
    name: "Weld Quality Inspector - Line 3"
    edge_inference_config: offline  # Offline mode for production
    confidence_threshold: 0.90  # High accuracy required
    patience_time: 30.0
    mode: MULTICLASS
    class_names: ["good", "crack", "porosity", "incomplete_fusion"]
    hrm_enabled: false

streams:
  camera_weld_line3:
    name: "Weld Station - Line 3"
    detector_id: det_weld_quality_line3
    url: "rtsp://192.168.10.50:554/stream1"
    sampling_interval_seconds: 3.0
    reconnect_delay_seconds: 5.0
    backend: "auto"
    encoding: "jpeg"
    submission_method: "edge"

    credentials:
      username: "admin"
      password: "weld_camera_pass"

    camera_health:
      enabled: true
      check_tampering: false  # Not needed for fixed camera
      log_health_status: true
      skip_unhealthy_frames: true
      health_check_interval_seconds: 10.0
      blur_threshold: 150.0  # Require sharp images for defect detection
      brightness_low: 80.0  # Well-lit environment
      brightness_high: 200.0
      contrast_low: 40.0
```

### Step 4: Deploy and Test

```bash
# Restart edge API to load new configuration
docker-compose -f edge/docker-compose.yml restart edge-api

# Monitor logs
docker-compose -f edge/docker-compose.yml logs -f edge-api
```

**Expected logs**:
```
[INFO] Loaded detector: det_weld_quality_line3 (abc123-def456-ghi789)
[INFO] Downloading model from cloud...
[INFO] Model cached: /opt/intellioptics/models/abc123-def456-ghi789/primary/1/model.buf
[INFO] Starting RTSP ingest for stream 'camera_weld_line3'
[INFO] Camera health enabled with 10s interval
[DEBUG] Camera health: status=healthy, score=92.0, blur=187.3, brightness=135.2
[INFO] Inference result: label=good, confidence=0.94
```

---

## Example Detectors for Different Use Cases

### 1. Binary Classification: Vehicle Detection

```yaml
detectors:
  det_vehicle_parking:
    detector_id: <uuid-from-api>
    name: "Vehicle Detection - Parking Lot"
    edge_inference_config: default
    confidence_threshold: 0.85
    patience_time: 30.0
    mode: BINARY
    class_names: ["no_vehicle", "vehicle"]
```

### 2. Multiclass: Defect Type Classification

```yaml
detectors:
  det_defect_classifier:
    detector_id: <uuid-from-api>
    name: "Defect Type Classifier"
    edge_inference_config: default
    confidence_threshold: 0.90
    patience_time: 15.0
    mode: MULTICLASS
    class_names: ["good", "crack", "scratch", "discoloration", "dent"]
```

### 3. Counting: People Counter

```yaml
detectors:
  det_people_counter:
    detector_id: <uuid-from-api>
    name: "People Counter - Entrance"
    edge_inference_config: default
    confidence_threshold: 0.80
    patience_time: 5.0
    mode: COUNTING
    class_names: ["person"]
```

### 4. Security: Unauthorized Access Detection

```yaml
detectors:
  det_security_access:
    detector_id: <uuid-from-api>
    name: "Security - Restricted Area"
    edge_inference_config: aggressive  # Low tolerance for uncertainty
    confidence_threshold: 0.95  # Very high accuracy required
    patience_time: 2.0  # Frequent alerts
    mode: BINARY
    class_names: ["authorized", "unauthorized"]
```

### 5. Offline: Remote Site Quality Check

```yaml
detectors:
  det_quality_remote:
    detector_id: <uuid-from-api>
    name: "Quality Check - Remote Site"
    edge_inference_config: offline  # No cloud connection
    confidence_threshold: 0.85
    patience_time: 30.0
    mode: BINARY
    class_names: ["pass", "fail"]
```

---

## Troubleshooting

### Issue: "Field required" error when creating detector

**Problem**:
```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "payload"],
      "msg": "Field required"
    }
  ]
}
```

**Solution**: Wrap request body in `"payload"`:
```bash
# WRONG
{"name": "Test", "description": "Test"}

# CORRECT
{"payload": {"name": "Test", "description": "Test"}}
```

### Issue: Edge device not downloading model

**Check**:
1. Model uploaded to cloud? `curl http://localhost:8000/detectors/<id>`
2. Detector ID correct in edge-config.yaml?
3. Edge API has internet access?
4. API token configured? `INTELLIOPTICS_API_TOKEN` in environment

**Logs**:
```bash
docker-compose -f edge/docker-compose.yml logs edge-api | grep "model"
```

### Issue: Detector created but not appearing on edge

**Solution**:
1. Add detector to `edge/config/edge-config.yaml` under `detectors:` section
2. Restart edge-api: `docker-compose restart edge-api`
3. Check logs for detector loading confirmation

### Issue: All inference results escalated (100%)

**Problem**: Confidence threshold too high or model not loaded

**Check**:
1. Model file uploaded and downloaded by edge?
2. Confidence threshold reasonable (0.80-0.90 for most cases)?
3. OODD model reducing confidence incorrectly?

**Debug**:
```bash
# Check model files on edge
ls /opt/intellioptics/models/<detector_id>/primary/1/

# Expected files:
# - model.buf (ONNX model)
# - model_id.txt
# - pipeline_config.yaml
```

---

## Best Practices

### 1. Naming Convention

Use descriptive, hierarchical names:
```
<What> - <Where> [- <Variant>]
```

Examples:
- "Vehicle Detection - Parking Lot"
- "Weld Quality Inspector - Line 3 - V2"
- "Defect Classifier - Assembly Station A"
- "People Counter - Entrance - North"

### 2. Confidence Thresholds

| Use Case | Threshold | Reasoning |
|----------|-----------|-----------|
| **Safety-critical** | 0.95-0.98 | False negatives dangerous |
| **Quality inspection** | 0.90-0.95 | High accuracy needed |
| **General detection** | 0.85-0.90 | Balance accuracy and escalations |
| **Monitoring/counting** | 0.80-0.85 | Some false positives acceptable |
| **Offline/remote** | 0.80-0.85 | Lower threshold (no human review) |

### 3. Model Versioning

Include version in description:
```json
{
  "name": "Weld Inspector - Line 3",
  "description": "v2.1 - Trained on 8000 images. Improved porosity detection. Deployed: 2026-01-10"
}
```

### 4. Testing Workflow

1. **Create detector** with test model
2. **Deploy to test edge device** first
3. **Run sample images** through inference
4. **Validate results** (accuracy, confidence distribution)
5. **Tune threshold** based on false positive/negative rate
6. **Deploy to production** edge devices

---

## Summary

### Quick Reference

**Create via API**:
```bash
curl -X POST http://localhost:8000/detectors/ \
  -H "Content-Type: application/json" \
  -d '{"payload": {"name": "My Detector", "description": "Description"}}'
```

**Upload model**:
```bash
curl -X POST http://localhost:8000/detectors/<id>/model \
  -F "file=@model.onnx"
```

**Configure edge** (`edge-config.yaml`):
```yaml
detectors:
  my_detector:
    detector_id: <uuid-from-api>
    edge_inference_config: default
    confidence_threshold: 0.85
    mode: BINARY
    class_names: ["no", "yes"]
```

**Assign to camera** (`edge-config.yaml`):
```yaml
streams:
  my_camera:
    detector_id: my_detector
    url: "rtsp://camera-ip/stream"
```

**Next Steps**:
1. Create detector via Web UI or API
2. Upload ONNX model (optional)
3. Configure edge device
4. Assign to camera stream
5. Monitor results in Web UI escalation queue
6. Iterate: human labels → retrain → deploy
