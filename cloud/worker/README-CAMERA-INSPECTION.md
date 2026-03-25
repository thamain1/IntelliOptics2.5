# Camera Inspection Worker

CPU-only Python worker for automated camera health inspections. Designed to run on edge devices (Raspberry Pi, low-power servers) with configurable inspection intervals.

## Features

- **RTSP Stream Connection**: Connects to RTSP camera streams for health checks
- **FPS Measurement**: Measures actual frame rate vs. expected
- **Image Quality Analysis**: Calculates brightness and sharpness scores
- **View Change Detection**: Detects physical camera movement using SSIM + ORB features
- **Network Metrics**: Measures connection latency
- **Alert Generation**: Creates alerts for offline cameras, FPS drops, view changes
- **Email Notifications**: Sends email alerts via SendGrid
- **Configurable Intervals**: Runs inspections every 1-4 hours (configurable per customer)
- **Raspberry Pi Compatible**: CPU-only, no GPU/ML dependencies

## System Requirements

### Minimum Hardware:
- **Raspberry Pi 4 (4GB RAM)**: Up to 150 cameras (1hr interval)
- **Raspberry Pi 5 (8GB RAM)**: Up to 250 cameras (1hr interval)
- **x86_64 Server**: Higher capacity depending on specs

### Software:
- Python 3.11+
- OpenCV (headless)
- 500MB RAM per worker process
- ~10MB disk space per camera baseline image

## Installation

### 1. Install Dependencies

```bash
cd "C:\Dev\IntelliOptics 2.0\cloud\worker"

# Install Python dependencies
pip install -r requirements-camera-inspection.txt
```

### 2. Configure Environment

```bash
# Copy template
cp .env.camera-inspection.template .env

# Edit .env with your settings
nano .env
```

**Required Environment Variables**:
```bash
API_BASE_URL=http://localhost:8000  # Backend API URL
SENDGRID_API_KEY=SG.xxxxx           # SendGrid API key for email alerts
ALERT_FROM_EMAIL=alerts@intellioptics.com
AZURE_BLOB_CONNECTION_STRING=xxx    # For baseline image storage
AZURE_BLOB_CONTAINER=camera-baselines
```

### 3. Run Worker

```bash
python camera_inspection_worker.py
```

## Docker Deployment

### Build Image

```bash
docker build -f Dockerfile.camera-inspection -t intellioptics-camera-inspection:latest .
```

### Run Container

```bash
docker run -d \
  --name camera-inspection-worker \
  --restart unless-stopped \
  -e API_BASE_URL=http://backend:8000 \
  -e SENDGRID_API_KEY=your_key_here \
  -e ALERT_FROM_EMAIL=alerts@intellioptics.com \
  intellioptics-camera-inspection:latest
```

## Raspberry Pi Deployment

### Option 1: Systemd Service (Recommended)

Create `/etc/systemd/system/camera-inspection.service`:

```ini
[Unit]
Description=IntelliOptics Camera Inspection Worker
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/opt/intellioptics/worker
ExecStart=/usr/bin/python3 /opt/intellioptics/worker/camera_inspection_worker.py
Restart=always
RestartSec=10
EnvironmentFile=/opt/intellioptics/worker/.env

[Install]
WantedBy=multi-user.target
```

**Enable and start service**:
```bash
sudo systemctl enable camera-inspection
sudo systemctl start camera-inspection
sudo systemctl status camera-inspection
```

### Option 2: Docker Compose

Add to `docker-compose.yml`:

```yaml
services:
  camera-inspection-worker:
    build:
      context: ./worker
      dockerfile: Dockerfile.camera-inspection
    restart: unless-stopped
    environment:
      - API_BASE_URL=http://backend:8000
      - SENDGRID_API_KEY=${SENDGRID_API_KEY}
      - ALERT_FROM_EMAIL=${ALERT_FROM_EMAIL}
      - AZURE_BLOB_CONNECTION_STRING=${AZURE_BLOB_CONNECTION_STRING}
      - AZURE_BLOB_CONTAINER=camera-baselines
    depends_on:
      - backend
```

## Configuration

### Inspection Intervals

Set via Backend API:

```bash
curl -X PUT http://localhost:8000/inspection-config \
  -H "Content-Type: application/json" \
  -d '{
    "inspection_interval_minutes": 60,
    "offline_threshold_minutes": 5,
    "fps_drop_threshold_pct": 0.5,
    "latency_threshold_ms": 1000,
    "view_change_threshold": 0.7,
    "alert_emails": ["admin@example.com"],
    "dashboard_retention_days": 30,
    "database_retention_days": 90
  }'
```

### Alert Types

| Type | Severity | Trigger |
|------|----------|---------|
| `offline` | critical | Camera connection fails |
| `fps_drop` | warning | FPS < 50% of expected |
| `view_change` | critical | Camera view physically changed (SSIM < threshold) |
| `quality_degradation` | warning | Low brightness or sharpness |
| `network_issue` | warning | Latency > threshold |

## Capacity Planning

### Inspection Time Per Camera:
- **Connection**: 2-3 seconds
- **FPS Measurement**: 1-2 seconds (30 frames)
- **Quality Analysis**: <0.5 seconds
- **View Change Detection**: 1-2 seconds (if baseline exists)
- **Total**: ~5-7 seconds per camera

### Capacity Estimates:

**1-Hour Inspection Interval**:
- Raspberry Pi 4 (4GB): **150 cameras** (150 × 7s = 1050s = 17.5 min)
- Raspberry Pi 5 (8GB): **250 cameras** (250 × 7s = 1750s = 29 min)

**4-Hour Inspection Interval**:
- Raspberry Pi 4 (4GB): **600 cameras**
- Raspberry Pi 5 (8GB): **1000 cameras**

**Power Consumption**:
- Idle: ~3W
- During Inspection: ~12W
- Average (1hr interval): ~4-5W

## View Change Detection Algorithm

Uses **CPU-only traditional computer vision** (no ML):

1. **SSIM (Structural Similarity Index)**:
   - Compares grayscale images pixel-by-pixel
   - Score: 1.0 = identical, 0.0 = completely different
   - Threshold: 0.7 (configurable)
   - Ignores minor lighting changes (day/night OK)

2. **ORB Feature Matching**:
   - Detects keypoints in both images
   - Matches features between baseline and current frame
   - Low match ratio (<30%) = view changed
   - More robust to lighting changes than SSIM alone

**Why This Works**:
- Camera physically moved → Major structural changes → SSIM < threshold
- Day/night transition → Minor pixel changes → SSIM still > threshold
- Lighting changes → ORB features remain similar → No false positive

## Troubleshooting

### Worker Not Starting

```bash
# Check logs
sudo journalctl -u camera-inspection -f

# Or for Docker
docker logs camera-inspection-worker
```

### Cameras Showing as Offline

1. Verify RTSP URL is correct
2. Check network connectivity to cameras
3. Increase connection timeout in code (default 10s)
4. Check camera authentication (URL should include credentials)

### High Memory Usage

- Reduce baseline image cache size
- Increase inspection interval
- Use smaller resolution for baseline images (640x480 recommended)

### View Change False Positives

- Increase `view_change_threshold` (default 0.7 → try 0.6)
- Check if baseline image is from same time of day
- Ensure baseline image is recent (not months old)

## Monitoring

### Health Check

Worker automatically creates inspection runs visible in dashboard:

```bash
curl http://localhost:8000/camera-inspection/runs
```

### Logs

```bash
# Systemd
sudo journalctl -u camera-inspection --since today

# Docker
docker logs camera-inspection-worker --tail 100 -f
```

## Development

### Running Locally

```bash
# Set environment variables
export API_BASE_URL=http://localhost:8000
export SENDGRID_API_KEY=your_key

# Run worker
python camera_inspection_worker.py
```

### Testing Single Camera

Modify `camera_inspection_worker.py` and add test function:

```python
async def test_single_camera():
    worker = CameraInspectionWorker()
    config = await worker.get_inspection_config()

    test_camera = {
        "id": "test-camera-id",
        "name": "Test Camera",
        "url": "rtsp://username:password@192.168.1.100:554/stream"
    }

    health_data = await worker.inspect_camera(test_camera, config)
    print(health_data)

if __name__ == "__main__":
    asyncio.run(test_single_camera())
```

## API Integration

Worker uses these backend endpoints:

- `GET /inspection-config` - Get configuration
- `GET /hubs` - Get all cameras
- `POST /camera-inspection/runs` - Create inspection run
- `PUT /camera-inspection/runs/{id}` - Update run status
- `POST /camera-inspection/cameras/{id}/health` - Create health record
- `POST /camera-inspection/alerts` - Create alert

## Future Enhancements

- [ ] Azure Blob Storage integration for baseline images
- [ ] Baseline image auto-update (schedule or manual trigger)
- [ ] Historical uptime calculation from database
- [ ] GPU acceleration option for view change detection (optional)
- [ ] Multi-threaded camera inspection (process multiple cameras in parallel)
- [ ] Webhook support for real-time alerting
- [ ] Integration with camera motion detection (reduce false positives)

## License

Proprietary - IntelliOptics 2.0
