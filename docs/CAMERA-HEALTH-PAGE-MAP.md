# Camera Health Inspection Page - Feature Map

## Overview
A dedicated page for monitoring the health and status of RTSP cameras across all edge hubs in the IntelliOptics system.

## Current System Analysis

### Existing Infrastructure ✅

**Database Models** (`models.py`):
```python
class Hub:
    id: UUID
    name: str
    status: str  # online/offline/unknown
    last_ping: datetime
    location: str
    cameras_list: relationship → Camera

class Camera:
    id: UUID
    hub_id: UUID (FK → hubs.id)
    name: str
    url: str  # RTSP URL
    status: str  # active (currently just a placeholder)
    created_at: datetime
```

**Existing Backend Endpoints**:
- `GET /hubs` - List all hubs
- `GET /hubs/{hub_id}/cameras` - Get cameras for a specific hub
- `POST /hubs/{hub_id}/cameras` - Create new camera

**Existing Frontend Pages**:
- `HubStatusPage.tsx` - Shows hub online/offline status
- No camera-specific health monitoring page yet

---

## Feature Requirements

### 1. Camera Health Metrics (What to Monitor)

#### Connection Health
- **RTSP Stream Status**: Can we connect to the camera?
  - ✅ Connected
  - ❌ Connection Failed
  - ⏳ Connecting...
  - 🔄 Reconnecting...

#### Stream Quality Metrics
- **Frame Rate**: Actual FPS vs. Expected FPS
  - Expected: 30 FPS, Actual: 28 FPS → ✅ Healthy
  - Expected: 30 FPS, Actual: 5 FPS → ⚠️ Degraded
  - Expected: 30 FPS, Actual: 0 FPS → ❌ Failed

- **Resolution**: Current stream resolution
  - 1920x1080, 1280x720, etc.

- **Bitrate**: Stream bandwidth usage
  - Normal: 2-5 Mbps for 1080p
  - Low: <1 Mbps (quality issues likely)

#### Image Quality Indicators
- **Brightness**: Average pixel intensity (detect if camera lens is covered/blocked)
  - Too Dark: <20% → ⚠️ "Camera may be obstructed"
  - Too Bright: >80% → ⚠️ "Overexposed or facing light source"

- **Motion Detection**: Is there movement in the scene?
  - No motion for 1+ hour in parking lot → ⚠️ "Camera may be frozen"

- **Blur Detection**: Sharpness score
  - High blur → ⚠️ "Focus issue or dirty lens"

#### Operational Metrics
- **Uptime**: % of time camera has been reachable
  - Last 24 hours: 99.5%
  - Last 7 days: 98.2%

- **Last Successful Frame**: When did we last receive a valid frame?
  - "2 minutes ago" → ✅ Healthy
  - "3 hours ago" → ❌ Offline

- **Error Count**: Recent errors (connection timeouts, decode failures, etc.)
  - 0-5 errors/hour → ✅ Healthy
  - 10+ errors/hour → ⚠️ Unstable

#### Network Health
- **Latency**: Time to fetch a frame
  - <100ms → ✅ Excellent
  - 100-500ms → ⚠️ Acceptable
  - >500ms → ❌ Poor (network congestion)

- **Packet Loss**: % of dropped frames
  - <1% → ✅ Healthy
  - 1-5% → ⚠️ Degraded
  - >5% → ❌ Severe Issues

---

## Page Design

### Layout: Camera Health Dashboard

```
┌────────────────────────────────────────────────────────────────┐
│  🎥 Camera Health Inspection                    [Refresh] [⚙️] │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  📊 System Overview                                            │
│  ┌──────────────┬──────────────┬──────────────┬─────────────┐ │
│  │  Total       │  Healthy     │  Warning     │  Offline    │ │
│  │  Cameras     │              │              │             │ │
│  │              │              │              │             │ │
│  │     24       │  18 (75%)    │  4 (17%)     │  2 (8%)     │ │
│  │              │  🟢          │  🟡          │  🔴         │ │
│  └──────────────┴──────────────┴──────────────┴─────────────┘ │
│                                                                │
│  🏢 Group By: [All Hubs ▼]  Filter: [All Statuses ▼]         │
│  Search: [🔍 Search cameras...]                               │
│                                                                │
│  ┌────────────────────────────────────────────────────────────┐│
│  │ Hub: Parking Lot A (Edge Device #1)          Status: 🟢   ││
│  ├────────────────────────────────────────────────────────────┤│
│  │                                                            ││
│  │ Camera 1: North Entrance                                  ││
│  │ ┌──────────────────┬──────────────────┬──────────────────┐││
│  │ │ 🟢 Connected     │ Frame Rate       │ Last Frame       │││
│  │ │ RTSP: rtsp://... │ 28.5 / 30 FPS    │ 2 sec ago        │││
│  │ │                  │                  │                  │││
│  │ │ Resolution       │ Uptime (24h)     │ Error Count      │││
│  │ │ 1920x1080        │ 99.8%            │ 2 errors/hr      │││
│  │ │                  │                  │                  │││
│  │ │ [View Live Feed] │ [Test Stream]    │ [Health Logs]    │││
│  │ └──────────────────┴──────────────────┴──────────────────┘││
│  │                                                            ││
│  │ Camera 2: South Entrance                                  ││
│  │ ┌──────────────────┬──────────────────┬──────────────────┐││
│  │ │ 🟡 Degraded      │ Frame Rate       │ Last Frame       │││
│  │ │ RTSP: rtsp://... │ 5.2 / 30 FPS ⚠️  │ 15 sec ago       │││
│  │ │                  │                  │                  │││
│  │ │ Resolution       │ Uptime (24h)     │ Error Count      │││
│  │ │ 1280x720         │ 87.3% ⚠️         │ 45 errors/hr ❌   │││
│  │ │                  │                  │                  │││
│  │ │ ⚠️ Issues: Low FPS, High packet loss, Frequent timeouts│││
│  │ │ [View Live Feed] │ [Restart Stream] │ [Health Logs]    │││
│  │ └──────────────────┴──────────────────┴──────────────────┘││
│  │                                                            ││
│  │ Camera 3: Loading Bay                                     ││
│  │ ┌──────────────────┬──────────────────┬──────────────────┐││
│  │ │ 🔴 Offline       │ Frame Rate       │ Last Frame       │││
│  │ │ RTSP: rtsp://... │ 0 FPS            │ 2 hours ago ❌    │││
│  │ │                  │                  │                  │││
│  │ │ ❌ Connection Error: RTSP timeout (Connection refused) │││
│  │ │ [Retry Connection] │ [Edit Config]  │ [Health Logs]    │││
│  │ └──────────────────┴──────────────────┴──────────────────┘││
│  └────────────────────────────────────────────────────────────┘│
│                                                                │
│  ┌────────────────────────────────────────────────────────────┐│
│  │ Hub: Warehouse B (Edge Device #2)            Status: 🟢   ││
│  ├────────────────────────────────────────────────────────────┤│
│  │  ... (repeat camera cards)                                ││
│  └────────────────────────────────────────────────────────────┘│
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### UI Components Breakdown

#### 1. Summary Stats Cards (Top Row)
- Total cameras across all hubs
- Healthy count (green)
- Warning count (yellow)
- Offline count (red)

#### 2. Filters & Search Bar
- Group By: Dropdown to filter by hub
- Filter: Show only healthy/warning/offline
- Search: Find camera by name or RTSP URL

#### 3. Camera Cards (Main Content)
Each camera card shows:
- **Status Badge**: 🟢 Healthy | 🟡 Warning | 🔴 Offline
- **RTSP URL**: Truncated with tooltip
- **Metrics Grid**:
  - Connection Status
  - Frame Rate (current/expected)
  - Last Frame timestamp
  - Resolution
  - Uptime % (24h)
  - Error count (last hour)
- **Issue Alerts**: If degraded/offline, show specific problems
- **Action Buttons**:
  - View Live Feed (open modal with live stream)
  - Test Stream (run connectivity test)
  - Restart Stream (force reconnect)
  - Health Logs (detailed event log)
  - Edit Config (modify RTSP URL, credentials)

---

## Database Schema Changes

### Add `camera_health` Table
```sql
CREATE TABLE camera_health (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    camera_id UUID NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Connection
    status VARCHAR(32) NOT NULL,  -- connected, degraded, offline
    connection_error TEXT,

    -- Stream Quality
    fps FLOAT,
    expected_fps FLOAT DEFAULT 30.0,
    resolution VARCHAR(32),  -- "1920x1080"
    bitrate_kbps INT,

    -- Image Quality
    avg_brightness FLOAT,  -- 0.0 to 1.0
    sharpness_score FLOAT,  -- 0.0 to 1.0 (higher = sharper)
    motion_detected BOOLEAN,

    -- Operational
    last_frame_at TIMESTAMP,
    uptime_24h FLOAT,  -- Percentage
    error_count_1h INT,

    -- Network
    latency_ms INT,
    packet_loss_pct FLOAT,

    -- Metadata
    created_at TIMESTAMP DEFAULT NOW()
);

-- Index for recent health records
CREATE INDEX idx_camera_health_camera_timestamp
ON camera_health(camera_id, timestamp DESC);

-- Retention: Keep only last 30 days of health records
-- (Add cron job to delete old records)
```

### Update `cameras` Table
```sql
ALTER TABLE cameras
ADD COLUMN last_health_check TIMESTAMP,
ADD COLUMN current_status VARCHAR(32) DEFAULT 'unknown',
ADD COLUMN health_score FLOAT;  -- 0-100, aggregate health metric
```

---

## Backend API Changes

### New Endpoints

#### 1. Get Camera Health Summary
```http
GET /cameras/health/summary
Response:
{
  "total_cameras": 24,
  "healthy": 18,
  "warning": 4,
  "offline": 2,
  "last_updated": "2026-01-13T16:30:00Z"
}
```

#### 2. Get All Cameras with Health
```http
GET /cameras?include_health=true&hub_id={hub_id}
Response:
[
  {
    "id": "uuid",
    "name": "North Entrance",
    "url": "rtsp://...",
    "hub_id": "uuid",
    "hub_name": "Parking Lot A",
    "health": {
      "status": "connected",
      "fps": 28.5,
      "expected_fps": 30.0,
      "resolution": "1920x1080",
      "last_frame_at": "2026-01-13T16:29:58Z",
      "uptime_24h": 99.8,
      "error_count_1h": 2,
      "latency_ms": 45,
      "health_score": 95
    }
  },
  {
    "id": "uuid",
    "name": "South Entrance",
    "url": "rtsp://...",
    "hub_id": "uuid",
    "hub_name": "Parking Lot A",
    "health": {
      "status": "degraded",
      "fps": 5.2,
      "expected_fps": 30.0,
      "resolution": "1280x720",
      "last_frame_at": "2026-01-13T16:29:45Z",
      "uptime_24h": 87.3,
      "error_count_1h": 45,
      "latency_ms": 450,
      "health_score": 52,
      "issues": ["Low FPS", "High packet loss", "Frequent timeouts"]
    }
  }
]
```

#### 3. Test Camera Stream
```http
POST /cameras/{camera_id}/test
Response:
{
  "success": true,
  "latency_ms": 89,
  "frame_received": true,
  "resolution": "1920x1080",
  "fps_sample": 29.8,
  "message": "Stream test successful"
}
```

#### 4. Restart Camera Stream
```http
POST /cameras/{camera_id}/restart
Response:
{
  "success": true,
  "message": "Stream restart initiated on edge hub"
}
```

#### 5. Get Camera Health History
```http
GET /cameras/{camera_id}/health/history?hours=24
Response:
{
  "camera_id": "uuid",
  "data_points": [
    {
      "timestamp": "2026-01-13T16:00:00Z",
      "status": "connected",
      "fps": 29.1,
      "latency_ms": 67,
      "health_score": 94
    },
    // ... more data points
  ]
}
```

---

## Edge Hub Changes (Worker/Inference Service)

### Add Camera Health Monitor Service

**Location**: `C:\Dev\IntelliOptics 2.0\cloud\worker\camera_health_monitor.py`

**Functionality**:
1. **Periodic Health Checks** (every 30 seconds per camera):
   - Connect to RTSP stream
   - Measure FPS, latency, resolution
   - Analyze frame quality (brightness, sharpness)
   - Detect motion
   - Count errors

2. **Send Health Data to Cloud**:
   - POST health metrics to cloud backend every 60 seconds
   - Batch multiple camera health records in one request

3. **Local Alerts**:
   - If camera goes offline, log error
   - Attempt auto-reconnect (3 retries, exponential backoff)

**Example Implementation**:
```python
import cv2
import time
import numpy as np
import requests
from threading import Thread

class CameraHealthMonitor:
    def __init__(self, camera_id, rtsp_url, expected_fps=30.0):
        self.camera_id = camera_id
        self.rtsp_url = rtsp_url
        self.expected_fps = expected_fps
        self.health_data = {}

    def run_health_check(self):
        try:
            cap = cv2.VideoCapture(self.rtsp_url)

            # Check connection
            if not cap.isOpened():
                return {
                    "status": "offline",
                    "connection_error": "Failed to open RTSP stream"
                }

            # Measure FPS
            start_time = time.time()
            frame_count = 0
            for _ in range(30):  # Sample 30 frames
                ret, frame = cap.read()
                if ret:
                    frame_count += 1
                    # Analyze last frame
                    if frame_count == 30:
                        brightness = np.mean(frame) / 255.0
                        sharpness = self.calculate_sharpness(frame)

            elapsed = time.time() - start_time
            actual_fps = frame_count / elapsed

            cap.release()

            # Determine status
            status = "connected"
            if actual_fps < self.expected_fps * 0.5:
                status = "degraded"

            return {
                "status": status,
                "fps": actual_fps,
                "expected_fps": self.expected_fps,
                "avg_brightness": brightness,
                "sharpness_score": sharpness,
                "last_frame_at": datetime.utcnow()
            }

        except Exception as e:
            return {
                "status": "offline",
                "connection_error": str(e)
            }

    def calculate_sharpness(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        return min(laplacian_var / 1000.0, 1.0)  # Normalize to 0-1
```

---

## Frontend Implementation

### New Page: `CameraHealthPage.tsx`

**Location**: `C:\Dev\IntelliOptics 2.0\cloud\frontend\src\pages\CameraHealthPage.tsx`

**Key Features**:
- Auto-refresh every 30 seconds
- Real-time status updates (WebSocket optional)
- Filter by hub, status
- Search cameras
- Click camera card to expand details
- Health history chart (last 24 hours)

**Component Structure**:
```typescript
CameraHealthPage
├── SummaryStatsCards (total, healthy, warning, offline)
├── FilterBar (hub filter, status filter, search)
└── CameraList
    └── CameraCard (per camera)
        ├── StatusBadge
        ├── MetricsGrid
        ├── IssueAlerts
        └── ActionButtons
            ├── ViewLiveFeedModal
            ├── TestStreamButton
            ├── RestartStreamButton
            └── HealthLogsModal
```

---

## Implementation Phases

### Phase 1: Basic Health Monitoring (MVP)
**Goal**: Show camera connection status and basic metrics

1. ✅ Database: Add `camera_health` table
2. ✅ Backend:
   - `GET /cameras/health/summary`
   - `GET /cameras?include_health=true`
3. ✅ Frontend:
   - Create `CameraHealthPage.tsx`
   - Show connection status (🟢/🔴)
   - Display FPS, last frame timestamp

**Deliverable**: Basic health dashboard showing which cameras are online/offline

---

### Phase 2: Advanced Metrics
**Goal**: Add stream quality and network metrics

1. ✅ Edge Worker: Implement `camera_health_monitor.py`
2. ✅ Backend: Add metrics to health endpoint (brightness, sharpness, latency)
3. ✅ Frontend: Display advanced metrics in camera cards

**Deliverable**: Detailed health metrics for each camera

---

### Phase 3: Historical Tracking & Alerts
**Goal**: Track health over time and alert on issues

1. ✅ Database: Retention policy for `camera_health` (30 days)
2. ✅ Backend: `GET /cameras/{id}/health/history`
3. ✅ Frontend: Health history charts (line graph of FPS, uptime over 24h)
4. ✅ Alerting: Email/SMS when camera goes offline >5 min

**Deliverable**: Health trends and automated alerts

---

### Phase 4: Diagnostics & Remediation
**Goal**: Tools to fix camera issues

1. ✅ Backend:
   - `POST /cameras/{id}/test` - Test stream
   - `POST /cameras/{id}/restart` - Restart stream
2. ✅ Frontend: Action buttons (test, restart, view logs)
3. ✅ Edge Worker: Auto-reconnect logic

**Deliverable**: Self-service troubleshooting tools

---

## Success Metrics

- **Visibility**: Can we see the health status of all cameras at a glance?
- **Proactive Alerting**: Are we notified before customers report camera issues?
- **Diagnostic Speed**: Can we identify the root cause of a camera failure in <5 minutes?
- **Uptime**: Do we maintain >99% camera uptime across all deployments?

---

## Questions to Clarify

1. **RTSP Credentials**: How are camera credentials stored? (Need secure storage for username/password)
2. **Edge or Cloud Health Checks**: Should health monitoring run on edge hubs or cloud worker?
   - **Edge**: Lower latency, accurate local metrics, but requires edge worker update
   - **Cloud**: Centralized, easier to deploy, but higher network overhead
3. **Real-Time Updates**: Do we need WebSocket for live updates, or is 30-second polling sufficient?
4. **Alerts**: What alert thresholds? (e.g., email if camera offline >5 min, SMS if >10 cameras offline)
5. **Storage**: How long to retain health history? (Suggested: 30 days, archive older data)

---

**Created**: 2026-01-13
**Status**: 📋 Planning - Awaiting user feedback
**Next Step**: Review this map, clarify questions, then implement Phase 1 MVP
