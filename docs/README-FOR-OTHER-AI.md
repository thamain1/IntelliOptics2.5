# IntelliOptics 2.0 — AI Handoff Document

**Last Updated**: March 2026

This document provides context for AI assistants working on this codebase. Read `CLAUDE.md` in the repo root for full project context, tech stack, and file structure.

---

## System Overview

IntelliOptics 2.0 is an edge-first AI inspection platform with two Docker Compose stacks:

- **Cloud** (`cloud/`): FastAPI backend, React frontend, nginx, ONNX worker — 4 containers
- **Edge** (`edge/`): Edge API, multi-model inference service, nginx, postgres — 4 containers

The cloud uses **Supabase** for PostgreSQL and blob storage (not Azure). All AI inference runs on the **edge** device. The cloud handles human review, alerts, and the management UI.

---

## Current State (March 2026)

### What Works
- All 8 Docker containers build and run
- Open-vocabulary detection via YOLOE and YOLO-World
- Moondream VLM queries (natural language image analysis)
- IntelliSearch live stream detection with real-time bounding box overlay
- Vehicle identification pipeline (YOLOE + VLM OCR)
- Forensic video search (BOLO) with job management
- Parking dashboard with zone management
- Confidence-based escalation to human review queue
- Email/SMS alerts via SendGrid/Twilio
- Data management with background purge
- 17 frontend pages, 19 backend routers, 9 edge inference endpoints

### Known Issues

1. **GPU Compute Capability**: GPUs with capability < 7.0 (e.g., GTX 1050 Ti) can't run PyTorch CUDA kernels even though `torch.cuda.is_available()` returns True. All inference services have a CPU fallback that checks `torch.cuda.get_device_capability()`. If you see `RuntimeError: Expected all tensors to be on the same device`, the GPU fallback needs to be applied.

2. **OODD Low Confidence on "Vehicle Detection Lot A"**: Detector `2467f56e-07bb-447e-9122-47595563e34a` returns 3-8% confidence because the OODD model thinks parking lot images are out-of-domain. Fix: set `oodd_model_blob_path = NULL` for this detector. See `docs/LOW-CONFIDENCE-ISSUE-ANALYSIS.md` for details.

3. **Edge nginx unhealthy**: The edge nginx container may show as unhealthy — this is a health check configuration issue and doesn't affect functionality.

4. **RTSP streams**: The `edge-config.yaml` `streams` section should be `streams: {}` unless actual cameras are connected. Non-existent RTSP URLs cause `cv2.VideoCapture()` to block edge-api startup.

---

## Architecture Decisions

### Why Supabase (not Azure)?
- Simpler setup: PostgreSQL + blob storage in one service
- No Azure dependency for local/demo deployments
- Cloud backend connects via `SUPABASE_URL` + `SUPABASE_KEY`

### Why Edge-First?
- Latency: sub-100ms inference on edge vs 500ms+ round-trip to cloud
- Privacy: images stay on-device unless escalated
- Cost: only uncertain results consume cloud bandwidth
- Offline capability: edge works without cloud connectivity

### Why YOLOE over YOLO-World?
- YOLOE supports per-request dynamic prompts without model re-parameterization
- YOLO-World requires `model.set_classes()` which can be slower
- Both are available; YOLOE is the default for IO-E Detect mode

### Why Moondream VLM?
- Apache 2.0 license (no AGPL concerns)
- Small enough for edge (0.5B model)
- Supports query, detect, and OCR tasks
- Runs on CPU efficiently

---

## Key Files to Know

### Backend (Cloud)
| File | Purpose |
|------|---------|
| `cloud/backend/app/main.py` | Entry point, registers 19 routers |
| `cloud/backend/app/models.py` | All SQLAlchemy ORM models |
| `cloud/backend/app/schemas.py` | All Pydantic request/response schemas |
| `cloud/backend/app/config.py` | Settings from env vars |
| `cloud/backend/app/routers/demo_streams.py` | Demo sessions, frame capture, live detections, prompt updates |
| `cloud/backend/app/services/demo_session_manager.py` | Manages active capture sessions, YouTubeFrameGrabber |
| `cloud/backend/app/services/yoloworld_inference.py` | Calls edge YOLOWorld/YOLOE endpoints, stores results |

### Frontend
| File | Purpose |
|------|---------|
| `cloud/frontend/src/pages/DemoStreamPage.tsx` | Main demo page — webcam/stream capture, IntelliSearch, IO-E Detect |
| `cloud/frontend/src/components/LiveBboxOverlay.tsx` | Real-time bounding box canvas overlay (expects normalized 0-1 coords) |

### Edge Inference
| File | Purpose |
|------|---------|
| `edge/inference/inference_service.py` | FastAPI app with all endpoints: /infer, /yoloworld, /yoloe, /vlm/*, /vehicle-id/* |
| `edge/inference/yoloe_inference.py` | YOLOE model singleton with CPU fallback |
| `edge/inference/vlm_inference.py` | Moondream VLM singleton with CPU fallback |
| `edge/inference/vehicle_id.py` | Vehicle identification pipeline |
| `edge/inference/forensic_search.py` | BOLO forensic search engine |

### Configuration
| File | Purpose |
|------|---------|
| `edge/config/edge-config.yaml` | All edge config: detectors, open_vocab, VLM, vehicle ID, forensic search |
| `cloud/.env` | Cloud environment variables |
| `edge/.env` | Edge environment variables |

---

## Data Flow: IntelliSearch (Live Stream Detection)

This is the most complex flow in the system:

```
1. User starts session on DemoStreamPage
   → POST /demo-streams/sessions (creates DemoSession record)
   → DemoSessionManager.start_session() creates YouTubeFrameGrabber

2. YouTubeFrameGrabber captures frames at configured FPS
   → on_frame_captured callback fires
   → Frame stored in _latest_frames dict
   → Frame uploaded to Supabase Storage
   → Query + DemoDetectionResult records created

3. If yoloworld_prompts is set:
   → Thread spawned calling process_yoloworld_inference()
   → Sends image to edge /yoloworld endpoint
   → Edge returns normalized bounding boxes
   → Results stored as query.detections_json

4. Frontend polls every 500ms:
   → GET /sessions/{id}/latest-frame → displays <img>
   → GET /sessions/{id}/latest-detections → feeds LiveBboxOverlay
   → GET /sessions/{id} → updates session stats

5. User changes prompts:
   → PUT /sessions/{id}/prompts → updates _session_prompts dict
   → Next frame capture uses new prompts
```

---

## Recent Fixes Applied (March 2026)

| Fix | File(s) | Detail |
|-----|---------|--------|
| Bbox normalization | `edge/inference/inference_service.py` | YOLOWorld `/yoloworld` endpoint now divides bbox by `result.orig_shape` to return 0-1 normalized coords |
| Live prompt updates | `cloud/backend/app/services/demo_session_manager.py`, `demo_streams.py`, `DemoStreamPage.tsx` | Added mutable `_session_prompts` dict, PUT endpoint, and Update button in frontend |
| detections_json storage | `cloud/backend/app/services/yoloworld_inference.py` | Added `query.detections_json = detections` (was missing) |
| Background purge | `cloud/backend/app/routers/data_management.py` | Converted sync purge to FastAPI BackgroundTasks |
| CUDA fallback | `yoloe_inference.py`, `vlm_inference.py`, `inference_service.py` | Check `torch.cuda.get_device_capability() >= 7.0` before using CUDA |
| RTSP blocking fix | `edge/config/edge-config.yaml` | Set `streams: {}` to prevent startup blocking |

---

## How to Rebuild

```bash
# Cloud (from cloud/ directory)
docker compose build backend frontend worker
docker compose up -d

# Edge (from edge/ directory)
docker compose build inference edge-api
docker compose up -d
```

Changes to Python files in `backend/app/` or `edge/inference/` require rebuilding the respective Docker image. Frontend changes in `src/` require rebuilding the frontend image (it runs `npm run build` during Docker build).

---

## What NOT to Touch

1. **Supabase credentials** in `.env` — these are production secrets
2. **Other detectors' data** when fixing a specific detector
3. **Global ONNX models** shared across detectors
4. **Database migrations** — the system uses `create_all()`, not Alembic

---

**Previous version of this doc focused on the OODD low-confidence issue. That info is preserved in `docs/LOW-CONFIDENCE-ISSUE-ANALYSIS.md` and `docs/QUICK-FIX-OODD-DISABLE.md`.**
