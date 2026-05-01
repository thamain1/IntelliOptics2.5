# IntelliOptics 2.5 - Project Context for Claude

## Repository & Local Path
- **GitHub**: https://github.com/thamain1/IntelliOptics2.5.git
- **Local Path**: `C:\Dev\intellioptics_2.5`
- **Branch**: `main`

## Overview
IntelliOptics 2.5 is an **edge-first AI inspection platform** for security, manufacturing, and visual detection. It uses ONNX models running on-device (edge) with confidence-based escalation to cloud-based human review. All inference is **local-only** — cloud is Supabase (DB/storage) + SendGrid/Twilio (alerts) only.

## Architecture

```
Edge Device(s)                        Central Cloud (Supabase)
──────────────                        ──────────────────────────
nginx :30101                          nginx → backend :8000
  └─ edge-api :8718    (low conf.)          → frontend :3000
      └─ inference :8001  ──────────────→   → worker :8081
         ├─ YOLO (custom trained)           → Supabase PostgreSQL
         ├─ YOLOE (open-vocab)              → Supabase Storage
         ├─ YOLO-World (open-vocab)    Human Review Queue
         └─ Moondream VLM             Email/SMS Alerts (SendGrid/Twilio)
```

## Tech Stack

### Frontend (Cloud)
- React 18.2.0 + TypeScript 5.2.2 + Vite 4.4.9
- Tailwind CSS 3.3.2
- React Router DOM 6.17.0
- Azure MSAL 2.39.0 (Microsoft Auth) + local JWT fallback
- Axios, React Hook Form + Zod, Recharts, React Toastify, react-youtube

### Backend (Cloud)
- FastAPI + Uvicorn (Python)
- PostgreSQL via SQLAlchemy ORM (Supabase hosted)
- Supabase Storage (images + models buckets)
- SendGrid (email alerts), Twilio (SMS alerts)
- JWT auth (python-jose + passlib)

### Edge
- FastAPI + Uvicorn (Python)
- ONNX Runtime (YOLOv8/v10, YOLOE, YOLO-World inference)
- Moondream VLM (0.5B/2B) for natural language queries
- OpenCV, APScheduler, Prometheus metrics
- IntelliOptics SDK (https://github.com/thamain1/IntelliOptics-SDK)

## Project Structure
```
IntelliOptics 2.0/
├── cloud/
│   ├── frontend/           # React UI
│   │   └── src/
│   │       ├── pages/      # See "Frontend Pages" section below
│   │       └── components/ # See "Frontend Components" section below
│   ├── backend/            # FastAPI backend
│   │   └── app/
│   │       ├── main.py     # Entry point (14+ routers)
│   │       ├── routers/    # detectors, queries, demo_streams, escalations, hubs,
│   │       │               # alerts, users, camera_inspection, deployments,
│   │       │               # annotations, settings, admin, open_vocab,
│   │       │               # vehicle_id, forensic_search, parking
│   │       ├── services/   # yoloworld_inference.py
│   │       ├── models.py   # SQLAlchemy ORM
│   │       ├── schemas.py  # Pydantic schemas
│   │       ├── config.py   # Pydantic settings
│   │       ├── database.py # SQLAlchemy engine + session
│   │       ├── auth.py     # JWT auth
│   │       └── utils/      # supabase_storage.py
│   ├── worker/             # Cloud inference worker
│   │   ├── onnx_worker.py  # Health + /infer HTTP server
│   │   └── detector_inference.py  # Detector-aware inference, model caching, letterbox, NMS
│   ├── nginx/              # Nginx routing config
│   └── docker-compose.yml  # Services: nginx, backend, frontend, worker
├── edge/
│   ├── edge-api/           # Edge API service
│   │   └── app/
│   │       ├── main.py
│   │       ├── api/routes/ # health, image-queries, ping
│   │       ├── core/       # edge_inference.py, configs.py, models
│   │       └── escalation_queue/ # Queue uncertain results for cloud
│   ├── inference/          # ONNX inference service
│   │   ├── inference_service.py  # Multi-detector: /infer, /yoloworld, /yoloe, /vlm/*, /vehicle-id/*
│   │   ├── yoloe_inference.py    # YOLOE open-vocab detection
│   │   ├── vlm_inference.py      # Moondream VLM (query, detect, OCR)
│   │   ├── vehicle_id.py         # Vehicle ID pipeline (YOLOE + VLM)
│   │   ├── forensic_search.py    # BOLO forensic video search engine
│   │   └── yolov8s-worldv2.pt   # Sample model
│   ├── nginx/
│   ├── config/
│   │   └── edge-config.yaml      # Detector configurations
│   └── docker-compose.yml  # Services: nginx, edge-api, inference, postgres
├── docs/
│   ├── README.md           # Main architecture & quick start (449 lines)
│   ├── README-FOR-OTHER-AI.md  # AI handoff doc with known issues
│   ├── ARCHITECTURE.md
│   ├── DETECTOR-CREATION-GUIDE.md
│   ├── WEB-INTERFACE-GUIDE.md
│   ├── CAMERA-HEALTH-MONITORING.md
│   ├── HRM-TRAINING.md     # Phase 2: Hierarchical Reasoning Model
│   └── LOW-CONFIDENCE-ISSUE-ANALYSIS.md
├── hrm-training/           # Phase 2 HRM training module
├── install/
│   ├── README.md           # Installation guide
│   ├── install-windows.ps1
│   └── deploy-azure.ps1
├── generate_presentation.py    # 20-slide PowerPoint generator
├── add_bolo_slide.py           # Adds BOLO slide to existing PPTX
├── IntelliOptics_Smart_Detection_Plan.pptx  # 21-slide team presentation
└── test-builds.sh
```

## Frontend Pages (18 existing)
| Page | File | Purpose |
|------|------|---------|
| Login | `LoginPage.tsx` | Azure MSAL + local JWT auth |
| Admin | `AdminPage.tsx` | System administration |
| Detectors | `DetectorsPage.tsx` | List/CRUD all detectors |
| Detector Config | `DetectorConfigPage.tsx` | Full detector configuration (model upload, thresholds, NMS) |
| Detector Alerts Config | `DetectorAlertConfigPage.tsx` | Per-detector alert settings |
| Detector Alerts | `DetectorAlertsPage.tsx` | Alert history |
| Escalation Queue | `EscalationQueuePage.tsx` | Human review of low-confidence detections |
| Query History | `QueryHistoryPage.tsx` | Past inference queries |
| Demo Streams | `DemoStreamPage.tsx` | Live video streaming (YouTube/webcam/RTSP), YOLOWorld IntelliSearch |
| Camera Inspection | `CameraInspectionPage.tsx` | Camera health monitoring |
| Hub Status | `HubStatusPage.tsx` | Edge device status |
| Deployment Manager | `DeploymentManagerPage.tsx` | Deploy detectors to edge hubs |
| Alert Settings | `AlertSettingsPage.tsx` | Global alert configuration |
| Detector Metrics | `DetectorMetricsPage.tsx` | Performance analytics |
| Data Management | `DataManagementPage.tsx` | Data export/management |
| Users | `UsersPage.tsx` | User management |
| Settings | Various | Application settings |

## Frontend Pages (New — Implemented)
| Page | File | Purpose |
|------|------|---------|
| Open Vocab | `OpenVocabPage.tsx` | YOLOE detection + VLM query with image upload |
| Vehicle Search | `VehicleSearchPage.tsx` | Search vehicles by plate/color/type with CSV export |
| Forensic Search | `ForensicSearchPage.tsx` | BOLO video forensic search with progress tracking |
| Parking Dashboard | `ParkingDashboardPage.tsx` | Maven Parking zone occupancy + violations + events |

## Frontend Components (Existing)
| Component | File | Purpose |
|-----------|------|---------|
| BoundingBoxAnnotator | `BoundingBoxAnnotator.tsx` | Interactive bbox annotation (normalized coords, 8-color palette) |
| DetectorMetrics | `DetectorMetrics.tsx` | Recharts performance visualization |
| KeyValueEditor | `KeyValueEditor.tsx` | Generic key-value pair editor |

## Frontend Components (New — Implemented)
| Component | File | Purpose |
|-----------|------|---------|
| LiveBboxOverlay | `LiveBboxOverlay.tsx` | HTML5 Canvas overlay for real-time bbox rendering at 30fps over video/image |

## Detector Modes
- `BINARY` — Yes/No, Pass/Fail
- `MULTICLASS` — Defect type classification
- `COUNTING` — Object counting with max threshold
- `BOUNDING_BOX` — Object detection with ROIs
- `OPEN_VOCAB` — Open-vocabulary detection via YOLOE/YOLO-World + VLM (default for new detectors)

## Running Locally

### Cloud (Docker Compose)
```bash
cd "/c/dev/IntelliOptics 2.0/cloud"
docker compose up
# Frontend: http://localhost:3000
# Backend: http://localhost:8000
```

### Edge (Docker Compose)
```bash
cd "/c/dev/IntelliOptics 2.0/edge"
docker compose up
# Edge API: http://localhost:30101
```

### Frontend Dev (no Docker)
```bash
cd "/c/dev/IntelliOptics 2.0/cloud/frontend"
npm run dev   # Vite dev server
npm run build # Production build
npm run serve # Preview build
```

## Key Concepts

### Detector-Centric Design
- Each **Detector** is a named inspection point (e.g., "Vehicle Detection Lot A")
- Controls its own: AI model, confidence threshold, escalation logic, alert config
- CRUD managed via `/detectors` API and frontend Detectors page

### Confidence-Based Escalation
- Edge runs primary model + OODD (Out-of-Domain Detection) model
- If confidence < threshold → image goes to cloud escalation queue
- Human reviewer approves/rejects in the Escalation Queue UI
- Approved annotations can be used for model retraining

### Model Format
- ONNX `.buf` files stored at edge in versioned paths: `/primary/1`, `/primary/2`, `/oodd/1`
- YOLOv8/v10 architecture
- Model Updater service pulls new models from cloud automatically

### Dual-Track Architecture (Open-Vocab — Implemented)
- **Fast track**: YOLOE runs every frame (15-30 FPS) — real-time object detection
- **Smart track**: Moondream VLM runs every 10th-30th frame (1-3/sec) — complex queries
- Async, non-blocking: VLM never stalls YOLOE detection
- Configured via `edge-config.yaml` → `vlm_config.dual_track_enabled`

### Vehicle ID Pipeline (Implemented)
- YOLOE detects vehicles + license plates
- VLM OCR reads plate text, queries vehicle color and type
- Spatial overlap matching: plate bbox inside vehicle bbox = belongs to that vehicle
- Frontend: VehicleSearchPage.tsx with search/filter and CSV export
- Backend: `/vehicle-id` router (identify, search, list)
- Edge: `/vehicle-id/identify` endpoint in inference_service.py

### Video Forensic Search / BOLO (Implemented)
- Extract DVR frames at configurable intervals (1-2 sec)
- YOLOE batch scan at high throughput on GPU (falls back to CPU)
- VLM confirms only on candidate frames
- Natural language queries: "Man with red backpack near Lot C around 3PM"
- Frontend: ForensicSearchPage.tsx with job creation, progress tracking, result review
- Backend: `/forensic-search` router (jobs CRUD, results, stop)
- Edge: forensic_search.py engine

## Environment Variables

### Cloud Backend (`.env.template` — 180 vars)
Key vars:
- `POSTGRES_PASSWORD`, `POSTGRES_DSN`
- `SUPABASE_URL`, `SUPABASE_KEY`
- `SENDGRID_API_KEY`, `ALERT_RECIPIENT_EMAIL`
- `API_SECRET_KEY`
- `YOLOWORLD_WORKER_URL`
- `REACT_APP_API_URL`, `REACT_APP_WS_URL`

### Edge (`.env.template` — 110+ vars)
Key vars:
- `INTELLIOPTICS_API_TOKEN` — token to authenticate with cloud
- `CENTRAL_WEB_APP_URL` — cloud backend URL
- `EDGE_DEVICE_ID`, `EDGE_DEVICE_NAME`
- `SENDGRID_API_KEY` (for local email alerts)
- `CONFIDENCE_THRESHOLD`

## Current Versions
- Backend: v2.0.3
- Frontend: v2.0.2
- Worker: v2.0.0

## Licensing
- YOLOE / YOLO-World: AGPL-3.0 (need Ultralytics Enterprise license for client distribution)
- Moondream VLM: Apache 2.0 (free for all use)

## Known Issues / Docs
- Low-confidence issue on "Vehicle Detection Lot A": see `docs/LOW-CONFIDENCE-ISSUE-ANALYSIS.md`
- OODD disable quick fix: `docs/QUICK-FIX-OODD-DISABLE.md`
- Detector model path issues: `docs/DETECTOR-MODEL-PATH-FIX.md`
- AI handoff context: `docs/README-FOR-OTHER-AI.md`

## GPU Compatibility
- GPUs with compute capability < 7.0 (e.g., GTX 1050 Ti) cannot run PyTorch 2.10+ CUDA kernels
- `torch.cuda.is_available()` returns True but kernels fail at runtime
- All inference services check `torch.cuda.get_device_capability()` and fall back to CPU automatically
- Affected files: `yoloe_inference.py`, `vlm_inference.py`, `inference_service.py` (all have the fix)

## Recent Fixes (March 2026)
- **Bbox normalization**: YOLOWorld endpoint now returns normalized 0-1 bounding boxes (was pixel-space)
- **Live prompt updates**: IntelliSearch prompts can be changed during active session via Update button
- **detections_json**: `process_yoloworld_inference` now stores detections on the query for LiveBboxOverlay
- **Data purge**: Converted synchronous purge to background task (was hanging on 40K+ records)
- **CUDA fallback**: All edge inference paths check GPU compute capability before using CUDA

## Phase 2 (Planned)
- **HRM (Hierarchical Reasoning Model)**: Explainable AI showing reasoning transparency
- Training pipeline: `hrm-training/` directory
- Guide: `docs/HRM-TRAINING.md`
