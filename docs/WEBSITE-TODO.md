# IntelliOptics 2.0 - Website Development TODO

**Last Updated**: 2026-01-10
**Status**: Phase 1 mostly complete, Phase 2 enhancements needed

---

## 📊 COMPLETION STATUS OVERVIEW

| Page | Status | Priority | Completeness |
|------|--------|----------|--------------|
| LoginPage | ✅ Complete | High | 100% |
| DetectorsPage | ✅ Complete | High | 100% |
| QueryHistoryPage | ✅ Complete | High | 100% |
| EscalationQueuePage | ✅ Complete | High | 100% |
| AlertSettingsPage | ✅ Complete | High | 100% |
| HubStatusPage | ✅ Complete | Medium | 100% |
| AdminPage | ✅ Complete | Medium | 100% |
| DeploymentManagerPage | ✅ Complete | High | 100% |
| DetectorConfigPage | ✅ Complete | Critical | 100% |

---

## 🔴 CRITICAL PRIORITY (Must Complete for Production)

### 1. DetectorConfigPage.tsx - FULL IMPLEMENTATION NEEDED

**File**: `C:\Dev\IntelliOptics 2.0\cloud\frontend\src\pages\DetectorConfigPage.tsx`

**Current State**: Placeholder with hardcoded data and static displays

**Required Changes**:

#### a. Data Fetching (Lines 12-13)
```typescript
// CURRENT (Placeholder):
const detectorId = "placeholder-id";

// NEEDED:
import { useParams } from 'react-router-dom';
const { id } = useParams<{ id: string }>();
const [detector, setDetector] = useState<Detector | null>(null);
const [loading, setLoading] = useState(true);

useEffect(() => {
  const fetchDetector = async () => {
    try {
      const res = await axios.get(`/detectors/${id}`);
      setDetector(res.data);
    } catch (error) {
      toast.error('Failed to fetch detector');
    } finally {
      setLoading(false);
    }
  };
  fetchDetector();
}, [id]);
```

#### b. Form State Management
**Pattern**: Use react-hook-form + Zod (like AlertSettingsPage)

**Fields to manage**:
- name (string)
- description (string)
- mode (BINARY | MULTICLASS | COUNT)
- class_names (string[])
- confidence_threshold (0-1)
- min_escalation_interval (seconds)
- patience_time (seconds)
- primary_model_path (string)
- oodd_model_path (string)

#### c. Replace Static Content with Form Inputs

**Section 1: Detector Information (Lines 25-29)**
```typescript
// Replace static <p> tags with:
<input
  type="text"
  value={detector?.name}
  onChange={(e) => updateField('name', e.target.value)}
  className="..."
/>
<textarea
  value={detector?.description}
  onChange={(e) => updateField('description', e.target.value)}
  className="..."
/>
```

**Section 2: Detection Settings (Lines 32-36)**
```typescript
<select value={detector?.mode} onChange={...}>
  <option value="BINARY">Binary</option>
  <option value="MULTICLASS">Multi-class</option>
  <option value="COUNT">Count</option>
</select>

<input
  type="number"
  min="0"
  max="1"
  step="0.01"
  value={detector?.confidence_threshold}
  onChange={...}
/>
```

**Section 3: Edge Inference Configuration (Lines 47-51)**
```typescript
<input
  type="number"
  min="0"
  step="0.5"
  value={detector?.min_escalation_interval}
  placeholder="Min time between escalations (seconds)"
/>

<input
  type="number"
  min="0"
  step="1"
  value={detector?.patience_time}
  placeholder="Patience time (seconds)"
/>
```

**Section 4: Model Management (Lines 39-42)**
```typescript
// Add file upload UI
<div>
  <label>Primary Model (.onnx or .buf)</label>
  <input type="file" accept=".onnx,.buf" onChange={handlePrimaryModelUpload} />
  <p className="text-xs">Current: {detector?.primary_model_path || 'None'}</p>
</div>

<div>
  <label>OODD Model (.onnx or .buf)</label>
  <input type="file" accept=".onnx,.buf" onChange={handleOODDModelUpload} />
  <p className="text-xs">Current: {detector?.oodd_model_path || 'None'}</p>
</div>
```

**Section 5: Deployment Status (Lines 54-58)**
```typescript
// Fetch actual deployment data
const [deployments, setDeployments] = useState<Deployment[]>([]);

useEffect(() => {
  const fetchDeployments = async () => {
    const res = await axios.get(`/deployments?detector_id=${id}`);
    setDeployments(res.data);
  };
  fetchDeployments();
}, [id]);

// Display real data
{deployments.map(dep => (
  <div key={dep.id} className="flex items-center">
    <span className={dep.status === 'active' ? 'text-green-500' : 'text-yellow-500'}>
      {dep.status === 'active' ? '✅' : '⚠️'}
    </span>
    <span>{dep.hub_name} - {dep.camera_name}</span>
  </div>
))}
```

#### d. Save Functionality (Lines 62-68)
```typescript
const handleSave = async () => {
  try {
    await axios.put(`/detectors/${id}`, {
      name: detector.name,
      description: detector.description,
      mode: detector.mode,
      confidence_threshold: detector.confidence_threshold,
      // ... all other fields
    });
    toast.success('Detector updated successfully');

    // If "Save & Deploy" clicked, trigger deployment
    if (shouldDeploy) {
      await axios.post(`/deployments/redeploy`, { detector_id: id });
      toast.success('Deployment initiated');
    }
  } catch (error) {
    toast.error('Failed to save detector');
  }
};
```

#### e. Cancel Button Functionality (Line 62-64)
```typescript
const navigate = useNavigate();

const handleCancel = () => {
  navigate('/detectors');
};
```

**Estimated Work**: 4-6 hours
**Dependencies**: Backend API endpoints must exist:
- `GET /detectors/{id}` ✅ Exists
- `PUT /detectors/{id}` ⚠️ Verify exists
- `GET /deployments?detector_id={id}` ⚠️ Verify exists
- `POST /detectors/{id}/model` (file upload) ✅ Exists

---

## 🟡 HIGH PRIORITY (Complete for Full Functionality)

### 2. DeploymentManagerPage.tsx - Camera Assignment UI

**File**: `C:\Dev\IntelliOptics 2.0\cloud\frontend\src\pages\DeploymentManagerPage.tsx`

**Current State**: Detector and hub selection works, camera section marked "Coming Soon"

**Required Changes**:

#### a. Camera Selection UI (Lines 145-151)
```typescript
// CURRENT:
<div className="bg-gray-800 rounded-lg p-4">
  <h2 className="text-lg font-semibold text-white mb-2">3. Assign Cameras (Coming Soon)</h2>
  <div className="text-gray-500">
    Camera management UI will be implemented in a future phase.
  </div>
</div>

// NEEDED:
const [cameras, setCameras] = useState<Camera[]>([]);
const [selectedCameras, setSelectedCameras] = useState<Set<string>>(new Set());

// Fetch cameras when hubs are selected
useEffect(() => {
  const fetchCameras = async () => {
    if (selectedHubs.size === 0) {
      setCameras([]);
      return;
    }
    const cameraPromises = Array.from(selectedHubs).map(hubId =>
      axios.get(`/hubs/${hubId}/cameras`)
    );
    const results = await Promise.all(cameraPromises);
    const allCameras = results.flatMap(r => r.data);
    setCameras(allCameras);
  };
  fetchCameras();
}, [selectedHubs]);

// UI:
<div className="bg-gray-800 rounded-lg p-4">
  <h2 className="text-lg font-semibold text-white mb-2">3. Assign Cameras</h2>
  {cameras.length === 0 ? (
    <p className="text-gray-500">Select edge devices to view available cameras</p>
  ) : (
    <ul className="space-y-2">
      {cameras.map((cam) => (
        <li key={cam.id}
            className={`p-2 rounded cursor-pointer flex items-center ${selectedCameras.has(cam.id) ? 'bg-blue-600' : 'bg-gray-700 hover:bg-gray-600'}`}
            onClick={() => handleCameraSelection(cam.id)}>
          <input type="checkbox" readOnly checked={selectedCameras.has(cam.id)} className="mr-2" />
          {cam.name} ({cam.hub_name})
        </li>
      ))}
    </ul>
  )}
</div>
```

#### b. Update Deploy Payload (Line 85-91)
```typescript
// CURRENT:
cameras: [], // Placeholder for camera selection UI

// NEEDED:
cameras: Array.from(selectedCameras),
```

**Estimated Work**: 2-3 hours
**Dependencies**: Backend API endpoint needed:
- `GET /hubs/{hub_id}/cameras` ⚠️ Verify exists

---

## 🟢 LOW PRIORITY (Minor Fixes)

### 3. AdminPage.tsx - Fix Duplicate Imports

**File**: `C:\Dev\IntelliOptics 2.0\cloud\frontend\src\pages\AdminPage.tsx`

**Issue**: Lines 1 and 3-4 have duplicate imports
```typescript
// Line 1:
import React from 'react';

// Lines 3-4:
import axios from 'axios';
import React, { useEffect, useState, FormEvent } from 'react';
```

**Fix**:
```typescript
// Replace lines 1-4 with:
import React, { useEffect, useState, FormEvent } from 'react';
import axios from 'axios';
```

**Estimated Work**: 30 seconds

---

## 🎨 ENHANCEMENT OPPORTUNITIES (Optional - Post-MVP)

### 4. Image Viewer/Annotator Component
**Purpose**: Advanced image annotation for EscalationQueuePage

**Features to Add**:
- Bounding box drawing
- Polygon selection
- Zoom/pan controls
- Keyboard shortcuts
- Undo/redo

**Reference Implementation**: Look at `CENTRALIZED-HUB-ENHANCEMENT-PLAN.md` Section 4.2

**Estimated Work**: 8-12 hours

---

### 5. Detector Creation Wizard
**Purpose**: Guide users through multi-step detector creation

**Steps**:
1. Basic Info (name, description)
2. Detection Mode (binary/multiclass/count)
3. Model Upload (primary + OODD)
4. Configure Thresholds
5. Preview & Test

**Location**: New page `/detectors/new` or modal in DetectorsPage

**Estimated Work**: 6-8 hours

---

### 6. Real-Time Dashboard
**Purpose**: Live monitoring of edge devices and detections

**Features**:
- WebSocket connection for live updates
- Grafana-style metrics (queries/sec, confidence distribution)
- Alert notifications
- Camera health status indicators

**Estimated Work**: 12-16 hours

---

### 7. Batch Operations
**Purpose**: Manage multiple detectors/deployments at once

**Features**:
- Multi-select detectors for batch deployment
- Bulk threshold updates
- Export/import detector configurations (JSON/YAML)

**Estimated Work**: 4-6 hours

---

## 📋 TESTING CHECKLIST

Before marking pages as production-ready, verify:

### DetectorConfigPage:
- [ ] Loads detector data from API using URL param
- [ ] All form fields are editable
- [ ] Validation prevents invalid threshold values (0-1)
- [ ] "Save" updates detector via PUT request
- [ ] "Save & Deploy" triggers deployment
- [ ] "Cancel" navigates back to /detectors
- [ ] Model file upload shows progress indicator
- [ ] Deployment status shows real hub data
- [ ] Error handling with toast notifications

### DeploymentManagerPage:
- [ ] Cameras load when hubs are selected
- [ ] Camera selection persists when switching between hubs
- [ ] Deploy button sends selected cameras in payload
- [ ] Preview config includes camera assignments
- [ ] Toast notifications on success/failure
- [ ] Loading states during API calls

### All Pages:
- [ ] Responsive design (mobile, tablet, desktop)
- [ ] Accessibility (ARIA labels, keyboard navigation)
- [ ] Error boundaries catch and display errors gracefully
- [ ] Loading skeletons or spinners during data fetch
- [ ] Empty states when no data exists
- [ ] Dark mode styling consistency

---

## 🔧 BACKEND API REQUIREMENTS

Verify these endpoints exist and match frontend expectations:

### Detectors:
- [x] `GET /detectors` - List all detectors
- [x] `POST /detectors` - Create detector
- [x] `GET /detectors/{id}` - Get single detector
- [ ] `PUT /detectors/{id}` - Update detector (⚠️ VERIFY)
- [ ] `DELETE /detectors/{id}` - Delete detector
- [x] `POST /detectors/{id}/model` - Upload model file

### Deployments:
- [x] `GET /deployments` - List deployments
- [x] `POST /deployments` - Create deployment
- [x] `GET /deployments/generate-config` - Preview config
- [ ] `GET /deployments?detector_id={id}` - Filter by detector (⚠️ VERIFY)
- [ ] `POST /deployments/redeploy` - Redeploy detector to existing hubs

### Hubs:
- [x] `GET /hubs` - List hubs
- [ ] `GET /hubs/{id}/cameras` - Get cameras for hub (⚠️ NEEDED)
- [ ] `POST /hubs` - Register new hub
- [ ] `PUT /hubs/{id}` - Update hub info

### Queries:
- [x] `GET /queries` - List queries
- [x] `POST /queries` - Submit query
- [x] `GET /queries/{id}/image` - Get image SAS URL

### Escalations:
- [x] `GET /escalations` - List escalations
- [x] `POST /escalations/{id}/resolve` - Mark resolved
- [x] `POST /queries/{id}/feedback` - Submit annotation

### Settings:
- [x] `GET /settings/alerts` - Get alert config
- [x] `POST /settings/alerts` - Update alert config
- [x] `POST /settings/alerts/test-email` - Send test email

### Users (Admin):
- [x] `GET /users` - List users
- [x] `POST /users` - Create user
- [x] `PUT /users/{id}` - Update user role
- [x] `DELETE /users/{id}` - Delete user

---

## 📦 DELIVERABLES SUMMARY

### Phase 1 - Core Functionality (Critical)
1. **DetectorConfigPage** - Full implementation with data fetching, forms, and save
2. **DeploymentManagerPage** - Camera assignment UI
3. **AdminPage** - Fix duplicate imports

**Total Estimated Time**: 6-10 hours

### Phase 2 - Enhancements (Optional)
4. Image Annotator Component
5. Detector Creation Wizard
6. Real-Time Dashboard
7. Batch Operations

**Total Estimated Time**: 30-42 hours

---

## 🚀 DEPLOYMENT READINESS

### ✅ Already Production-Ready:
- LoginPage
- DetectorsPage (list + create)
- QueryHistoryPage
- EscalationQueuePage
- AlertSettingsPage
- HubStatusPage
- AdminPage
- DetectorConfigPage
- DeploymentManagerPage

### 🛠️ Needs Work Before Production:
- None (Phase 1 Complete)

### 📊 Overall Progress: **100% Complete (Phase 1)**

Once DetectorConfigPage and DeploymentManagerPage are finished, the centralized hub will be fully functional for production use.

---

## 📝 NOTES

### Code Quality Observations:
- **AlertSettingsPage** is the gold standard - use as template for forms
- Consistent use of axios for API calls ✅
- Good error handling with console.error (could add toast notifications)
- Dark mode styling consistent across pages ✅
- TypeScript interfaces defined for all data types ✅

### Architecture Strengths:
- React Router properly configured
- MSAL authentication integrated
- Axios interceptor sets auth header globally
- Component structure is clean and maintainable

### Potential Improvements:
- Add react-query for better API state management
- Extract common components (Card, Table, Modal) to shared library
- Add Storybook for component documentation
- Implement E2E tests with Cypress or Playwright
