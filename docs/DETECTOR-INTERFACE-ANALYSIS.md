# DetectorConfigPage Interface Analysis - Critical Gaps

**Date**: 2026-01-10
**File**: `cloud/frontend/src/pages/DetectorConfigPage.tsx`
**Status**: ⚠️ Incomplete - Missing Critical Detector Definition Fields

---

## 🔍 EXECUTIVE SUMMARY

The current `DetectorConfigPage` is essentially a **deployment configuration interface**, not a complete **detector definition interface**. It handles edge optimization and model file uploads well, but lacks critical fields needed to fully define what a detector is and how it should operate.

**Current Completeness**: ~40% of what a production detector definition requires

---

## 📊 CURRENT INTERFACE - WHAT EXISTS

### Section 1: General Information ✅ (Adequate)
- ✅ Name
- ✅ Description

**Assessment**: Good for basic metadata.

---

### Section 2: Detection Logic ⚠️ (Incomplete)
**What Exists**:
- ✅ Mode selector (BINARY/MULTICLASS/COUNTING/BOUNDING_BOX)
- ✅ Global confidence threshold (slider, 0-1)

**What's Missing**:
- ❌ **Class Names Editor** (for MULTICLASS/COUNTING/BOUNDING_BOX)
  - Current: `class_names` exists in backend schema but no UI to edit
  - Need: Dynamic list editor to add/remove/rename classes
  - Example: ["vehicle", "person", "bicycle"]

- ❌ **Per-Class Confidence Thresholds**
  - Current: Single global threshold for all classes
  - Need: Different thresholds for different classes
  - Example: "vehicle" = 0.85, "person" = 0.95 (higher for critical detections)

- ❌ **Class Priorities/Weights**
  - Need: Define which classes are most important
  - Example: "defect" class more critical than "acceptable" class

- ❌ **Query Text** (Groundlight pattern)
  - Need: Natural language question the detector answers
  - Example: "Is there a vehicle in the parking space?"
  - Use case: Human reviewers need context

**Assessment**: Basic mode selection exists, but no configuration for multiclass scenarios.

---

### Section 3: Model Specifications ❌ (Missing Entirely)
**Critical Missing Fields**:

#### A. Input Configuration
```typescript
// NEEDED:
interface ModelInputConfig {
  input_size: { width: number; height: number };     // e.g., {640, 640}
  channels: number;                                   // 1 (grayscale) or 3 (RGB)
  normalization: {
    mean: [number, number, number];                  // e.g., [0.485, 0.456, 0.406]
    std: [number, number, number];                   // e.g., [0.229, 0.224, 0.225]
  };
  pixel_format: "RGB" | "BGR";                       // Important for OpenCV vs. PIL
  value_range: [number, number];                     // e.g., [0, 255] or [0, 1]
}
```

**Why It Matters**: Edge inference service needs to know how to preprocess images before feeding to model.

**Current Workaround**: Hardcoded in inference service or edge-config.yaml (fragile).

---

#### B. Output Configuration
```typescript
// NEEDED:
interface ModelOutputConfig {
  output_format: "logits" | "probabilities" | "bboxes" | "segmentation_masks";
  num_outputs: number;                               // Number of output tensors
  class_mapping: Record<number, string>;             // Map output indices to class names

  // For BOUNDING_BOX mode:
  bbox_format?: "xyxy" | "xywh" | "cxcywh";         // Bounding box coordinate format
  bbox_normalized?: boolean;                         // Coordinates in [0,1] or pixels

  // For post-processing:
  apply_sigmoid?: boolean;                           // Apply sigmoid to logits
  apply_softmax?: boolean;                           // Apply softmax to logits
}
```

**Why It Matters**: Inference service needs to know how to interpret model outputs.

---

#### C. Detection Parameters (for BOUNDING_BOX mode)
```typescript
// NEEDED:
interface DetectionParams {
  nms_threshold: number;          // Non-maximum suppression (0-1), default 0.45
  iou_threshold: number;          // Intersection over Union (0-1), default 0.5
  max_detections: number;         // Max objects per image, default 100
  min_score: number;              // Min confidence to keep detection, default 0.25
  min_object_size: number;        // Min bbox area (pixels²), filter small noise
  max_object_size: number;        // Max bbox area (pixels²), filter anomalies
  agnostic_nms: boolean;          // Apply NMS across all classes or per-class
}
```

**Current State**: None of these exist. Edge inference likely uses hardcoded defaults.

**Impact**: Can't tune detector performance without redeploying code.

---

### Section 4: ROI/Zone Management ❌ (Missing Entirely)
**Critical for Industrial Use Cases**:

```typescript
interface RegionOfInterest {
  id: string;
  name: string;
  type: "include" | "exclude";
  polygon: Array<{x: number, y: number}>;  // Pixel coordinates
  enabled: boolean;
}

interface ZoneConfig {
  zones: RegionOfInterest[];
  default_behavior: "include_all" | "exclude_all";
}
```

**Example Use Cases**:
1. **Parking Lot Monitoring**: Define zones for each parking space
2. **Defect Inspection**: Ignore edges/borders, only check center area
3. **Safety Monitoring**: Restricted zones where people shouldn't enter

**Current Workaround**: None. Must inspect entire image.

**UI Needed**: Canvas-based zone editor (like image annotation tools):
- Draw polygons on reference image
- Name each zone
- Toggle include/exclude
- Preview detection overlay with zones

---

### Section 5: Testing & Validation ❌ (Missing Entirely)
**Critical Missing Features**:

#### A. Live Test Interface
```typescript
interface TestInterface {
  upload_test_image: File;
  run_inference_button: () => void;

  // Results Display:
  output_visualization: {
    original_image: ImageData;
    annotated_image: ImageData;      // With bboxes, labels, confidence
    detections: Array<{
      class: string;
      confidence: number;
      bbox?: BoundingBox;
      count?: number;
    }>;
  };

  // Performance:
  inference_time_ms: number;
  preprocessing_time_ms: number;
  postprocessing_time_ms: number;
}
```

**Why It Matters**:
- Verify model works before deployment
- Tune thresholds based on real results
- Catch issues early (wrong preprocessing, output format, etc.)

**Current State**: No way to test detector without deploying to edge device.

---

#### B. Performance Metrics Dashboard
```typescript
interface PerformanceMetrics {
  // From historical queries with human feedback:
  total_queries: number;
  accuracy: number;                    // % of correct predictions
  precision: number;                   // TP / (TP + FP)
  recall: number;                      // TP / (TP + FN)
  f1_score: number;                    // Harmonic mean of precision/recall

  // Confusion matrix (for multiclass):
  confusion_matrix: number[][];

  // Per-class metrics:
  per_class_metrics: Record<string, {
    precision: number;
    recall: number;
    support: number;                   // Number of samples
  }>;

  // Escalation stats:
  escalation_rate: number;             // % of queries escalated
  avg_confidence: number;
  low_confidence_rate: number;         // % below threshold
}
```

**Why It Matters**: Track detector quality over time, identify when retraining is needed.

**Current State**: No visibility into detector performance.

---

### Section 6: Version Control & History ❌ (Missing Entirely)
**Critical for Production ML**:

```typescript
interface ModelVersion {
  version_id: string;
  version_number: number;              // Auto-incrementing: v1, v2, v3...
  uploaded_at: datetime;
  uploaded_by: string;                 // User ID/email

  // Model metadata:
  model_size_bytes: number;
  model_checksum: string;              // SHA256 hash for integrity

  // Training metadata:
  training_dataset_size?: number;
  training_date?: datetime;
  training_accuracy?: number;

  // Deployment:
  status: "draft" | "testing" | "production" | "deprecated";
  deployed_to_hubs: string[];          // Hub IDs using this version

  // Changelog:
  release_notes?: string;
  performance_delta?: string;          // "5% improvement in precision"
}

interface VersionControl {
  current_version: ModelVersion;
  version_history: ModelVersion[];

  actions: {
    rollback_to_version: (version_id: string) => void;
    compare_versions: (v1: string, v2: string) => ComparisonReport;
    set_production_version: (version_id: string) => void;
  };
}
```

**Why It Matters**:
- Rollback if new model performs worse
- A/B test different models
- Audit trail for compliance
- Track improvement over time

**Current State**: Model uploads overwrite previous version. No history.

---

### Section 7: Business Logic & Actions ❌ (Missing Entirely)
**What Happens After Detection?**

```typescript
interface DetectionAction {
  trigger: {
    on_class: string;                  // Which class triggers action
    min_confidence: number;            // Minimum confidence to trigger
    conditions: {
      consecutive_detections?: number; // Fire only after N consecutive frames
      time_window_seconds?: number;    // Debounce: only fire once per window
      custom_logic?: string;           // JavaScript expression for complex rules
    };
  };

  action: {
    type: "webhook" | "email" | "sms" | "push_notification" | "log" | "database_write";

    // Webhook configuration:
    webhook_url?: string;
    webhook_method?: "POST" | "PUT";
    webhook_headers?: Record<string, string>;
    webhook_body_template?: string;    // Jinja2 template with detection data

    // Email configuration:
    email_recipients?: string[];
    email_subject_template?: string;
    email_body_template?: string;
    attach_image?: boolean;

    // SMS configuration:
    sms_recipients?: string[];
    sms_message_template?: string;
  };
}

interface ActionConfig {
  actions: DetectionAction[];
  global_rate_limit?: {
    max_actions_per_hour: number;
    max_actions_per_day: number;
  };
}
```

**Example Use Cases**:
1. **Defect Detection**: Send Slack webhook when defect detected with confidence > 0.9
2. **Safety Violation**: Send SMS to supervisor when person detected in restricted zone
3. **Parking Management**: Update database record when vehicle enters/exits space

**Current State**: AlertSettings page exists globally, but no per-detector action configuration.

---

### Section 8: Advanced Detector Features ❌ (Missing Entirely)

#### A. Ensemble Models
```typescript
interface EnsembleConfig {
  enabled: boolean;
  models: Array<{
    model_id: string;
    weight: number;                    // Voting weight (0-1)
  }>;
  fusion_strategy: "average" | "max" | "voting" | "weighted_average";

  // Use case: Combine YOLO + EfficientNet for better accuracy
}
```

---

#### B. Fallback Detectors
```typescript
interface FallbackConfig {
  enabled: boolean;
  primary_detector_id: string;
  fallback_detector_id: string;

  trigger: {
    on_low_confidence: boolean;        // Use fallback if primary < threshold
    on_error: boolean;                 // Use fallback if primary fails
    on_oodd: boolean;                  // Use fallback if OODD detects out-of-domain
  };
}
```

---

#### C. A/B Testing
```typescript
interface ABTestConfig {
  enabled: boolean;
  variant_a: {
    model_version: string;
    traffic_percentage: number;        // 0-100
  };
  variant_b: {
    model_version: string;
    traffic_percentage: number;
  };

  metrics_to_track: string[];          // ["accuracy", "latency", "escalation_rate"]
  test_duration_days: number;

  // Auto-promote winner:
  auto_promote: boolean;
  promotion_criteria: {
    min_accuracy_improvement: number;  // e.g., 5%
    max_latency_increase_ms: number;   // e.g., 50ms
  };
}
```

---

## 🎯 PRIORITIZED RECOMMENDATIONS

### PRIORITY 1: Critical for Production (Must Have)

#### 1.1 Class Configuration UI
**File**: `DetectorConfigPage.tsx`

**Add to "Detection Logic" Card**:
```tsx
{/* Show only when mode = MULTICLASS, COUNTING, or BOUNDING_BOX */}
{mode !== "BINARY" && (
  <div>
    <label>Class Names</label>
    <ClassListEditor
      value={classNames}
      onChange={setClassNames}
      placeholder="Enter class name..."
    />
    {/* Dynamic list with add/remove buttons */}
  </div>
)}

{/* Per-class threshold overrides */}
{mode === "MULTICLASS" && (
  <div>
    <label>Per-Class Thresholds (Optional)</label>
    {classNames.map(className => (
      <div key={className}>
        <span>{className}</span>
        <input type="range" min="0" max="1" step="0.01" />
      </div>
    ))}
  </div>
)}
```

**Backend Schema Update** (`detector_configs` table):
```sql
ALTER TABLE detector_configs
ADD COLUMN per_class_thresholds JSONB;  -- {"vehicle": 0.85, "person": 0.95}
```

**Estimated Time**: 2-3 hours

---

#### 1.2 Model Input/Output Specifications
**Add New Card**: "Model Specifications"

**UI**:
```tsx
<Card title="Model Specifications">
  <h3>Input Configuration</h3>
  <Input label="Input Width" type="number" value={inputWidth} />
  <Input label="Input Height" type="number" value={inputHeight} />
  <Select label="Color Space">
    <option value="RGB">RGB</option>
    <option value="BGR">BGR</option>
    <option value="GRAYSCALE">Grayscale</option>
  </Select>

  <h3>Normalization</h3>
  <Input label="Mean (R,G,B)" placeholder="0.485, 0.456, 0.406" />
  <Input label="Std (R,G,B)" placeholder="0.229, 0.224, 0.225" />

  <h3>Output Configuration</h3>
  <Select label="Output Format">
    <option value="probabilities">Probabilities</option>
    <option value="logits">Logits</option>
    <option value="bboxes">Bounding Boxes</option>
  </Select>
</Card>
```

**Backend Schema**:
```sql
ALTER TABLE detector_configs
ADD COLUMN model_input_config JSONB,
ADD COLUMN model_output_config JSONB;
```

**Estimated Time**: 3-4 hours

---

#### 1.3 Detection Parameters (for BOUNDING_BOX mode)
**Add to "Detection Logic" Card** (conditional):

```tsx
{mode === "BOUNDING_BOX" && (
  <div className="mt-4 p-4 border rounded">
    <h3>Object Detection Parameters</h3>
    <Input label="NMS Threshold" type="number" min="0" max="1" step="0.01" value={nmsThreshold} />
    <Input label="IoU Threshold" type="number" min="0" max="1" step="0.01" value={iouThreshold} />
    <Input label="Max Detections" type="number" min="1" max="1000" value={maxDetections} />
    <Input label="Min Object Size (px²)" type="number" value={minObjectSize} />
  </div>
)}
```

**Backend Schema**:
```sql
ALTER TABLE detector_configs
ADD COLUMN detection_params JSONB;  -- For bbox-specific params
```

**Estimated Time**: 2 hours

---

### PRIORITY 2: High Value (Should Have)

#### 2.1 Live Test Interface
**Add New Tab/Section**: "Test & Validate"

**UI**:
```tsx
<Card title="Test Detector">
  <input type="file" accept="image/*" onChange={handleTestImageUpload} />
  <button onClick={runTest}>Run Inference</button>

  {testResult && (
    <div className="grid grid-cols-2 gap-4">
      <div>
        <h4>Original Image</h4>
        <img src={testResult.originalImageUrl} />
      </div>
      <div>
        <h4>Detected Objects</h4>
        <img src={testResult.annotatedImageUrl} />
        <ul>
          {testResult.detections.map(det => (
            <li>{det.class}: {det.confidence.toFixed(2)}</li>
          ))}
        </ul>
      </div>
    </div>
  )}

  <div className="mt-4">
    <p>Inference Time: {testResult.inferenceTimeMs}ms</p>
  </div>
</Card>
```

**Backend API Needed**:
```python
POST /detectors/{detector_id}/test
Body: multipart/form-data with image
Response: {
  "detections": [...],
  "annotated_image_url": "...",
  "inference_time_ms": 45
}
```

**Estimated Time**: 6-8 hours

---

#### 2.2 Performance Metrics Dashboard
**Add New Tab**: "Analytics"

**UI**: Display metrics from historical queries with human feedback
- Accuracy, Precision, Recall, F1
- Confusion matrix heatmap
- Confidence distribution histogram
- Escalation rate trend chart

**Backend API Needed**:
```python
GET /detectors/{detector_id}/metrics?days=30
Response: {
  "accuracy": 0.92,
  "precision": 0.89,
  "recall": 0.95,
  ...
}
```

**Estimated Time**: 10-12 hours

---

#### 2.3 Model Version Control
**Add New Section**: "Model Versions" (below Model Management)

**UI**:
```tsx
<Card title="Model Versions">
  <table>
    <thead>
      <tr>
        <th>Version</th>
        <th>Uploaded</th>
        <th>Status</th>
        <th>Deployed To</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody>
      {versions.map(v => (
        <tr>
          <td>v{v.version_number}</td>
          <td>{v.uploaded_at}</td>
          <td>{v.status}</td>
          <td>{v.deployed_to_hubs.length} hubs</td>
          <td>
            <button onClick={() => rollback(v.id)}>Rollback</button>
            <button onClick={() => setProduction(v.id)}>Set Production</button>
          </td>
        </tr>
      ))}
    </tbody>
  </table>
</Card>
```

**Backend Schema**:
```sql
CREATE TABLE model_versions (
  id UUID PRIMARY KEY,
  detector_id UUID REFERENCES detectors(id),
  version_number INTEGER,
  model_blob_path VARCHAR(512),
  status VARCHAR(50),
  uploaded_at TIMESTAMP,
  uploaded_by UUID,
  ...
);
```

**Estimated Time**: 8-10 hours

---

### PRIORITY 3: Nice to Have (Future Enhancements)

#### 3.1 ROI/Zone Editor
- Visual polygon drawing tool
- Zone management (include/exclude)
- **Estimated Time**: 12-16 hours

#### 3.2 Action Configuration
- Per-detector webhooks, alerts
- Custom business logic
- **Estimated Time**: 10-14 hours

#### 3.3 Ensemble & A/B Testing
- Advanced ML ops features
- **Estimated Time**: 16-20 hours

---

## 📋 IMPLEMENTATION CHECKLIST

### Phase 1: Essential Fields (20-30 hours)
- [ ] Class names list editor (for multiclass)
- [ ] Per-class confidence thresholds
- [ ] Model input configuration (size, normalization, color space)
- [ ] Model output configuration (format, post-processing)
- [ ] Detection parameters (NMS, IoU, max detections) for BOUNDING_BOX mode
- [ ] Query text field (natural language question)
- [ ] Backend schema updates for all above

### Phase 2: Testing & Validation (16-20 hours)
- [ ] Live test interface (upload image, run inference, see results)
- [ ] Performance metrics dashboard (accuracy, precision, recall)
- [ ] Confusion matrix visualization
- [ ] Confidence distribution charts

### Phase 3: Version Control (8-10 hours)
- [ ] Model version history table
- [ ] Rollback functionality
- [ ] Version comparison
- [ ] Production/staging designation

### Phase 4: Advanced Features (30-50 hours)
- [ ] ROI/Zone editor with visual polygon tool
- [ ] Per-detector action configuration
- [ ] Ensemble model support
- [ ] A/B testing framework

---

## 🎯 RECOMMENDED IMMEDIATE ACTIONS

### Option A: Minimal Viable Detector (MVP)
**Goal**: Make detector definition complete enough for real production use

**Implement**:
1. Class names editor (Priority 1.1)
2. Model input/output specs (Priority 1.2)
3. Detection parameters for bbox mode (Priority 1.3)
4. Live test interface (Priority 2.1)

**Total Time**: 12-16 hours
**Result**: Can fully configure multiclass/bbox detectors and test before deployment

---

### Option B: Full Production-Ready
**Goal**: Industry-standard ML ops capabilities

**Implement**: All of Phase 1 + Phase 2 + Phase 3

**Total Time**: 40-60 hours
**Result**: Complete detector lifecycle management with testing, metrics, and version control

---

## 💡 DESIGN PATTERNS TO FOLLOW

### 1. Conditional Field Visibility
```tsx
// Show fields only when relevant to selected mode
{mode === "MULTICLASS" && <ClassNamesEditor />}
{mode === "BOUNDING_BOX" && <BBoxParametersCard />}
{mode === "COUNTING" && <CountingConfigCard />}
```

### 2. Progressive Disclosure
- Start with basic config (name, mode, threshold)
- Expand to advanced (model specs, detection params)
- Separate tab for testing/analytics

### 3. Smart Defaults
- Pre-populate common values (input size: 640x640, NMS: 0.45)
- Detect from model metadata if possible (ONNX models include input shape)
- Show tooltips explaining each parameter

### 4. Validation & Warnings
```tsx
{mode === "MULTICLASS" && classNames.length === 0 && (
  <Alert severity="warning">
    Multiclass mode requires at least 2 class names
  </Alert>
)}

{inputWidth % 32 !== 0 && (
  <Alert severity="info">
    Input width should be divisible by 32 for optimal performance
  </Alert>
)}
```

---

## 📖 REFERENCE IMPLEMENTATIONS

### Similar Tools for Inspiration:
1. **Roboflow** - Computer vision platform
   - Class configuration UI
   - Test interface with annotation overlay
   - Model version management

2. **Groundlight** - Pattern we're following
   - Natural language detector definition
   - Confidence-based escalation
   - Human-in-the-loop feedback

3. **Label Studio** - Annotation tool
   - ROI/polygon editor
   - Multiple output formats

---

## ✅ SUCCESS CRITERIA

**A detector is "fully defined" when**:
1. ✅ All classes are named (for multiclass)
2. ✅ Model input/output specs are configured
3. ✅ Detection parameters are set (for bbox mode)
4. ✅ Detector can be tested with sample images before deployment
5. ✅ Performance metrics are tracked over time
6. ✅ Model versions are managed with rollback capability
7. ✅ Business actions are configured (what happens on detection)

**Current Status**: ~2 out of 7 criteria met (28%)

---

## 🚀 NEXT STEPS

**Immediate**:
1. Review this analysis with team/stakeholders
2. Prioritize which missing features are critical for your use cases
3. Create UI mockups for new sections
4. Estimate backend schema changes needed

**Short-term** (1-2 weeks):
1. Implement Priority 1 items (class config, model specs, detection params)
2. Add live test interface
3. Update backend API to support new fields

**Long-term** (1-2 months):
1. Build performance metrics dashboard
2. Implement model version control
3. Add ROI/zone editor for advanced use cases

---

**Bottom Line**: The current interface is good for **deployment settings**, but needs significant expansion to be a true **detector definition** tool. The missing pieces are standard in production ML platforms and critical for industrial CV applications.
