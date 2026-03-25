# IntelliOptics 2.0 - Next Steps Action Plan

**Status**: Code complete, ready for testing and deployment
**Date**: January 6, 2026

---

## Phase 1: Pre-Deployment Testing (30 minutes)

### Step 1.1: Test Container Builds

Verify all Docker images build successfully:

```bash
cd "C:\Dev\IntelliOptics 2.0"
bash test-builds.sh
```

**Expected result**: All 6 containers build without errors
- ✅ Edge nginx
- ✅ Edge API
- ✅ Edge inference
- ✅ Cloud nginx
- ✅ Cloud backend
- ✅ Cloud frontend

**If build fails**: Check the error message, likely missing dependencies or syntax errors.

### Step 1.2: Review Code Dependencies

Check if IntelliOptics SDK is needed:

```bash
# Search for SDK usage in edge-api
cd "C:\Dev\IntelliOptics 2.0\edge\edge-api\app"
grep -r "from intellioptics" . || echo "No SDK imports found"
grep -r "import intellioptics" . || echo "No SDK imports found"
```

**Action**:
- If SDK imports found → Uncomment line 44 in `edge/edge-api/requirements.txt`
- If no imports → Continue without SDK

### Step 1.3: Check for Kubernetes Dependencies

Verify K8s code is disabled:

```bash
# Check edge-api for K8s usage
cd "C:\Dev\IntelliOptics 2.0\edge\edge-api\app"
grep -r "kubernetes" . | grep -v ".pyc" | head -10
```

**Action**:
- Environment variable `DEPLOY_DETECTOR_LEVEL_INFERENCE=0` in docker-compose.yml will disable K8s logic
- No code changes needed if env var is set

---

## Phase 2: Environment Configuration (15 minutes)

### Step 2.1: Configure Edge Environment

```bash
cd "C:\Dev\IntelliOptics 2.0\edge"
cp .env.template .env
```

**Required variables** to fill in `.env`:

```bash
# Minimum required for testing
POSTGRES_PASSWORD=test-password-123
LOG_LEVEL=INFO
EDGE_DEVICE_ID=edge-test-001
EDGE_DEVICE_NAME=Test Edge Device

# Optional (can be added later)
# INTELLIOPTICS_API_TOKEN=<from-cloud>
# CENTRAL_WEB_APP_URL=http://localhost:8000
# SENDGRID_API_KEY=SG.xxx
```

### Step 2.2: Configure Cloud Environment

```bash
cd "C:\Dev\IntelliOptics 2.0\cloud"
cp .env.template .env
```

**Minimum required** for testing (no Azure/SendGrid needed initially):

```bash
# Core required
POSTGRES_PASSWORD=cloud-password-456
API_SECRET_KEY=test-secret-key-at-least-32-characters-long-12345
LOG_LEVEL=INFO

# Optional for initial testing
# AZURE_STORAGE_CONNECTION_STRING=<azure-storage>
# SENDGRID_API_KEY=SG.xxx
# SERVICE_BUS_CONN=<azure-servicebus>
```

**Note**: For production, you MUST configure Azure Storage and SendGrid.

### Step 2.3: Create Azure Resources (If deploying with full features)

Skip this for local testing. For production:

```bash
# Create resource group
az group create --name intellioptics-rg --location eastus

# Create storage account
az storage account create \
  --name intelliopticsstorage \
  --resource-group intellioptics-rg \
  --location eastus \
  --sku Standard_LRS

# Get connection string
az storage account show-connection-string \
  --name intelliopticsstorage \
  --resource-group intellioptics-rg \
  --output tsv
```

Copy the connection string to `cloud/.env` → `AZURE_STORAGE_CONNECTION_STRING`

---

## Phase 3: Deploy Cloud (First) (10 minutes)

### Step 3.1: Start Cloud Services

```bash
cd "C:\Dev\IntelliOptics 2.0\cloud"
docker-compose up -d
```

**Wait 30 seconds** for services to start.

### Step 3.2: Verify Cloud Deployment

```bash
# Check services are running
docker-compose ps

# Check backend health
curl http://localhost:8000/health
# Expected: {"status":"ok"}

# Check frontend (if accessible)
curl http://localhost:3000
# Expected: HTML response

# Check logs for errors
docker-compose logs backend | tail -50
docker-compose logs frontend | tail -20
```

### Step 3.3: Access Cloud Web UI

Open browser: **http://localhost:3000**

**Expected**:
- Login page or dashboard loads
- No console errors in browser DevTools (F12)

**If errors**: Check `docker-compose logs` for backend/frontend

---

## Phase 4: Prepare Models (Variable time)

### Step 4.1: Create Model Directory Structure

```bash
# Windows PowerShell
mkdir "C:\opt\intellioptics\models\det_test_001\primary\1"
mkdir "C:\opt\intellioptics\models\det_test_001\oodd\1"

# Linux/Mac
mkdir -p /opt/intellioptics/models/det_test_001/primary/1
mkdir -p /opt/intellioptics/models/det_test_001/oodd/1
```

### Step 4.2: Place ONNX Models

**Option A: Use your trained models**

```bash
# Copy your ONNX models
cp path/to/your/primary-model.onnx /opt/intellioptics/models/det_test_001/primary/1/model.buf
cp path/to/your/oodd-model.onnx /opt/intellioptics/models/det_test_001/oodd/1/model.buf
```

**Option B: Use placeholder for testing (inference will fail but API will work)**

```bash
# Create dummy files just to test API layer
echo "dummy" > /opt/intellioptics/models/det_test_001/primary/1/model.buf
echo "dummy" > /opt/intellioptics/models/det_test_001/oodd/1/model.buf
```

### Step 4.3: Configure Detector

Edit `edge/config/edge-config.yaml`:

```yaml
detectors:
  det_test_001:
    detector_id: det_test_001
    name: "Test Detector"
    edge_inference_config: default
    confidence_threshold: 0.85
    mode: BINARY
    class_names: ["pass", "fail"]
```

---

## Phase 5: Deploy Edge (10 minutes)

### Step 5.1: Start Edge Services

```bash
cd "C:\Dev\IntelliOptics 2.0\edge"
docker-compose up -d
```

**Wait 60 seconds** for inference service to load models.

### Step 5.2: Verify Edge Deployment

```bash
# Check services
docker-compose ps

# Check nginx gateway
curl http://localhost:30101/health
# Expected: Health check response

# Check edge-api
curl http://localhost:8718/health
# Expected: {"status":"ok"}

# Check inference service
curl http://localhost:8001/health
# Expected: {"status":"healthy","cached_models":0}

# List available models
curl http://localhost:8001/models
# Expected: List of detectors with model status
```

### Step 5.3: Check Logs

```bash
# Edge API logs (check for startup errors)
docker-compose logs edge-api | tail -50

# Inference logs (check model loading)
docker-compose logs inference | tail -50

# Look for:
# ✅ "Loaded model: /models/det_test_001/primary/1/model.buf"
# ✅ "Loaded model: /models/det_test_001/oodd/1/model.buf"
# ❌ "Failed to load model" - indicates missing/invalid models
```

---

## Phase 6: End-to-End Testing (15 minutes)

### Step 6.1: Test Image Submission

```bash
# Get a test image (any JPG/PNG)
# On Windows: copy from Pictures folder
# On Linux: use any image file

# Submit to edge endpoint
curl -X POST "http://localhost:30101/v1/image-queries?detector_id=det_test_001" \
  -F "image=@test-image.jpg"
```

**Expected responses**:

**Success (with real models)**:
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

**Low confidence (triggers escalation)**:
```json
{
  "query_id": "qry_xyz789",
  "label": 1,
  "confidence": 0.72,
  "escalated": true,
  "message": "Image escalated for human review"
}
```

**Error (model issues)**:
```json
{
  "detail": "Primary model not found for detector: det_test_001"
}
```

### Step 6.2: Test Cloud Fallback

```bash
# Request non-existent detector (should fallback to cloud)
curl -X POST "http://localhost:30101/v1/image-queries?detector_id=det_nonexistent" \
  -F "image=@test-image.jpg"
```

**Expected**: nginx forwards to cloud (if cloud endpoint configured)

### Step 6.3: Test Escalation Flow

1. Submit image with low confidence (< 0.85)
2. Check cloud backend logs:
   ```bash
   cd "C:\Dev\IntelliOptics 2.0\cloud"
   docker-compose logs backend | grep escalation
   ```
3. Check Review Queue in Web UI: http://localhost:3000

### Step 6.4: Test RTSP Streaming (Optional)

If you have RTSP cameras, edit `edge/config/edge-config.yaml`:

```yaml
streams:
  cam_001:
    rtsp_url: "rtsp://your-camera-ip:554/stream"
    detector_id: det_test_001
    frame_interval: 1.0
```

Restart edge-api:
```bash
docker-compose restart edge-api
```

Check logs for frame processing:
```bash
docker-compose logs edge-api | grep rtsp
```

---

## Phase 7: Troubleshooting Common Issues

### Issue 1: Edge API Returns 503

**Cause**: Inference service not ready

**Fix**:
```bash
cd "C:\Dev\IntelliOptics 2.0\edge"
docker-compose logs inference
# Look for model loading errors

# Restart inference
docker-compose restart inference
```

### Issue 2: "Primary model not found"

**Cause**: Models not in correct directory or wrong detector_id

**Fix**:
```bash
# Check model paths
ls -la /opt/intellioptics/models/det_test_001/primary/1/

# Verify detector_id matches in:
# - edge/config/edge-config.yaml
# - Model directory name
# - API request ?detector_id=xxx
```

### Issue 3: Frontend Not Loading

**Cause**: Frontend build failed or nginx routing issue

**Fix**:
```bash
cd "C:\Dev\IntelliOptics 2.0\cloud"
docker-compose logs frontend

# Rebuild if needed
docker-compose build frontend
docker-compose up -d frontend
```

### Issue 4: Escalations Not Working

**Cause**: Cloud connectivity or configuration issue

**Fix**:
```bash
# Check edge .env has cloud URL
cat edge/.env | grep CENTRAL_WEB_APP_URL

# Test cloud endpoint
curl http://localhost:8000/escalations

# Check edge logs
docker-compose logs edge-api | grep escalation
```

### Issue 5: Database Connection Errors

**Cause**: PostgreSQL not ready or wrong password

**Fix**:
```bash
# Check postgres is running
docker-compose ps postgres

# Verify password matches in:
# - .env file
# - docker-compose.yml

# Restart services
docker-compose restart backend
docker-compose restart edge-api
```

---

## Phase 8: Production Readiness (Optional)

Once testing is successful, prepare for production:

### 8.1: Security Hardening

- [ ] Change all default passwords
- [ ] Generate strong API secret keys
- [ ] Configure HTTPS with SSL certificates
- [ ] Restrict CORS origins
- [ ] Enable authentication in cloud backend

### 8.2: Azure Integration

- [ ] Configure Azure Blob Storage (required for production)
- [ ] Set up Azure Service Bus for async processing
- [ ] Configure SendGrid for email alerts
- [ ] Set up Application Insights for monitoring

### 8.3: Deployment to Cloud

- [ ] Deploy cloud backend to Azure Container Instances or App Service
- [ ] Deploy frontend to Azure Static Web Apps or App Service
- [ ] Configure custom domain and SSL
- [ ] Set up Azure Database for PostgreSQL

### 8.4: Edge Production Deployment

- [ ] Install Docker on edge device (factory server)
- [ ] Copy IntelliOptics 2.0 edge folder to device
- [ ] Configure .env with production credentials
- [ ] Place production ONNX models
- [ ] Run docker-compose up -d
- [ ] Configure as systemd service for auto-restart

---

## Phase 9: HRM AI Integration (Phase 2 - Future)

After Phase 1 is stable:

1. Collect 1000+ escalated images from production
2. Follow `docs/HRM-TRAINING.md` for HRM training
3. Add HRM inference service to edge deployment
4. Enable explainable AI reasoning

---

## Summary Checklist

### Immediate Actions (Do These First)

- [ ] Run `test-builds.sh` to verify all containers build
- [ ] Copy `.env.template` to `.env` for edge and cloud
- [ ] Fill in minimum required environment variables
- [ ] Deploy cloud: `cd cloud && docker-compose up -d`
- [ ] Verify cloud health: `curl http://localhost:8000/health`
- [ ] Create model directories (even with dummy files for testing)
- [ ] Configure one test detector in `edge-config.yaml`
- [ ] Deploy edge: `cd edge && docker-compose up -d`
- [ ] Test image submission: `curl -X POST ...`

### Optional (For Full Features)

- [ ] Set up Azure Storage account
- [ ] Configure SendGrid API key
- [ ] Place real ONNX models
- [ ] Configure RTSP cameras
- [ ] Set up production HTTPS

---

## Quick Command Reference

```bash
# Build test
cd "C:\Dev\IntelliOptics 2.0"
bash test-builds.sh

# Deploy cloud
cd cloud
docker-compose up -d
docker-compose logs -f

# Deploy edge
cd edge
docker-compose up -d
docker-compose logs -f

# Test endpoints
curl http://localhost:8000/health  # Cloud
curl http://localhost:30101/health  # Edge gateway
curl http://localhost:8001/models   # Inference service

# Submit test image
curl -X POST "http://localhost:30101/v1/image-queries?detector_id=det_test_001" \
  -F "image=@test.jpg"

# Stop services
docker-compose down

# Rebuild after code changes
docker-compose build
docker-compose up -d
```

---

## Support

- **Quick Start**: See `QUICKSTART.md`
- **Architecture**: See `docs/ARCHITECTURE.md`
- **Source Tracking**: See `SOURCE_MANIFEST.md`
- **HRM Training**: See `docs/HRM-TRAINING.md`

**Status**: Ready to begin testing! Start with Phase 1.
