# Detector Configuration Enhancement Plan

**Generated:** 2026-01-14
**Purpose:** Add missing configuration fields from IntelliOptics API to the Create Detector page

---

## Executive Summary

**Analysis of:** IntelliOptics APIs.txt vs current DetectorsPage.tsx implementation

**Critical Finding:** The current detector creation form is missing **5 important configuration fields** that are available in the official IntelliOptics API, most notably the **metadata** field which allows storing custom key-value pairs for tracking deployment-specific information.

---

## Current vs API Configuration Fields

### ✅ Currently Implemented

| Field | API Parameter | UI Location | Notes |
|-------|---------------|-------------|-------|
| Detector Name | `name` | Section 1: Basic Information | ✓ Implemented |
| Query Text | `query` | Section 1: Basic Information (as query_text) | ✓ Implemented |
| Description | N/A (UI only) | Section 1: Basic Information | UI-specific field |
| Detection Type | `mode` | Section 2: Detection Type | ✓ BINARY, MULTICLASS, COUNTING, BOUNDING_BOX |
| Class Names | `class_names` | Section 3: Define Classes | ✓ Dynamic array |
| Confidence Threshold | `confidence_threshold` | Section 4: Settings | ✓ Slider (0-100%) |
| Edge Inference Profile | N/A (UI only) | Section 4: Settings | UI-specific field |
| Patience Time | `patience_time` | Advanced Settings | ✓ In advanced section |
| Min Time Between Escalations | N/A (UI only) | Advanced Settings | UI-specific field |

### ❌ Missing from UI (Available in API)

| Field | API Parameter | Type | Purpose | Priority |
|-------|---------------|------|---------|----------|
| **Metadata** | `metadata` | `Mapping[str, Any]` or `str` | **Store custom key-value pairs** (hub_id, camera_id, location, etc.) | **CRITICAL** |
| Detector Group | `group_name` | `str` | Organize detectors into logical groups | HIGH |
| Pipeline Config | `pipeline_config` | `str` | Advanced model pipeline configuration | MEDIUM |
| Mode Configuration | `mode_configuration` | `Mapping[str, Any]` | Mode-specific settings (e.g., max_count for COUNTING) | HIGH |
| ROIs (Regions of Interest) | Via submit_image_query | `Sequence[ROI]` | Define detection zones | MEDIUM |

---

## Detailed Field Analysis

### 1. Metadata (CRITICAL - User Requested)

**API Definition:**
```python
metadata: Mapping[str, Any] | str | None = None
```

**Purpose:**
- Store deployment-specific information with each detector
- Track which hub, camera, or location the detector is associated with
- Enable filtering and reporting by metadata fields
- Store custom business logic parameters

**Common Use Cases:**
```json
{
  "hub_id": "hub-12345",
  "camera_id": "cam-789",
  "location": "Warehouse Loading Dock",
  "department": "Security",
  "priority": "high",
  "contact_email": "security@company.com",
  "custom_field_1": "value1"
}
```

**Why It's Critical:**
- **Deployment Tracking:** Associate detectors with specific edge devices/cameras
- **Multi-tenancy:** Track which client/organization owns each detector
- **Reporting:** Filter queries by metadata (e.g., "all queries from hub-123")
- **Business Logic:** Store custom parameters for alerting, escalation rules, etc.
- **Debugging:** Identify where a detector is deployed when troubleshooting

**Implementation Complexity:** MEDIUM
- Need to build a key-value editor component
- Support both JSON object and string formats
- Validate JSON structure

---

### 2. Detector Group (group_name)

**API Definition:**
```python
group_name: str | None = None
```

**Purpose:**
- Organize detectors into logical groups (e.g., "Building A Security", "Production Line 1")
- Enable bulk operations on detector groups
- Simplify management for large deployments

**Backend Support:**
```python
def create_detector_group(self, name: str, description: str | None = None) -> DetectorGroup
def list_detector_groups(self) -> list[DetectorGroup]
```

**Implementation Complexity:** LOW
- Simple dropdown/autocomplete field
- Fetch existing groups from `/v1/detector-groups`
- Allow creating new groups on-the-fly

---

### 3. Pipeline Config (pipeline_config)

**API Definition:**
```python
pipeline_config: str | None = None
```

**Purpose:**
- Advanced users can customize the AI model pipeline
- Override default preprocessing, inference, or postprocessing steps
- Expert-level configuration

**Implementation Complexity:** LOW
- Simple textarea field
- Include in "Advanced Settings" section
- Add tooltip explaining it's for expert users only

**Recommendation:** Add with clear warning that this is for advanced users only

---

### 4. Mode Configuration (mode_configuration)

**API Definition:**
```python
mode_configuration: Mapping[str, Any] | None = None
```

**Purpose:**
- Mode-specific settings that don't fit in the standard schema
- Examples:
  - **COUNTING mode:** `{"class_name": "person", "max_count": 100}`
  - **BOUNDING_BOX mode:** `{"class_name": "vehicle", "max_num_bboxes": 50}`

**Current Limitation:**
The UI doesn't expose mode-specific advanced settings like `max_count` for COUNTING detectors

**Implementation Complexity:** MEDIUM
- Need conditional fields based on selected mode
- COUNTING mode: Add `max_count` field
- BOUNDING_BOX mode: Add `max_num_bboxes` field

---

### 5. ROIs (Regions of Interest)

**API Support:**
```python
def create_roi(
    self,
    label: str,
    top_left: Sequence[float],
    bottom_right: Sequence[float],
) -> ROI
```

**Purpose:**
- Define specific regions within an image where detection should occur
- Ignore detections outside the ROI
- Reduce false positives from background activity

**Implementation Complexity:** HIGH
- Requires image upload for visual ROI drawing
- Interactive canvas-based ROI editor
- Store coordinates as bounding boxes

**Recommendation:** Phase 2 - Complex UI component needed

---

## Implementation Plan

### Phase 1: Critical Fields (Immediate)

**Priority: Add Metadata Field**

**Location:** Section 1: Basic Information (below Description)

**UI Component:** Key-Value Editor with JSON preview

**Implementation:**

1. **Add to Zod Schema:**
```typescript
const DetectorCreateSchema = z.object({
  // ... existing fields
  metadata: z.record(z.string(), z.any()).optional(),
  // OR as string JSON:
  metadata_json: z.string().optional().refine((val) => {
    if (!val) return true;
    try {
      JSON.parse(val);
      return true;
    } catch {
      return false;
    }
  }, "Must be valid JSON"),
});
```

2. **Add Key-Value Editor Component:**
```tsx
// components/KeyValueEditor.tsx
const KeyValueEditor = ({ value, onChange }: {
  value: Record<string, any>,
  onChange: (val: Record<string, any>) => void
}) => {
  const [pairs, setPairs] = useState<{key: string, value: string}[]>([]);
  const [jsonMode, setJsonMode] = useState(false);

  // Allow toggling between key-value pairs and raw JSON
  // Support adding/removing pairs
  // Validate on change
};
```

3. **Add to Form:**
```tsx
<div>
  <label className="block text-sm font-medium text-gray-400 mb-1">
    Metadata (Key-Value Pairs)
  </label>
  <KeyValueEditor
    value={watch("metadata")}
    onChange={(val) => setValue("metadata", val)}
  />
  <p className="text-[10px] text-gray-500 mt-1 italic">
    💡 Store deployment info: hub_id, camera_id, location, etc.
  </p>
</div>
```

**Time Estimate:** 3-4 hours

---

### Phase 2: Organization Fields (High Priority)

**Add Detector Group Field**

**Location:** Section 1: Basic Information

**Implementation:**

1. **Add to Schema:**
```typescript
group_name: z.string().optional(),
```

2. **Fetch Detector Groups:**
```typescript
const [detectorGroups, setDetectorGroups] = useState<string[]>([]);

useEffect(() => {
  const fetchGroups = async () => {
    const res = await axios.get('/detector-groups');
    setDetectorGroups(res.data.map((g: any) => g.name));
  };
  fetchGroups();
}, []);
```

3. **Add Autocomplete/Select Field:**
```tsx
<div>
  <label className="block text-sm font-medium text-gray-400 mb-1">
    Detector Group (Optional)
  </label>
  <select {...register("group_name")} className="...">
    <option value="">No Group</option>
    {detectorGroups.map(name => (
      <option key={name} value={name}>{name}</option>
    ))}
  </select>
  <p className="text-[10px] text-gray-500 mt-1">
    Organize detectors into groups for easier management
  </p>
</div>
```

**Time Estimate:** 2 hours

---

### Phase 3: Mode-Specific Configuration (High Priority)

**Add Mode Configuration Fields**

**Location:** Conditional section after Section 3 (Define Classes)

**Implementation:**

1. **Add to Schema:**
```typescript
mode_configuration: z.record(z.string(), z.any()).optional(),
// Mode-specific fields:
max_count: z.number().positive().optional(), // For COUNTING
max_num_bboxes: z.number().positive().optional(), // For BOUNDING_BOX
```

2. **Conditional Fields Based on Mode:**
```tsx
{/* COUNTING Mode Configuration */}
{selectedMode === "COUNTING" && (
  <div className="space-y-4">
    <h3 className="text-lg font-semibold text-blue-400">
      4. Counting Configuration
    </h3>
    <div>
      <label>Maximum Expected Count (Optional)</label>
      <input
        type="number"
        {...register("max_count", { valueAsNumber: true })}
        placeholder="e.g., 100"
        className="..."
      />
      <p className="text-xs text-gray-500">
        Set upper limit for count validation
      </p>
    </div>
  </div>
)}

{/* BOUNDING_BOX Mode Configuration */}
{selectedMode === "BOUNDING_BOX" && (
  <div className="space-y-4">
    <h3 className="text-lg font-semibold text-blue-400">
      4. Bounding Box Configuration
    </h3>
    <div>
      <label>Maximum Bounding Boxes (Optional)</label>
      <input
        type="number"
        {...register("max_num_bboxes", { valueAsNumber: true })}
        placeholder="e.g., 50"
        className="..."
      />
      <p className="text-xs text-gray-500">
        Limit number of detected objects
      </p>
    </div>
  </div>
)}
```

3. **Build mode_configuration Object:**
```typescript
const onSubmit = async (data: DetectorCreateFormData) => {
  const payload = {
    ...data,
    mode_configuration: selectedMode === "COUNTING" && data.max_count
      ? { class_name: data.class_names[0], max_count: data.max_count }
      : selectedMode === "BOUNDING_BOX" && data.max_num_bboxes
      ? { class_name: data.class_names[0], max_num_bboxes: data.max_num_bboxes }
      : undefined,
  };

  // Send to API
};
```

**Time Estimate:** 2-3 hours

---

### Phase 4: Advanced Settings (Medium Priority)

**Add Pipeline Config Field**

**Location:** Advanced Settings section (collapsible)

**Implementation:**

1. **Add to Schema:**
```typescript
pipeline_config: z.string().optional(),
```

2. **Add Textarea in Advanced Section:**
```tsx
{showAdvanced && (
  <div className="... grid grid-cols-1 gap-6"> {/* Remove md:grid-cols-2 */}
    {/* Existing patience_time and min_time fields */}

    <div>
      <label className="block text-sm font-medium text-gray-400 mb-1">
        Pipeline Configuration (Expert Only)
        <span className="text-orange-500 ml-1">⚠️</span>
      </label>
      <textarea
        {...register("pipeline_config")}
        rows={4}
        placeholder='{"preprocessing": {...}, "inference": {...}}'
        className="w-full rounded-md bg-gray-700 border-gray-600 text-white p-2 text-sm font-mono"
      />
      <p className="text-[10px] text-orange-400 mt-1">
        ⚠️ Advanced users only: Custom AI pipeline configuration
      </p>
    </div>
  </div>
)}
```

**Time Estimate:** 1 hour

---

### Phase 5: Visual Enhancements (Future)

**ROI Editor (Complex UI Component)**

**Purpose:** Allow users to visually draw detection regions on a reference image

**Complexity:** HIGH - Requires:
- Image upload capability
- Canvas-based drawing tool
- ROI coordinate calculation
- Integration with detector creation flow

**Recommendation:** Separate feature/project. Build after Phase 1-4 are complete.

**Time Estimate:** 8-12 hours

---

## Updated Form Structure (After Implementation)

### Section 1: Basic Information
- Detector Name *
- Query Text
- Description
- **Detector Group** ← NEW
- **Metadata (Key-Value Pairs)** ← NEW (CRITICAL)

### Section 2: Detection Type *
- BINARY / MULTICLASS / COUNTING / BOUNDING_BOX

### Section 3: Define Classes * (if not BINARY)
- Class names array

### Section 4: Mode Configuration (Conditional) ← NEW
- **COUNTING:** max_count
- **BOUNDING_BOX:** max_num_bboxes

### Section 5: Settings
- Confidence Threshold
- Edge Inference Profile

### Advanced Settings (Collapsible)
- Patience Time
- Min Time Between Escalations
- **Pipeline Configuration** ← NEW

---

## Backend API Compatibility

### Current Backend Endpoint
```
POST /detectors/
```

### Expected Request Payload (After Updates)
```json
{
  "name": "Vehicle Detection - Lot A",
  "query_text": "Is there a vehicle?",
  "description": "Monitors parking lot A",
  "mode": "BINARY",
  "confidence_threshold": 0.85,
  "patience_time": 30.0,
  "edge_inference_profile": "default",
  "min_time_between_escalations": 2.0,

  // NEW FIELDS:
  "group_name": "Building A Security",
  "metadata": {
    "hub_id": "hub-12345",
    "camera_id": "cam-789",
    "location": "Parking Lot A - North Entrance",
    "deployment_date": "2026-01-14",
    "contact": "security@company.com"
  },
  "pipeline_config": null,
  "mode_configuration": null
}
```

### Backend Requirements

**Check if backend already supports these fields:**

1. Read backend models file to confirm fields exist
2. If missing, add to Detector model and DetectorConfig model
3. Update create detector endpoint to accept new fields

---

## Implementation Priority

### Immediate (This Week)
1. **Metadata field** - CRITICAL for deployment tracking
   - Time: 3-4 hours
   - Impact: HIGH

2. **Detector Group field** - HIGH for organization
   - Time: 2 hours
   - Impact: MEDIUM

### Short-term (Next Week)
3. **Mode Configuration fields** - HIGH for COUNTING/BOUNDING_BOX
   - Time: 2-3 hours
   - Impact: MEDIUM

4. **Pipeline Config field** - MEDIUM for advanced users
   - Time: 1 hour
   - Impact: LOW

### Long-term (Future Sprint)
5. **ROI Editor** - Complex UI component
   - Time: 8-12 hours
   - Impact: MEDIUM
   - Requires: Image upload, canvas editor, coordinate management

---

## Testing Plan

### Unit Tests
- Validate metadata JSON parsing
- Validate mode_configuration based on mode type
- Test form submission with all new fields

### Integration Tests
- Create detector with metadata
- Create detector with group_name
- Create COUNTING detector with max_count
- Create BOUNDING_BOX detector with max_num_bboxes

### Manual QA Checklist
- [ ] Metadata key-value editor works correctly
- [ ] Metadata can be toggled to JSON mode
- [ ] Invalid JSON shows error message
- [ ] Detector group dropdown populates from backend
- [ ] Mode-specific fields appear/disappear correctly
- [ ] Pipeline config accepts valid JSON
- [ ] Form submits successfully with all new fields
- [ ] Created detector shows metadata in detail view

---

## Risk Assessment

### Low Risk
- Adding detector group field (simple dropdown)
- Adding pipeline config field (simple textarea)

### Medium Risk
- Metadata key-value editor (new complex component)
- Mode configuration conditional logic (requires testing across all modes)

### High Risk
- None for Phase 1-4
- ROI editor would be high risk (Phase 5, deferred)

---

## Success Metrics

### Developer Metrics
- All API-supported fields available in UI
- Form validation catches invalid inputs
- No regression in existing detector creation

### User Metrics
- Users can track detector deployments via metadata
- Users can organize detectors into groups
- Advanced users can configure pipelines
- Mode-specific settings improve COUNTING accuracy

---

## Code Changes Summary

### Files to Modify

1. **`DetectorsPage.tsx`**
   - Add metadata, group_name, pipeline_config, mode_configuration to schema
   - Add KeyValueEditor component import
   - Add detector group fetch logic
   - Add conditional mode configuration sections
   - Update onSubmit to include new fields

2. **`components/KeyValueEditor.tsx`** (NEW FILE)
   - Create reusable key-value pair editor
   - Support JSON mode toggle
   - Validation and error handling

3. **Backend (if needed):**
   - Verify `models.py` has metadata field
   - Verify `schemas.py` includes metadata in DetectorCreate schema
   - Update `detectors.py` router to accept new fields

### Estimated Total Time
- **Phase 1 (Critical):** 5-6 hours
- **Phase 2 (High Priority):** 4-5 hours
- **Phase 3 (Medium Priority):** 1 hour
- **Phase 4 (Future):** 8-12 hours (deferred)

**Total for Phase 1-3:** 10-12 hours

---

## Recommended Execution Order

1. **Day 1 (4 hours):** Build KeyValueEditor component and add metadata field
2. **Day 1 (2 hours):** Add detector group field and API integration
3. **Day 2 (3 hours):** Add mode configuration conditional fields
4. **Day 2 (1 hour):** Add pipeline config to advanced settings
5. **Day 2 (2 hours):** Testing, bug fixes, QA

**Total:** 2 days of focused development

---

## Next Steps

1. **Approve this plan** and confirm priorities
2. **Verify backend support** for new fields (read models.py)
3. **Build KeyValueEditor component** (reusable across the app)
4. **Implement Phase 1** (metadata + detector group)
5. **Test and iterate** before moving to Phase 2

---

**Document Version:** 1.0
**Last Updated:** 2026-01-14
**Ready for Implementation:** YES
