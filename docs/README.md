# IntelliOptics 2.0

**Edge-First AI Inspection & Smart Detection Platform**

---

## Overview

IntelliOptics 2.0 is a complete AI-powered visual inspection and smart detection platform for security, manufacturing, and surveillance. It combines:

- **Edge-First Architecture**: ONNX models running on-device with confidence-based escalation to human review
- **Open-Vocabulary Detection**: Detect anything by typing what you're looking for — no retraining needed (YOLOE + YOLO-World)
- **Visual Language Model (VLM)**: Natural language image queries via Moondream VLM (0.5B/2B)
- **IntelliSearch**: Live video stream analysis with real-time bounding box overlay
- **Vehicle Identification**: Automated plate OCR, color, and vehicle type recognition
- **Forensic Video Search (BOLO)**: Search hours of video footage with natural language queries
- **Parking Management**: Zone-based occupancy tracking, violation detection, and event logging
- **Detector-Centric Design**: Each detector controls its own AI model, thresholds, escalation logic, and alerts
- **No Kubernetes**: Simple Docker Compose deployment on both edge and cloud

---

## Architecture

```
Edge Device(s)                            Central Cloud (Supabase)
──────────────                            ──────────────────────────
nginx :30101                              nginx → backend :8000
  └─ edge-api :8718                             → frontend :3000
      └─ inference :8001                        → worker :8081
         ├─ YOLO (custom trained ONNX)          → Supabase PostgreSQL
         ├─ YOLOE (open-vocab detection)        → Supabase Storage
         ├─ YOLO-World (open-vocab detection)   → Human Review Queue
         ├─ Moondream VLM (natural language)    → Email/SMS Alerts (SendGrid/Twilio)
         └─ Vehicle ID Pipeline (plate OCR)
                    │
                    │ (low confidence → escalation)
                    ↓
              Cloud Backend
```

### Cloud Services (Docker Compose)
| Service | Port | Purpose |
|---------|------|---------|
| nginx | 80/443 | Reverse proxy routing |
| backend | 8000 | FastAPI REST API (19 routers, 170+ endpoints) |
| frontend | 3000 | React UI (17 pages) |
| worker | 8081 | Cloud-side ONNX inference worker |

### Edge Services (Docker Compose)
| Service | Port | Purpose |
|---------|------|---------|
| nginx | 30101 | Gateway with cloud fallback |
| edge-api | 8718 | Edge endpoint + escalation queue |
| inference | 8001 | Multi-model inference (YOLO, YOLOE, YOLO-World, VLM, Vehicle ID) |
| postgres | 5432 | Local detector metadata (optional) |

---

## Tech Stack

### Frontend (Cloud)
- React 18.2 + TypeScript 5.2 + Vite 4.4
- Tailwind CSS 3.3
- React Router DOM 6.17
- Azure MSAL 2.39 (Microsoft Auth) + local JWT fallback
- Axios, React Hook Form + Zod, Recharts, React Toastify, react-youtube

### Backend (Cloud)
- FastAPI + Uvicorn (Python)
- PostgreSQL via SQLAlchemy ORM (Supabase hosted)
- Supabase Storage (images + models)
- SendGrid (email alerts), Twilio (SMS alerts)
- JWT auth (python-jose + passlib)

### Edge
- FastAPI + Uvicorn (Python)
- ONNX Runtime (YOLOv8/v10 custom models)
- Ultralytics (YOLOE, YOLO-World open-vocabulary)
- Moondream VLM 0.5B/2B (natural language queries, OCR)
- OpenCV, NumPy, Pillow
- NVIDIA GPU support (optional, falls back to CPU)

---

## Quick Start

### Prerequisites

- **Docker** & **Docker Compose** installed
- **Python 3.11+** (for local dev)
- **Node.js 18+** (for frontend dev)
- **NVIDIA GPU** (optional — system falls back to CPU automatically)

### Deploy Cloud

```bash
cd cloud/
cp .env.template .env
# Edit .env with: POSTGRES_DSN, SUPABASE_URL, SUPABASE_KEY, API_SECRET_KEY

docker compose up -d

# Frontend: http://localhost:3000
# Backend:  http://localhost:8000
# Health:   http://localhost:8000/health
```

### Deploy Edge

```bash
cd edge/
cp .env.template .env
# Edit .env with: INTELLIOPTICS_API_TOKEN, CENTRAL_WEB_APP_URL

docker compose up -d

# Edge API: http://localhost:30101
# Health:   http://localhost:8001/health
```

### Frontend Dev (no Docker)

```bash
cd cloud/frontend/
npm install
npm run dev    # Vite dev server on :5173
npm run build  # Production build
```

---

## Key Features

### 1. Open-Vocabulary Detection (YOLOE + YOLO-World)

Detect **anything** by typing text prompts — no model retraining required.

- **YOLOE**: Fast open-vocab detection with dynamic per-request prompts
- **YOLO-World**: CLIP-based open-vocab detection with text encoding
- **IntelliSearch**: Live video stream analysis — type "person, car, fire" and watch detections appear in real-time with bounding box overlays
- **IO-E Detect**: YOLOE-powered stream detection mode

**Usage**: Demo Streams page → Select "IntelliSearch" or "IO-E Detect" mode → Enter prompts → Start session

### 2. Visual Language Model (Moondream VLM)

Ask natural language questions about images:

- **Query**: "What color is this car?" → "The car is red"
- **Detect**: "Find all people wearing hard hats" → Bounding boxes
- **OCR**: "Read the license plate" → "ABC 1234"

**Dual-Track Architecture**: YOLOE runs every frame (15-30 FPS) while VLM runs every 10th-30th frame for complex queries — VLM never stalls detection.

### 3. Vehicle Identification Pipeline

Automated vehicle recognition combining YOLOE + VLM:

- YOLOE detects vehicles and license plates
- VLM OCR reads plate text
- VLM queries vehicle color and type
- Spatial overlap matching: plate bbox inside vehicle bbox = belongs to that vehicle
- Search by plate number, color, or vehicle type with CSV export

**Pages**: Vehicle Search → search/filter results | Open Vocab → upload image for identification

### 4. Forensic Video Search (BOLO)

Search hours of video footage with natural language:

- Upload DVR footage or provide video URL
- Extract frames at configurable intervals (1-2 sec)
- YOLOE batch scan at high throughput
- VLM confirms only on candidate frames
- Natural language queries: "Man with red backpack near Lot C around 3PM"
- Progress tracking with real-time status updates

**Page**: Forensic Search → Create job → Monitor progress → Review results

### 5. Parking Management (IntelliPark)

Zone-based parking intelligence:

- Define parking zones with capacity
- Real-time occupancy monitoring
- Violation detection and resolution
- Event logging and history
- Dashboard with zone overview

**Page**: Parking Dashboard

### 6. Confidence-Based Escalation

- **High confidence** (>= threshold): Return edge result immediately
- **Low confidence** (< threshold): Escalate to cloud human review queue
- **OODD ground truth**: Out-of-domain images automatically escalated
- Human reviewer approves/rejects in the Escalation Queue UI
- Approved annotations feed back into model retraining

### 7. Live Bounding Box Overlay

Real-time detection visualization using HTML5 Canvas:

- Renders normalized bounding boxes at 30fps over video/image
- Color-coded labels with confidence scores
- ResizeObserver for responsive scaling
- Works with webcam, YouTube, EarthCam, and server-captured frames

### 8. Detector-Centric Configuration

Each detector independently controls:
- AI model (ONNX, YOLOE, or YOLO-World)
- Confidence threshold and escalation behavior
- Mode: BINARY, MULTICLASS, COUNTING, BOUNDING_BOX, or OPEN_VOCAB
- Alert settings (email, SMS, batch rules)
- RTSP camera streams

### 9. Alerts & Notifications

- **Email**: SendGrid-powered alerts with rich HTML
- **SMS**: Twilio alerts for critical detections
- Configurable per-detector: recipient list, batch size, batch interval
- Alert history and acknowledgment tracking

---

## Frontend Pages (17)

| Page | File | Purpose |
|------|------|---------|
| Login | `LoginPage.tsx` | Azure MSAL + local JWT auth |
| Detectors | `DetectorsPage.tsx` | List/CRUD all detectors |
| Detector Config | `DetectorConfigPage.tsx` | Model upload, thresholds, NMS settings |
| Detector Alerts Config | `DetectorAlertConfigPage.tsx` | Per-detector alert settings |
| Detector Alerts | `DetectorAlertsPage.tsx` | Alert history |
| Escalation Queue | `EscalationQueuePage.tsx` | Human review of low-confidence detections |
| Query History | `QueryHistoryPage.tsx` | Past inference queries |
| Demo Streams | `DemoStreamPage.tsx` | Live video streaming with IntelliSearch / IO-E Detect |
| Open Vocab | `OpenVocabPage.tsx` | YOLOE detection + VLM query with image upload |
| Vehicle Search | `VehicleSearchPage.tsx` | Search vehicles by plate/color/type, CSV export |
| Forensic Search | `ForensicSearchPage.tsx` | BOLO video forensic search with progress tracking |
| Parking Dashboard | `ParkingDashboardPage.tsx` | Zone occupancy, violations, events |
| Camera Inspection | `CameraInspectionPage.tsx` | Camera health monitoring |
| Hub Status | `HubStatusPage.tsx` | Edge device status |
| Deployment Manager | `DeploymentManagerPage.tsx` | Deploy detectors to edge hubs |
| Alert Settings | `AlertSettingsPage.tsx` | Global alert configuration |
| Admin | `AdminPage.tsx` | System administration |

---

## API Endpoints

### Edge Inference Service (port 8001)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/infer` | Primary + OODD detector inference |
| POST | `/yoloworld` | YOLO-World open-vocab detection |
| POST | `/yoloe` | YOLOE open-vocab detection |
| POST | `/vlm/query` | Natural language image question |
| POST | `/vlm/detect` | VLM object detection |
| POST | `/vlm/ocr` | Text extraction from image |
| POST | `/vehicle-id/identify` | Vehicle identification pipeline |
| GET | `/health` | Health check |
| GET | `/models` | List loaded models |

### Cloud Backend (port 8000) — Key Endpoints

| Router | Prefix | Key Operations |
|--------|--------|----------------|
| detectors | `/detectors` | CRUD, model upload, config, test, metrics |
| queries | `/queries` | Submit, list, feedback |
| escalations | `/escalations` | Review queue, resolve |
| demo_streams | `/demo-streams` | Sessions, configs, frame submission, live detections, prompt updates |
| open_vocab | `/open-vocab` | YOLOE detect, VLM query |
| vehicle_id | `/vehicle-id` | Identify, search, list |
| forensic_search | `/forensic-search` | Create/list/stop jobs, get results |
| parking | `/parking` | Zones CRUD, events, violations, dashboard |
| hubs | `/hubs` | Edge device management |
| camera_inspection | `/camera-inspection` | Dashboard, runs, alerts |
| annotations | `/annotations` | CRUD, bulk, review |
| data_management | `/data-management` | Retention, purge, export |
| users | `/users` | User CRUD |
| settings | `/settings` | Alert configuration |
| deployments | `/deployments` | Deploy to edge hubs |

---

## Project Structure

```
IntelliOptics 2.0/
├── cloud/
│   ├── frontend/               # React UI (17 pages, 4 components)
│   │   └── src/
│   │       ├── pages/          # All page components
│   │       └── components/     # LiveBboxOverlay, BoundingBoxAnnotator, etc.
│   ├── backend/                # FastAPI backend (19 routers)
│   │   └── app/
│   │       ├── main.py         # Entry point
│   │       ├── routers/        # All API endpoints
│   │       ├── services/       # yoloworld_inference, demo_session_manager
│   │       ├── models.py       # SQLAlchemy ORM
│   │       ├── schemas.py      # Pydantic schemas
│   │       ├── config.py       # Settings
│   │       ├── auth.py         # JWT auth
│   │       └── utils/          # supabase_storage.py
│   ├── worker/                 # Cloud inference worker
│   │   ├── onnx_worker.py      # HTTP inference server
│   │   └── detector_inference.py
│   ├── nginx/                  # Nginx config
│   └── docker-compose.yml
├── edge/
│   ├── edge-api/               # Edge API service
│   ├── inference/              # Multi-model inference service
│   │   ├── inference_service.py    # /infer, /yoloworld, /yoloe, /vlm/*, /vehicle-id/*
│   │   ├── yoloe_inference.py      # YOLOE singleton
│   │   ├── vlm_inference.py        # Moondream VLM
│   │   ├── vehicle_id.py           # Vehicle ID pipeline
│   │   └── forensic_search.py      # BOLO engine
│   ├── config/
│   │   └── edge-config.yaml        # All edge configuration
│   └── docker-compose.yml
├── docs/                       # Documentation
├── hrm-training/               # Phase 2: HRM training module
├── install/                    # Installation scripts
├── CLAUDE.md                   # AI context document
└── test-builds.sh
```

---

## Detector Modes

| Mode | Description |
|------|-------------|
| `BINARY` | Yes/No, Pass/Fail classification |
| `MULTICLASS` | Defect type classification |
| `COUNTING` | Object counting with max threshold |
| `BOUNDING_BOX` | Object detection with bounding boxes and ROIs |
| `OPEN_VOCAB` | Open-vocabulary detection via YOLOE/YOLO-World + VLM (default for new detectors) |

---

## Edge Configuration

The `edge/config/edge-config.yaml` controls all edge behavior:

```yaml
# Detector definitions
detectors:
  det_quality_check_001:
    detector_id: det_quality_check_001
    name: "Quality Check - Main Line"
    confidence_threshold: 0.85
    mode: BINARY
    class_names: ["pass", "defect"]

# Open-vocabulary detection
open_vocab_config:
  model: yoloe-v8s
  default_conf: 0.25
  nms_iou: 0.45

# Visual Language Model
vlm_config:
  model: moondream-0.5b
  interval_frames: 15
  dual_track_enabled: true

# Vehicle identification
vehicle_id_config:
  enabled: true
  detection_prompts: "car, truck, van, motorcycle, license plate"

# Forensic search
forensic_search_config:
  enabled: true
  frame_interval_seconds: 1.0
  confidence_threshold: 0.3
```

---

## Environment Variables

### Cloud (.env)
| Variable | Purpose |
|----------|---------|
| `POSTGRES_DSN` | PostgreSQL connection string |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_KEY` | Supabase anon/service key |
| `API_SECRET_KEY` | JWT signing key |
| `SENDGRID_API_KEY` | Email alerts |
| `TWILIO_*` | SMS alerts |
| `YOLOWORLD_WORKER_URL` | Edge YOLOWorld endpoint |
| `YOLOE_WORKER_URL` | Edge YOLOE endpoint |

### Edge (.env)
| Variable | Purpose |
|----------|---------|
| `INTELLIOPTICS_API_TOKEN` | Cloud auth token |
| `CENTRAL_WEB_APP_URL` | Cloud backend URL |
| `EDGE_DEVICE_ID` | Unique device identifier |
| `CONFIDENCE_THRESHOLD` | Default escalation threshold |
| `SENDGRID_API_KEY` | Local email alerts |

---

## Monitoring

```bash
# Cloud logs
cd cloud/
docker compose logs -f backend
docker compose logs -f worker

# Edge logs
cd edge/
docker compose logs -f inference
docker compose logs -f edge-api

# Health checks
curl http://localhost:8000/health    # Cloud backend
curl http://localhost:8001/health    # Edge inference
curl http://localhost:30101/health   # Edge gateway
```

---

## GPU Notes

- The system automatically detects GPU availability and compute capability
- GPUs with compute capability < 7.0 (e.g., GTX 1050 Ti) automatically fall back to CPU inference
- `torch.cuda.is_available()` may return `true` even when the GPU can't run PyTorch kernels — the system checks `torch.cuda.get_device_capability()` to verify
- CPU inference is fully functional but slower

---

## Phase 2: HRM AI (Planned)

**Hierarchical Reasoning Model** for explainable AI:
- Reasoning chains explaining detection decisions
- Few-shot learning: train new detectors with ~1000 samples
- Intelligent escalation decisions
- 27M parameter model, edge-optimized

See `docs/HRM-TRAINING.md` for the training guide.

---

## Licensing

- **YOLOE / YOLO-World**: AGPL-3.0 (Ultralytics Enterprise license needed for client distribution)
- **Moondream VLM**: Apache 2.0 (free for all use)
- **IntelliOptics Platform**: Proprietary — Product of 4wardmotion Solutions, Inc.

---

## Current Versions

- Backend: v2.0.3
- Frontend: v2.0.2
- Worker: v2.0.0
