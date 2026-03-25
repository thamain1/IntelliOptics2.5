# IntelliOptics 2.0 — Architecture

## System Architecture

IntelliOptics 2.0 uses a split edge/cloud architecture. AI inference runs entirely on edge devices. The cloud handles management UI, human review, alerts, and data storage via Supabase.

```
┌──────────────────────────────────────────────────────────────────┐
│                        Edge Device                               │
│                                                                  │
│  Client → nginx:30101 ──┬─ Success → edge-api:8718              │
│                          └─ 404 → Cloud Fallback                 │
│                                                                  │
│  edge-api:8718 (Edge Endpoint)                                   │
│    ├─ Image query processing                                     │
│    ├─ Confidence-based escalation                                │
│    └─ Escalation queue (sync to cloud)                           │
│                                                                  │
│  inference:8001 (Multi-Model Inference Service)                  │
│    ├─ POST /infer          — Custom YOLO ONNX (Primary + OODD)  │
│    ├─ POST /yoloworld      — YOLO-World open-vocab detection     │
│    ├─ POST /yoloe          — YOLOE open-vocab detection          │
│    ├─ POST /vlm/query      — Moondream VLM natural language Q&A  │
│    ├─ POST /vlm/detect     — VLM object detection                │
│    ├─ POST /vlm/ocr        — VLM text extraction                 │
│    └─ POST /vehicle-id/identify — Vehicle plate + color + type   │
│                                                                  │
│  postgres:5432 (optional — local detector metadata)              │
└──────────────────────────────────────────────────────────────────┘
         │
         │  Escalation (low confidence / out-of-domain)
         │  Model downloads (new versions)
         ↓
┌──────────────────────────────────────────────────────────────────┐
│                    Central Cloud (Supabase)                       │
│                                                                  │
│  nginx:80/443 → backend:8000  (FastAPI — 19 routers)            │
│              → frontend:3000 (React — 17 pages)                 │
│                                                                  │
│  backend:8000 (FastAPI)                                          │
│    ├─ /detectors          — Detector CRUD, model upload, config  │
│    ├─ /queries            — Image query submission & history     │
│    ├─ /escalations        — Human review queue                   │
│    ├─ /demo-streams       — Live stream sessions & IntelliSearch │
│    ├─ /open-vocab         — YOLOE detect + VLM query (upload)   │
│    ├─ /vehicle-id         — Vehicle search & identification      │
│    ├─ /forensic-search    — BOLO job management & results       │
│    ├─ /parking            — Zone occupancy & violations          │
│    ├─ /hubs               — Edge device management               │
│    ├─ /camera-inspection  — Camera health monitoring             │
│    ├─ /annotations        — Bounding box annotations             │
│    ├─ /data-management    — Retention, purge, export             │
│    ├─ /users              — User CRUD                            │
│    ├─ /settings           — Alert configuration                  │
│    └─ /deployments        — Deploy detectors to edge hubs        │
│                                                                  │
│  worker:8081 (Cloud ONNX Inference Worker)                       │
│    └─ HTTP /infer endpoint for cloud-side inference              │
│                                                                  │
│  Supabase PostgreSQL  — All application data                     │
│  Supabase Storage     — Images, models, exports                  │
│  SendGrid             — Email alerts                             │
│  Twilio               — SMS alerts                               │
└──────────────────────────────────────────────────────────────────┘
```

---

## Inference Architecture

### Custom Detector Inference (Traditional)

```
Image → /infer endpoint
  → Load ONNX model from cache (LRU, keyed by detector_id)
  → Run Primary model → label + raw_confidence
  → Run OODD model (optional) → in-domain score
  → Final confidence = raw_confidence × in_domain_score
  → If confidence >= threshold → Return result (edge-only, fast path)
  → If confidence < threshold → Escalate to cloud human review queue
```

### Open-Vocabulary Detection (YOLOE / YOLO-World)

```
Image + Text Prompts → /yoloe or /yoloworld endpoint
  → Parse comma-separated prompts ("person, car, fire")
  → Load model (singleton, cached)
  → Set detection classes from prompts
  → Run inference → detections with labels, confidence, normalized bboxes
  → Return JSON response
```

**YOLOE** supports per-request dynamic prompts without re-parameterization.
**YOLO-World** uses CLIP text encoding; requires `model.set_classes()` per request.

Both return bounding boxes **normalized to 0-1 range** for direct use by the frontend LiveBboxOverlay component.

### Dual-Track Architecture

For live stream analysis, two inference tracks run concurrently:

```
Frame Stream (15-30 FPS)
  │
  ├─ Fast Track: YOLOE (every frame)
  │   → Real-time object detection
  │   → Bounding boxes with labels
  │   → Sub-100ms latency
  │
  └─ Smart Track: Moondream VLM (every 10th-30th frame)
      → Complex natural language queries
      → Scene understanding, OCR, reasoning
      → 200-500ms latency
      → Never blocks fast track
```

### Vehicle Identification Pipeline

```
Image → YOLOE detect "car, truck, van, motorcycle, license plate"
  → For each detected license plate:
      → VLM OCR: read plate text
      → Find overlapping vehicle bbox (spatial matching)
      → VLM query: vehicle color + type
  → Return: [{plate: "ABC 1234", color: "red", type: "sedan", bbox: [...]}]
```

### Forensic Search / BOLO

```
Video → Extract frames at 1-2 sec intervals
  → YOLOE batch scan all frames (high throughput)
  → Filter candidate frames by detection match
  → VLM confirmation on candidates only (natural language verification)
  → Return matching frames with timestamps and confidence
```

---

## Data Flow: Live Stream Detection (IntelliSearch)

This is the most complex data flow in the system:

```
┌─────────────┐    POST /sessions     ┌──────────────┐
│  Frontend    │ ──────────────────→   │  Backend     │
│  DemoStream  │                       │  demo_streams│
│  Page.tsx    │    Creates session    │  .py         │
└──────┬───────┘                       └──────┬───────┘
       │                                      │
       │  Polls every 500ms:                  │ DemoSessionManager
       │  GET /latest-frame                   │ .start_session()
       │  GET /latest-detections              │
       │  GET /sessions/{id}                  ▼
       │                              ┌──────────────┐
       │                              │ YouTubeFrame │
       │                              │ Grabber      │
       │                              │ (streamlink) │
       │                              └──────┬───────┘
       │                                     │ on_frame_captured
       │                                     ▼
       │                              ┌──────────────┐
       │                              │ Upload to    │
       │                              │ Supabase     │
       │                              │ Storage      │
       │                              └──────┬───────┘
       │                                     │ Thread
       │                                     ▼
       │                              ┌──────────────┐
       │                              │ Edge         │
       │                              │ /yoloworld   │──→ Normalized bbox
       │                              │ endpoint     │    detections
       │                              └──────┬───────┘
       │                                     │
       │                                     ▼
       │                              ┌──────────────┐
       │  GET /latest-detections      │ Query.       │
       │ ◀────────────────────────    │ detections   │
       │                              │ _json        │
       │                              └──────────────┘
       ▼
┌─────────────┐
│ LiveBbox    │  Renders normalized 0-1 bboxes
│ Overlay.tsx │  on HTML5 Canvas at 30fps
└─────────────┘
```

---

## Database Schema (Key Models)

| Model | Purpose |
|-------|---------|
| `User` | Authentication, roles |
| `Detector` | Detector definition, model paths, thresholds |
| `DetectorConfig` | Detailed config (class names, NMS, mode) |
| `Query` | Image inference request + result |
| `Escalation` | Human review queue item |
| `DemoSession` | Live stream capture session |
| `DemoDetectionResult` | Detection result within a demo session |
| `Hub` | Edge device registration |
| `ImageAnnotation` | Bounding box annotation |
| `AlertConfig` | Per-detector alert settings |
| `DetectorAlert` | Alert history |
| `Feedback` | Human feedback on queries |
| `CameraInspectionRun` | Camera health check run |
| `Vehicle` | Identified vehicle record |
| `ForensicSearchJob` | BOLO search job |
| `ParkingZone` | Parking zone definition |
| `ParkingEvent` | Parking entry/exit event |
| `ParkingViolation` | Parking violation record |

---

## Authentication

- **Azure MSAL**: Microsoft identity provider (optional, for enterprise deployments)
- **Local JWT**: `python-jose` + `passlib` for standalone deployments
- Token endpoint: `POST /token`
- All API endpoints require `Authorization: Bearer <token>` header
- Frontend uses Axios interceptors to attach token

---

## Configuration

### Edge Configuration (`edge-config.yaml`)

```yaml
global_config:
  refresh_rate: 60              # Model refresh interval (seconds)
  confident_audit_rate: 0.01    # Audit sampling rate

detectors:                      # Custom ONNX detectors
  det_quality_check_001:
    confidence_threshold: 0.85
    mode: BINARY
    class_names: ["pass", "defect"]

open_vocab_config:              # YOLOE settings
  model: yoloe-v8s
  default_conf: 0.25

vlm_config:                     # Moondream VLM settings
  model: moondream-0.5b
  dual_track_enabled: true

vehicle_id_config:              # Vehicle identification
  enabled: true

forensic_search_config:         # BOLO search
  enabled: true
  frame_interval_seconds: 1.0

alerts:                         # SendGrid email alerts
  enabled: true
```

### Environment Variables

Cloud and edge each have `.env` files with database credentials, API keys, and service URLs. See `.env.template` files for all available variables.

---

## Deployment

### Docker Compose (Local / On-Prem)

```bash
# Cloud stack
cd cloud/ && docker compose up -d
# → nginx (80), backend (8000), frontend (3000), worker (8081)

# Edge stack
cd edge/ && docker compose up -d
# → nginx (30101), edge-api (8718), inference (8001), postgres (5432)
```

### GPU Support

The edge `inference` container supports NVIDIA GPUs via the `nvidia` runtime in docker-compose. If no GPU is available or compute capability < 7.0, inference automatically falls back to CPU.

### Scaling

- **Multiple edge devices**: Each edge device runs its own Docker Compose stack, configured with a unique `EDGE_DEVICE_ID`
- **Cloud is central**: Single cloud deployment manages all edge devices via the Hub Status page
- **No Kubernetes needed**: Docker Compose provides sufficient orchestration for most deployments

---

## Phase 2: HRM AI (Planned)

**Hierarchical Reasoning Model** adds explainable AI:

```
Image → Primary Model (YOLO) → Object detection
      → OODD Model → In-domain check
      → HRM Model → Reasoning layer (context, severity, action)
```

- 27M parameter model, edge-optimized
- Reasoning chains explaining detection decisions
- Few-shot learning (~1000 samples for new detectors)
- See `docs/HRM-TRAINING.md` for the training guide
