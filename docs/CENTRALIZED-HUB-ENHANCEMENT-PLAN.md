# IntelliOptics Centralized Hub - Enhancement Plan

## Vision

**Single centralized website for complete IntelliOptics management**:
- 🎯 **Detector Setup & Configuration** - Complete detector lifecycle management
- 📸 **Image Review & Annotation** - Human-in-the-loop labeling
- 🚀 **Deployment Management** - Push detectors to edge devices
- 🔔 **Alert Configuration** - Centralized alert setup
- 📊 **Analytics Dashboard** - System-wide metrics

---

## Current State vs. Target State

### Current State ✅
| Feature | Status | Notes |
|---------|--------|-------|
| Create Detector | ✅ Works | Basic name/description only |
| Upload Model | ✅ Works | Upload ONNX file to detector |
| List Detectors | ✅ Works | Table view of all detectors |
| Review Escalations | ✅ Works | View escalation queue |
| Annotate Images | ✅ Works | Provide labels and feedback |
| View Edge Devices | ✅ Works | Hub status dashboard |
| User Management | ✅ Works | Add/remove reviewers |

### Target State 🎯
| Feature | Status | Priority |
|---------|--------|----------|
| **Full Detector Configuration** | ❌ Needed | **HIGH** |
| **Deployment to Edge** | ❌ Needed | **HIGH** |
| **Alert Configuration UI** | ❌ Needed | **HIGH** |
| **Camera Stream Assignment** | ❌ Needed | MEDIUM |
| **Model Version Management** | ❌ Needed | MEDIUM |
| **Analytics Dashboard** | ❌ Needed | MEDIUM |
| **Detector Templates** | ❌ Needed | LOW |

---

## Enhancement 1: Full Detector Configuration UI

**Goal**: Complete detector setup in web UI (no manual YAML editing)

### New Page: Detector Configuration

**URL**: `/detectors/:id/configure`

### UI Components

#### Section 1: Basic Information
```
┌─────────────────────────────────────────────────┐
│ Detector Information                            │
├─────────────────────────────────────────────────┤
│ Name: [Vehicle Detection - Parking Lot       ] │
│ Description: [Detects vehicles in parking...  ] │
│ Status: ● Active  ○ Inactive                   │
└─────────────────────────────────────────────────┘
```

#### Section 2: Detection Configuration
```
┌─────────────────────────────────────────────────┐
│ Detection Settings                              │
├─────────────────────────────────────────────────┤
│ Mode: [▼ BINARY        ]                        │
│       - BINARY (Pass/Fail)                      │
│       - MULTICLASS (Classification)             │
│       - COUNTING (Count objects)                │
│       - BOUNDING_BOX (Object detection)         │
│                                                 │
│ Class Names:                                    │
│ [no_vehicle      ] [+ Add]                      │
│ [vehicle         ] [✕ Remove]                   │
│                                                 │
│ Confidence Threshold: [0.85    ] (0.0 - 1.0)   │
│ ├──────┼──────────────┼────────┤                │
│ 0.0   0.85          1.0                         │
│ Low    ↑            High                        │
│       Current                                   │
└─────────────────────────────────────────────────┘
```

#### Section 3: Edge Inference Profile
```
┌─────────────────────────────────────────────────┐
│ Edge Inference Configuration                    │
├─────────────────────────────────────────────────┤
│ Profile: ○ Default (Cloud escalation enabled)  │
│          ○ Offline (No cloud dependency)       │
│          ○ Aggressive (Frequent escalation)    │
│          ● Custom                               │
│                                                 │
│ ☑ Always return edge prediction                │
│ ☐ Disable cloud escalation                     │
│ Min time between escalations: [2.0  ] seconds  │
│                                                 │
│ Patience time: [30.0 ] seconds                 │
│ (Wait before escalating same area again)       │
└─────────────────────────────────────────────────┘
```

#### Section 4: Model Management
```
┌─────────────────────────────────────────────────┐
│ Model Files                                     │
├─────────────────────────────────────────────────┤
│ Primary Model:                                  │
│ ● vehicle_detector_v2.onnx (45.2 MB)          │
│   Uploaded: 2026-01-10 14:23                   │
│   Version: 2                                    │
│   [Upload New Version]                          │
│                                                 │
│ OODD Model (Ground Truth):                     │
│ ● oodd_vehicle_v1.onnx (12.3 MB)              │
│   Uploaded: 2026-01-08 09:15                   │
│   Version: 1                                    │
│   [Upload New Version]                          │
└─────────────────────────────────────────────────┘
```

#### Section 5: Deployment Status
```
┌─────────────────────────────────────────────────┐
│ Deployment Status                               │
├─────────────────────────────────────────────────┤
│ Deployed to 3 edge devices:                    │
│                                                 │
│ ✅ Factory Floor 1 - Line A                    │
│    Last sync: 2 minutes ago                    │
│    Model version: 2 (latest)                   │
│                                                 │
│ ✅ Factory Floor 2 - Line B                    │
│    Last sync: 5 minutes ago                    │
│    Model version: 2 (latest)                   │
│                                                 │
│ ⚠️  Warehouse - Loading Dock                   │
│    Last sync: 35 minutes ago                   │
│    Model version: 1 (outdated)                 │
│    [Force Update]                               │
│                                                 │
│ [Deploy to More Devices]                        │
└─────────────────────────────────────────────────┘
```

### Backend API Updates Needed

```python
# New endpoint: Update detector configuration
PUT /detectors/{detector_id}/config
{
  "mode": "BINARY",
  "class_names": ["no_vehicle", "vehicle"],
  "confidence_threshold": 0.85,
  "edge_inference_config": {
    "always_return_edge_prediction": false,
    "disable_cloud_escalation": false,
    "min_time_between_escalations": 2.0
  },
  "patience_time": 30.0
}

# New endpoint: Get detector configuration
GET /detectors/{detector_id}/config

# New endpoint: Deploy detector to edge device
POST /detectors/{detector_id}/deploy
{
  "hub_ids": ["hub_abc123", "hub_def456"]
}
```

---

## Enhancement 2: Deployment Management

**Goal**: Push detector configurations to edge devices from web UI

### New Page: Deployment Manager

**URL**: `/deployments`

### UI Layout

```
┌─────────────────────────────────────────────────────────┐
│ Deployment Manager                                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│ [Detectors ▼] [Edge Devices ▼] [Cameras ▼]            │
│                                                         │
│ ┌─────────────────┐  ┌──────────────┐  ┌────────────┐ │
│ │ Detectors       │  │ Edge Devices │  │ Assignments│ │
│ ├─────────────────┤  ├──────────────┤  ├────────────┤ │
│ │ ☑ Vehicle Det   │→ │ ☑ Floor 1-A  │→ │ Camera 1   │ │
│ │ ☐ Defect Class  │  │ ☐ Floor 1-B  │  │ Camera 2   │ │
│ │ ☐ People Count  │  │ ☐ Floor 2-A  │  │ Camera 3   │ │
│ └─────────────────┘  └──────────────┘  └────────────┘ │
│                                                         │
│ [Preview Configuration] [Deploy Now]                    │
└─────────────────────────────────────────────────────────┘
```

### Workflow

1. **Select Detector** - Choose which detector to deploy
2. **Select Edge Devices** - Pick target edge devices (hubs)
3. **Assign Cameras** - Map RTSP cameras to detector
4. **Preview Configuration** - Show generated edge-config.yaml
5. **Deploy** - Push configuration to edge devices

### Generated Configuration Preview

```yaml
# Generated edge-config.yaml for: Factory Floor 1 - Line A

detectors:
  det_vehicle_parking:
    detector_id: 5b69c510-f84a-4a3c-b9bf-aa73ff368401
    name: "Vehicle Detection - Parking Lot"
    edge_inference_config: default
    confidence_threshold: 0.85
    patience_time: 30.0
    mode: BINARY
    class_names: ["no_vehicle", "vehicle"]

streams:
  camera_parking_lot_1:
    name: "Parking Lot - East Entrance"
    detector_id: det_vehicle_parking
    url: "rtsp://192.168.1.100:554/stream1"
    sampling_interval_seconds: 2.0
    camera_health:
      enabled: true
      health_check_interval_seconds: 10.0
```

**Actions**:
- [Download YAML] - Download configuration file
- [Deploy to Edge] - Push via API to edge device
- [Schedule Deploy] - Deploy at specific time

### Backend API Updates Needed

```python
# Generate edge config for specific hub
GET /deployments/generate-config?hub_id={hub_id}&detector_id={detector_id}

# Deploy configuration to edge device
POST /deployments/deploy
{
  "hub_id": "hub_abc123",
  "detector_id": "det_vehicle",
  "cameras": [
    {
      "name": "Camera 1",
      "url": "rtsp://192.168.1.100/stream",
      "sampling_interval": 2.0
    }
  ]
}

# Get deployment status
GET /deployments/status?hub_id={hub_id}
```

---

## Enhancement 3: Alert Configuration UI

**Goal**: Configure SendGrid email alerts and thresholds from web UI

### New Page: Alert Settings

**URL**: `/settings/alerts`

### UI Layout

#### Section 1: Email Configuration

```
┌─────────────────────────────────────────────────┐
│ Email Alert Configuration                       │
├─────────────────────────────────────────────────┤
│ Provider: ● SendGrid  ○ SMTP  ○ Webhook         │
│                                                 │
│ SendGrid API Key:                               │
│ [SG.****************************] [Verify]      │
│ ✅ API key verified                             │
│                                                 │
│ From Email:                                     │
│ [alerts@intellioptics.com                    ]  │
│                                                 │
│ From Name:                                      │
│ [IntelliOptics Alert System                  ]  │
└─────────────────────────────────────────────────┘
```

#### Section 2: Alert Recipients

```
┌─────────────────────────────────────────────────┐
│ Alert Recipients                                │
├─────────────────────────────────────────────────┤
│ Reviewer Email List:                            │
│                                                 │
│ ● reviewer1@company.com     [✕ Remove]          │
│ ● reviewer2@company.com     [✕ Remove]          │
│ ● qa-team@company.com       [✕ Remove]          │
│                                                 │
│ [Add Recipient]                                 │
│ [Import from CSV]                               │
└─────────────────────────────────────────────────┘
```

#### Section 3: Alert Triggers

```
┌─────────────────────────────────────────────────┐
│ Alert Triggers                                  │
├─────────────────────────────────────────────────┤
│ When to send alerts:                            │
│                                                 │
│ ☑ Low Confidence Detection                      │
│   Threshold: [0.80    ] (send if < 0.80)       │
│                                                 │
│ ☑ Out-of-Domain Detection (OODD)                │
│   OODD Threshold: [0.50    ] (send if < 0.50)  │
│                                                 │
│ ☑ Camera Health Critical                        │
│   ☑ Obstruction                                 │
│   ☑ Camera Movement                             │
│   ☐ Focus Change                                │
│                                                 │
│ ☑ Edge Device Offline                           │
│   No heartbeat for: [5    ] minutes            │
└─────────────────────────────────────────────────┘
```

#### Section 4: Batching & Rate Limiting

```
┌─────────────────────────────────────────────────┐
│ Batching & Rate Limiting                        │
├─────────────────────────────────────────────────┤
│ Batching Strategy:                              │
│ ● Send batch every [10  ] escalations           │
│ ● Send batch every [15  ] minutes               │
│ ○ Send immediately (no batching)                │
│                                                 │
│ Rate Limiting:                                  │
│ Max escalations per detector per hour:          │
│ [100    ] alerts/hour                           │
│                                                 │
│ Quiet Hours:                                    │
│ ☐ Enable quiet hours                            │
│   From: [22:00] To: [06:00]                     │
│   Queue alerts during quiet hours               │
└─────────────────────────────────────────────────┘
```

#### Section 5: Alert Templates

```
┌─────────────────────────────────────────────────┐
│ Email Templates                                 │
├─────────────────────────────────────────────────┤
│ Low Confidence Alert:                           │
│ Subject: [🔔 IntelliOptics Alert: Review Req...│
│                                                 │
│ [Edit Template]  [Preview]  [Send Test Email]  │
│                                                 │
│ Camera Health Alert:                            │
│ Subject: [⚠️ Camera Health Warning: {camera...│
│                                                 │
│ [Edit Template]  [Preview]  [Send Test Email]  │
└─────────────────────────────────────────────────┘
```

### Backend API Updates Needed

```python
# Get alert configuration
GET /settings/alerts

# Update alert configuration
PUT /settings/alerts
{
  "sendgrid_api_key": "SG.xxx",
  "from_email": "alerts@intellioptics.com",
  "recipients": ["reviewer1@company.com"],
  "triggers": {
    "low_confidence": true,
    "confidence_threshold": 0.80,
    "oodd_threshold": 0.50,
    "camera_health_critical": true,
    "edge_device_offline": true
  },
  "batching": {
    "strategy": "count",
    "batch_size": 10,
    "batch_interval_minutes": 15
  },
  "rate_limiting": {
    "max_per_hour": 100
  }
}

# Test send alert
POST /settings/alerts/test
{
  "recipient": "test@example.com",
  "template": "low_confidence"
}
```

---

## Enhancement 4: Camera Stream Management

**Goal**: Configure RTSP cameras and assign to detectors from web UI

### New Page: Camera Streams

**URL**: `/cameras`

### UI Layout

```
┌─────────────────────────────────────────────────────────┐
│ Camera Stream Management                                │
├─────────────────────────────────────────────────────────┤
│ [+ Add Camera Stream]                                   │
│                                                         │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Camera: Parking Lot - East Entrance                 │ │
│ ├─────────────────────────────────────────────────────┤ │
│ │ Hub: Factory Floor 1 - Line A                       │ │
│ │ RTSP URL: rtsp://192.168.1.100:554/stream1         │ │
│ │ Detector: Vehicle Detection - Parking Lot           │ │
│ │ Status: ● Online  Last frame: 2 seconds ago         │ │
│ │ Sampling: Every 2.0 seconds                         │ │
│ │                                                     │ │
│ │ Camera Health: ✅ Enabled (Check every 10s)         │ │
│ │ Last health: HEALTHY (score: 95.0)                 │ │
│ │                                                     │ │
│ │ [Edit] [Test Connection] [View Live]                │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                         │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Camera: Weld Station - Line 3                       │ │
│ ├─────────────────────────────────────────────────────┤ │
│ │ Hub: Factory Floor 3 - Line A                       │ │
│ │ RTSP URL: rtsp://192.168.10.50:554/stream1         │ │
│ │ Detector: Weld Quality Inspector                    │ │
│ │ Status: ⚠️ Warning  Last frame: 35 seconds ago      │ │
│ │ Sampling: Every 3.0 seconds                         │ │
│ │                                                     │ │
│ │ Camera Health: ✅ Enabled (Check every 10s)         │ │
│ │ Last health: WARNING (blur detected)                │ │
│ │                                                     │ │
│ │ [Edit] [Test Connection] [View Live]                │ │
│ └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### Add/Edit Camera Form

```
┌─────────────────────────────────────────────────┐
│ Add Camera Stream                               │
├─────────────────────────────────────────────────┤
│ Camera Name:                                    │
│ [Parking Lot - East Entrance                 ]  │
│                                                 │
│ Edge Device (Hub):                              │
│ [▼ Factory Floor 1 - Line A                  ]  │
│                                                 │
│ RTSP URL:                                       │
│ [rtsp://192.168.1.100:554/stream1            ]  │
│ [Test Connection]                               │
│                                                 │
│ Credentials (optional):                         │
│ Username: [admin        ]                       │
│ Password: [************]                        │
│                                                 │
│ Detector:                                       │
│ [▼ Vehicle Detection - Parking Lot           ]  │
│                                                 │
│ Sampling Interval: [2.0  ] seconds              │
│ Reconnect Delay:   [5.0  ] seconds              │
│                                                 │
│ Camera Health Monitoring:                       │
│ ☑ Enable health monitoring                      │
│ Health check interval: [10.0 ] seconds          │
│ ☑ Skip unhealthy frames                         │
│ ☑ Enable tampering detection                    │
│                                                 │
│ [Cancel] [Save & Deploy]                        │
└─────────────────────────────────────────────────┘
```

---

## Enhancement 5: Analytics Dashboard

**Goal**: System-wide metrics and insights

### New Page: Analytics Dashboard

**URL**: `/analytics`

### UI Layout

#### Section 1: System Overview (Cards)

```
┌─────────────────────────────────────────────────────────┐
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐       │
│ │ Detectors   │ │ Edge Devices│ │ Cameras     │       │
│ │     12      │ │      8      │ │     24      │       │
│ │ +2 this mo  │ │ ✅ All online│ │ ⚠️ 1 offline│       │
│ └─────────────┘ └─────────────┘ └─────────────┘       │
│                                                         │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐       │
│ │ Queries/Day │ │ Escalations │ │ Accuracy    │       │
│ │   45,230    │ │    4,523    │ │   92.3%     │       │
│ │ +12% ↑      │ │  10% of tot │ │ +2.1% ↑     │       │
│ └─────────────┘ └─────────────┘ └─────────────┘       │
└─────────────────────────────────────────────────────────┘
```

#### Section 2: Inference Trends (Chart)

```
┌─────────────────────────────────────────────────────────┐
│ Inference Volume (Last 30 Days)                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│     │        ╱╲                                         │
│ 60k │      ╱   ╲      ╱╲                               │
│     │    ╱       ╲  ╱    ╲                             │
│ 40k │  ╱           ╲╱       ╲                           │
│     │╱                        ╲                         │
│ 20k │                           ╲___                    │
│     └───────────────────────────────────────           │
│     Jan 1    Jan 10    Jan 20    Jan 30                │
│                                                         │
│ ━━ Total Queries  ━━ Edge Results  ━━ Escalated       │
└─────────────────────────────────────────────────────────┘
```

#### Section 3: Detector Performance

```
┌─────────────────────────────────────────────────────────┐
│ Detector Performance                                    │
├─────────────────────────────────────────────────────────┤
│ Detector              │ Queries │ Escalated │ Accuracy  │
│───────────────────────┼─────────┼───────────┼───────────│
│ Vehicle Detection     │  12,450 │  1,245    │  95.2%    │
│ Weld Quality          │   8,920 │    892    │  93.1%    │
│ Defect Classifier     │   6,780 │  1,356    │  88.7%    │
│ People Counter        │   4,560 │    228    │  97.3%    │
└─────────────────────────────────────────────────────────┘
```

---

## Implementation Roadmap

### Phase 1: Core Enhancements (2-3 weeks)
**Priority: HIGH**

✅ **Week 1**: Full Detector Configuration UI
- Create detector config page
- Add mode selection, class names
- Confidence threshold slider
- Edge inference profile selector
- Save configuration endpoint

✅ **Week 2**: Alert Configuration UI
- Alert settings page
- SendGrid integration
- Recipient management
- Trigger configuration
- Test email functionality

✅ **Week 3**: Deployment Manager
- Deployment workflow UI
- Configuration generator
- Deploy to edge API
- Deployment status tracking

### Phase 2: Camera & Analytics (2 weeks)
**Priority: MEDIUM**

✅ **Week 4**: Camera Stream Management
- Camera list/add/edit UI
- RTSP connection testing
- Health monitoring dashboard
- Live preview (if feasible)

✅ **Week 5**: Analytics Dashboard
- System overview cards
- Inference trend charts
- Detector performance tables
- Export reports

### Phase 3: Advanced Features (1-2 weeks)
**Priority: LOW**

- Detector templates
- Scheduled deployments
- A/B testing (multiple models)
- Advanced alerting (webhooks, Slack, Teams)

---

## Technical Requirements

### Frontend (React)

**New Dependencies**:
```json
{
  "recharts": "^2.5.0",          // For charts/graphs
  "react-hook-form": "^7.43.0",  // Form management
  "zod": "^3.20.0",              // Schema validation
  "react-toastify": "^9.1.0"     // Toast notifications
}
```

**New Pages**:
1. `src/pages/DetectorConfigPage.tsx`
2. `src/pages/DeploymentManagerPage.tsx`
3. `src/pages/AlertSettingsPage.tsx`
4. `src/pages/CameraStreamsPage.tsx`
5. `src/pages/AnalyticsDashboardPage.tsx`

**Shared Components**:
1. `src/components/DetectorForm.tsx`
2. `src/components/CameraForm.tsx`
3. `src/components/AlertForm.tsx`
4. `src/components/DeploymentWizard.tsx`
5. `src/components/ConfigPreview.tsx`

### Backend (FastAPI)

**New Endpoints**:
```python
# Detector configuration
GET    /detectors/{id}/config
PUT    /detectors/{id}/config
POST   /detectors/{id}/deploy

# Deployments
GET    /deployments/
POST   /deployments/deploy
GET    /deployments/status

# Alert settings
GET    /settings/alerts
PUT    /settings/alerts
POST   /settings/alerts/test

# Camera streams
GET    /cameras/
POST   /cameras/
PUT    /cameras/{id}
DELETE /cameras/{id}
POST   /cameras/{id}/test-connection

# Analytics
GET    /analytics/overview
GET    /analytics/trends
GET    /analytics/detector-performance
```

**New Database Tables**:
```sql
-- Detector configurations
CREATE TABLE detector_configs (
    detector_id UUID PRIMARY KEY,
    mode VARCHAR(50),
    class_names JSONB,
    confidence_threshold FLOAT,
    edge_inference_config JSONB,
    patience_time FLOAT
);

-- Camera streams
CREATE TABLE camera_streams (
    id UUID PRIMARY KEY,
    hub_id UUID REFERENCES hubs(id),
    detector_id UUID REFERENCES detectors(id),
    name VARCHAR(255),
    rtsp_url TEXT,
    credentials JSONB,
    sampling_interval FLOAT,
    health_config JSONB,
    created_at TIMESTAMP
);

-- Alert settings
CREATE TABLE alert_settings (
    id UUID PRIMARY KEY,
    sendgrid_api_key TEXT,
    from_email VARCHAR(255),
    recipients JSONB,
    triggers JSONB,
    batching JSONB,
    rate_limiting JSONB
);

-- Deployments
CREATE TABLE deployments (
    id UUID PRIMARY KEY,
    detector_id UUID,
    hub_id UUID,
    config JSONB,
    deployed_at TIMESTAMP,
    status VARCHAR(50)
);
```

---

## Next Steps

**Option 1**: I can implement this enhancement plan for you
- Start with Phase 1 (Core Enhancements)
- Build UI components and backend endpoints
- Test and deploy

**Option 2**: Use this as a specification document
- Share with your development team
- Implement according to roadmap
- I can assist with specific components

Which approach would you prefer?
