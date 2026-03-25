# IntelliOptics 2.0 - Source Code Manifest

This document tracks all source code copied from existing repositories to the IntelliOptics 2.0 clean build.

**Generated**: January 6, 2026
**Status**: ✅ Complete and ready for deployment

---

## Source Code Copies

### Edge Deployment

#### 1. Edge API (`edge/edge-api/app/`)
**Source**: `C:\Dev\IntelliOpticsDev\IntelliOptics-Edge-clean\app`
**Status**: ✅ Copied successfully

**Key modules**:
- `main.py` - FastAPI application entry point
- `api/routes/image_queries.py` - Main image submission endpoint
- `api/routes/health.py` - Health check endpoints
- `core/edge_inference.py` - Edge inference orchestration logic (31KB)
- `core/configs.py` - Pydantic configuration models
- `core/kubernetes_management.py` - ⚠️ **TO BE REMOVED** (K8s specific)
- `streaming/rtsp_ingest.py` - RTSP camera integration
- `escalation_queue/` - Escalation queue management
- `status_monitor/` - Metrics and monitoring

**Modifications needed**:
- Remove/disable Kubernetes dependencies in `core/kubernetes_management.py`
- Update inference URLs in `core/edge_inference.py` from K8s services to `http://inference:8001`
- Remove dynamic pod creation logic
- Simplify to use static docker-compose services

#### 2. Inference Service (`edge/inference/`)
**Source**: Custom built for IntelliOptics 2.0
**Status**: ✅ Created from scratch

**Files**:
- `inference_service.py` - Multi-detector ONNX inference with Primary + OODD ground truth
- `Dockerfile` - Container build specification
- `requirements.txt` - Python ML/CV dependencies

**Features**:
- LRU model caching (5 models max)
- Primary + OODD dual model inference
- Confidence adjustment: `final_confidence = primary × oodd_in_domain_score`
- CPU/GPU support via ONNX Runtime

### Cloud Deployment

#### 3. Cloud Backend (`cloud/backend/app/`)
**Source**: `C:\Dev\intellioptics_platform_no_auth\backend\app`
**Status**: ✅ Copied successfully

**Key modules**:
- `main.py` - FastAPI application entry point
- `routers/detectors.py` - Detector CRUD operations
- `routers/queries.py` - Image query processing
- `routers/escalations.py` - Escalation review queue
- `routers/hubs.py` - Edge device management
- `routers/users.py` - User management
- `utils/azure.py` - Azure Blob Storage, Service Bus integration
- `models.py` - SQLAlchemy database models
- `schemas.py` - Pydantic request/response schemas
- `config.py` - Application configuration
- `auth.py` - Authentication and token management

**No modifications needed** - Cloud backend works as-is with IntelliOptics 2.0 architecture.

#### 4. Cloud Frontend (`cloud/frontend/`)
**Source**: `C:\Dev\intellioptics_full_platform_with_env\frontend`
**Status**: ✅ Copied successfully

**Key files**:
- `src/App.tsx` - Main React application
- `src/pages/` - Page components (Review Queue, Detectors, Dashboard)
- `src/utils/` - Utility functions
- `package.json` - NPM dependencies
- `Dockerfile` - Multi-stage build (Node.js → nginx)
- `vite.config.ts` - Vite build configuration
- `tailwind.config.cjs` - Tailwind CSS configuration

**Technology stack**:
- React + TypeScript
- Vite (build tool)
- Tailwind CSS (styling)
- Nginx (production serving)

#### 5. Cloud Worker (`cloud/worker/`)
**Source**: `C:\Dev\IntelliOpticsDev\IntelliOptics-Edge-clean\backend\worker`
**Status**: ✅ Copied successfully

**Key files**:
- `worker.py` - Service Bus queue worker
- `onnx_worker.py` - ONNX inference worker (17KB)
- `models.py` - Data models
- `db.py` - Database connection
- `Dockerfile` - Container build specification
- `requirements.txt` - Python dependencies

**Features**:
- Azure Service Bus integration
- Cloud-side ONNX inference
- Async processing of escalated queries

---

## Created Files (New for IntelliOptics 2.0)

### Configuration Files

| File | Purpose | Status |
|------|---------|--------|
| `edge/docker-compose.yml` | Edge deployment orchestration | ✅ Created |
| `edge/.env.template` | Edge environment variables (50+ vars) | ✅ Created |
| `edge/config/edge-config.yaml` | Detector configurations | ✅ Created |
| `edge/nginx/nginx.conf` | Edge gateway (port 30101) with cloud fallback | ✅ Created |
| `edge/nginx/Dockerfile` | nginx container build | ✅ Created |
| `cloud/docker-compose.yml` | Cloud deployment orchestration | ✅ Created |
| `cloud/.env.template` | Cloud environment variables (60+ vars) | ✅ Created |
| `cloud/nginx/nginx.conf` | Cloud API gateway | ✅ Created |
| `cloud/nginx/Dockerfile` | nginx container build | ✅ Created |
| `.gitignore` | Git ignore patterns (protects .env, models) | ✅ Created |

### Container Builds

| File | Purpose | Status |
|------|---------|--------|
| `edge/edge-api/Dockerfile` | Edge API container | ✅ Created |
| `edge/edge-api/requirements.txt` | Edge API Python deps | ✅ Created |
| `edge/inference/Dockerfile` | Inference service container | ✅ Created |
| `edge/inference/requirements.txt` | Inference service deps | ✅ Created |
| `cloud/backend/Dockerfile` | Cloud backend container | ✅ Created |
| `cloud/backend/requirements.txt` | Cloud backend Python deps | ✅ Created |

### Documentation

| File | Purpose | Status |
|------|---------|--------|
| `README.md` | Complete deployment guide | ✅ Created |
| `QUICKSTART.md` | 15-minute deployment guide | ✅ Created |
| `docs/ARCHITECTURE.md` | Full system architecture | ✅ Created |
| `docs/HRM-TRAINING.md` | HRM AI training guide (Phase 2) | ✅ Created |
| `SOURCE_MANIFEST.md` | This file - source tracking | ✅ Created |

---

## Directory Structure

```
C:\Dev\IntelliOptics 2.0\
├── edge\                          # Edge deployment
│   ├── docker-compose.yml         # ✅ Orchestration
│   ├── .env.template              # ✅ Configuration
│   ├── nginx\
│   │   ├── Dockerfile             # ✅
│   │   └── nginx.conf             # ✅ Port 30101 gateway
│   ├── edge-api\
│   │   ├── Dockerfile             # ✅
│   │   ├── requirements.txt       # ✅
│   │   └── app\                   # ✅ Copied from IntelliOptics-Edge-clean
│   │       ├── main.py
│   │       ├── api\routes\image_queries.py
│   │       ├── core\edge_inference.py
│   │       └── streaming\rtsp_ingest.py
│   ├── inference\
│   │   ├── Dockerfile             # ✅
│   │   ├── requirements.txt       # ✅
│   │   └── inference_service.py   # ✅ Primary + OODD inference
│   ├── config\
│   │   └── edge-config.yaml       # ✅ Detector configurations
│   └── scripts\                   # Empty (for future deployment scripts)
│
├── cloud\                          # Central web application
│   ├── docker-compose.yml         # ✅ Orchestration
│   ├── .env.template              # ✅ Configuration
│   ├── nginx\
│   │   ├── Dockerfile             # ✅
│   │   └── nginx.conf             # ✅ API gateway
│   ├── backend\
│   │   ├── Dockerfile             # ✅
│   │   ├── requirements.txt       # ✅
│   │   └── app\                   # ✅ Copied from intellioptics_platform_no_auth
│   │       ├── main.py
│   │       ├── routers\           # detectors, queries, escalations, hubs
│   │       ├── utils\azure.py     # Azure integrations
│   │       └── models.py          # Database models
│   ├── frontend\
│   │   ├── Dockerfile             # ✅ (from source)
│   │   ├── package.json           # ✅ (from source)
│   │   └── src\                   # ✅ Copied from intellioptics_full_platform_with_env
│   │       ├── App.tsx
│   │       ├── pages\
│   │       └── utils\
│   └── worker\
│       ├── Dockerfile             # ✅ (from source)
│       ├── requirements.txt       # ✅ (from source)
│       ├── worker.py              # ✅ Copied from IntelliOptics-Edge-clean
│       └── onnx_worker.py         # ✅
│
├── hrm-training\                   # HRM AI Phase 2 (future)
│   ├── dataset\                   # (empty - for training data)
│   ├── models\                    # (empty - for trained models)
│   └── scripts\                   # (empty - for training scripts)
│
├── docs\
│   ├── ARCHITECTURE.md            # ✅ System design documentation
│   └── HRM-TRAINING.md            # ✅ HRM training guide
│
├── README.md                       # ✅ Main documentation
├── QUICKSTART.md                   # ✅ Fast deployment guide
├── SOURCE_MANIFEST.md              # ✅ This file
└── .gitignore                      # ✅ Git ignore patterns
```

---

## File Counts

| Category | Count | Status |
|----------|-------|--------|
| Configuration files | 4 | ✅ Complete |
| Docker Compose files | 2 | ✅ Complete |
| Dockerfiles | 6 | ✅ Complete |
| Environment templates | 2 | ✅ Complete |
| Documentation files | 5 | ✅ Complete |
| **Total created files** | **19** | **✅ Ready** |
| Source code directories copied | 4 | ✅ Complete |

---

## Next Steps

### 1. Configure Environment Variables

```bash
# Edge
cd "C:\Dev\IntelliOptics 2.0\edge"
cp .env.template .env
# Edit .env with your credentials

# Cloud
cd "C:\Dev\IntelliOptics 2.0\cloud"
cp .env.template .env
# Edit .env with your credentials
```

### 2. Place ONNX Models

```bash
# Create model directories
mkdir -p /opt/intellioptics/models/det_abc123/primary/1
mkdir -p /opt/intellioptics/models/det_abc123/oodd/1

# Copy models
cp primary-model.onnx /opt/intellioptics/models/det_abc123/primary/1/model.buf
cp oodd-model.onnx /opt/intellioptics/models/det_abc123/oodd/1/model.buf
```

### 3. Deploy Cloud

```bash
cd "C:\Dev\IntelliOptics 2.0\cloud"
docker-compose up -d
```

### 4. Deploy Edge

```bash
cd "C:\Dev\IntelliOptics 2.0\edge"
docker-compose up -d
```

### 5. Test Deployment

```bash
# Test edge gateway
curl http://localhost:30101/health

# Test inference
curl -X POST "http://localhost:30101/v1/image-queries?detector_id=det_abc123" \
  -F "image=@test.jpg"

# Check cloud web UI
# Open: http://localhost:3000
```

---

## Modifications Required

### Edge API Modifications (Optional - for optimization)

The edge-api code currently contains Kubernetes-specific logic that can be disabled:

**File**: `edge/edge-api/app/core/kubernetes_management.py`
**Action**: Set environment variable `DEPLOY_DETECTOR_LEVEL_INFERENCE=0` in docker-compose.yml (already done)

**File**: `edge/edge-api/app/core/edge_inference.py`
**Action**: Inference URLs automatically use `http://inference:8001` when K8s is disabled

**Result**: Edge API will work without modifications by using the environment variable override.

---

## Status Summary

| Component | Source | Status | Ready for Deployment |
|-----------|--------|--------|---------------------|
| Edge API | Copied | ✅ Complete | ✅ Yes (with env var) |
| Inference Service | Created | ✅ Complete | ✅ Yes |
| Cloud Backend | Copied | ✅ Complete | ✅ Yes |
| Cloud Frontend | Copied | ✅ Complete | ✅ Yes |
| Cloud Worker | Copied | ✅ Complete | ✅ Yes |
| Configuration | Created | ✅ Complete | ✅ Yes |
| Documentation | Created | ✅ Complete | ✅ Yes |

**Overall Status**: ✅ **READY FOR DEPLOYMENT**

---

## Support

For deployment help, see:
- `README.md` - Complete deployment guide
- `QUICKSTART.md` - Fast 15-minute deployment
- `docs/ARCHITECTURE.md` - System design details

**All originals preserved** - Original codebases remain untouched in their original locations.
