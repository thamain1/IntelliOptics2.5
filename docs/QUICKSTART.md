# IntelliOptics 2.0 - Quick Start Guide

Get IntelliOptics 2.0 running in under 15 minutes.

---

## Prerequisites

- **Docker** and **Docker Compose** installed
- **Azure Account** (for Blob Storage)
- **SendGrid Account** (for email alerts)
- **ONNX Models** ready for your detectors

---

## Step 1: Configure Environment Variables

### Edge Deployment

```bash
cd "C:\intellioptics-2.0\edge"
cp .env.template .env
```

Edit `.env` and set these **required** variables:

```bash
# Required
INTELLIOPTICS_API_TOKEN=<get-from-central-web-app>
CENTRAL_WEB_APP_URL=https://your-central-app.com
POSTGRES_PASSWORD=<generate-secure-password>
SENDGRID_API_KEY=SG.<your-key>
SENDGRID_FROM_EMAIL=alerts@yourdomain.com
SENDGRID_ALERT_RECIPIENTS=team@yourdomain.com
EDGE_DEVICE_ID=edge-001
EDGE_DEVICE_NAME=Factory A - Line 1
```

### Cloud Deployment

```bash
cd "C:\intellioptics-2.0\cloud"
cp .env.template .env
```

Edit `.env` and set these **required** variables:

```bash
# Required
POSTGRES_PASSWORD=<generate-secure-password>
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
SENDGRID_API_KEY=SG.<your-key>
SENDGRID_FROM_EMAIL=alerts@yourdomain.com
API_SECRET_KEY=<generate-random-32-char-string>

# Optional but recommended
SERVICE_BUS_CONN=Endpoint=sb://...
BLOB_CONTAINER_NAME=intellioptics-images
```

**Generate secure passwords/keys:**
```bash
# PowerShell (Windows)
-join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | ForEach-Object {[char]$_})

# Linux/Mac
openssl rand -base64 32
```

---

## Step 2: Set Up Azure Resources

### Create Storage Account

```bash
# Azure CLI
az storage account create \
  --name intelliopticsstorage \
  --resource-group intellioptics-rg \
  --location eastus \
  --sku Standard_LRS

# Get connection string
az storage account show-connection-string \
  --name intelliopticsstorage \
  --resource-group intellioptics-rg
```

### Create Blob Container

```bash
az storage container create \
  --name intellioptics-images \
  --connection-string "<your-connection-string>"
```

### Create Service Bus (Optional)

```bash
az servicebus namespace create \
  --name intellioptics-sb \
  --resource-group intellioptics-rg \
  --location eastus

az servicebus queue create \
  --namespace-name intellioptics-sb \
  --name image-queries \
  --resource-group intellioptics-rg
```

---

## Step 3: Configure Detectors

Edit `edge/config/edge-config.yaml`:

```yaml
detectors:
  det_quality_check_001:
    detector_id: det_quality_check_001
    name: "Quality Check - Main Line"
    edge_inference_config: default
    confidence_threshold: 0.85  # Adjust based on your needs
    mode: BINARY
    class_names: ["pass", "defect"]
    hrm_enabled: false
```

---

## Step 4: Add ONNX Models

Create model directories:

```bash
# Windows PowerShell
mkdir "C:\opt\intellioptics\models\det_quality_check_001\primary\1"
mkdir "C:\opt\intellioptics\models\det_quality_check_001\oodd\1"

# Linux/Mac
mkdir -p /opt/intellioptics/models/det_quality_check_001/primary/1
mkdir -p /opt/intellioptics/models/det_quality_check_001/oodd/1
```

Copy your models:

```bash
# Copy Primary model
cp your-primary-model.onnx /opt/intellioptics/models/det_quality_check_001/primary/1/model.buf

# Copy OODD model
cp your-oodd-model.onnx /opt/intellioptics/models/det_quality_check_001/oodd/1/model.buf
```

---

## Step 5: Deploy Cloud (Central Web App)

```bash
cd "C:\intellioptics-2.0\cloud"
docker-compose up -d
```

**Wait for services to start** (~30 seconds):

```bash
# Check status
docker-compose ps

# View logs
docker-compose logs -f backend
```

**Verify deployment:**

```bash
curl http://localhost:8000/health
# Expected: {"status":"healthy"}
```

**Access Web UI:**
- Open browser: http://localhost:3000
- Default view: Review Queue (for human labeling)

---

## Step 6: Deploy Edge

```bash
cd "C:\intellioptics-2.0\edge"
docker-compose up -d
```

**Wait for services to start** (~60 seconds - models need to load):

```bash
# Check status
docker-compose ps

# View logs
docker-compose logs -f edge-api
docker-compose logs -f inference
```

**Verify deployment:**

```bash
# Check nginx gateway
curl http://localhost:30101/health

# Check edge API
curl http://localhost:8718/health

# Check inference service
curl http://localhost:8001/health

# List available detectors
curl http://localhost:30101/v1/detectors
```

---

## Step 7: Test Image Submission

```bash
# Submit test image
curl -X POST "http://localhost:30101/v1/image-queries?detector_id=det_quality_check_001" \
  -F "image=@test-image.jpg"
```

**Expected response:**

```json
{
  "query_id": "qry_abc123",
  "label": 0,
  "confidence": 0.92,
  "raw_primary_confidence": 0.95,
  "oodd_in_domain_score": 0.97,
  "is_out_of_domain": false,
  "result": "pass"
}
```

**If confidence < 0.85** (threshold), image escalates to cloud:
- Check cloud logs: `docker-compose logs backend`
- View in web UI: http://localhost:3000 (Review Queue)
- Email alert sent to `SENDGRID_ALERT_RECIPIENTS`

---

## Step 8: Monitor

### View Logs

```bash
# Edge logs
cd "C:\intellioptics-2.0\edge"
docker-compose logs -f edge-api
docker-compose logs -f inference

# Cloud logs
cd "C:\intellioptics-2.0\cloud"
docker-compose logs -f backend
docker-compose logs -f worker
```

### Check Model Cache

```bash
curl http://localhost:8001/models
```

### Check Escalations

```bash
curl http://localhost:8000/escalations
```

---

## Troubleshooting

### Issue: Models not loading

```bash
# Check model files exist
ls /opt/intellioptics/models/det_quality_check_001/primary/1/

# Check inference logs
docker-compose logs inference | grep "model"
```

### Issue: Edge API returns 503

```bash
# Check inference service health
curl http://localhost:8001/health

# Restart inference service
docker-compose restart inference
```

### Issue: Escalations not working

```bash
# Check cloud connectivity
curl https://your-central-app.com/health

# Verify API token
echo $INTELLIOPTICS_API_TOKEN

# Check edge logs for escalation attempts
docker-compose logs edge-api | grep "escalation"
```

### Issue: SendGrid emails not sending

```bash
# Verify SendGrid API key
curl -X GET "https://api.sendgrid.com/v3/scopes" \
  -H "Authorization: Bearer $SENDGRID_API_KEY"

# Check backend logs
docker-compose logs backend | grep "sendgrid"
```

---

## What's Next?

### Production Deployment

- [ ] Deploy cloud to Azure Container Instances or Azure App Service
- [ ] Configure HTTPS with SSL certificates (Let's Encrypt)
- [ ] Set up Azure Monitor for logging and alerts
- [ ] Configure backup for PostgreSQL database
- [ ] Set up CI/CD pipeline for updates

### Add More Detectors

1. Create model directories for new detector
2. Copy ONNX models
3. Add detector config to `edge-config.yaml`
4. Restart edge-api: `docker-compose restart edge-api`

### Enable RTSP Camera Streaming

Edit `edge-config.yaml`:

```yaml
streams:
  cam_001:
    rtsp_url: "rtsp://camera-ip:554/stream"
    detector_id: det_quality_check_001
    frame_interval: 1.0  # Sample every 1 second
```

Restart edge-api to start streaming.

### Phase 2: HRM AI Integration

See `docs/HRM-TRAINING.md` for complete guide on training explainable AI models.

---

## Support

For issues or questions:
1. Check `README.md` for detailed documentation
2. Review `docs/ARCHITECTURE.md` for system design
3. Check logs: `docker-compose logs`

---

## Summary

You now have:
- ✅ Edge deployment processing images locally
- ✅ Confidence-based escalation (only questionable images go to cloud)
- ✅ OODD ground truth validation
- ✅ Central web app for human review
- ✅ SendGrid email alerts for escalations
- ✅ Detector-centric configuration

**Total deployment time: ~15 minutes**
