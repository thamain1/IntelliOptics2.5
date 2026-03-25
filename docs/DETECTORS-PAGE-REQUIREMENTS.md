# DetectorsPage - Complete Data Entry Requirements

**Date**: 2026-01-10
**File**: `cloud/frontend/src/pages/DetectorsPage.tsx`
**Current Status**: ⚠️ Incomplete - Missing Critical Fields
**Priority**: 🔴 CRITICAL - Cannot create functional detectors without these fields

---

## 🔍 PROBLEM STATEMENT

**Current DetectorsPage only captures**:
- ✅ Detector Name
- ✅ Description
- ✅ Model File Upload (optional)

**Missing Critical Fields**:
- ❌ **Operation Mode** (BINARY, MULTICLASS, COUNTING, BOUNDING_BOX) - **REQUIRED**
- ❌ **Class Names** (for multiclass/counting/bbox modes) - **REQUIRED**
- ❌ **Confidence Threshold** (escalation threshold) - **REQUIRED**
- ❌ **Query Text** (natural language question) - **RECOMMENDED**

**Impact**: Users create "empty shell" detectors that cannot function until fully configured on the DetectorConfigPage. This creates a poor user experience and requires extra steps.

---

## 🎯 RECOMMENDED APPROACH

### Option A: Multi-Step Creation Wizard (RECOMMENDED)
**Best UX** - Guide users through essential fields in logical order

**Steps**:
1. **Basic Info** - Name, Description, Query Text
2. **Detection Type** - Mode selection (with examples/help text)
3. **Classes** - Class names (if mode requires it)
4. **Initial Settings** - Confidence threshold, Primary model upload
5. **Review & Create** - Summary of all settings

**Time to Build**: 8-10 hours
**Result**: Users create fully-configured detectors ready for deployment

---

### Option B: Expanded Single-Page Form (FASTER)
**Good UX** - All essential fields on one page, organized in sections

**Sections**:
1. Basic Information
2. Detection Configuration
3. Initial Thresholds
4. Model Upload (optional)

**Time to Build**: 4-6 hours
**Result**: Users create detectors with all critical fields, can deploy after model upload

---

### Option C: Current Minimal + Mandatory Config (CURRENT - NOT RECOMMENDED)
**Poor UX** - Create skeleton, force user to configure before use

**Flow**:
1. Create detector (name only)
2. Redirect to DetectorConfigPage
3. Prevent deployment until mode + classes configured

**Time to Build**: 2 hours (just validation)
**Result**: Extra steps, confusing UX, high chance of incomplete detectors

---

## 📋 COMPLETE DATA ENTRY REQUIREMENTS

### 1. BASIC INFORMATION (Required at Creation)

#### 1.1 Detector Name
```typescript
{
  field: "name",
  type: "text",
  required: true,
  validation: {
    minLength: 3,
    maxLength: 128,
    pattern: /^[a-zA-Z0-9\s\-_]+$/,  // Alphanumeric, spaces, hyphens, underscores
  },
  placeholder: "e.g., Vehicle Detection - Parking Lot A",
  helpText: "Descriptive name to identify this detector",
}
```

**Why Required**: Unique identifier for the detector across the system.

---

#### 1.2 Description
```typescript
{
  field: "description",
  type: "textarea",
  required: false,
  validation: {
    maxLength: 500,
  },
  placeholder: "e.g., Detects vehicles in parking lot for occupancy monitoring",
  helpText: "Detailed explanation of what this detector does and where it's used",
}
```

**Why Optional**: Nice to have for documentation, not critical for functionality.

---

#### 1.3 Query Text (Groundlight Pattern)
```typescript
{
  field: "query_text",
  type: "text",
  required: false,  // But HIGHLY RECOMMENDED
  validation: {
    maxLength: 200,
    endsWithQuestionMark: true,  // Encourage question format
  },
  placeholder: "e.g., Is there a vehicle in the parking space?",
  helpText: "Natural language question this detector answers. Helps human reviewers understand context.",
  examples: [
    "Is there a defect on the weld?",
    "How many people are in the restricted area?",
    "Is the worker wearing a hard hat?",
    "Is the packaging label correctly aligned?",
  ],
}
```

**Why Recommended**:
- Human reviewers need context when annotating escalations
- Makes detector purpose immediately clear
- Follows Groundlight API pattern (industry best practice)
- Improves annotation quality → better model retraining

---

### 2. DETECTION CONFIGURATION (CRITICAL - Required at Creation)

#### 2.1 Operation Mode
```typescript
{
  field: "mode",
  type: "select",
  required: true,
  options: [
    {
      value: "BINARY",
      label: "Binary Classification (Yes/No)",
      description: "Answers a yes/no question about the image",
      examples: [
        "Is there a vehicle present?",
        "Is there a defect?",
        "Is the worker wearing PPE?",
      ],
      icon: "🔵",
    },
    {
      value: "MULTICLASS",
      label: "Multi-class Classification",
      description: "Categorizes the image into one of several classes",
      examples: [
        "Vehicle type: sedan, truck, SUV, motorcycle",
        "Defect type: crack, dent, scratch, discoloration",
        "PPE status: full, partial, none",
      ],
      icon: "🎨",
    },
    {
      value: "COUNTING",
      label: "Object Counting",
      description: "Counts instances of objects in the image",
      examples: [
        "How many people are in the area?",
        "How many products on the shelf?",
        "How many defects on the surface?",
      ],
      icon: "🔢",
    },
    {
      value: "BOUNDING_BOX",
      label: "Object Detection (Bounding Boxes)",
      description: "Locates and classifies multiple objects with bounding boxes",
      examples: [
        "Locate all vehicles in the parking lot",
        "Detect all defects and their locations",
        "Find all workers and equipment in the scene",
      ],
      icon: "📦",
    },
  ],
  helpText: "Choose the type of detection this detector performs. This determines what data is returned and how models are trained.",
}
```

**Why CRITICAL**:
- Determines everything else about the detector
- Cannot train model without knowing mode
- Cannot configure inference without mode
- Cannot create meaningful escalations without mode

**UI Pattern**: Large selectable cards with icons, not a dropdown. Visual selection.

---

#### 2.2 Class Names (Conditional - Required for MULTICLASS, COUNTING, BOUNDING_BOX)
```typescript
{
  field: "class_names",
  type: "dynamic_list",
  required: (mode) => mode !== "BINARY",  // Required if not binary
  conditionalDisplay: (mode) => mode !== "BINARY",
  validation: {
    minItems: (mode) => mode === "MULTICLASS" ? 2 : 1,
    maxItems: 50,
    uniqueValues: true,
    pattern: /^[a-zA-Z0-9\s\-_]+$/,
  },
  placeholder: "Enter class name",
  helpText: {
    MULTICLASS: "Define the categories for classification (minimum 2). E.g., 'sedan', 'truck', 'SUV'",
    COUNTING: "What object are you counting? E.g., 'person', 'product', 'defect'",
    BOUNDING_BOX: "What objects should be detected? E.g., 'vehicle', 'person', 'equipment'",
  },
  examples: {
    MULTICLASS: ["acceptable", "defect_minor", "defect_major"],
    COUNTING: ["person"],
    BOUNDING_BOX: ["vehicle", "person", "bicycle"],
  },
}
```

**Why CRITICAL**:
- Model training requires class definitions
- Inference outputs need class labels
- Human annotators need class options
- Cannot function without classes for these modes

**UI Pattern**:
- Dynamic list with Add/Remove buttons
- Pre-filled with example for selected mode
- Show count: "2 classes defined (minimum 2 required)"

---

### 3. INITIAL SETTINGS (Required at Creation)

#### 3.1 Confidence Threshold
```typescript
{
  field: "confidence_threshold",
  type: "slider",
  required: true,
  default: 0.85,
  validation: {
    min: 0.0,
    max: 1.0,
    step: 0.01,
  },
  display: {
    showPercentage: true,
    showLabels: {
      0.0: "All escalate",
      0.5: "Uncertain",
      0.85: "Recommended",
      1.0: "Never escalate",
    },
  },
  helpText: "Results below this threshold will be sent to the cloud for human review. Higher = fewer escalations, lower = more human validation.",
  recommendations: {
    production: 0.85,
    testing: 0.70,
    safetyTriggered: 0.95,
  },
}
```

**Why Required**:
- Determines escalation behavior (core system feature)
- Affects cost (more escalations = more human review time)
- Affects accuracy (lower threshold = catch more edge cases)
- Has sensible default (0.85) but should be configurable at creation

**UI Pattern**:
- Large slider with live percentage display
- Color gradient (red → yellow → green)
- Show estimated escalation rate based on threshold

---

#### 3.2 Edge Inference Profile (Optional - Has Smart Default)
```typescript
{
  field: "edge_inference_profile",
  type: "select",
  required: false,
  default: "default",
  options: [
    {
      value: "default",
      label: "Default (Cloud Escalation Enabled)",
      description: "Low confidence results escalate to cloud for human review",
      recommended: true,
    },
    {
      value: "offline",
      label: "Offline Mode (No Cloud Escalation)",
      description: "Always return edge prediction, never escalate to cloud",
      useCase: "Air-gapped environments, privacy-sensitive deployments",
    },
    {
      value: "aggressive",
      label: "Aggressive Escalation",
      description: "Lower threshold, more human review, higher accuracy",
      useCase: "Critical safety applications, initial model training",
    },
  ],
  helpText: "Controls how the edge device handles low-confidence predictions",
}
```

**Why Optional**:
- Has sensible default ("default" profile)
- Can be changed later on config page
- Most users don't need to change this

---

### 4. MODEL UPLOAD (Optional at Creation - Can Be Done Later)

#### 4.1 Primary Model File
```typescript
{
  field: "primary_model_file",
  type: "file",
  required: false,
  accept: [".onnx", ".buf", ".pt", ".pth"],
  validation: {
    maxSize: "500MB",
    fileTypes: ["application/octet-stream", "application/x-onnx"],
  },
  helpText: "Upload the main inference model (ONNX or .buf format). Can be uploaded later if not ready.",
  placeholder: "Choose ONNX model file...",
}
```

**Why Optional**:
- Users may not have trained model yet
- May want to test configuration before uploading large files
- Can be uploaded later via DetectorConfigPage

---

#### 4.2 OODD Model File (Optional at Creation)
```typescript
{
  field: "oodd_model_file",
  type: "file",
  required: false,
  accept: [".onnx", ".buf"],
  validation: {
    maxSize: "500MB",
  },
  helpText: "Out-of-Domain Detection model (ground truth). Optional but recommended for production.",
  placeholder: "Choose OODD model file...",
  conditionalDisplay: (advanced_mode) => advanced_mode === true,  // Show in "Advanced" section
}
```

**Why Optional**:
- OODD is advanced feature
- Not all users need it initially
- Can be added later

---

### 5. ADVANCED SETTINGS (Optional - Collapsible Section)

These should be in an "Advanced Settings" collapsible section, not shown by default:

#### 5.1 Patience Time
```typescript
{
  field: "patience_time",
  type: "number",
  required: false,
  default: 30.0,
  unit: "seconds",
  validation: {
    min: 0.0,
    max: 300.0,
  },
  helpText: "How long to wait before processing another query for the same detector (debounce)",
}
```

#### 5.2 Min Time Between Escalations
```typescript
{
  field: "min_time_between_escalations",
  type: "number",
  required: false,
  default: 2.0,
  unit: "seconds",
  validation: {
    min: 0.0,
    max: 60.0,
  },
  helpText: "Minimum time between escalations to avoid flooding human reviewers",
}
```

---

## 🎨 RECOMMENDED UI LAYOUT

### Layout: Multi-Step Wizard (Option A)

```
┌────────────────────────────────────────────────────────────┐
│  Create New Detector                          Step 1 of 4  │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Step Indicator: [●]──[○]──[○]──[○]                       │
│                Basic  Type  Classes  Review               │
│                                                            │
│  ┌────────────────────────────────────────────────────┐  │
│  │ STEP 1: BASIC INFORMATION                          │  │
│  ├────────────────────────────────────────────────────┤  │
│  │                                                     │  │
│  │  Detector Name *                                    │  │
│  │  [Vehicle Detection - Parking Lot A____________]   │  │
│  │                                                     │  │
│  │  Description                                        │  │
│  │  [Detects vehicles in parking lot for        ]    │  │
│  │  [occupancy monitoring                         ]    │  │
│  │                                                     │  │
│  │  Query Text (Recommended)                          │  │
│  │  [Is there a vehicle in the parking space?___]    │  │
│  │  💡 This helps human reviewers understand context  │  │
│  │                                                     │  │
│  └────────────────────────────────────────────────────┘  │
│                                                            │
│                           [Cancel]  [Next: Choose Type →] │
└────────────────────────────────────────────────────────────┘
```

```
┌────────────────────────────────────────────────────────────┐
│  Create New Detector                          Step 2 of 4  │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Step Indicator: [●]──[●]──[○]──[○]                       │
│                Basic  Type  Classes  Review               │
│                                                            │
│  ┌────────────────────────────────────────────────────┐  │
│  │ STEP 2: DETECTION TYPE                             │  │
│  ├────────────────────────────────────────────────────┤  │
│  │                                                     │  │
│  │  What type of detection does this perform? *       │  │
│  │                                                     │  │
│  │  ┌──────────────────┐ ┌──────────────────┐        │  │
│  │  │ 🔵 BINARY       │ │ 🎨 MULTICLASS    │        │  │
│  │  │ Yes/No Question │ │ Classify into    │        │  │
│  │  │                 │ │ multiple classes │        │  │
│  │  │ [○ Select]      │ │ [○ Select]       │        │  │
│  │  └──────────────────┘ └──────────────────┘        │  │
│  │                                                     │  │
│  │  ┌──────────────────┐ ┌──────────────────┐        │  │
│  │  │ 🔢 COUNTING     │ │ 📦 BOUNDING BOX  │        │  │
│  │  │ Count objects   │ │ Detect & locate  │        │  │
│  │  │ in image        │ │ multiple objects │        │  │
│  │  │ [● Selected]    │ │ [○ Select]       │        │  │
│  │  └──────────────────┘ └──────────────────┘        │  │
│  │                                                     │  │
│  │  💡 Selected: COUNTING                             │  │
│  │  Example: "How many people are in the area?"      │  │
│  │                                                     │  │
│  └────────────────────────────────────────────────────┘  │
│                                                            │
│                              [← Back]  [Next: Classes →] │
└────────────────────────────────────────────────────────────┘
```

```
┌────────────────────────────────────────────────────────────┐
│  Create New Detector                          Step 3 of 4  │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Step Indicator: [●]──[●]──[●]──[○]                       │
│                Basic  Type  Classes  Review               │
│                                                            │
│  ┌────────────────────────────────────────────────────┐  │
│  │ STEP 3: DEFINE CLASSES                             │  │
│  ├────────────────────────────────────────────────────┤  │
│  │                                                     │  │
│  │  What object are you counting? *                   │  │
│  │                                                     │  │
│  │  Class Name 1:                                     │  │
│  │  [person_______________________] [✕ Remove]        │  │
│  │                                                     │  │
│  │  [+ Add Another Class]                             │  │
│  │                                                     │  │
│  │  1 class defined                                   │  │
│  │                                                     │  │
│  │  ─────────────────────────────────────────────     │  │
│  │                                                     │  │
│  │  Confidence Threshold *                            │  │
│  │  ├───────────────●───────┤ 85%                     │  │
│  │  Low                 High                          │  │
│  │                                                     │  │
│  │  💡 Results below 85% will be sent for human       │  │
│  │     review to improve model accuracy               │  │
│  │                                                     │  │
│  └────────────────────────────────────────────────────┘  │
│                                                            │
│                             [← Back]  [Next: Review →]   │
└────────────────────────────────────────────────────────────┘
```

```
┌────────────────────────────────────────────────────────────┐
│  Create New Detector                          Step 4 of 4  │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  Step Indicator: [●]──[●]──[●]──[●]                       │
│                Basic  Type  Classes  Review               │
│                                                            │
│  ┌────────────────────────────────────────────────────┐  │
│  │ STEP 4: REVIEW & CREATE                            │  │
│  ├────────────────────────────────────────────────────┤  │
│  │                                                     │  │
│  │  Summary                                           │  │
│  │  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │  │
│  │  Name: Vehicle Detection - Parking Lot A          │  │
│  │  Description: Detects vehicles in parking lot...  │  │
│  │  Query: Is there a vehicle in the parking space?  │  │
│  │                                                     │  │
│  │  Type: 🔢 COUNTING                                 │  │
│  │  Classes: person (1 class)                         │  │
│  │  Confidence Threshold: 85%                         │  │
│  │                                                     │  │
│  │  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │  │
│  │                                                     │  │
│  │  Optional: Upload Models Now                       │  │
│  │  (You can also upload models later)                │  │
│  │                                                     │  │
│  │  Primary Model:                                    │  │
│  │  [Choose File...] No file selected                │  │
│  │                                                     │  │
│  │  OODD Model:                                       │  │
│  │  [Choose File...] No file selected                │  │
│  │                                                     │  │
│  └────────────────────────────────────────────────────┘  │
│                                                            │
│              [← Back]  [Skip Models]  [Create Detector]  │
└────────────────────────────────────────────────────────────┘
```

---

### Layout: Single-Page Form (Option B - Faster to Build)

```
┌────────────────────────────────────────────────────────────┐
│  Create New Detector                                  [✕]  │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  ┌────── 1. BASIC INFORMATION ──────────────────────┐    │
│  │ Detector Name *                                    │    │
│  │ [_________________________________________]        │    │
│  │                                                    │    │
│  │ Description                                        │    │
│  │ [_________________________________________]        │    │
│  │                                                    │    │
│  │ Query Text (Recommended)                          │    │
│  │ [_________________________________________]        │    │
│  └─────────────────────────────────────────────────┘    │
│                                                            │
│  ┌────── 2. DETECTION TYPE * ───────────────────────┐    │
│  │ [○] Binary   [○] Multiclass  [●] Counting  [○] BBox │  │
│  └─────────────────────────────────────────────────┘    │
│                                                            │
│  ┌────── 3. CLASSES (for Counting mode) ───────────┐    │
│  │ [person_________________] [✕]                     │    │
│  │ [+ Add Class]                                     │    │
│  └─────────────────────────────────────────────────┘    │
│                                                            │
│  ┌────── 4. THRESHOLD ──────────────────────────────┐    │
│  │ Confidence Threshold: ├────●──┤ 85%              │    │
│  └─────────────────────────────────────────────────┘    │
│                                                            │
│  ┌────── 5. MODELS (Optional) ──────────────────────┐    │
│  │ Primary Model: [Choose File...]                   │    │
│  │ OODD Model: [Choose File...]                      │    │
│  └─────────────────────────────────────────────────┘    │
│                                                            │
│  ⚠️ Advanced Settings (click to expand)                  │
│                                                            │
│                              [Cancel]  [Create Detector]  │
└────────────────────────────────────────────────────────────┘
```

---

## 🔧 BACKEND API CHANGES NEEDED

### Update: POST /detectors

**Current Schema** (too minimal):
```python
class DetectorCreate(BaseModel):
    name: str
    description: Optional[str] = None
```

**New Schema** (complete):
```python
class DetectorCreate(BaseModel):
    # Basic Info
    name: str = Field(..., min_length=3, max_length=128)
    description: Optional[str] = Field(None, max_length=500)
    query_text: Optional[str] = Field(None, max_length=200)

    # Detection Configuration (REQUIRED)
    mode: str = Field(..., regex="^(BINARY|MULTICLASS|COUNTING|BOUNDING_BOX)$")
    class_names: Optional[List[str]] = Field(None, min_items=1, max_items=50)
    confidence_threshold: float = Field(0.85, ge=0.0, le=1.0)

    # Edge Inference Profile
    edge_inference_profile: Optional[str] = Field("default", regex="^(default|offline|aggressive)$")

    # Advanced (optional)
    patience_time: Optional[float] = Field(30.0, ge=0.0)
    min_time_between_escalations: Optional[float] = Field(2.0, ge=0.0)

    @validator("class_names")
    def validate_class_names(cls, v, values):
        mode = values.get("mode")
        if mode in ["MULTICLASS", "COUNTING", "BOUNDING_BOX"]:
            if not v or len(v) == 0:
                raise ValueError(f"class_names required for {mode} mode")
            if mode == "MULTICLASS" and len(v) < 2:
                raise ValueError("MULTICLASS mode requires at least 2 classes")
        return v
```

**Update Endpoint**:
```python
@router.post("/", response_model=schemas.DetectorOut, status_code=201)
def create_detector(
    payload: schemas.DetectorCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_admin),
) -> models.Detector:
    """Create a new detector with complete configuration."""

    # Create detector
    det = models.Detector(
        name=payload.name,
        description=payload.description,
        query_text=payload.query_text  # NEW
    )
    db.add(det)
    db.commit()
    db.refresh(det)

    # Create full config (not just defaults)
    config = models.DetectorConfig(
        detector_id=det.id,
        mode=payload.mode,  # NEW - no longer default
        class_names=payload.class_names,  # NEW
        confidence_threshold=payload.confidence_threshold,  # NEW - user-specified
        patience_time=payload.patience_time,
        edge_inference_config={
            "profile": payload.edge_inference_profile,
            "min_time_between_escalations": payload.min_time_between_escalations,
        }
    )
    db.add(config)
    db.commit()
    db.refresh(det)

    return det
```

---

## ✅ ACCEPTANCE CRITERIA

A detector is "properly created" when:

1. ✅ **Name** is provided (3-128 characters)
2. ✅ **Mode** is selected (BINARY, MULTICLASS, COUNTING, or BOUNDING_BOX)
3. ✅ **Class names** are defined (if mode requires them)
   - MULTICLASS: minimum 2 classes
   - COUNTING: minimum 1 class
   - BOUNDING_BOX: minimum 1 class
4. ✅ **Confidence threshold** is set (default 0.85, user can adjust)
5. ✅ **Query text** is recommended but optional
6. ✅ Detector is immediately functional (can receive queries)
7. ✅ Detector can be deployed to edge devices after model upload

---

## 🚫 VALIDATION RULES

### Field-Level Validation:
- Name: 3-128 chars, alphanumeric + spaces/hyphens/underscores
- Description: 0-500 chars
- Query text: 0-200 chars, recommend ending with "?"
- Mode: Must be one of 4 valid modes
- Class names: 1-50 items, unique, alphanumeric
- Confidence threshold: 0.0-1.0

### Cross-Field Validation:
- If mode = MULTICLASS, require class_names.length >= 2
- If mode = COUNTING or BOUNDING_BOX, require class_names.length >= 1
- If mode = BINARY, class_names should be empty or ["YES", "NO"]

### Business Logic Validation:
- Detector name must be unique across tenant
- Cannot create detector without mode
- Cannot deploy detector without model upload (warn user)

---

## 📊 COMPARISON: Current vs. Recommended

| Field | Current | Recommended | Impact |
|-------|---------|-------------|--------|
| Name | ✅ Required | ✅ Required | Same |
| Description | ✅ Optional | ✅ Optional | Same |
| Query Text | ❌ Missing | ⚠️ Recommended | Better UX for reviewers |
| **Mode** | ❌ **Missing** | ✅ **REQUIRED** | **CRITICAL - Can't function without** |
| **Class Names** | ❌ **Missing** | ✅ **REQUIRED** (conditional) | **CRITICAL for multiclass** |
| **Confidence Threshold** | ❌ **Missing** (uses default) | ✅ **REQUIRED** (with default) | **User control over escalation** |
| Edge Profile | ❌ Missing | ⚠️ Optional (default) | Nice to have |
| Model Upload | ✅ Optional | ✅ Optional | Same |

**Completeness Score**:
- Current: 3/8 fields (37.5%)
- Recommended: 8/8 fields (100%)

---

## 🎯 IMPLEMENTATION PRIORITY

### CRITICAL (Must Have - 4-6 hours):
1. Add Mode selection (visual cards)
2. Add Class names editor (conditional on mode)
3. Add Confidence threshold slider
4. Update backend schema validation
5. Update POST /detectors endpoint

### HIGH (Should Have - 2-3 hours):
6. Add Query text field
7. Multi-step wizard UI (optional, but better UX)

### MEDIUM (Nice to Have - 1-2 hours):
8. Add Edge inference profile selector
9. Add Advanced settings collapsible section

---

## 🎨 UI/UX RECOMMENDATIONS

### Visual Mode Selection:
Use large, clickable cards (not dropdown) with:
- Icon (emoji or SVG)
- Mode name
- 1-sentence description
- Example use case
- Radio button selection

### Class Name Editor:
- Pre-populate with sensible example based on mode
- Dynamic add/remove
- Show count: "2 classes defined"
- Validation message: "MULTICLASS requires at least 2 classes"

### Confidence Slider:
- Large, prominent slider
- Live percentage display
- Color gradient (red → yellow → green)
- Suggested values: 0.7 (testing), 0.85 (production), 0.95 (critical)
- Show icon/emoji at different ranges

### Progressive Disclosure:
- Start with Basic Info
- Show Detection Type
- Conditionally show Class Names (only if needed)
- Advanced settings collapsed by default

---

## 📦 DELIVERABLES

When complete, you should have:

1. **Updated DetectorsPage.tsx** with all required fields
2. **Updated DetectorCreate schema** in backend
3. **Updated POST /detectors endpoint** with full validation
4. **Validation messages** for all fields
5. **Help text/tooltips** explaining each field
6. **Examples** showing typical values

**Result**: Users can create fully-functional detectors in one step, ready for model upload and deployment.

---

## 🚀 NEXT STEPS FOR HANDOFF

To implement this, provide to another AI:

1. This document (DETECTORS-PAGE-REQUIREMENTS.md)
2. Current DetectorsPage.tsx file
3. Current backend schemas.py file
4. Instruction: "Implement Option B (Single-Page Form) with all required fields per the specification"

**Estimated Time**: 4-6 hours for complete implementation

---

**BOTTOM LINE**: Current DetectorsPage is incomplete and creates non-functional "skeleton" detectors. Adding Mode, Class Names, and Confidence Threshold is CRITICAL for creating usable detectors. The rest is nice-to-have but strongly recommended for good UX.
