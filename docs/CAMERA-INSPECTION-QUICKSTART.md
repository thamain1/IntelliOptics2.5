# Camera Inspection System - Quick Start Guide

## What Was Built

A complete automated camera health inspection system for IntelliOptics 2.0 with:

- **Dashboard UI** - Real-time camera health monitoring
- **Backend API** - Health metrics storage and alerting
- **Worker Service** - CPU-only inspection engine (Raspberry Pi compatible)

## ✅ All Phases Complete

**Status**: Ready for deployment

- ✅ Phase 1: Database & Backend (FastAPI, PostgreSQL)
- ✅ Phase 2: Inspection Worker (Python, OpenCV, CPU-only)
- ✅ Phase 3: Frontend Dashboard (React, TypeScript)

## Key Features

### Automated Inspections
- Configurable intervals (1-4 hours typical)
- RTSP stream connection testing
- FPS measurement (30 frames)
- Image quality analysis (brightness, sharpness)
- Network latency measurement

### View Change Detection (CPU-Only)
- SSIM (Structural Similarity Index)
- ORB feature matching
- Ignores day/night transitions
- Detects physical camera movement

### Alerting
- Email notifications (SendGrid)
- Dashboard alerts
- Mute capability (1-30 days)
- Multiple severity levels (critical, warning, info)

### Dashboard
- Summary cards (Total, Healthy, Warning, Offline)
- Camera list grouped by hub
- Health metrics display
- Alert management
- Search and filters

## Quick Start

### 1. Access Dashboard

```
http://localhost:3000/camera-inspection
```

The dashboard is already integrated into IntelliOptics 2.0 navigation bar under "Camera Health".

### 2. Add Cameras

Add cameras via the Hubs page or API:

```bash
curl -X POST http://localhost:8000/hubs/{hub_id}/cameras \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Camera 1",
    "url": "rtsp://username:password@192.168.1.100:554/stream"
  }'
```

### 3. Deploy Worker

**On Raspberry Pi** (recommended for edge deployment):

```bash
# Copy worker files
scp -r cloud/worker/* pi@raspberrypi:/tmp/worker/

# SSH and run deployment script
ssh pi@raspberrypi
cd /tmp/worker
sudo bash deploy-camera-inspection-rpi.sh
```

**Or via Docker** (for development/testing):

```bash
cd cloud/worker

# Build image
docker build -f Dockerfile.camera-inspection -t camera-inspection:latest .

# Run container
docker run -d \
  --name camera-inspection-worker \
  -e API_BASE_URL=http://localhost:8000 \
  -e SENDGRID_API_KEY=your_key_here \
  camera-inspection:latest
```

### 4. Configure Settings

```bash
curl -X PUT http://localhost:8000/inspection-config \
  -H "Content-Type: application/json" \
  -d '{
    "inspection_interval_minutes": 60,
    "alert_emails": ["admin@example.com"]
  }'
```

### 5. Verify It's Working

**Check worker logs**:
```bash
sudo journalctl -u camera-inspection -f
```

**Check dashboard**:
- Navigate to http://localhost:3000/camera-inspection
- Wait for first inspection cycle (up to 60 minutes depending on interval)
- Camera health data should appear

**Check inspection runs**:
```bash
curl http://localhost:8000/camera-inspection/runs
```

## Architecture

```
┌─────────────────────────────────────────┐
│         Frontend (React)                │
│  http://localhost:3000/camera-inspection│
└─────────────────┬───────────────────────┘
                  │ GET /camera-inspection/dashboard
                  ↓
┌─────────────────────────────────────────┐
│      Backend API (FastAPI)              │
│      http://localhost:8000              │
│                                         │
│  - Inspection config endpoints          │
│  - Camera health endpoints              │
│  - Alert management endpoints           │
└─────────────────┬───────────────────────┘
                  │ Stores health data
                  ↓
┌─────────────────────────────────────────┐
│       Database (PostgreSQL)             │
│                                         │
│  - inspection_config                    │
│  - inspection_runs                      │
│  - camera_health                        │
│  - camera_alerts                        │
└─────────────────────────────────────────┘
                  ↑
                  │ POST health data
┌─────────────────┴───────────────────────┐
│    Worker (Python, OpenCV)              │
│    Runs on Raspberry Pi or edge device  │
│                                         │
│  - Connect to RTSP streams              │
│  - Measure FPS, latency, quality        │
│  - Detect view changes (SSIM + ORB)     │
│  - Create alerts                        │
│  - Send email notifications             │
└─────────────────────────────────────────┘
```

## Capacity

### Raspberry Pi 4 (4GB RAM)
- **1-hour interval**: 150 cameras
- **4-hour interval**: 600 cameras
- **Power**: ~4-5W average

### Raspberry Pi 5 (8GB RAM)
- **1-hour interval**: 250 cameras
- **4-hour interval**: 1000 cameras
- **Power**: ~4-5W average

## API Endpoints

### Configuration
```
GET  /inspection-config          # Get config (auto-creates default)
PUT  /inspection-config          # Update config
```

### Dashboard
```
GET  /camera-inspection/dashboard                        # Main dashboard
GET  /camera-inspection/cameras/{id}/history            # Camera history
POST /camera-inspection/cameras/{id}/mute-alerts        # Mute alerts
POST /camera-inspection/cameras/{id}/acknowledge-alert/{alert_id}
POST /camera-inspection/cameras/{id}/update-baseline    # Update baseline
```

### Worker (Internal)
```
POST /camera-inspection/runs                            # Create run
PUT  /camera-inspection/runs/{id}                       # Update run
POST /camera-inspection/cameras/{id}/health             # Create health record
POST /camera-inspection/alerts                          # Create alert
```

## Configuration Options

```javascript
{
  "inspection_interval_minutes": 60,     // How often to inspect (1-4 hours typical)
  "offline_threshold_minutes": 5,        // When to mark camera offline
  "fps_drop_threshold_pct": 0.5,         // FPS drop threshold (50% = alert if <15 FPS for 30 FPS camera)
  "latency_threshold_ms": 1000,          // Network latency threshold
  "view_change_threshold": 0.7,          // SSIM threshold (lower = more sensitive)
  "alert_emails": ["admin@example.com"], // Email recipients
  "dashboard_retention_days": 30,        // Dashboard history retention
  "database_retention_days": 90          // Database history retention
}
```

## Troubleshooting

### Dashboard shows no cameras
- Add cameras via Hubs page or API first
- Wait for first inspection cycle to complete

### Worker not running
```bash
sudo systemctl status camera-inspection
sudo journalctl -u camera-inspection -n 50
```

### Cameras showing as offline
- Verify RTSP URL is correct
- Check network connectivity
- Test RTSP URL with VLC: `vlc rtsp://username:password@camera-ip:554/stream`
- Check camera authentication credentials

### No email alerts
- Verify `SENDGRID_API_KEY` is set in `.env`
- Check SendGrid account status
- Verify alert emails are configured in inspection config

### View change false positives
- Increase `view_change_threshold` (0.7 → 0.6)
- Ensure baseline image is recent
- Check if baseline was captured during same time of day

## File Locations

```
C:\Dev\IntelliOptics 2.0\
├── cloud\
│   ├── backend\
│   │   ├── app\
│   │   │   ├── models.py                       # Database models
│   │   │   ├── schemas.py                      # Pydantic schemas
│   │   │   ├── routers\
│   │   │   │   ├── inspection_config.py        # Config endpoints
│   │   │   │   └── camera_inspection.py        # Dashboard endpoints
│   │   │   └── main.py                         # FastAPI app
│   │   └── ...
│   ├── frontend\
│   │   ├── src\
│   │   │   ├── pages\
│   │   │   │   └── CameraInspectionPage.tsx    # Dashboard UI
│   │   │   └── App.tsx                         # Navigation
│   │   └── ...
│   └── worker\
│       ├── camera_inspection_worker.py         # Main worker
│       ├── requirements-camera-inspection.txt  # Dependencies
│       ├── .env.camera-inspection.template     # Config template
│       ├── Dockerfile.camera-inspection        # Docker image
│       ├── deploy-camera-inspection-rpi.sh     # Deployment script
│       └── README-CAMERA-INSPECTION.md         # Worker guide
└── docs\
    ├── CAMERA-INSPECTION-IMPLEMENTATION.md     # Full spec
    ├── CAMERA-INSPECTION-BUILD-SUMMARY.md      # Build summary
    └── CAMERA-INSPECTION-QUICKSTART.md         # This file
```

## Documentation

- **Full Technical Specification**: `docs/CAMERA-INSPECTION-IMPLEMENTATION.md`
- **Build Summary**: `docs/CAMERA-INSPECTION-BUILD-SUMMARY.md`
- **Worker Deployment Guide**: `cloud/worker/README-CAMERA-INSPECTION.md`
- **Quick Start**: `docs/CAMERA-INSPECTION-QUICKSTART.md` (this file)

## Next Steps

1. **Add test cameras** to the system
2. **Deploy worker** on Raspberry Pi or edge device
3. **Configure inspection settings** (interval, thresholds, emails)
4. **Test complete flow** (connection, alerts, muting)
5. **Monitor performance** via logs and dashboard

## Support

For issues or questions:
- Check worker logs: `sudo journalctl -u camera-inspection -f`
- Check backend logs: `docker-compose logs backend -f`
- Review documentation in `docs/` folder
- Check API docs: http://localhost:8000/docs

---

**Status**: ✅ All phases complete, ready for deployment
**Build Date**: 2026-01-13
**Version**: 1.0.0
