# IntelliOptics 2.5

**Edge-First AI Inspection & Smart Detection Platform — Production Build**

---

## Overview

IntelliOptics 2.5 is the production-ready build of the IntelliOptics AI-powered visual inspection and smart detection platform for security, manufacturing, and surveillance. It combines:

- **Edge-First Architecture**: ONNX models running on-device with confidence-based escalation to human review
- **Open-Vocabulary Detection**: Detect anything by typing what you're looking for — no retraining needed (YOLOE + YOLO-World)
- **Visual Language Model (VLM)**: Natural language image queries via Moondream VLM (0.5B/2B)
- **IntelliSearch**: Live video stream analysis with real-time bounding box overlay
- **Vehicle Identification**: Automated plate OCR, color, and vehicle type recognition
- **Forensic Video Search (BOLO)**: Search hours of video footage with natural language queries
- **Parking Management**: Zone-based occupancy tracking, violation detection, and event logging
- **Unified Deployment**: Single `docker compose` bringing up all cloud + edge services on one machine

---

## Quick Start (Production)

### Prerequisites

- **Windows Server** or **Windows 10/11 Pro** with Docker Desktop
- **Git** installed
- **20GB free disk space** (images + models)
- **NVIDIA GPU** (optional — falls back to CPU automatically)

### Install

```powershell
git clone https://github.com/thamain1/IntelliOptics2.5.git
cd IntelliOptics2.5\install
.\Install-IntelliOptics.ps1
```

The installer will:
1. Detect and stop any old IntelliOptics 2.0 containers
2. Check prerequisites (Docker, ports, disk space)
3. Generate `.env` with pre-configured credentials and auto-generated API secret
4. Build all Docker images
5. Start all services
6. Run health checks
7. Create admin user

**After install:**
- Frontend: `http://localhost/`
- Edge API: `http://localhost:30101/`

See [`install/README.md`](install/README.md) for configuration, GPU setup, and troubleshooting.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Docker Network (intellioptics-net)      │
│                                                         │
│  Cloud Services                Edge Services            │
│  ──────────────                ──────────────            │
│  cloud-nginx :80/:443         edge-nginx :30101         │
│    ├─ cloud-backend :8000       └─ edge-api :8718       │
│    ├─ cloud-frontend :3000      └─ edge-inference :8001 │
│    └─ cloud-worker :8081           ├─ YOLO (ONNX)       │
│                                    ├─ YOLOE             │
│  External                          ├─ YOLO-World        │
│  ────────                          ├─ Moondream VLM     │
│  Supabase PostgreSQL               └─ Vehicle ID        │
│  Supabase Storage                                       │
│  SendGrid / Twilio                                      │
└─────────────────────────────────────────────────────────┘
```

All services run on a single Docker network. Cloud backend reaches edge inference directly as `edge-inference:8001` — no `host.docker.internal` workarounds.

### Services

| Service | Internal Port | Exposed Port | Purpose |
|---------|---------------|--------------|---------|
| cloud-nginx | 80 | **80, 443** | Reverse proxy for frontend + backend |
| cloud-backend | 8000 | — | FastAPI REST API (19 routers, 170+ endpoints) |
| cloud-frontend | 3000 | — | React UI (17 pages) |
| cloud-worker | 8081 | — | Cloud-side ONNX inference worker |
| edge-nginx | 30101 | **30101** | Edge gateway |
| edge-api | 8718 | — | Edge endpoint + escalation queue |
| edge-inference | 8001 | — | Multi-model inference (YOLO, YOLOE, VLM, Vehicle ID) |

---

## Tech Stack

### Frontend
- React 18.2 + TypeScript 5.2 + Vite 4.4
- Tailwind CSS 3.3, React Router DOM 6.17
- Azure MSAL (Microsoft Auth) + local JWT fallback
- Axios, React Hook Form + Zod, Recharts

### Backend
- FastAPI + Uvicorn (Python)
- PostgreSQL via SQLAlchemy ORM (Supabase hosted)
- Supabase Storage (images + models)
- SendGrid (email), Twilio (SMS)
- JWT auth (python-jose + passlib)

### Edge Inference
- ONNX Runtime (YOLOv8/v10 custom models)
- Ultralytics (YOLOE, YOLO-World open-vocabulary)
- Moondream VLM 0.5B/2B (natural language queries, OCR)
- OpenCV, NumPy, Pillow
- NVIDIA GPU support (optional, auto-fallback to CPU)

---

## Key Features

### 1. Open-Vocabulary Detection (YOLOE + YOLO-World)

Detect **anything** by typing text prompts — no model retraining required.

- **YOLOE**: Fast open-vocab detection with dynamic per-request prompts
- **YOLO-World**: CLIP-based open-vocab detection with text encoding
- **IntelliSearch**: Live video stream analysis — type "person, car, fire" and watch detections appear in real-time
- **IO-E Detect**: YOLOE-powered stream detection mode

### 2. Visual Language Model (Moondream VLM)

Ask natural language questions about images:

- **Query**: "What color is this car?" → "The car is red"
- **Detect**: "Find all people wearing hard hats" → Bounding boxes
- **OCR**: "Read the license plate" → "ABC 1234"

**Dual-Track Architecture**: YOLOE runs every frame (15-30 FPS) while VLM runs every 10th-30th frame — VLM never stalls detection.

### 3. Vehicle Identification Pipeline

Automated vehicle recognition combining YOLOE + VLM:

- YOLOE detects vehicles and license plates
- VLM OCR reads plate text, queries color and type
- Spatial overlap matching: plate inside vehicle bbox = belongs to that vehicle
- Search by plate number, color, or type with CSV export

### 4. Forensic Video Search (BOLO)

Search hours of video footage with natural language:

- Upload DVR footage or provide video URL
- Extract frames at configurable intervals (1-2 sec)
- YOLOE batch scan → VLM confirms on candidate frames
- Example: "Man with red backpack near Lot C around 3PM"

### 5. Parking Management (IntelliPark)

Zone-based parking intelligence:

- Define parking zones with capacity
- Real-time occupancy monitoring
- Violation detection and resolution
- Event logging and dashboard

### 6. Confidence-Based Escalation

- **High confidence** (>= threshold): Return edge result immediately
- **Low confidence** (< threshold): Escalate to cloud human review queue
- Human reviewer approves/rejects in Escalation Queue UI
- Approved annotations feed back into model retraining

### 7. Live Bounding Box Overlay

Real-time detection visualization using HTML5 Canvas at 30fps over video/image with color-coded labels and confidence scores.

### 8. Detector-Centric Configuration

Each detector independently controls: AI model, confidence threshold, escalation behavior, mode (BINARY/MULTICLASS/COUNTING/BOUNDING_BOX/OPEN_VOCAB), alert settings, and RTSP camera streams.

### 9. Alerts & Notifications

Email (SendGrid) and SMS (Twilio) alerts with configurable per-detector recipients, batch rules, and acknowledgment tracking.

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

## Project Structure

```
IntelliOptics2.5/
├── cloud/
│   ├── frontend/               # React UI (17 pages, 4 components)
│   ├── backend/                # FastAPI backend (19 routers)
│   ├── worker/                 # Cloud inference worker
│   ├── nginx/                  # Cloud nginx config
│   └── docker-compose.yml      # Cloud-only compose (dev)
├── edge/
│   ├── inference/              # Multi-model inference service
│   ├── edge-api/               # Edge API + escalation queue
│   ├── config/                 # edge-config.yaml
│   ├── nginx/                  # Edge nginx config
│   └── docker-compose.yml      # Edge-only compose (dev)
├── install/
│   ├── Install-IntelliOptics.ps1    # Main installer
│   ├── Uninstall-IntelliOptics.ps1  # Clean removal
│   ├── docker-compose.prod.yml      # Unified full-stack compose
│   ├── .env.template                # Environment template
│   ├── config/                      # Nginx + edge configs
│   ├── scripts/                     # Modular install scripts
│   └── README.md                    # Install guide
├── docs/                       # Documentation
├── CLAUDE.md                   # AI context document
└── README.md                   # This file
```

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

### Cloud Backend (port 8000) — Key Routers

| Router | Prefix | Key Operations |
|--------|--------|----------------|
| detectors | `/detectors` | CRUD, model upload, config, test, metrics |
| queries | `/queries` | Submit, list, feedback |
| escalations | `/escalations` | Review queue, resolve |
| demo_streams | `/demo-streams` | Sessions, configs, frame submission, live detections |
| open_vocab | `/open-vocab` | YOLOE detect, VLM query |
| vehicle_id | `/vehicle-id` | Identify, search, list |
| forensic_search | `/forensic-search` | Create/list/stop jobs, get results |
| parking | `/parking` | Zones CRUD, events, violations, dashboard |
| hubs | `/hubs` | Edge device management |
| camera_inspection | `/camera-inspection` | Dashboard, runs, alerts |
| data_management | `/data-management` | Retention, purge, export |
| users | `/users` | User CRUD |

---

## Detector Modes

| Mode | Description |
|------|-------------|
| `BINARY` | Yes/No, Pass/Fail classification |
| `MULTICLASS` | Defect type classification |
| `COUNTING` | Object counting with max threshold |
| `BOUNDING_BOX` | Object detection with bounding boxes and ROIs |
| `OPEN_VOCAB` | Open-vocabulary detection via YOLOE/YOLO-World + VLM (default) |

---

## GPU Notes

- System automatically detects GPU availability and compute capability
- GPUs with compute capability < 7.0 (e.g., GTX 1050 Ti) fall back to CPU
- CPU inference is fully functional but slower
- GPU support can be enabled in `docker-compose.prod.yml` (commented out by default)

---

## Development (Separate Stacks)

For development, you can run cloud and edge stacks separately:

```bash
# Cloud only
cd cloud/
cp .env.template .env  # Edit with your Supabase creds
docker compose up -d
# Frontend: http://localhost:3000 | Backend: http://localhost:8000

# Edge only
cd edge/
cp .env.template .env
docker compose up -d
# Edge API: http://localhost:30101 | Inference: http://localhost:8001

# Frontend dev (no Docker)
cd cloud/frontend/
npm install && npm run dev  # Vite dev server on :5173
```

---

## Monitoring

```bash
# All services (production)
cd install/
docker compose -f docker-compose.prod.yml logs -f

# Specific service
docker compose -f docker-compose.prod.yml logs -f cloud-backend
docker compose -f docker-compose.prod.yml logs -f edge-inference

# Health checks
curl http://localhost/api/health         # Cloud backend (via nginx)
curl http://localhost:30101/health       # Edge gateway
```

---

## Licensing

- **YOLOE / YOLO-World**: AGPL-3.0 (Ultralytics Enterprise license needed for client distribution)
- **Moondream VLM**: Apache 2.0 (free for all use)
- **IntelliOptics Platform**: Proprietary — Product of 4wardmotion Solutions, Inc.

---

## Version

- IntelliOptics: 2.5.0
- Backend: v2.5.0
- Frontend: v2.5.0
