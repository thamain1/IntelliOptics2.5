# Camera Inspection System - Implementation Plan

## Overview
Automated camera health inspection system that monitors camera quality, detects view changes, sends alerts, and provides a comprehensive dashboard for managing camera health across all edge deployments.

---

## Core Requirements

### 1. Inspection Engine
- **Runs on interval**: Configurable per customer (15 min, 1 hour, 2 hours, 4 hours, etc.)
- **Typical intervals**: 1-4 hours for most deployments (camera health changes slowly)
- **High-frequency option**: 15-30 minutes for critical infrastructure
- **Low-frequency option**: 6-12 hours for cost optimization
- **Automated**: No manual intervention required
- **Comprehensive checks**: Connection, quality metrics, view change detection
- **Report generation**: Create detailed reports for dashboard display
- **Resource efficient**: Worker is idle 95%+ of the time, only active during inspection cycles

### 2. Quality Metrics Monitored
- ✅ **Connection Status**: Connected/Offline
- ✅ **Stream Quality**: FPS, Resolution, Bitrate
- ✅ **Image Quality**: Brightness, Sharpness, Blur detection
- ✅ **Network Health**: Latency, Packet loss
- ✅ **Operational**: Uptime %, Error count
- 🆕 **View Change Detection**: Detect camera movement/repositioning

### 3. View Change Detection (Critical Feature)
**Problem**: Detect when a camera has been physically moved or repositioned

**Solution**: Traditional Computer Vision (CPU-Only, No ML/GPU)
- **Baseline Image**: Store reference image when camera is first configured or manually set
- **Comparison Method** (Pure Python + OpenCV on CPU):
  - **SSIM (Structural Similarity Index)**: Compare structural patterns (scikit-image)
  - **ORB Features**: Fast binary feature detector (CPU-optimized, no GPU needed)
  - **Edge Detection**: Canny edge detection for structure comparison
  - **Histogram Comparison**: Color/intensity distribution analysis
- **Day/Night Handling**:
  - Extract structural features (edges, corners) that are invariant to lighting
  - Compare feature positions, not pixel intensities
  - Use normalized cross-correlation on edge maps
- **Threshold**: If >30% of features have moved or SSIM <0.7, flag as view change

**Why CPU-Only**:
- ✅ Works on Raspberry Pi (ARM CPU)
- ✅ No GPU dependencies
- ✅ Low power consumption
- ✅ Traditional CV algorithms (ORB, SSIM) are fast enough for periodic checks
- ✅ No ML model training/inference needed

**Example**:
```
Baseline Image (Parking Lot A - North Camera):
- Building at top-left corner
- Entry gate at center
- Trees on right side

Current Image:
- Building now at center (camera rotated)
- Entry gate at left
→ ALERT: "Camera view has changed - possible camera movement"
```

### 4. Alerting System
**Triggers**:
- Camera goes offline for >5 minutes
- FPS drops below 50% of expected
- View change detected
- Image quality degradation (too dark, too blurry)
- Network latency >1000ms

**Alert Methods**:
- 📧 **Email**: Send to configured recipients
- 🔔 **Dashboard Notification**: Show alert badge on Camera Inspection page
- 📊 **Alert Log**: Record all alerts in database

**Mute Capability**:
- User can mute alerts for specific camera
- Mute duration: 1-30 days (user selectable)
- After mute expires, alerts resume
- Dashboard shows "Muted" badge on camera card

### 5. Dashboard
- **View**: List of all cameras with current health status
- **Timeframe**: Display last 30 days of health data
- **Filters**: By hub, status, alert type
- **Actions**:
  - Mute alerts (per camera)
  - View detailed health report
  - Update baseline image (for view change detection)
  - Acknowledge alert

### 6. Data Retention
- **Dashboard**: Last 30 days visible
- **Database**: Keep 90 days of inspection history
- **Cleanup**: Automated job to delete records older than 90 days

---

## Database Schema

### 1. Add `inspection_config` Table
Per-customer inspection settings:

```sql
CREATE TABLE inspection_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID,  -- If multi-tenant, otherwise use default config

    -- Inspection interval (in minutes)
    inspection_interval_minutes INT NOT NULL DEFAULT 15,

    -- Alert thresholds
    offline_threshold_minutes INT DEFAULT 5,
    fps_drop_threshold_pct FLOAT DEFAULT 0.5,  -- Alert if FPS drops below 50%
    latency_threshold_ms INT DEFAULT 1000,
    view_change_threshold FLOAT DEFAULT 0.7,  -- SSIM threshold

    -- Alert recipients
    alert_emails TEXT[],  -- Array of email addresses

    -- Retention
    dashboard_retention_days INT DEFAULT 30,
    database_retention_days INT DEFAULT 90,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Default configuration (1 hour interval = 60 minutes)
INSERT INTO inspection_config (inspection_interval_minutes, alert_emails)
VALUES (60, ARRAY['admin@example.com']);

-- Example: High-frequency for critical sites (15 minutes)
-- INSERT INTO inspection_config (inspection_interval_minutes, alert_emails)
-- VALUES (15, ARRAY['admin@example.com']);

-- Example: Standard for most sites (4 hours = 240 minutes)
-- INSERT INTO inspection_config (inspection_interval_minutes, alert_emails)
-- VALUES (240, ARRAY['admin@example.com']);
```

### 2. Update `cameras` Table
Add view change detection fields:

```sql
ALTER TABLE cameras
ADD COLUMN baseline_image_path TEXT,  -- Path to baseline image in Azure Blob
ADD COLUMN baseline_image_updated_at TIMESTAMP,
ADD COLUMN view_change_detected BOOLEAN DEFAULT FALSE,
ADD COLUMN view_change_detected_at TIMESTAMP;
```

### 3. Update `camera_health` Table
Add view change detection metrics:

```sql
ALTER TABLE camera_health
ADD COLUMN view_similarity_score FLOAT,  -- SSIM score (0-1, 1=identical)
ADD COLUMN view_change_detected BOOLEAN DEFAULT FALSE,
ADD COLUMN feature_match_count INT,  -- Number of matched features
ADD COLUMN inspection_run_id UUID;  -- Link to specific inspection run
```

### 4. Add `inspection_runs` Table
Track each inspection cycle:

```sql
CREATE TABLE inspection_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    total_cameras INT,
    cameras_inspected INT,
    cameras_healthy INT,
    cameras_warning INT,
    cameras_failed INT,
    status VARCHAR(32) DEFAULT 'running',  -- running, completed, failed

    created_at TIMESTAMP DEFAULT NOW()
);
```

### 5. Add `camera_alerts` Table
Record all alerts:

```sql
CREATE TABLE camera_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    camera_id UUID NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    inspection_run_id UUID REFERENCES inspection_runs(id),

    -- Alert details
    alert_type VARCHAR(64) NOT NULL,  -- offline, fps_drop, view_change, quality_degradation, network_issue
    severity VARCHAR(32) NOT NULL,  -- critical, warning, info
    message TEXT,
    details JSONB,  -- Store specific metrics that triggered the alert

    -- Alert management
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by UUID REFERENCES users(id),
    acknowledged_at TIMESTAMP,

    muted_until TIMESTAMP,  -- If alert is muted, when does it unmute?
    muted_by UUID REFERENCES users(id),

    -- Email tracking
    email_sent BOOLEAN DEFAULT FALSE,
    email_sent_at TIMESTAMP,

    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_camera_alerts_camera ON camera_alerts(camera_id, created_at DESC);
CREATE INDEX idx_camera_alerts_unmuted ON camera_alerts(camera_id) WHERE muted_until IS NULL OR muted_until < NOW();
```

---

## Backend Implementation

### New Routers

#### 1. Inspection Config Router
**Location**: `backend/app/routers/inspection_config.py`

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/inspection-config", tags=["Inspection Config"])

@router.get("/", response_model=schemas.InspectionConfigOut)
def get_inspection_config(
    db: Session = Depends(get_db)
):
    """Get current inspection configuration"""
    config = db.query(models.InspectionConfig).first()
    if not config:
        # Return default config
        config = models.InspectionConfig(
            inspection_interval_minutes=15,
            alert_emails=["admin@example.com"]
        )
    return config

@router.put("/", response_model=schemas.InspectionConfigOut)
def update_inspection_config(
    config_update: schemas.InspectionConfigUpdate,
    db: Session = Depends(get_db)
):
    """Update inspection configuration"""
    config = db.query(models.InspectionConfig).first()
    if not config:
        config = models.InspectionConfig(**config_update.dict())
        db.add(config)
    else:
        for key, value in config_update.dict(exclude_unset=True).items():
            setattr(config, key, value)

    db.commit()
    db.refresh(config)
    return config
```

#### 2. Camera Inspection Router
**Location**: `backend/app/routers/camera_inspection.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/camera-inspection", tags=["Camera Inspection"])

@router.get("/dashboard", response_model=schemas.InspectionDashboard)
def get_inspection_dashboard(
    hub_id: Optional[str] = None,
    status_filter: Optional[str] = None,  # healthy, warning, failed
    days: int = 30,
    db: Session = Depends(get_db)
):
    """
    Get inspection dashboard data for last N days
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    # Get all cameras with latest health status
    query = db.query(models.Camera).join(models.Hub)
    if hub_id:
        query = query.filter(models.Camera.hub_id == hub_id)

    cameras = query.all()

    # For each camera, get latest health record
    dashboard_data = []
    for camera in cameras:
        latest_health = db.query(models.CameraHealth).filter(
            models.CameraHealth.camera_id == camera.id,
            models.CameraHealth.timestamp >= cutoff_date
        ).order_by(models.CameraHealth.timestamp.desc()).first()

        # Get active alerts (not acknowledged, not muted)
        active_alerts = db.query(models.CameraAlert).filter(
            models.CameraAlert.camera_id == camera.id,
            models.CameraAlert.acknowledged == False,
            (models.CameraAlert.muted_until == None) |
            (models.CameraAlert.muted_until < datetime.utcnow())
        ).all()

        dashboard_data.append({
            "camera": camera,
            "health": latest_health,
            "alerts": active_alerts,
            "hub_name": camera.hub.name
        })

    # Apply status filter
    if status_filter:
        dashboard_data = [
            d for d in dashboard_data
            if d["health"] and d["health"].status == status_filter
        ]

    # Summary stats
    total = len(dashboard_data)
    healthy = sum(1 for d in dashboard_data if d["health"] and d["health"].status == "connected")
    warning = sum(1 for d in dashboard_data if d["health"] and d["health"].status == "degraded")
    failed = sum(1 for d in dashboard_data if d["health"] and d["health"].status == "offline")

    return {
        "summary": {
            "total": total,
            "healthy": healthy,
            "warning": warning,
            "failed": failed
        },
        "cameras": dashboard_data,
        "last_updated": datetime.utcnow()
    }

@router.get("/cameras/{camera_id}/history")
def get_camera_inspection_history(
    camera_id: str,
    days: int = 30,
    db: Session = Depends(get_db)
):
    """Get inspection history for a specific camera"""
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    history = db.query(models.CameraHealth).filter(
        models.CameraHealth.camera_id == camera_id,
        models.CameraHealth.timestamp >= cutoff_date
    ).order_by(models.CameraHealth.timestamp.asc()).all()

    alerts = db.query(models.CameraAlert).filter(
        models.CameraAlert.camera_id == camera_id,
        models.CameraAlert.created_at >= cutoff_date
    ).order_by(models.CameraAlert.created_at.desc()).all()

    return {
        "camera_id": camera_id,
        "health_history": history,
        "alerts": alerts
    }

@router.post("/cameras/{camera_id}/mute-alerts")
def mute_camera_alerts(
    camera_id: str,
    mute_days: int,  # 1-30 days
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)  # Add auth
):
    """Mute alerts for a specific camera"""
    if mute_days < 1 or mute_days > 30:
        raise HTTPException(400, "Mute duration must be between 1 and 30 days")

    mute_until = datetime.utcnow() + timedelta(days=mute_days)

    # Update all active alerts for this camera
    db.query(models.CameraAlert).filter(
        models.CameraAlert.camera_id == camera_id,
        models.CameraAlert.acknowledged == False
    ).update({
        "muted_until": mute_until,
        "muted_by": current_user.id
    })

    db.commit()

    return {"message": f"Alerts muted until {mute_until}", "muted_until": mute_until}

@router.post("/cameras/{camera_id}/unmute-alerts")
def unmute_camera_alerts(
    camera_id: str,
    db: Session = Depends(get_db)
):
    """Unmute alerts for a specific camera"""
    db.query(models.CameraAlert).filter(
        models.CameraAlert.camera_id == camera_id
    ).update({"muted_until": None})

    db.commit()

    return {"message": "Alerts unmuted"}

@router.post("/cameras/{camera_id}/acknowledge-alert/{alert_id}")
def acknowledge_alert(
    camera_id: str,
    alert_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Acknowledge a specific alert"""
    alert = db.query(models.CameraAlert).filter(
        models.CameraAlert.id == alert_id,
        models.CameraAlert.camera_id == camera_id
    ).first()

    if not alert:
        raise HTTPException(404, "Alert not found")

    alert.acknowledged = True
    alert.acknowledged_by = current_user.id
    alert.acknowledged_at = datetime.utcnow()

    db.commit()

    return {"message": "Alert acknowledged"}

@router.post("/cameras/{camera_id}/update-baseline")
async def update_baseline_image(
    camera_id: str,
    db: Session = Depends(get_db)
):
    """
    Capture current camera frame and set as new baseline image
    for view change detection
    """
    camera = db.query(models.Camera).filter(models.Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(404, "Camera not found")

    # Capture current frame from RTSP stream
    from ..services.camera_service import capture_frame, upload_to_blob

    frame = capture_frame(camera.url)
    if frame is None:
        raise HTTPException(500, "Failed to capture frame from camera")

    # Upload to Azure Blob Storage
    blob_path = f"baselines/{camera_id}/{datetime.utcnow().isoformat()}.jpg"
    upload_to_blob(frame, blob_path)

    # Update camera record
    camera.baseline_image_path = blob_path
    camera.baseline_image_updated_at = datetime.utcnow()
    camera.view_change_detected = False

    db.commit()

    return {
        "message": "Baseline image updated",
        "baseline_path": blob_path
    }
```

---

## Worker/Inspection Engine

### Camera Inspection Worker
**Location**: `cloud/worker/camera_inspection_worker.py`

**Note**: This worker is designed to run on CPU-only devices (Raspberry Pi, edge servers).
All computer vision operations use traditional algorithms (no ML/GPU required).

```python
import cv2  # opencv-python-headless (CPU-only)
import numpy as np
from datetime import datetime
import time
from typing import Dict, List
import requests
from azure.storage.blob import BlobServiceClient
from skimage.metrics import structural_similarity as ssim  # CPU-based SSIM
import os

class CameraInspectionWorker:
    """
    CPU-only camera inspection worker.
    Compatible with Raspberry Pi 4/5 and any x86/ARM64 device.
    No GPU or ML models required.
    """
    def __init__(self, config):
        self.config = config
        self.blob_client = BlobServiceClient.from_connection_string(
            os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        )

    def run_inspection_cycle(self):
        """Run a complete inspection cycle for all cameras"""
        print(f"[{datetime.utcnow()}] Starting inspection cycle...")

        # Create inspection run record
        run_id = self.create_inspection_run()

        # Get all cameras
        cameras = self.get_all_cameras()

        results = {
            "total": len(cameras),
            "inspected": 0,
            "healthy": 0,
            "warning": 0,
            "failed": 0
        }

        for camera in cameras:
            try:
                health_data = self.inspect_camera(camera, run_id)
                self.save_health_data(camera["id"], health_data, run_id)

                # Check for alerts
                alerts = self.check_alert_conditions(camera, health_data)
                for alert in alerts:
                    self.create_alert(camera["id"], alert, run_id)

                results["inspected"] += 1
                if health_data["status"] == "connected":
                    results["healthy"] += 1
                elif health_data["status"] == "degraded":
                    results["warning"] += 1
                else:
                    results["failed"] += 1

            except Exception as e:
                print(f"Error inspecting camera {camera['id']}: {e}")
                results["failed"] += 1

        self.complete_inspection_run(run_id, results)
        print(f"[{datetime.utcnow()}] Inspection cycle completed: {results}")

    def inspect_camera(self, camera: Dict, run_id: str) -> Dict:
        """Perform comprehensive inspection on a single camera"""
        rtsp_url = camera["url"]

        health_data = {
            "status": "unknown",
            "timestamp": datetime.utcnow(),
            "fps": 0,
            "expected_fps": 30.0,
            "resolution": None,
            "latency_ms": 0,
            "avg_brightness": 0,
            "sharpness_score": 0,
            "view_similarity_score": None,
            "view_change_detected": False,
            "connection_error": None
        }

        try:
            # 1. Connection test
            start_time = time.time()
            cap = cv2.VideoCapture(rtsp_url)

            if not cap.isOpened():
                health_data["status"] = "offline"
                health_data["connection_error"] = "Failed to connect to RTSP stream"
                return health_data

            health_data["latency_ms"] = int((time.time() - start_time) * 1000)

            # 2. FPS measurement (sample 30 frames)
            frame_count = 0
            fps_start = time.time()
            current_frame = None

            for i in range(30):
                ret, frame = cap.read()
                if ret:
                    frame_count += 1
                    if i == 29:  # Save last frame for analysis
                        current_frame = frame

            fps_elapsed = time.time() - fps_start
            health_data["fps"] = frame_count / fps_elapsed if fps_elapsed > 0 else 0

            # 3. Resolution
            if current_frame is not None:
                height, width = current_frame.shape[:2]
                health_data["resolution"] = f"{width}x{height}"

                # 4. Image quality metrics
                health_data["avg_brightness"] = np.mean(current_frame) / 255.0
                health_data["sharpness_score"] = self.calculate_sharpness(current_frame)

                # 5. View change detection
                if camera.get("baseline_image_path"):
                    similarity, view_changed = self.detect_view_change(
                        current_frame,
                        camera["baseline_image_path"]
                    )
                    health_data["view_similarity_score"] = similarity
                    health_data["view_change_detected"] = view_changed

            cap.release()

            # 6. Determine overall status
            if health_data["fps"] < health_data["expected_fps"] * 0.5:
                health_data["status"] = "degraded"
            elif health_data["view_change_detected"]:
                health_data["status"] = "degraded"
            else:
                health_data["status"] = "connected"

        except Exception as e:
            health_data["status"] = "offline"
            health_data["connection_error"] = str(e)

        return health_data

    def calculate_sharpness(self, frame) -> float:
        """Calculate sharpness using Laplacian variance"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        # Normalize to 0-1 range
        return min(laplacian_var / 1000.0, 1.0)

    def detect_view_change(self, current_frame, baseline_blob_path) -> tuple:
        """
        Detect if camera view has changed compared to baseline
        Returns: (similarity_score, view_changed_bool)
        """
        # Download baseline image from Azure Blob
        baseline_frame = self.download_baseline_image(baseline_blob_path)
        if baseline_frame is None:
            return (None, False)

        # Resize to same dimensions
        h, w = current_frame.shape[:2]
        baseline_frame = cv2.resize(baseline_frame, (w, h))

        # Convert to grayscale
        current_gray = cv2.cvtColor(current_frame, cv2.COLOR_BGR2GRAY)
        baseline_gray = cv2.cvtColor(baseline_frame, cv2.COLOR_BGR2GRAY)

        # Method 1: Structural Similarity (SSIM)
        similarity_score = ssim(current_gray, baseline_gray)

        # Method 2: Feature matching (ORB features)
        orb = cv2.ORB_create()
        kp1, des1 = orb.detectAndCompute(current_gray, None)
        kp2, des2 = orb.detectAndCompute(baseline_gray, None)

        if des1 is not None and des2 is not None:
            bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
            matches = bf.match(des1, des2)

            # Calculate match ratio
            match_ratio = len(matches) / max(len(kp1), len(kp2))
        else:
            match_ratio = 0

        # Decision: View changed if SSIM < threshold OR few feature matches
        threshold_ssim = self.config.get("view_change_threshold", 0.7)
        view_changed = (similarity_score < threshold_ssim) or (match_ratio < 0.3)

        return (similarity_score, view_changed)

    def download_baseline_image(self, blob_path):
        """Download baseline image from Azure Blob Storage"""
        try:
            blob_client = self.blob_client.get_blob_client(
                container="camera-baselines",
                blob=blob_path
            )
            image_data = blob_client.download_blob().readall()

            # Decode image
            nparr = np.frombuffer(image_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            return frame
        except Exception as e:
            print(f"Error downloading baseline image: {e}")
            return None

    def check_alert_conditions(self, camera: Dict, health_data: Dict) -> List[Dict]:
        """Check if any alert conditions are met"""
        alerts = []

        # 1. Offline alert
        if health_data["status"] == "offline":
            alerts.append({
                "alert_type": "offline",
                "severity": "critical",
                "message": f"Camera '{camera['name']}' is offline",
                "details": {"error": health_data.get("connection_error")}
            })

        # 2. FPS drop alert
        if health_data["fps"] < health_data["expected_fps"] * 0.5:
            alerts.append({
                "alert_type": "fps_drop",
                "severity": "warning",
                "message": f"Camera '{camera['name']}' FPS dropped to {health_data['fps']:.1f}",
                "details": {
                    "current_fps": health_data["fps"],
                    "expected_fps": health_data["expected_fps"]
                }
            })

        # 3. View change alert
        if health_data.get("view_change_detected"):
            alerts.append({
                "alert_type": "view_change",
                "severity": "critical",
                "message": f"Camera '{camera['name']}' view has changed - possible movement detected",
                "details": {
                    "similarity_score": health_data.get("view_similarity_score")
                }
            })

        # 4. Quality degradation (too dark)
        if health_data["avg_brightness"] < 0.2:
            alerts.append({
                "alert_type": "quality_degradation",
                "severity": "warning",
                "message": f"Camera '{camera['name']}' image too dark - possible obstruction",
                "details": {"brightness": health_data["avg_brightness"]}
            })

        # 5. Network latency
        if health_data["latency_ms"] > self.config.get("latency_threshold_ms", 1000):
            alerts.append({
                "alert_type": "network_issue",
                "severity": "warning",
                "message": f"Camera '{camera['name']}' high network latency",
                "details": {"latency_ms": health_data["latency_ms"]}
            })

        return alerts

    def create_alert(self, camera_id: str, alert_data: Dict, run_id: str):
        """Create alert and send email if not muted"""
        # Check if camera has muted alerts
        response = requests.get(f"{self.api_url}/camera-inspection/cameras/{camera_id}/alerts")
        existing_alerts = response.json()

        # Check if similar alert already exists and is muted
        is_muted = any(
            a["alert_type"] == alert_data["alert_type"] and
            a.get("muted_until") and
            datetime.fromisoformat(a["muted_until"]) > datetime.utcnow()
            for a in existing_alerts
        )

        if is_muted:
            print(f"Alert muted for camera {camera_id}: {alert_data['alert_type']}")
            return

        # Create alert in database
        alert_payload = {
            "camera_id": camera_id,
            "inspection_run_id": run_id,
            **alert_data
        }

        response = requests.post(
            f"{self.api_url}/camera-inspection/alerts",
            json=alert_payload
        )

        if response.status_code == 201:
            # Send email alert
            if alert_data["severity"] in ["critical", "warning"]:
                self.send_email_alert(camera_id, alert_data)

    def send_email_alert(self, camera_id: str, alert_data: Dict):
        """Send email alert to configured recipients"""
        # Get alert email recipients from config
        config = requests.get(f"{self.api_url}/inspection-config").json()
        recipients = config.get("alert_emails", [])

        if not recipients:
            return

        # Email content
        subject = f"🚨 Camera Alert: {alert_data['message']}"
        body = f"""
        <h2>IntelliOptics Camera Alert</h2>
        <p><strong>Alert Type:</strong> {alert_data['alert_type']}</p>
        <p><strong>Severity:</strong> {alert_data['severity']}</p>
        <p><strong>Message:</strong> {alert_data['message']}</p>
        <p><strong>Time:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>

        <p><strong>Details:</strong></p>
        <pre>{alert_data.get('details', {})}</pre>

        <p><a href="http://localhost/camera-inspection">View Camera Inspection Dashboard</a></p>
        """

        # Send via SendGrid or configured email service
        from ..services.email_service import send_email
        send_email(recipients, subject, body)

    def get_all_cameras(self) -> List[Dict]:
        """Fetch all cameras from API"""
        response = requests.get(f"{self.api_url}/cameras?include_baseline=true")
        return response.json()

    def create_inspection_run(self) -> str:
        """Create new inspection run record"""
        response = requests.post(f"{self.api_url}/camera-inspection/runs")
        return response.json()["id"]

    def complete_inspection_run(self, run_id: str, results: Dict):
        """Mark inspection run as completed"""
        requests.put(
            f"{self.api_url}/camera-inspection/runs/{run_id}",
            json={
                "status": "completed",
                "completed_at": datetime.utcnow().isoformat(),
                **results
            }
        )

    def save_health_data(self, camera_id: str, health_data: Dict, run_id: str):
        """Save health data to database"""
        requests.post(
            f"{self.api_url}/cameras/{camera_id}/health",
            json={**health_data, "inspection_run_id": run_id}
        )


# Main execution loop
if __name__ == "__main__":
    import os

    worker = CameraInspectionWorker({
        "api_url": os.getenv("API_URL", "http://backend:8000"),
        "view_change_threshold": 0.7,
        "latency_threshold_ms": 1000
    })

    # Get inspection interval from config
    config_response = requests.get(f"{worker.api_url}/inspection-config")
    config = config_response.json()
    interval_minutes = config.get("inspection_interval_minutes", 60)  # Default: 1 hour

    print(f"Camera Inspection Worker started")
    print(f"Inspection interval: {interval_minutes} minutes ({interval_minutes/60:.1f} hours)")
    print(f"Worker will be idle between inspection cycles (low power consumption)")

    while True:
        cycle_start = datetime.utcnow()
        print(f"\n[{cycle_start}] Starting inspection cycle...")

        worker.run_inspection_cycle()

        cycle_end = datetime.utcnow()
        cycle_duration = (cycle_end - cycle_start).total_seconds()
        print(f"[{cycle_end}] Inspection cycle completed in {cycle_duration:.1f} seconds")

        # Sleep until next cycle
        sleep_seconds = interval_minutes * 60
        print(f"Worker entering idle mode for {interval_minutes} minutes...")
        time.sleep(sleep_seconds)
```

---

## Frontend Implementation

### Camera Inspection Page
**Location**: `frontend/src/pages/CameraInspectionPage.tsx`

```typescript
import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { Card } from '../components/Card';

interface CameraSummary {
  total: number;
  healthy: number;
  warning: number;
  failed: number;
}

interface CameraHealth {
  status: string;
  fps: number;
  expected_fps: number;
  resolution: string;
  last_frame_at: string;
  uptime_24h: number;
  latency_ms: number;
  view_similarity_score?: number;
  view_change_detected: boolean;
}

interface CameraAlert {
  id: string;
  alert_type: string;
  severity: string;
  message: string;
  created_at: string;
  muted_until?: string;
  acknowledged: boolean;
}

interface CameraData {
  camera: {
    id: string;
    name: string;
    url: string;
    hub_id: string;
  };
  hub_name: string;
  health: CameraHealth;
  alerts: CameraAlert[];
}

const CameraInspectionPage: React.FC = () => {
  const [summary, setSummary] = useState<CameraSummary>({
    total: 0,
    healthy: 0,
    warning: 0,
    failed: 0
  });
  const [cameras, setCameras] = useState<CameraData[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterHub, setFilterHub] = useState<string>('');
  const [filterStatus, setFilterStatus] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');

  const fetchDashboard = async () => {
    try {
      setLoading(true);
      const params = new URLSearchParams();
      if (filterHub) params.append('hub_id', filterHub);
      if (filterStatus) params.append('status_filter', filterStatus);

      const res = await axios.get(`/camera-inspection/dashboard?${params.toString()}`);
      setSummary(res.data.summary);
      setCameras(res.data.cameras);
    } catch (err) {
      console.error('Failed to fetch camera inspection data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboard();
    // No auto-refresh - dashboard updates on login/manual refresh only
  }, [filterHub, filterStatus]);

  const handleMuteAlerts = async (cameraId: string, days: number) => {
    try {
      await axios.post(`/camera-inspection/cameras/${cameraId}/mute-alerts`, { mute_days: days });
      fetchDashboard();
    } catch (err) {
      console.error('Failed to mute alerts:', err);
    }
  };

  const handleAcknowledgeAlert = async (cameraId: string, alertId: string) => {
    try {
      await axios.post(`/camera-inspection/cameras/${cameraId}/acknowledge-alert/${alertId}`);
      fetchDashboard();
    } catch (err) {
      console.error('Failed to acknowledge alert:', err);
    }
  };

  const handleUpdateBaseline = async (cameraId: string) => {
    try {
      await axios.post(`/camera-inspection/cameras/${cameraId}/update-baseline`);
      alert('Baseline image updated successfully');
      fetchDashboard();
    } catch (err) {
      console.error('Failed to update baseline:', err);
    }
  };

  const getStatusBadge = (status: string) => {
    const badges = {
      connected: '🟢 Healthy',
      degraded: '🟡 Warning',
      offline: '🔴 Offline'
    };
    const colors = {
      connected: 'bg-green-900 text-green-300',
      degraded: 'bg-yellow-900 text-yellow-300',
      offline: 'bg-red-900 text-red-300'
    };

    return (
      <span className={`px-3 py-1 rounded-full text-xs font-bold ${colors[status] || 'bg-gray-700'}`}>
        {badges[status] || status}
      </span>
    );
  };

  // Filter cameras by search query
  const filteredCameras = cameras.filter(c =>
    c.camera.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    c.hub_name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="p-8 bg-gray-900 min-h-screen">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold text-white">🎥 Camera Health Inspection</h1>
        <button
          onClick={fetchDashboard}
          className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded font-bold transition"
        >
          🔄 Refresh
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <Card title="Total Cameras">
          <div className="text-4xl font-bold text-white">{summary.total}</div>
        </Card>
        <Card title="Healthy">
          <div className="text-4xl font-bold text-green-400">
            {summary.healthy}
            <span className="text-sm text-gray-400 ml-2">
              ({summary.total > 0 ? Math.round((summary.healthy / summary.total) * 100) : 0}%)
            </span>
          </div>
        </Card>
        <Card title="Warning">
          <div className="text-4xl font-bold text-yellow-400">
            {summary.warning}
            <span className="text-sm text-gray-400 ml-2">
              ({summary.total > 0 ? Math.round((summary.warning / summary.total) * 100) : 0}%)
            </span>
          </div>
        </Card>
        <Card title="Offline">
          <div className="text-4xl font-bold text-red-400">
            {summary.failed}
            <span className="text-sm text-gray-400 ml-2">
              ({summary.total > 0 ? Math.round((summary.failed / summary.total) * 100) : 0}%)
            </span>
          </div>
        </Card>
      </div>

      {/* Filters */}
      <div className="bg-gray-800 p-4 rounded-lg mb-6 flex gap-4">
        <input
          type="text"
          placeholder="🔍 Search cameras..."
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          className="flex-1 bg-gray-700 text-white px-4 py-2 rounded border border-gray-600 focus:border-blue-500"
        />
        <select
          value={filterStatus}
          onChange={e => setFilterStatus(e.target.value)}
          className="bg-gray-700 text-white px-4 py-2 rounded border border-gray-600"
        >
          <option value="">All Statuses</option>
          <option value="connected">Healthy</option>
          <option value="degraded">Warning</option>
          <option value="offline">Offline</option>
        </select>
      </div>

      {/* Camera List */}
      {loading ? (
        <div className="text-center text-gray-400 py-8">Loading...</div>
      ) : filteredCameras.length === 0 ? (
        <div className="text-center text-gray-500 py-8">No cameras found</div>
      ) : (
        <div className="space-y-6">
          {/* Group by hub */}
          {Object.entries(
            filteredCameras.reduce((acc, cam) => {
              const hubName = cam.hub_name;
              if (!acc[hubName]) acc[hubName] = [];
              acc[hubName].push(cam);
              return acc;
            }, {} as Record<string, CameraData[]>)
          ).map(([hubName, hubCameras]) => (
            <div key={hubName} className="bg-gray-800 rounded-lg p-6">
              <h2 className="text-xl font-bold text-white mb-4">
                🏢 {hubName}
              </h2>

              <div className="space-y-4">
                {hubCameras.map(({ camera, health, alerts }) => (
                  <div key={camera.id} className="bg-gray-700 rounded-lg p-4">
                    {/* Camera Header */}
                    <div className="flex justify-between items-start mb-4">
                      <div>
                        <h3 className="text-lg font-bold text-white">{camera.name}</h3>
                        <p className="text-xs text-gray-400 truncate" title={camera.url}>
                          {camera.url}
                        </p>
                      </div>
                      {health && getStatusBadge(health.status)}
                    </div>

                    {/* Health Metrics Grid */}
                    {health && (
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-4">
                        <div>
                          <p className="text-xs text-gray-400">Frame Rate</p>
                          <p className="text-white font-bold">
                            {health.fps.toFixed(1)} / {health.expected_fps} FPS
                            {health.fps < health.expected_fps * 0.5 && <span className="text-yellow-400 ml-1">⚠️</span>}
                          </p>
                        </div>
                        <div>
                          <p className="text-xs text-gray-400">Resolution</p>
                          <p className="text-white font-bold">{health.resolution || 'N/A'}</p>
                        </div>
                        <div>
                          <p className="text-xs text-gray-400">Last Frame</p>
                          <p className="text-white font-bold">
                            {health.last_frame_at ? new Date(health.last_frame_at).toLocaleTimeString() : 'N/A'}
                          </p>
                        </div>
                        <div>
                          <p className="text-xs text-gray-400">Uptime (24h)</p>
                          <p className="text-white font-bold">{health.uptime_24h?.toFixed(1)}%</p>
                        </div>
                        <div>
                          <p className="text-xs text-gray-400">Latency</p>
                          <p className="text-white font-bold">{health.latency_ms} ms</p>
                        </div>
                        {health.view_similarity_score && (
                          <div>
                            <p className="text-xs text-gray-400">View Similarity</p>
                            <p className="text-white font-bold">
                              {(health.view_similarity_score * 100).toFixed(1)}%
                              {health.view_change_detected && <span className="text-red-400 ml-1">🚨</span>}
                            </p>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Alerts */}
                    {alerts.length > 0 && (
                      <div className="bg-gray-800 p-3 rounded mb-4">
                        <h4 className="text-sm font-bold text-white mb-2">🚨 Active Alerts</h4>
                        <div className="space-y-2">
                          {alerts.map(alert => (
                            <div key={alert.id} className="flex justify-between items-center bg-gray-700 p-2 rounded">
                              <div>
                                <p className="text-white text-sm">{alert.message}</p>
                                <p className="text-xs text-gray-400">
                                  {new Date(alert.created_at).toLocaleString()}
                                  {alert.muted_until && (
                                    <span className="ml-2 text-yellow-400">
                                      🔇 Muted until {new Date(alert.muted_until).toLocaleDateString()}
                                    </span>
                                  )}
                                </p>
                              </div>
                              {!alert.acknowledged && !alert.muted_until && (
                                <button
                                  onClick={() => handleAcknowledgeAlert(camera.id, alert.id)}
                                  className="bg-blue-600 hover:bg-blue-500 text-white text-xs px-3 py-1 rounded"
                                >
                                  Acknowledge
                                </button>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Action Buttons */}
                    <div className="flex gap-2 flex-wrap">
                      <button className="bg-purple-600 hover:bg-purple-500 text-white text-sm px-3 py-1 rounded">
                        📺 View Live Feed
                      </button>
                      {health?.view_change_detected && (
                        <button
                          onClick={() => handleUpdateBaseline(camera.id)}
                          className="bg-orange-600 hover:bg-orange-500 text-white text-sm px-3 py-1 rounded"
                        >
                          📸 Update Baseline
                        </button>
                      )}
                      <select
                        onChange={(e) => {
                          if (e.target.value) {
                            handleMuteAlerts(camera.id, parseInt(e.target.value));
                            e.target.value = '';
                          }
                        }}
                        className="bg-gray-600 text-white text-sm px-3 py-1 rounded"
                      >
                        <option value="">🔇 Mute Alerts...</option>
                        <option value="1">1 Day</option>
                        <option value="7">7 Days</option>
                        <option value="14">14 Days</option>
                        <option value="30">30 Days</option>
                      </select>
                      <button className="bg-gray-600 hover:bg-gray-500 text-white text-sm px-3 py-1 rounded">
                        📊 View History
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default CameraInspectionPage;
```

---

## Technology Stack & Hardware Requirements

### Inspection Worker (CPU-Only, Raspberry Pi Compatible)

**Software Stack**:
- **Python 3.9+** (ARM64 and x86_64 compatible)
- **OpenCV (cv2)**: CPU-optimized image processing
  - `pip install opencv-python-headless` (no GUI, lighter for edge devices)
- **scikit-image**: SSIM calculation (pure NumPy, no GPU)
- **NumPy**: Array operations (CPU-based, optimized for ARM)
- **Pillow**: Image format handling
- **RTSP Stream Processing**: Using `cv2.VideoCapture` (CPU decoding)
- **Azure Blob Storage Client**: For baseline image storage
- **SendGrid Python SDK**: Email alerting
- **Requests**: HTTP API calls to backend

**Hardware Requirements**:

| Device | RAM | CPU | Camera Capacity (1hr interval) | Camera Capacity (4hr interval) | Notes |
|--------|-----|-----|-------------------------------|-------------------------------|-------|
| **Raspberry Pi 4** (4GB) | 4GB | ARM Cortex-A72 (4 cores) | **Up to 150 cameras** | **Up to 600 cameras** | Recommended for most deployments |
| **Raspberry Pi 5** (8GB) | 8GB | ARM Cortex-A76 (4 cores) | **Up to 250 cameras** | **Up to 1000 cameras** | Best price/performance |
| **Intel NUC / x86 Mini PC** | 8GB+ | Any modern CPU | **Up to 500 cameras** | **Up to 2000 cameras** | High-capacity single-site |
| **Standard Server** | 16GB+ | Multi-core CPU | **1000+ cameras** | **4000+ cameras** | Multi-site centralized |

**Capacity Calculation Logic**:
- **Single camera inspection time**: ~5-10 seconds (RTSP connect + frame capture + CV analysis)
- **Inspection window**: Must complete all cameras before next cycle
- **Example (1-hour interval, Raspberry Pi 4)**:
  - Available time: 3600 seconds
  - Per-camera time: 10 seconds (conservative)
  - Safety margin: 60% utilization (leave room for network delays, retries)
  - **Capacity**: (3600 × 0.6) / 10 = **216 cameras** → Recommended: **150 cameras**
- **Example (4-hour interval, Raspberry Pi 4)**:
  - Available time: 14,400 seconds
  - **Capacity**: (14,400 × 0.6) / 10 = **864 cameras** → Recommended: **600 cameras**

**Performance Targets (Raspberry Pi 4, 4GB)**:
- **Inspect 1 camera**: ~5-10 seconds (including RTSP connect, frame capture, analysis)
- **Inspect 50 cameras**: ~5-8 minutes (sequential processing)
- **Inspect 150 cameras**: ~15-25 minutes (batched, sequential)
- **CPU usage**: <5% idle, 40-60% during inspection cycle, then back to idle
- **Memory usage**: ~500MB baseline + 50MB per concurrent camera (batches of 5)
- **Power consumption**: ~3W idle, ~12W during inspection (Raspberry Pi 4)

**Typical Inspection Intervals**:
- **Standard**: 1-4 hours (most customers)
- **High-frequency**: 15-30 minutes (critical infrastructure, high-value assets)
- **Low-frequency**: 6-12 hours (low-priority cameras, cost optimization)
- **Custom**: Configurable per customer (5 minutes to 24 hours)

**Why No GPU/ML**:
- ✅ **Raspberry Pi Compatibility**: No CUDA/cuDNN dependencies
- ✅ **Low Power**: <15W total power consumption on RPi
- ✅ **Traditional CV is Sufficient**: ORB features and SSIM are fast and accurate for view change detection
- ✅ **Simpler Deployment**: No model files, no TensorFlow/PyTorch dependencies
- ✅ **Cost-Effective**: Can run on $50 Raspberry Pi instead of $500+ GPU device

---

## Inspection Interval Strategy & Advantages

### Why Long Intervals (1-4 hours) Work Best

**Camera health issues develop slowly**:
- 🎥 **Physical problems** (camera moved, lens dirty, cable loose): Persist for hours/days
- 🌐 **Network issues** (router down, switch failure): Don't resolve in minutes
- 💡 **Lighting changes**: Day/night transitions are gradual (dawn/dusk over 30+ min)
- 🔌 **Power failures**: Either camera is up or down, no need for minute-by-minute checks

**Immediate detection not critical**:
- If a camera goes offline at 2:00 PM and inspection runs at 3:00 PM (1-hour interval), the 1-hour delay is acceptable
- Security footage is typically reviewed after-the-fact, not in real-time
- Operators check dashboard periodically, not continuously

**Massive capacity increase**:
- **1-hour interval**: Raspberry Pi 4 can handle **150 cameras** (vs. 20 if checking every 5 minutes)
- **4-hour interval**: Same device can handle **600 cameras**
- **Cost savings**: One $50 RPi replaces what would need 10-30 devices with continuous monitoring

**Resource efficiency**:
- Worker is **idle 95%+ of time**, consuming only ~3W
- During 15-minute inspection window, CPU spikes to 40-60%, then returns to idle
- Low heat generation, silent operation, minimal wear on SD card

### Configurable Per-Customer

```python
# Low-priority parking lot cameras (100 cameras, 4-hour checks)
inspection_config = {
    "inspection_interval_minutes": 240,  # 4 hours
    "camera_capacity": 600  # Raspberry Pi 4 can handle
}

# Critical infrastructure (20 cameras, 15-minute checks)
inspection_config = {
    "inspection_interval_minutes": 15,
    "camera_capacity": 20  # More frequent = lower capacity
}

# Standard deployment (150 cameras, 1-hour checks) - MOST COMMON
inspection_config = {
    "inspection_interval_minutes": 60,  # 1 hour
    "camera_capacity": 150
}
```

### False Alarm Reduction

**Day/night transitions**:
- With 1-hour intervals, we capture fewer "edge case" frames during dawn/dusk
- View change detection compares structure (not lighting), so day/night differences are ignored
- Fewer false positives from transient lighting changes

**Network blips**:
- Single dropped frame or 5-second network hiccup won't trigger alert
- Only persistent issues (offline for full hour) are reported

---

### Backend API

**Stack**:
- FastAPI (Python 3.11)
- PostgreSQL 15
- SQLAlchemy ORM
- Azure Blob Storage
- SendGrid Email Service

### Frontend Dashboard

**Stack**:
- React 18 + TypeScript
- Vite build tool
- Axios for API calls
- TailwindCSS (matching IntelliOptics 2.0 theme)
- **No auto-refresh** (manual refresh only)

---

## Implementation Checklist

### Phase 1: Database & Backend (Week 1)
- [ ] Create database tables:
  - [ ] `inspection_config`
  - [ ] `inspection_runs`
  - [ ] `camera_alerts`
  - [ ] Update `cameras` table (baseline image fields)
  - [ ] Update `camera_health` table (view change fields)
- [ ] Create backend routers:
  - [ ] `inspection_config.py`
  - [ ] `camera_inspection.py`
- [ ] Add Pydantic schemas for new models

### Phase 2: Inspection Worker (Week 2)
- [ ] Build `camera_inspection_worker.py`:
  - [ ] RTSP connection testing
  - [ ] FPS measurement
  - [ ] Image quality metrics
  - [ ] View change detection (SSIM + ORB)
  - [ ] Alert condition checking
- [ ] Integrate with Azure Blob Storage (baseline images)
- [ ] Add email alerting (SendGrid)
- [ ] Deploy worker as Docker container

### Phase 3: Frontend Dashboard (Week 3)
- [ ] Create `CameraInspectionPage.tsx`:
  - [ ] Summary stats cards
  - [ ] Camera list grouped by hub
  - [ ] Health metrics display
  - [ ] Alert display
  - [ ] Mute alerts functionality
  - [ ] Acknowledge alerts
  - [ ] Update baseline image
- [ ] Add route to App.tsx
- [ ] Update navigation menu

### Phase 4: Configuration & Testing (Week 4)
- [ ] Create inspection config settings page
- [ ] Test view change detection accuracy
- [ ] Test alert muting/unmuting
- [ ] Test email delivery
- [ ] Performance testing (100+ cameras)
- [ ] Documentation

---

## Success Metrics

1. **Inspection Accuracy**:
   - View change detection: >95% true positive rate, <5% false positive rate
   - Connection status: 100% accurate

2. **Performance**:
   - Inspect 100 cameras in <5 minutes
   - Dashboard loads in <2 seconds

3. **Reliability**:
   - Worker uptime: >99.9%
   - Alerts delivered within 1 minute of detection

4. **User Experience**:
   - Clear, actionable alerts
   - Easy mute/acknowledge workflow
   - Intuitive dashboard layout

---

## Raspberry Pi Deployment Guide

### Prerequisites
```bash
# On Raspberry Pi OS (64-bit recommended)
sudo apt update
sudo apt install -y python3-pip python3-venv libopencv-dev python3-opencv

# Create virtual environment
python3 -m venv /opt/intellioptics/venv
source /opt/intellioptics/venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install opencv-python-headless  # Lighter than full opencv-python
pip install scikit-image numpy pillow
pip install azure-storage-blob
pip install sendgrid
pip install requests
```

### Deploy Worker
```bash
# Copy worker files
scp -r cloud/worker/camera_inspection_worker.py pi@raspberrypi.local:/opt/intellioptics/

# Create systemd service
sudo nano /etc/systemd/system/camera-inspection.service
```

**Service file**:
```ini
[Unit]
Description=IntelliOptics Camera Inspection Worker
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/opt/intellioptics
Environment="AZURE_STORAGE_CONNECTION_STRING=<your_connection_string>"
Environment="API_URL=http://your-backend:8000"
ExecStart=/opt/intellioptics/venv/bin/python camera_inspection_worker.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Start service**:
```bash
sudo systemctl daemon-reload
sudo systemctl enable camera-inspection
sudo systemctl start camera-inspection
sudo systemctl status camera-inspection
```

### Performance Optimization for Raspberry Pi

**1. Reduce RTSP timeout**:
```python
# In camera_inspection_worker.py
cap = cv2.VideoCapture(rtsp_url)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce buffer
cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)  # 5 sec timeout
```

**2. Process cameras in batches**:
```python
# Inspect 5 cameras at a time to avoid memory issues
BATCH_SIZE = 5
for i in range(0, len(cameras), BATCH_SIZE):
    batch = cameras[i:i+BATCH_SIZE]
    process_batch(batch)
```

**3. Enable hardware acceleration (if available)**:
```bash
# Check for hardware video decode support
vcgencmd get_config int | grep decode

# If available, OpenCV will automatically use it
```

**4. Monitor resource usage**:
```bash
# Install monitoring tools
sudo apt install htop

# Watch CPU/memory during inspection
htop
```

---

---

## Summary: Capacity & Cost Benefits

### Inspection Interval Impact on Capacity

| Inspection Interval | Raspberry Pi 4 Capacity | Raspberry Pi 5 Capacity | Cost per Camera |
|---------------------|-------------------------|-------------------------|-----------------|
| **15 minutes** (high-frequency) | 20 cameras | 40 cameras | ~$2.50/camera |
| **1 hour** (standard) | **150 cameras** | **250 cameras** | **~$0.33/camera** |
| **4 hours** (low-frequency) | **600 cameras** | **1000 cameras** | **~$0.08/camera** |

**Key Takeaway**: Longer inspection intervals dramatically increase camera capacity per device.

### Example Deployments

**Small Site (50 cameras, 1-hour interval)**:
- Hardware: 1× Raspberry Pi 4 ($50)
- Capacity utilization: 33% (50/150)
- Power: ~12W peak, ~3W idle
- Cost: **$1/camera** (one-time hardware)

**Medium Site (300 cameras, 4-hour interval)**:
- Hardware: 1× Raspberry Pi 5 ($80)
- Capacity utilization: 30% (300/1000)
- Power: ~15W peak, ~4W idle
- Cost: **$0.27/camera** (one-time hardware)

**Large Site (1000 cameras, 4-hour interval)**:
- Hardware: 2× Raspberry Pi 5 ($160 total)
- Capacity utilization: 50% (500 cameras each)
- Power: ~30W total peak, ~8W idle
- Cost: **$0.16/camera** (one-time hardware)

### Why This Works

✅ **Camera health changes slowly** - 1-4 hour intervals are sufficient for detection
✅ **Massive capacity per device** - One RPi handles hundreds of cameras
✅ **Ultra-low cost** - $50-80 device vs. $500+ GPU server
✅ **Low power** - <15W vs. 200W+ for GPU server
✅ **Silent operation** - No fans, fanless RPi
✅ **Scalable** - Add more RPis as deployments grow

---

**Created**: 2026-01-13
**Updated**: 2026-01-13
**Status**: 📋 Ready for Implementation
**Key Changes**:
- ✅ CPU-only implementation (no GPU/ML)
- ✅ Raspberry Pi compatible with **massive capacity** (150-1000 cameras per device)
- ✅ No auto-refresh on dashboard (updates on login only)
- ✅ Traditional computer vision for view change detection
- ✅ Long inspection intervals (1-4 hours) for optimal capacity and cost

**Next Step**: Review and approve implementation plan, then begin Phase 1
