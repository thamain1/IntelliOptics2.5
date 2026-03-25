# IntelliOptics 2.0 - AI Handoff Brief

**Date**: 2026-01-10
**Phase**: Backend Implementation & Integration Testing
**Frontend Status**: ✅ 100% Complete
**Backend Status**: ⚠️ Needs Verification & Implementation

---

## 🎯 PROJECT OVERVIEW

**IntelliOptics 2.0** is an edge-first computer vision platform for industrial inspection and monitoring. It uses a **detector-centric architecture** with confidence-based escalation:

- **80-90% of queries** processed on edge devices (low latency, low cost)
- **10-20% escalated to cloud** when confidence < threshold (human review + retraining)
- **Continuous learning loop**: Escalations → Human labels → Model retraining → Deploy to edge

### Key Concepts:
- **Detectors**: Core control object (owns models, thresholds, escalation rules)
- **Hubs**: Edge devices running inference locally
- **Cameras**: RTSP streams monitored by hubs
- **Deployments**: Assignment of Detector + Cameras to Hubs
- **Escalations**: Low-confidence queries sent to cloud for human review

---

## 📂 PROJECT STRUCTURE

```
C:\Dev\IntelliOptics 2.0\
├── cloud\                          # Centralized web application
│   ├── backend\                    # FastAPI backend
│   │   ├── app\
│   │   │   ├── main.py
│   │   │   ├── models.py           # SQLAlchemy database models
│   │   │   └── routers\
│   │   │       ├── detectors.py    # ⚠️ NEEDS UPDATES
│   │   │       ├── deployments.py  # ⚠️ NEEDS UPDATES
│   │   │       ├── hubs.py         # ⚠️ NEEDS NEW ENDPOINTS
│   │   │       ├── queries.py      # ✅ Complete
│   │   │       ├── escalations.py  # ✅ Complete
│   │   │       └── settings.py     # ✅ Complete
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── frontend\                   # React + TypeScript
│   │   ├── src\
│   │   │   ├── App.tsx             # ✅ Complete
│   │   │   └── pages\
│   │   │       ├── DetectorConfigPage.tsx     # ✅ JUST COMPLETED
│   │   │       ├── DeploymentManagerPage.tsx  # ✅ JUST COMPLETED
│   │   │       ├── AlertSettingsPage.tsx      # ✅ Complete
│   │   │       ├── DetectorsPage.tsx          # ✅ Complete
│   │   │       ├── QueryHistoryPage.tsx       # ✅ Complete
│   │   │       ├── EscalationQueuePage.tsx    # ✅ Complete
│   │   │       ├── HubStatusPage.tsx          # ✅ Complete
│   │   │       └── AdminPage.tsx              # ✅ Complete
│   │   ├── Dockerfile
│   │   └── package.json
│   ├── worker\                     # Inference worker
│   └── docker-compose.yml
├── edge\                           # Edge device deployment
│   ├── edge-api\                   # FastAPI edge orchestrator
│   ├── inference\                  # ONNX Runtime inference service
│   ├── nginx\                      # Gateway (port 30101)
│   ├── config\
│   │   └── edge-config.yaml
│   └── docker-compose.yml
└── docs\
    ├── WEBSITE-TODO.md             # ✅ Phase 1 complete
    ├── NEXT-STEPS.md               # Detailed roadmap
    ├── DETECTOR-CREATION-GUIDE.md
    └── AI-HANDOFF-BRIEF.md         # ← You are here
```

---

## ✅ WHAT'S BEEN COMPLETED

### Frontend (100% Complete)

All 9 React pages are production-ready with:
- Full CRUD operations for detectors, deployments, escalations
- Form validation using `react-hook-form` + `Zod`
- Toast notifications for user feedback
- Dark mode consistent styling
- Responsive layouts (mobile, tablet, desktop)
- MSAL authentication integration

**Recently Completed (Critical):**

#### 1. **DetectorConfigPage.tsx** (`cloud/frontend/src/pages/DetectorConfigPage.tsx`)
**Purpose**: Configure detector settings, upload models, view deployments

**Key Features**:
- Dynamic routing: `/detectors/:id/configure` (uses `useParams()`)
- 5 sections implemented:
  1. General Information (name, description)
  2. Detection Logic (mode: BINARY/MULTICLASS/COUNTING/BOUNDING_BOX, confidence threshold slider)
  3. Edge Optimization (offline mode, patience time, min escalation interval)
  4. Model Management (file uploads for Primary + OODD models with progress indicators)
  5. Deployment Status (real-time list from API)
- Save & Save+Deploy buttons with proper API calls
- Quick Actions sidebar (links to Query History, Escalation Queue filtered by detector)

**API Calls Made**:
```typescript
// Data fetching (line 94-98)
GET  /detectors/{detectorId}                  // Detector metadata
GET  /detectors/{detectorId}/config           // Detector configuration ⚠️ NEEDS IMPLEMENTATION
GET  /deployments?detector_id={detectorId}    // Deployments ⚠️ NEEDS FILTER SUPPORT

// Model upload (line 130)
POST /detectors/{detectorId}/model?model_type=primary|oodd  // File upload ⚠️ NEEDS model_type PARAM

// Save configuration (line 148, 151)
PUT  /detectors/{detectorId}                  // Update name, description
PUT  /detectors/{detectorId}/config           // Update configuration ⚠️ NEEDS IMPLEMENTATION

// Redeploy (line 157)
POST /deployments/redeploy?detector_id={detectorId}  // ⚠️ NEEDS IMPLEMENTATION
```

---

#### 2. **DeploymentManagerPage.tsx** (`cloud/frontend/src/pages/DeploymentManagerPage.tsx`)
**Purpose**: 3-step wizard to deploy detectors to edge devices with camera assignment

**Key Features**:
- Column 1: Select detector (single select)
- Column 2: Select hubs/edge devices (multi-select with checkboxes)
- Column 3: Select cameras (multi-select, dynamically loaded based on selected hubs)
- Preview Config button: Shows YAML preview for first selected hub
- Deploy button: Creates deployments for all selected hub+camera combinations

**API Calls Made**:
```typescript
// Initial data (line 50-52)
GET  /detectors              // List detectors ✅ EXISTS
GET  /hubs                   // List hubs ✅ EXISTS

// Camera fetching (line 74-82)
GET  /hubs/{hubId}/cameras   // Fetch cameras for each selected hub ⚠️ NEEDS IMPLEMENTATION

// Preview config (line 126-128)
GET  /deployments/generate-config?hub_id={hubId}&detector_id={detectorId}  // ✅ EXISTS

// Deploy (line 153-161)
POST /deployments
Body: {
  hub_id: string,
  detector_id: string,
  cameras: [
    { name: string, url: string, sampling_interval: number }
  ]
}
// ⚠️ VERIFY backend accepts cameras array in payload
```

---

### Backend (Partial - Needs Verification)

**Known Existing Endpoints**:
```
✅ GET    /detectors                 # List all detectors
✅ POST   /detectors                 # Create detector
✅ GET    /detectors/{id}            # Get single detector
✅ POST   /detectors/{id}/model      # Upload model file
✅ GET    /hubs                      # List hubs
✅ POST   /hubs                      # Create hub
✅ GET    /queries                   # List queries
✅ POST   /queries                   # Submit query
✅ GET    /escalations               # List escalations
✅ POST   /escalations/{id}/resolve  # Resolve escalation
✅ POST   /queries/{id}/feedback     # Submit annotation
✅ GET    /settings/alerts           # Get alert config
✅ POST   /settings/alerts           # Update alert config
✅ GET    /deployments               # List deployments
✅ POST   /deployments               # Create deployment
✅ GET    /deployments/generate-config  # Preview YAML config
```

---

## 🔴 CRITICAL: WHAT NEEDS TO BE IMPLEMENTED

### Priority 1: Backend API Endpoints (Required for Frontend)

#### File: `cloud/backend/app/routers/detectors.py`

**1. GET /detectors/{detector_id}/config**
```python
@router.get("/{detector_id}/config")
async def get_detector_config(detector_id: str, db: Session = Depends(get_db)):
    """
    Fetch detector configuration (separate from detector metadata).
    Frontend expects this structure:
    {
      "mode": "BINARY" | "MULTICLASS" | "COUNTING" | "BOUNDING_BOX",
      "class_names": ["class1", "class2"],  # Optional
      "confidence_threshold": 0.85,          # 0.0 to 1.0
      "patience_time": 30.0,                 # Seconds
      "edge_inference_config": {
        "disable_cloud_escalation": false,
        "always_return_edge_prediction": false,
        "min_time_between_escalations": 2.0
      }
    }

    If no config exists yet, return defaults.
    """
    config = db.query(DetectorConfig).filter_by(detector_id=detector_id).first()

    if not config:
        # Return defaults
        return {
            "mode": "BINARY",
            "class_names": [],
            "confidence_threshold": 0.85,
            "patience_time": 30.0,
            "edge_inference_config": {
                "disable_cloud_escalation": False,
                "always_return_edge_prediction": False,
                "min_time_between_escalations": 2.0
            }
        }

    return {
        "mode": config.mode,
        "class_names": config.class_names or [],
        "confidence_threshold": config.confidence_threshold,
        "patience_time": config.patience_time,
        "edge_inference_config": config.edge_inference_config or {}
    }
```

**2. PUT /detectors/{detector_id}/config**
```python
from pydantic import BaseModel, Field

class EdgeInferenceConfigSchema(BaseModel):
    disable_cloud_escalation: bool = False
    always_return_edge_prediction: bool = False
    min_time_between_escalations: float = 2.0

class DetectorConfigUpdateSchema(BaseModel):
    mode: str = "BINARY"
    class_names: list[str] = []
    confidence_threshold: float = Field(0.85, ge=0.0, le=1.0)
    patience_time: float = Field(30.0, ge=0.0)
    edge_inference_config: EdgeInferenceConfigSchema = EdgeInferenceConfigSchema()

@router.put("/{detector_id}/config")
async def update_detector_config(
    detector_id: str,
    config: DetectorConfigUpdateSchema,
    db: Session = Depends(get_db)
):
    """
    Update detector configuration.
    Creates new record if doesn't exist.
    """
    existing = db.query(DetectorConfig).filter_by(detector_id=detector_id).first()

    if existing:
        # Update existing
        existing.mode = config.mode
        existing.class_names = config.class_names
        existing.confidence_threshold = config.confidence_threshold
        existing.patience_time = config.patience_time
        existing.edge_inference_config = config.edge_inference_config.dict()
        existing.updated_at = datetime.utcnow()
    else:
        # Create new
        new_config = DetectorConfig(
            detector_id=detector_id,
            mode=config.mode,
            class_names=config.class_names,
            confidence_threshold=config.confidence_threshold,
            patience_time=config.patience_time,
            edge_inference_config=config.edge_inference_config.dict()
        )
        db.add(new_config)

    db.commit()
    return {"status": "success", "message": "Configuration updated"}
```

**3. POST /detectors/{detector_id}/model (Update Existing)**
```python
# MODIFY EXISTING ENDPOINT to accept model_type query parameter

@router.post("/{detector_id}/model")
async def upload_detector_model(
    detector_id: str,
    model_type: str = Query("primary", regex="^(primary|oodd)$"),  # NEW PARAMETER
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload model file (.onnx or .buf) for detector.
    model_type: "primary" or "oodd"
    """
    detector = db.query(Detector).filter_by(id=detector_id).first()
    if not detector:
        raise HTTPException(status_code=404, detail="Detector not found")

    # Upload to Azure Blob Storage
    blob_path = f"models/{detector_id}/{model_type}/{file.filename}"
    upload_to_blob(file.file, blob_path)

    # Update detector record
    if model_type == "primary":
        detector.primary_model_blob_path = blob_path
    elif model_type == "oodd":
        detector.oodd_model_blob_path = blob_path

    db.commit()
    return {"status": "success", "blob_path": blob_path}
```

---

#### File: `cloud/backend/app/routers/hubs.py`

**4. GET /hubs/{hub_id}/cameras**
```python
@router.get("/{hub_id}/cameras")
async def get_hub_cameras(hub_id: str, db: Session = Depends(get_db)):
    """
    Fetch all cameras associated with a hub.
    Frontend expects:
    [
      {
        "id": "cam-001",
        "name": "Camera 1 - Entrance",
        "url": "rtsp://192.168.1.100:554/stream1",
        "hub_id": "hub-123",
        "status": "active"
      }
    ]
    """
    cameras = db.query(Camera).filter_by(hub_id=hub_id).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "url": c.url,
            "hub_id": c.hub_id,
            "status": c.status
        }
        for c in cameras
    ]
```

**5. POST /hubs/{hub_id}/cameras** (Optional - for manual registration)
```python
class CameraCreateSchema(BaseModel):
    name: str
    url: str  # RTSP URL

@router.post("/{hub_id}/cameras")
async def register_camera(
    hub_id: str,
    camera: CameraCreateSchema,
    db: Session = Depends(get_db)
):
    """Register a new camera to a hub"""
    new_camera = Camera(
        id=str(uuid.uuid4()),
        hub_id=hub_id,
        name=camera.name,
        url=camera.url,
        status="active",
        created_at=datetime.utcnow()
    )
    db.add(new_camera)
    db.commit()
    return new_camera
```

---

#### File: `cloud/backend/app/routers/deployments.py`

**6. GET /deployments (Update Existing - Add Filter)**
```python
@router.get("/")
async def list_deployments(
    detector_id: Optional[str] = None,  # NEW QUERY PARAMETER
    db: Session = Depends(get_db)
):
    """
    List deployments, optionally filtered by detector_id.
    Frontend expects:
    [
      {
        "id": "dep-001",
        "hub_id": "hub-123",
        "hub_name": "Factory Floor 1",  # Optional, from join
        "detector_id": "det-456",
        "status": "active",
        "deployed_at": "2026-01-10T12:00:00Z",
        "cameras": [...]  # Optional
      }
    ]
    """
    query = db.query(Deployment).join(Hub)

    if detector_id:
        query = query.filter(Deployment.detector_id == detector_id)

    deployments = query.all()

    return [
        {
            "id": d.id,
            "hub_id": d.hub_id,
            "hub_name": d.hub.name if d.hub else None,
            "detector_id": d.detector_id,
            "status": d.status,
            "deployed_at": d.deployed_at.isoformat(),
            "cameras": d.cameras  # JSONB field
        }
        for d in deployments
    ]
```

**7. POST /deployments (Update Existing - Accept Cameras)**
```python
class CameraDeploymentSchema(BaseModel):
    name: str
    url: str
    sampling_interval: float = 2.0

class DeploymentCreateSchema(BaseModel):
    hub_id: str
    detector_id: str
    cameras: list[CameraDeploymentSchema] = []  # NEW FIELD

@router.post("/")
async def create_deployment(
    deployment: DeploymentCreateSchema,
    db: Session = Depends(get_db)
):
    """
    Create a new deployment.
    Accepts cameras array to assign specific cameras to this deployment.
    """
    new_deployment = Deployment(
        id=str(uuid.uuid4()),
        hub_id=deployment.hub_id,
        detector_id=deployment.detector_id,
        status="active",
        deployed_at=datetime.utcnow(),
        cameras=[c.dict() for c in deployment.cameras]  # Store as JSONB
    )

    db.add(new_deployment)
    db.commit()

    # TODO: Trigger edge device update (webhook, Service Bus, or polling)
    send_deployment_notification(deployment.hub_id, deployment.detector_id)

    return new_deployment
```

**8. POST /deployments/redeploy**
```python
@router.post("/redeploy")
async def redeploy_detector(
    detector_id: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    Redeploy an existing detector to all its current hubs.
    Used when detector configuration changes (e.g., new model uploaded).
    Triggers edge devices to pull updated models/config.
    """
    deployments = db.query(Deployment).filter_by(detector_id=detector_id).all()

    if not deployments:
        raise HTTPException(status_code=404, detail="No deployments found for this detector")

    # Trigger edge device updates
    for dep in deployments:
        send_deployment_notification(dep.hub_id, detector_id)

    return {
        "status": "redeployment_triggered",
        "count": len(deployments),
        "message": f"Triggered redeployment to {len(deployments)} edge device(s)"
    }

# Helper function (implement based on your architecture)
def send_deployment_notification(hub_id: str, detector_id: str):
    """
    Notify edge device of deployment update.
    Options:
    1. Webhook to edge device
    2. Azure Service Bus message
    3. Edge device polls /detectors/{id} periodically (simplest)
    """
    # Example: Service Bus
    # service_bus_client.send_message({
    #     "event": "deployment_updated",
    #     "hub_id": hub_id,
    #     "detector_id": detector_id
    # })
    pass
```

---

### Priority 2: Database Schema Updates

#### File: `cloud/backend/app/models.py`

**Check if these models/columns exist. If not, add them:**

```python
from sqlalchemy import Column, String, Float, JSON, ARRAY, ForeignKey, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

# 1. Update Detector model
class Detector(Base):
    __tablename__ = "detectors"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    description = Column(String, nullable=True)

    # NEW COLUMNS (if not exist):
    primary_model_blob_path = Column(String(512), nullable=True)
    oodd_model_blob_path = Column(String(512), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# 2. NEW MODEL: DetectorConfig (if not exists)
class DetectorConfig(Base):
    __tablename__ = "detector_configs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    detector_id = Column(String, ForeignKey("detectors.id", ondelete="CASCADE"), nullable=False, unique=True)

    mode = Column(String(50), default="BINARY")  # BINARY, MULTICLASS, COUNTING, BOUNDING_BOX
    class_names = Column(ARRAY(String), nullable=True)  # For multiclass
    confidence_threshold = Column(Float, default=0.85)
    patience_time = Column(Float, default=30.0)
    edge_inference_config = Column(JSON, nullable=True)  # JSONB

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    detector = relationship("Detector", backref="config")


# 3. NEW MODEL: Camera (if not exists)
class Camera(Base):
    __tablename__ = "cameras"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    hub_id = Column(String, ForeignKey("hubs.id", ondelete="CASCADE"), nullable=False)

    name = Column(String(255), nullable=False)
    url = Column(String(512), nullable=False)  # RTSP URL
    status = Column(String(50), default="active")  # active, inactive, error

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    hub = relationship("Hub", backref="cameras")


# 4. Update Deployment model
class Deployment(Base):
    __tablename__ = "deployments"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    hub_id = Column(String, ForeignKey("hubs.id"), nullable=False)
    detector_id = Column(String, ForeignKey("detectors.id"), nullable=False)

    # NEW COLUMNS (if not exist):
    status = Column(String(50), default="active")  # active, inactive, pending
    cameras = Column(JSON, nullable=True)  # Array of {name, url, sampling_interval}

    deployed_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    hub = relationship("Hub", backref="deployments")
    detector = relationship("Detector", backref="deployments")
```

**Migration Command** (if using Alembic):
```bash
cd cloud/backend
alembic revision --autogenerate -m "Add detector configs and cameras"
alembic upgrade head
```

---

### Priority 3: Testing Requirements

#### Test Plan: Detector Configuration Flow

**1. Create Detector**
```bash
curl -X POST http://localhost:8000/detectors \
  -H "Content-Type: application/json" \
  -d '{
    "payload": {
      "name": "Test Vehicle Detector",
      "description": "Detects vehicles in parking lot"
    }
  }'

# Expected response:
{
  "id": "det-abc123",
  "name": "Test Vehicle Detector",
  "description": "Detects vehicles in parking lot",
  "primary_model_blob_path": null,
  "oodd_model_blob_path": null
}
```

**2. Upload Models**
```bash
# Primary model
curl -X POST http://localhost:8000/detectors/det-abc123/model?model_type=primary \
  -F "file=@vehicle_primary.onnx"

# OODD model
curl -X POST http://localhost:8000/detectors/det-abc123/model?model_type=oodd \
  -F "file=@vehicle_oodd.onnx"
```

**3. Update Configuration**
```bash
curl -X PUT http://localhost:8000/detectors/det-abc123/config \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "BINARY",
    "confidence_threshold": 0.75,
    "patience_time": 30.0,
    "edge_inference_config": {
      "disable_cloud_escalation": false,
      "min_time_between_escalations": 2.0
    }
  }'
```

**4. Get Configuration**
```bash
curl http://localhost:8000/detectors/det-abc123/config

# Expected response:
{
  "mode": "BINARY",
  "class_names": [],
  "confidence_threshold": 0.75,
  "patience_time": 30.0,
  "edge_inference_config": {
    "disable_cloud_escalation": false,
    "always_return_edge_prediction": false,
    "min_time_between_escalations": 2.0
  }
}
```

---

#### Test Plan: Deployment with Cameras Flow

**1. Create Hubs & Cameras** (Setup)
```bash
# Create hub
curl -X POST http://localhost:8000/hubs \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Factory Floor 1",
    "location": "Building A"
  }'

# Expected: {"id": "hub-123", "name": "Factory Floor 1", ...}

# Register cameras
curl -X POST http://localhost:8000/hubs/hub-123/cameras \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Camera 1 - Entrance",
    "url": "rtsp://192.168.1.100:554/stream1"
  }'

curl -X POST http://localhost:8000/hubs/hub-123/cameras \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Camera 2 - Exit",
    "url": "rtsp://192.168.1.101:554/stream1"
  }'
```

**2. List Cameras**
```bash
curl http://localhost:8000/hubs/hub-123/cameras

# Expected:
[
  {
    "id": "cam-001",
    "name": "Camera 1 - Entrance",
    "url": "rtsp://192.168.1.100:554/stream1",
    "hub_id": "hub-123",
    "status": "active"
  },
  {
    "id": "cam-002",
    "name": "Camera 2 - Exit",
    "url": "rtsp://192.168.1.101:554/stream1",
    "hub_id": "hub-123",
    "status": "active"
  }
]
```

**3. Create Deployment with Cameras**
```bash
curl -X POST http://localhost:8000/deployments \
  -H "Content-Type: application/json" \
  -d '{
    "hub_id": "hub-123",
    "detector_id": "det-abc123",
    "cameras": [
      {
        "name": "Camera 1 - Entrance",
        "url": "rtsp://192.168.1.100:554/stream1",
        "sampling_interval": 2.0
      },
      {
        "name": "Camera 2 - Exit",
        "url": "rtsp://192.168.1.101:554/stream1",
        "sampling_interval": 2.0
      }
    ]
  }'
```

**4. List Deployments by Detector**
```bash
curl "http://localhost:8000/deployments?detector_id=det-abc123"

# Expected:
[
  {
    "id": "dep-001",
    "hub_id": "hub-123",
    "hub_name": "Factory Floor 1",
    "detector_id": "det-abc123",
    "status": "active",
    "deployed_at": "2026-01-10T12:00:00Z",
    "cameras": [
      {"name": "Camera 1 - Entrance", "url": "rtsp://...", "sampling_interval": 2.0},
      {"name": "Camera 2 - Exit", "url": "rtsp://...", "sampling_interval": 2.0}
    ]
  }
]
```

**5. Redeploy Detector**
```bash
curl -X POST "http://localhost:8000/deployments/redeploy?detector_id=det-abc123"

# Expected:
{
  "status": "redeployment_triggered",
  "count": 1,
  "message": "Triggered redeployment to 1 edge device(s)"
}
```

---

#### Frontend Testing (Manual)

**Open**: http://localhost:3000

**Test Scenario 1: Detector Configuration**
1. Login with MSAL
2. Navigate to "Detectors" page
3. Click "Configure" on existing detector (or create new one first)
4. Verify all fields load correctly
5. Change confidence threshold using slider (should show live percentage)
6. Upload a test .onnx file for Primary model
7. Upload a test .onnx file for OODD model
8. Click "Save" → Should show success toast
9. Verify data persists after page reload

**Test Scenario 2: Deployment with Cameras**
1. Navigate to "Deployments" page
2. Select a detector from column 1
3. Select 1-2 hubs from column 2
4. Verify cameras appear in column 3 (with hub names)
5. Select 2-3 cameras
6. Click "Preview Config" → YAML should appear
7. Click "Deploy to X Devices" → Success toast
8. Navigate to DetectorConfigPage for that detector
9. Verify deployment appears in "Deployment Status" section

---

## 🛠️ IMPLEMENTATION CHECKLIST

Use this checklist to track progress:

### Backend Implementation
- [ ] Add `DetectorConfig` model to `models.py`
- [ ] Add `Camera` model to `models.py`
- [ ] Update `Detector` model with `primary_model_blob_path`, `oodd_model_blob_path`
- [ ] Update `Deployment` model with `status`, `cameras` columns
- [ ] Run database migration (Alembic)
- [ ] Implement `GET /detectors/{id}/config` in `detectors.py`
- [ ] Implement `PUT /detectors/{id}/config` in `detectors.py`
- [ ] Update `POST /detectors/{id}/model` to accept `model_type` parameter
- [ ] Implement `GET /hubs/{hub_id}/cameras` in `hubs.py`
- [ ] Implement `POST /hubs/{hub_id}/cameras` in `hubs.py` (optional)
- [ ] Update `GET /deployments` to accept `detector_id` filter in `deployments.py`
- [ ] Update `POST /deployments` to accept `cameras` array in payload
- [ ] Implement `POST /deployments/redeploy` in `deployments.py`

### Testing
- [ ] Test detector creation API
- [ ] Test model upload with `model_type=primary` and `model_type=oodd`
- [ ] Test detector config GET/PUT
- [ ] Test camera registration and listing
- [ ] Test deployment creation with cameras
- [ ] Test deployment filtering by detector_id
- [ ] Test redeployment trigger
- [ ] Manual frontend test: Detector configuration flow
- [ ] Manual frontend test: Deployment with cameras flow
- [ ] End-to-end test: Create detector → Upload models → Deploy to hub → Verify in database

### Deployment
- [ ] Build Docker images for backend, frontend, worker
- [ ] Update `docker-compose.yml` with environment variables
- [ ] Start services: `docker-compose up -d`
- [ ] Verify all containers healthy: `docker-compose ps`
- [ ] Check logs for errors: `docker-compose logs -f backend`
- [ ] Test frontend access: `http://localhost:3000`
- [ ] Test backend API: `http://localhost:8000/docs` (FastAPI Swagger UI)

---

## 📋 QUICK REFERENCE

### Key File Locations
```
Backend Router Files (where to add endpoints):
- cloud/backend/app/routers/detectors.py
- cloud/backend/app/routers/hubs.py
- cloud/backend/app/routers/deployments.py

Database Models:
- cloud/backend/app/models.py

Frontend Pages (already complete):
- cloud/frontend/src/pages/DetectorConfigPage.tsx
- cloud/frontend/src/pages/DeploymentManagerPage.tsx

Docker Compose:
- cloud/docker-compose.yml
```

### Environment Variables Needed
```bash
# Backend (.env)
DATABASE_URL=postgresql://user:pass@postgres:5432/intellioptics
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;...
AZURE_SERVICE_BUS_CONNECTION_STRING=Endpoint=sb://...
JWT_SECRET_KEY=your-secret-key

# Frontend (.env)
REACT_APP_API_URL=http://localhost:8000
REACT_APP_MSAL_CLIENT_ID=your-client-id
REACT_APP_MSAL_TENANT_ID=your-tenant-id
```

### Useful Commands
```bash
# Start cloud services
cd "C:\Dev\IntelliOptics 2.0\cloud"
docker-compose up -d

# View backend logs
docker-compose logs -f backend

# Restart backend after code changes
docker-compose restart backend

# Run database migration
docker-compose exec backend alembic upgrade head

# Access database directly
docker-compose exec postgres psql -U intellioptics

# Stop all services
docker-compose down
```

---

## 🎯 EXPECTED OUTCOME

After completing the above:

1. **Frontend** ✅ Already complete and production-ready
2. **Backend** ✅ All API endpoints implemented and tested
3. **Database** ✅ Schema supports detector configs, cameras, deployments
4. **Integration** ✅ Frontend ↔ Backend communication verified
5. **Deployment** ✅ Docker Compose runs all services successfully

**You will have a fully functional centralized web application** where users can:
- Create and configure detectors
- Upload Primary + OODD models
- Register edge hubs and cameras
- Deploy detectors to hubs with camera assignments
- Review and annotate escalated queries
- Manage alert settings and users

---

## 📞 SUPPORT RESOURCES

**Documentation Files**:
- `C:\Dev\IntelliOptics 2.0\docs\NEXT-STEPS.md` - Detailed roadmap
- `C:\Dev\IntelliOptics 2.0\docs\DETECTOR-CREATION-GUIDE.md` - User guide
- `C:\Dev\IntelliOptics 2.0\docs\CENTRALIZED-HUB-ENHANCEMENT-PLAN.md` - Architecture

**Architecture Diagrams**:
- Located in: `C:\Dev\IntelliOpticsDev\IntelliOptics-Edge-clean\images\`
- Key diagrams: K8s architecture, Happy path flow, Edge inference

**Existing Working Endpoints**:
- FastAPI Swagger UI: `http://localhost:8000/docs`
- Test any endpoint interactively

---

## 💡 TIPS FOR SUCCESS

1. **Start with Database Schema** - Ensure models exist before implementing endpoints
2. **Use FastAPI Swagger UI** - Test endpoints as you build them (`/docs`)
3. **Follow Existing Patterns** - Look at `settings.py` and `escalations.py` for reference
4. **Check Frontend First** - See exactly what data structure it expects
5. **Test Incrementally** - Don't wait until everything is done to test
6. **Use Type Hints** - Python type hints prevent bugs (Pydantic BaseModel for request/response)

---

**FINAL NOTE**: The frontend is production-quality and waiting for backend implementation. Focus on the 8 new/updated endpoints and database schema. Once those are complete, the entire system will be functional end-to-end.

**Estimated Total Time**: 6-8 hours for a developer familiar with FastAPI + SQLAlchemy.

Good luck! 🚀
