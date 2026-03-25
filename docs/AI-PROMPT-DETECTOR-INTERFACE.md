# AI Implementation Prompt: Complete Detector Interface

**Copy this entire prompt and paste it to your AI assistant to implement the missing detector configuration features.**

---

## 🎯 OBJECTIVE

Implement the missing critical features for the DetectorConfigPage interface based on the gap analysis in `C:\Dev\IntelliOptics 2.0\docs\DETECTOR-INTERFACE-ANALYSIS.md`.

**Target**: Transform the current 40% complete "deployment settings" interface into a **production-grade detector definition tool** (Option A: Minimal Viable Detector - 12-16 hour scope).

---

## 📋 TASK SUMMARY

You will implement **4 critical features** to make the detector interface production-ready:

1. **Class Configuration UI** - Dynamic list editor for multiclass detectors
2. **Model Specifications UI** - Input/output configuration for inference
3. **Detection Parameters UI** - NMS, IoU, and bbox tuning (for BOUNDING_BOX mode)
4. **Live Test Interface** - Upload test images and see inference results

Each feature requires both **frontend UI** and **backend API** changes.

---

## 📂 PROJECT CONTEXT

**Location**: `C:\Dev\IntelliOptics 2.0\`

**Architecture**:
- **Frontend**: React + TypeScript (`cloud/frontend/src/`)
- **Backend**: FastAPI + PostgreSQL (`cloud/backend/app/`)
- **Pattern**: React Hook Form + Zod validation (see `AlertSettingsPage.tsx` for reference)

**Key Files You'll Modify**:
```
Frontend:
  cloud/frontend/src/pages/DetectorConfigPage.tsx  (main work)

Backend:
  cloud/backend/app/routers/detectors.py            (add test endpoint)
  cloud/backend/app/models.py                       (add columns to DetectorConfig)
  cloud/backend/app/schemas.py                      (add Pydantic schemas)
```

---

## 🔍 STEP 1: READ THE ANALYSIS DOCUMENT

**CRITICAL FIRST STEP**: Read and understand the gap analysis:

```
File: C:\Dev\IntelliOptics 2.0\docs\DETECTOR-INTERFACE-ANALYSIS.md
```

**Pay special attention to**:
- Section "📊 CURRENT INTERFACE - WHAT EXISTS" (understand current state)
- Section "PRIORITY 1: Critical for Production" (what you'll implement)
- Code examples throughout the document

---

## 🛠️ STEP 2: IMPLEMENT FEATURE 1 - CLASS CONFIGURATION

### 2.1 Frontend Changes

**File**: `cloud/frontend/src/pages/DetectorConfigPage.tsx`

**Location**: Add to the "Detection Logic" Card (around line 219-255)

**What to Build**:

```tsx
{/* AFTER the mode selector, ADD: */}

{/* Show class editor for modes that need it */}
{(watch("mode") === "MULTICLASS" ||
  watch("mode") === "COUNTING" ||
  watch("mode") === "BOUNDING_BOX") && (
  <div className="mt-4">
    <label className="block text-sm font-medium text-gray-400 mb-2">
      Class Names
      <span className="text-red-400 ml-1">*</span>
    </label>

    <Controller
      name="class_names"
      control={control}
      rules={{
        validate: (value) => {
          if (!value || value.length === 0) {
            return "At least one class name is required for this mode";
          }
          if (value.length === 1 && watch("mode") === "MULTICLASS") {
            return "Multiclass mode requires at least 2 classes";
          }
          return true;
        }
      }}
      render={({ field }) => (
        <div className="space-y-2">
          {/* List of class names */}
          {field.value && field.value.map((className: string, index: number) => (
            <div key={index} className="flex items-center gap-2">
              <input
                type="text"
                value={className}
                onChange={(e) => {
                  const newClassNames = [...field.value];
                  newClassNames[index] = e.target.value;
                  field.onChange(newClassNames);
                }}
                placeholder="Enter class name"
                className="flex-1 rounded-md bg-gray-700 border-gray-600 text-white shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm px-3 py-2"
              />
              <button
                type="button"
                onClick={() => {
                  const newClassNames = field.value.filter((_: string, i: number) => i !== index);
                  field.onChange(newClassNames);
                }}
                className="text-red-400 hover:text-red-300 px-3 py-2"
                disabled={field.value.length === 1}
              >
                ✕ Remove
              </button>
            </div>
          ))}

          {/* Add class button */}
          <button
            type="button"
            onClick={() => {
              field.onChange([...(field.value || []), ""]);
            }}
            className="w-full bg-gray-700 hover:bg-gray-600 text-white font-medium py-2 px-4 rounded-md border border-gray-600 transition"
          >
            + Add Class
          </button>

          {errors.class_names && (
            <p className="text-red-400 text-sm mt-1">{errors.class_names.message}</p>
          )}
        </div>
      )}
    />
  </div>
)}

{/* OPTIONAL: Per-class thresholds (advanced feature) */}
{watch("mode") === "MULTICLASS" && watch("class_names")?.length > 0 && (
  <div className="mt-4">
    <label className="block text-sm font-medium text-gray-400 mb-2">
      Per-Class Confidence Thresholds (Optional)
      <span className="text-xs text-gray-500 ml-2">Override global threshold for specific classes</span>
    </label>

    <Controller
      name="per_class_thresholds"
      control={control}
      render={({ field }) => (
        <div className="space-y-2 bg-gray-700 p-3 rounded-md">
          {watch("class_names")?.map((className: string, index: number) => (
            <div key={index} className="flex items-center justify-between">
              <span className="text-sm text-white">{className || `Class ${index + 1}`}</span>
              <div className="flex items-center gap-2">
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.01"
                  value={field.value?.[className] || watch("confidence_threshold") || 0.85}
                  onChange={(e) => {
                    field.onChange({
                      ...field.value,
                      [className]: parseFloat(e.target.value)
                    });
                  }}
                  className="w-32 h-2 bg-gray-600 rounded-lg appearance-none cursor-pointer accent-blue-500"
                />
                <span className="text-blue-400 font-mono text-sm w-12 text-right">
                  {Math.round((field.value?.[className] || watch("confidence_threshold") || 0.85) * 100)}%
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    />
  </div>
)}
```

**Update Zod Schema** (around line 18-24):
```tsx
const DetectorConfigSchema = z.object({
  mode: z.string().default('BINARY'),
  class_names: z.array(z.string()).optional().default([]),  // Already exists
  per_class_thresholds: z.record(z.string(), z.number().min(0).max(1)).optional(),  // ADD THIS
  confidence_threshold: z.number().min(0).max(1).default(0.85),
  patience_time: z.number().min(0).default(30.0),
  edge_inference_config: EdgeInferenceConfigSchema.default({}),
});
```

### 2.2 Backend Changes

**File**: `cloud/backend/app/models.py`

**Add column to DetectorConfig** (around line 49-63):
```python
class DetectorConfig(Base):
    __tablename__ = "detector_configs"

    id: uuid.UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    detector_id: uuid.UUID = Column(UUID(as_uuid=True), ForeignKey("detectors.id"), unique=True, nullable=False)
    mode: str = Column(String(50), default="BINARY")
    class_names: list = Column(JSONB, nullable=True)
    confidence_threshold: float = Column(Float, default=0.85)

    # ADD THIS LINE:
    per_class_thresholds: dict = Column(JSONB, nullable=True)  # {"vehicle": 0.85, "person": 0.95}

    edge_inference_config: dict = Column(JSONB, nullable=True)
    patience_time: float = Column(Float, default=30.0)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    updated_at: datetime = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    detector = relationship("Detector", back_populates="config")
```

**Database Migration**:
```bash
# After modifying models.py, run:
cd cloud/backend
alembic revision --autogenerate -m "Add per_class_thresholds to detector_configs"
alembic upgrade head
```

---

## 🛠️ STEP 3: IMPLEMENT FEATURE 2 - MODEL SPECIFICATIONS

### 3.1 Frontend Changes

**File**: `cloud/frontend/src/pages/DetectorConfigPage.tsx`

**Location**: Add a NEW Card after "Model Management" (around line 290-318)

```tsx
{/* ADD NEW CARD: Model Specifications */}
<Card title="Model Specifications">
  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
    {/* Input Configuration */}
    <div className="space-y-4">
      <h3 className="text-sm font-bold text-white uppercase tracking-wider border-b border-gray-600 pb-2">
        Input Configuration
      </h3>

      <div className="grid grid-cols-2 gap-4">
        <Controller
          name="model_input_config.width"
          control={control}
          render={({ field }) => (
            <Input
              label="Input Width (px)"
              type="number"
              {...field}
              onChange={e => field.onChange(parseInt(e.target.value))}
              placeholder="640"
            />
          )}
        />
        <Controller
          name="model_input_config.height"
          control={control}
          render={({ field }) => (
            <Input
              label="Input Height (px)"
              type="number"
              {...field}
              onChange={e => field.onChange(parseInt(e.target.value))}
              placeholder="640"
            />
          )}
        />
      </div>

      <Controller
        name="model_input_config.color_space"
        control={control}
        render={({ field }) => (
          <Select label="Color Space" {...field}>
            <option value="RGB">RGB</option>
            <option value="BGR">BGR (OpenCV default)</option>
            <option value="GRAYSCALE">Grayscale</option>
          </Select>
        )}
      />

      <Controller
        name="model_input_config.normalization_mean"
        control={control}
        render={({ field }) => (
          <div>
            <label className="block text-sm font-medium text-gray-400">Normalization Mean (R,G,B)</label>
            <input
              type="text"
              {...field}
              placeholder="0.485, 0.456, 0.406"
              className="mt-1 block w-full rounded-md bg-gray-700 border-gray-600 text-white shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
            />
            <p className="text-xs text-gray-500 mt-1">ImageNet defaults shown</p>
          </div>
        )}
      />

      <Controller
        name="model_input_config.normalization_std"
        control={control}
        render={({ field }) => (
          <div>
            <label className="block text-sm font-medium text-gray-400">Normalization Std (R,G,B)</label>
            <input
              type="text"
              {...field}
              placeholder="0.229, 0.224, 0.225"
              className="mt-1 block w-full rounded-md bg-gray-700 border-gray-600 text-white shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
            />
          </div>
        )}
      />
    </div>

    {/* Output Configuration */}
    <div className="space-y-4">
      <h3 className="text-sm font-bold text-white uppercase tracking-wider border-b border-gray-600 pb-2">
        Output Configuration
      </h3>

      <Controller
        name="model_output_config.output_format"
        control={control}
        render={({ field }) => (
          <Select label="Output Format" {...field}>
            <option value="probabilities">Probabilities (0-1)</option>
            <option value="logits">Logits (raw scores)</option>
            <option value="bboxes">Bounding Boxes</option>
            <option value="segmentation">Segmentation Masks</option>
          </Select>
        )}
      />

      <Controller
        name="model_output_config.apply_sigmoid"
        control={control}
        render={({ field }) => (
          <Checkbox
            label="Apply Sigmoid to Outputs"
            checked={field.value || false}
            onChange={e => field.onChange(e.target.checked)}
          />
        )}
      />

      <Controller
        name="model_output_config.apply_softmax"
        control={control}
        render={({ field }) => (
          <Checkbox
            label="Apply Softmax to Outputs"
            checked={field.value || false}
            onChange={e => field.onChange(e.target.checked)}
          />
        )}
      />

      {watch("mode") === "BOUNDING_BOX" && (
        <>
          <Controller
            name="model_output_config.bbox_format"
            control={control}
            render={({ field }) => (
              <Select label="Bounding Box Format" {...field}>
                <option value="xyxy">XYXY (x1, y1, x2, y2)</option>
                <option value="xywh">XYWH (x, y, width, height)</option>
                <option value="cxcywh">CXCYWH (center_x, center_y, width, height)</option>
              </Select>
            )}
          />

          <Controller
            name="model_output_config.bbox_normalized"
            control={control}
            render={({ field }) => (
              <Checkbox
                label="Coordinates Normalized (0-1)"
                checked={field.value || false}
                onChange={e => field.onChange(e.target.checked)}
              />
            )}
          />
        </>
      )}
    </div>
  </div>
</Card>
```

**Update Zod Schema**:
```tsx
const ModelInputConfigSchema = z.object({
  width: z.number().min(1).default(640),
  height: z.number().min(1).default(640),
  color_space: z.enum(["RGB", "BGR", "GRAYSCALE"]).default("RGB"),
  normalization_mean: z.string().default("0.485, 0.456, 0.406"),
  normalization_std: z.string().default("0.229, 0.224, 0.225"),
});

const ModelOutputConfigSchema = z.object({
  output_format: z.enum(["probabilities", "logits", "bboxes", "segmentation"]).default("probabilities"),
  apply_sigmoid: z.boolean().default(false),
  apply_softmax: z.boolean().default(false),
  bbox_format: z.enum(["xyxy", "xywh", "cxcywh"]).optional(),
  bbox_normalized: z.boolean().optional(),
});

const DetectorConfigSchema = z.object({
  mode: z.string().default('BINARY'),
  class_names: z.array(z.string()).optional().default([]),
  per_class_thresholds: z.record(z.string(), z.number().min(0).max(1)).optional(),
  confidence_threshold: z.number().min(0).max(1).default(0.85),
  patience_time: z.number().min(0).default(30.0),

  // ADD THESE:
  model_input_config: ModelInputConfigSchema.default({}),
  model_output_config: ModelOutputConfigSchema.default({}),

  edge_inference_config: EdgeInferenceConfigSchema.default({}),
});
```

### 3.2 Backend Changes

**File**: `cloud/backend/app/models.py`

```python
class DetectorConfig(Base):
    __tablename__ = "detector_configs"

    # ... existing columns ...

    # ADD THESE:
    model_input_config: dict = Column(JSONB, nullable=True)
    model_output_config: dict = Column(JSONB, nullable=True)
```

**Run migration**:
```bash
alembic revision --autogenerate -m "Add model input/output config"
alembic upgrade head
```

---

## 🛠️ STEP 4: IMPLEMENT FEATURE 3 - DETECTION PARAMETERS

### 4.1 Frontend Changes

**File**: `cloud/frontend/src/pages/DetectorConfigPage.tsx`

**Location**: Inside "Detection Logic" Card, after confidence threshold (around line 254)

```tsx
{/* ADD: Detection Parameters for BOUNDING_BOX mode */}
{watch("mode") === "BOUNDING_BOX" && (
  <div className="mt-4 p-4 bg-gray-700 rounded-md border border-gray-600">
    <h3 className="text-sm font-bold text-white mb-3 uppercase tracking-wider">
      Object Detection Parameters
    </h3>

    <div className="space-y-3">
      <Controller
        name="detection_params.nms_threshold"
        control={control}
        render={({ field }) => (
          <div>
            <div className="flex justify-between items-center mb-1">
              <label className="text-sm font-medium text-gray-400">NMS Threshold</label>
              <span className="text-blue-400 font-mono text-sm">{field.value?.toFixed(2) || "0.45"}</span>
            </div>
            <input
              type="range"
              min="0"
              max="1"
              step="0.01"
              {...field}
              value={field.value || 0.45}
              onChange={e => field.onChange(parseFloat(e.target.value))}
              className="w-full h-2 bg-gray-600 rounded-lg appearance-none cursor-pointer accent-blue-500"
            />
            <p className="text-xs text-gray-500 mt-1">
              Non-Maximum Suppression: Remove overlapping boxes (higher = more boxes kept)
            </p>
          </div>
        )}
      />

      <Controller
        name="detection_params.iou_threshold"
        control={control}
        render={({ field }) => (
          <div>
            <div className="flex justify-between items-center mb-1">
              <label className="text-sm font-medium text-gray-400">IoU Threshold</label>
              <span className="text-blue-400 font-mono text-sm">{field.value?.toFixed(2) || "0.50"}</span>
            </div>
            <input
              type="range"
              min="0"
              max="1"
              step="0.01"
              {...field}
              value={field.value || 0.50}
              onChange={e => field.onChange(parseFloat(e.target.value))}
              className="w-full h-2 bg-gray-600 rounded-lg appearance-none cursor-pointer accent-green-500"
            />
            <p className="text-xs text-gray-500 mt-1">
              Intersection over Union: Overlap threshold for considering boxes as duplicates
            </p>
          </div>
        )}
      />

      <div className="grid grid-cols-2 gap-3">
        <Controller
          name="detection_params.max_detections"
          control={control}
          render={({ field }) => (
            <Input
              label="Max Detections"
              type="number"
              min="1"
              max="1000"
              {...field}
              value={field.value || 100}
              onChange={e => field.onChange(parseInt(e.target.value))}
            />
          )}
        />

        <Controller
          name="detection_params.min_score"
          control={control}
          render={({ field }) => (
            <Input
              label="Min Score"
              type="number"
              min="0"
              max="1"
              step="0.01"
              {...field}
              value={field.value || 0.25}
              onChange={e => field.onChange(parseFloat(e.target.value))}
            />
          )}
        />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Controller
          name="detection_params.min_object_size"
          control={control}
          render={({ field }) => (
            <Input
              label="Min Object Size (px²)"
              type="number"
              min="0"
              {...field}
              value={field.value || 0}
              onChange={e => field.onChange(parseInt(e.target.value))}
              placeholder="0 (disabled)"
            />
          )}
        />

        <Controller
          name="detection_params.max_object_size"
          control={control}
          render={({ field }) => (
            <Input
              label="Max Object Size (px²)"
              type="number"
              min="0"
              {...field}
              value={field.value || 999999}
              onChange={e => field.onChange(parseInt(e.target.value))}
              placeholder="999999 (disabled)"
            />
          )}
        />
      </div>
    </div>
  </div>
)}
```

**Update Zod Schema**:
```tsx
const DetectionParamsSchema = z.object({
  nms_threshold: z.number().min(0).max(1).default(0.45),
  iou_threshold: z.number().min(0).max(1).default(0.50),
  max_detections: z.number().min(1).max(1000).default(100),
  min_score: z.number().min(0).max(1).default(0.25),
  min_object_size: z.number().min(0).default(0),
  max_object_size: z.number().min(0).default(999999),
});

const DetectorConfigSchema = z.object({
  // ... existing fields ...

  // ADD THIS:
  detection_params: DetectionParamsSchema.optional(),

  edge_inference_config: EdgeInferenceConfigSchema.default({}),
});
```

### 4.2 Backend Changes

**File**: `cloud/backend/app/models.py`

```python
class DetectorConfig(Base):
    # ... existing columns ...

    # ADD THIS:
    detection_params: dict = Column(JSONB, nullable=True)
```

**Run migration**:
```bash
alembic revision --autogenerate -m "Add detection_params to detector_configs"
alembic upgrade head
```

---

## 🛠️ STEP 5: IMPLEMENT FEATURE 4 - LIVE TEST INTERFACE

### 5.1 Frontend Changes

**File**: `cloud/frontend/src/pages/DetectorConfigPage.tsx`

**Location**: Add a NEW Card in the right sidebar (around line 322-347)

```tsx
{/* ADD NEW CARD in right sidebar, before "Quick Actions" */}
<Card title="Test Detector">
  <div className="space-y-4">
    <div>
      <label className="block text-sm font-medium text-gray-400 mb-2">
        Upload Test Image
      </label>
      <input
        type="file"
        accept="image/*"
        onChange={handleTestImageUpload}
        className="block w-full text-sm text-gray-400 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-purple-600 file:text-white hover:file:bg-purple-500 cursor-pointer"
      />
    </div>

    <button
      type="button"
      onClick={runTest}
      disabled={!testImage || isTestRunning}
      className="w-full bg-purple-600 hover:bg-purple-500 text-white font-bold py-2 px-4 rounded disabled:bg-gray-600 disabled:cursor-not-allowed transition"
    >
      {isTestRunning ? "Running..." : "Run Inference Test"}
    </button>

    {testResult && (
      <div className="mt-4 space-y-3">
        <div className="bg-gray-700 p-3 rounded-md">
          <h4 className="text-sm font-bold text-white mb-2">Results</h4>

          {testResult.detections && testResult.detections.length > 0 ? (
            <div className="space-y-2">
              {testResult.detections.map((det: any, idx: number) => (
                <div key={idx} className="flex justify-between items-center bg-gray-800 p-2 rounded">
                  <span className="text-white font-mono text-sm">{det.class || det.label}</span>
                  <span className={`font-bold ${det.confidence >= (detector?.config?.confidence_threshold || 0.85) ? 'text-green-400' : 'text-yellow-400'}`}>
                    {(det.confidence * 100).toFixed(1)}%
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-400 text-sm italic">No detections</p>
          )}
        </div>

        <div className="bg-gray-700 p-3 rounded-md">
          <h4 className="text-sm font-bold text-white mb-2">Performance</h4>
          <div className="space-y-1 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-400">Inference Time:</span>
              <span className="text-white font-mono">{testResult.inference_time_ms}ms</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Status:</span>
              <span className={testResult.would_escalate ? "text-yellow-400" : "text-green-400"}>
                {testResult.would_escalate ? "Would Escalate" : "Confident"}
              </span>
            </div>
          </div>
        </div>

        {testResult.annotated_image_url && (
          <div>
            <h4 className="text-sm font-bold text-white mb-2">Annotated Output</h4>
            <img
              src={testResult.annotated_image_url}
              alt="Annotated detection"
              className="w-full rounded-md border border-gray-600"
            />
          </div>
        )}
      </div>
    )}
  </div>
</Card>
```

**Add state and handlers at top of component** (around line 70-76):
```tsx
const [testImage, setTestImage] = useState<File | null>(null);
const [testResult, setTestResult] = useState<any>(null);
const [isTestRunning, setIsTestRunning] = useState(false);

const handleTestImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
        setTestImage(file);
        setTestResult(null); // Clear previous results
    }
};

const runTest = async () => {
    if (!testImage || !detectorId) return;

    setIsTestRunning(true);
    try {
        const formData = new FormData();
        formData.append('image', testImage);

        const response = await axios.post(`/detectors/${detectorId}/test`, formData, {
            headers: { 'Content-Type': 'multipart/form-data' }
        });

        setTestResult(response.data);
        toast.success('Test completed successfully!');
    } catch (error) {
        toast.error('Test failed. Check if models are uploaded.');
        console.error('Test error:', error);
    } finally {
        setIsTestRunning(false);
    }
};
```

### 5.2 Backend Changes

**File**: `cloud/backend/app/routers/detectors.py`

**Add new endpoint**:
```python
from fastapi import UploadFile, File
import io
from PIL import Image
import numpy as np

@router.post("/{detector_id}/test")
async def test_detector(
    detector_id: str,
    image: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Test detector with a sample image.
    Returns inference results without saving to database.
    """
    detector = db.query(Detector).filter_by(id=detector_id).first()
    if not detector:
        raise HTTPException(status_code=404, detail="Detector not found")

    config = db.query(DetectorConfig).filter_by(detector_id=detector_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="Detector config not found")

    # Read image
    image_bytes = await image.read()

    # TODO: Call inference service
    # This is a placeholder - you'll need to implement actual inference
    # by calling the edge inference service or cloud worker

    # For now, return mock data:
    import random

    mock_detections = []
    if config.mode == "BINARY":
        mock_detections = [{
            "class": "YES" if random.random() > 0.5 else "NO",
            "confidence": random.uniform(0.6, 0.99),
        }]
    elif config.mode == "MULTICLASS" and config.class_names:
        mock_detections = [{
            "class": random.choice(config.class_names),
            "confidence": random.uniform(0.5, 0.95),
        }]
    elif config.mode == "BOUNDING_BOX":
        num_boxes = random.randint(0, 3)
        for _ in range(num_boxes):
            mock_detections.append({
                "class": random.choice(config.class_names or ["object"]),
                "confidence": random.uniform(0.5, 0.95),
                "bbox": {
                    "x1": random.randint(10, 200),
                    "y1": random.randint(10, 200),
                    "x2": random.randint(250, 600),
                    "y2": random.randint(250, 600),
                }
            })

    # Determine if would escalate
    max_confidence = max([d["confidence"] for d in mock_detections], default=0.0)
    would_escalate = max_confidence < config.confidence_threshold

    return {
        "detections": mock_detections,
        "inference_time_ms": random.randint(30, 150),
        "would_escalate": would_escalate,
        "annotated_image_url": None,  # TODO: Generate annotated image
        "message": "Mock inference - replace with actual inference service call"
    }
```

**Note**: The test endpoint above returns **mock data**. For production, you need to:
1. Call the actual inference service (edge or cloud worker)
2. Generate annotated images with bounding boxes
3. Use the real model uploaded to blob storage

---

## ✅ ACCEPTANCE CRITERIA

**You're done when ALL of these are true**:

### Feature 1: Class Configuration ✅
- [ ] Multiclass/Counting/BBox modes show class name editor
- [ ] Can add/remove class names dynamically
- [ ] Binary mode hides class editor
- [ ] Validation requires at least 2 classes for multiclass
- [ ] Per-class thresholds work with sliders
- [ ] Data saves to `per_class_thresholds` column in database

### Feature 2: Model Specifications ✅
- [ ] New "Model Specifications" card appears
- [ ] Can set input width/height
- [ ] Can choose RGB/BGR/Grayscale
- [ ] Can configure normalization mean/std
- [ ] Output format selector works
- [ ] BBox-specific options show only for BOUNDING_BOX mode
- [ ] Data saves to `model_input_config` and `model_output_config` columns

### Feature 3: Detection Parameters ✅
- [ ] Detection parameters section shows only for BOUNDING_BOX mode
- [ ] NMS threshold slider works (0-1)
- [ ] IoU threshold slider works (0-1)
- [ ] Can set max detections, min score, object size limits
- [ ] Data saves to `detection_params` column

### Feature 4: Live Test Interface ✅
- [ ] Can upload test image
- [ ] "Run Inference Test" button calls `/detectors/{id}/test`
- [ ] Results display detections with confidence scores
- [ ] Shows "Would Escalate" vs "Confident" status
- [ ] Shows inference time
- [ ] (Optional) Shows annotated image with bboxes

### General ✅
- [ ] All form fields use react-hook-form Controller
- [ ] Validation errors display properly
- [ ] "Save" button saves all new fields
- [ ] Page loads without errors
- [ ] Database migrations run successfully
- [ ] No TypeScript compilation errors

---

## 🧪 TESTING INSTRUCTIONS

After implementation, test each feature:

### Test 1: Class Configuration
1. Navigate to DetectorConfigPage for any detector
2. Select mode = "MULTICLASS"
3. Verify class editor appears
4. Add 3 classes: "vehicle", "person", "bicycle"
5. Remove "bicycle"
6. Set per-class threshold for "vehicle" to 0.90
7. Click "Save"
8. Reload page - verify classes persist

### Test 2: Model Specifications
1. Go to new "Model Specifications" card
2. Set input size to 640x640
3. Choose "BGR" color space
4. Set normalization mean to "0.5, 0.5, 0.5"
5. Click "Save"
6. Verify data in database: `SELECT model_input_config FROM detector_configs WHERE detector_id = '...'`

### Test 3: Detection Parameters
1. Change mode to "BOUNDING_BOX"
2. Verify detection params section appears
3. Set NMS threshold to 0.60
4. Set max detections to 50
5. Save and reload - verify persistence

### Test 4: Live Test
1. Upload a test image (any JPG/PNG)
2. Click "Run Inference Test"
3. Verify results display (even if mock data)
4. Check backend logs for `/detectors/{id}/test` call

---

## 🚨 COMMON ISSUES & SOLUTIONS

### Issue: "watch is not a function"
**Solution**: Make sure `watch` is destructured from `useForm`:
```tsx
const { handleSubmit, control, reset, watch, formState } = useForm({...});
```

### Issue: Database column doesn't exist
**Solution**: Run migration:
```bash
cd cloud/backend
alembic revision --autogenerate -m "Add new detector config fields"
alembic upgrade head
```

### Issue: TypeScript errors on JSONB columns
**Solution**: Add type annotations in models.py:
```python
per_class_thresholds: dict = Column(JSONB, nullable=True)
```

### Issue: Form doesn't save new fields
**Solution**: Update `onSubmit` handler to include new fields in payload:
```tsx
const configData = {
    ...data,
    per_class_thresholds: data.per_class_thresholds,
    model_input_config: data.model_input_config,
    model_output_config: data.model_output_config,
    detection_params: data.detection_params,
};
```

### Issue: Test endpoint returns 404
**Solution**: Make sure you imported and registered the endpoint in routers/detectors.py

---

## 📦 DELIVERABLES

When complete, provide:

1. **Modified Files List**:
   - `cloud/frontend/src/pages/DetectorConfigPage.tsx` (main changes)
   - `cloud/backend/app/models.py` (new columns)
   - `cloud/backend/app/routers/detectors.py` (test endpoint)
   - Migration file (e.g., `alembic/versions/abc123_add_detector_fields.py`)

2. **Screenshots** (optional but helpful):
   - Class editor with 3 classes
   - Model specifications card filled out
   - Detection parameters for bbox mode
   - Test results showing detections

3. **Test Evidence**:
   - Confirm all 4 features work
   - Database query showing new columns populated

---

## 🎯 SUCCESS METRICS

**Before**: 40% complete detector interface (just deployment settings)
**After**: 80% complete detector interface (can fully configure multiclass/bbox detectors + test them)

**Time Estimate**: 12-16 hours for all 4 features

**Priority**: CRITICAL - These features are required for production use of multiclass and object detection models.

---

## 📞 NEED HELP?

If stuck, refer to:
- `C:\Dev\IntelliOptics 2.0\docs\DETECTOR-INTERFACE-ANALYSIS.md` (detailed requirements)
- `cloud/frontend/src/pages/AlertSettingsPage.tsx` (reference implementation for forms)
- `cloud/backend/app/routers/settings.py` (reference backend endpoints)

**Good luck!** 🚀
