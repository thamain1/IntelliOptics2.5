# SAM Segment Enrichment — Technical Design Document
**IntelliOptics 2.5 · 4Ward Motions Solutions, Inc.**
**Status:** Scaffolded (2026-05-01) — uncommitted, requires container rebuild to activate

---

## 1. Problem statement

Every detection IO 2.5 produces today is a **bounding box** — a `[x1, y1, x2, y2]` rectangle. Bounding boxes are the right output for YOLOE's task (fast open-vocabulary detection), but they are the wrong representation for downstream consumers that need to know the actual shape of a detected object:

- Eagle Eye needs a polygon footprint to project onto a geospatial map
- The Analyst Workbench needs a clean object crop without background noise
- The severity scorer needs an area in square meters, not a pixel rectangle estimate
- The active learning loop produces better training labels from polygon masks than from bounding box rectangles

SAM (Segment Anything Model) is a Meta Foundation model that takes a bounding box as a prompt and returns a **pixel-precise mask** of the object within that box. It is not a replacement for YOLOE — it is a post-processing enrichment layer that runs *after* YOLOE, adding shape information to each detection.

---

## 2. Model selection

| Model | Checkpoint size | CPU latency | Notes |
|---|---|---|---|
| **MobileSAM** ← selected | ~10MB | ~40ms/frame | ViT-Tiny encoder; CPU-capable; fits edge inference pattern |
| SAM ViT-B (Meta) | ~375MB | ~200ms CPU | Higher accuracy; GPU preferred |
| SAM ViT-H (Meta) | ~2.4GB | ~800ms CPU | Highest quality; GPU only |
| FastSAM | ~23MB ONNX | ~30ms | YOLO-based; ONNX-native; slightly lower mask quality |

**MobileSAM** (`vit_t`) is the default because:
- Fits IO 2.5's CPU-capable, edge-first philosophy
- Pre-baked into the Docker image at ~10MB (negligible size addition vs. the existing 16GB image)
- Same predictor interface as full SAM — trivially swappable via `SAM_MODEL_TYPE=vit_b` env var
- `mobile-sam` pip package is MIT licensed

Swap path for production deployments with GPU: set `SAM_MODEL_TYPE=vit_b` and place `sam_vit_b_01ec64.pth` in `/models/sam/`. No code changes required.

---

## 3. Architecture

### 3.1 Pipeline position

```
Frame
  │
  ▼
YOLOE ONNX (yoloe_inference.py)
  │  detect_tiled() → [Detection(label, confidence, bbox_pixels)]
  │
  ▼
SAMInference.segment_from_bboxes()  ← NEW (sam_inference.py)
  │  predictor.set_image(image_np)
  │  for each bbox:
  │    predictor.predict(box=bbox, multimask_output=True)
  │    pick highest-score mask
  │    _mask_to_polygon(mask) → Douglas-Peucker simplified contour
  │  → Detection.mask_polygon = [[x,y],...] normalized [0,1]
  │
  ▼  (optional, if vlm_fallback=True)
Moondream VLM (vlm_inference.py)
  │  background-masked crop from mask_polygon → better VLM input
  │
  ▼
Detection.to_normalized() → {label, confidence, bbox[0-1], mask_polygon[0-1]}
  │
  ▼
Eagle Eye ingest worker → PostGIS GEOGRAPHY(POLYGON) via camera homography
```

### 3.2 Opt-in design

SAM enrichment is **opt-in per request**. Callers that don't need masks pay zero overhead:

| Endpoint | SAM call | When |
|---|---|---|
| `POST /yoloe` (default) | No | Normal detection flow, no change |
| `POST /yoloe?segment=true` | Yes | Caller requests enriched detections |
| `POST /segment` | Yes | Standalone: image + bbox array → polygon array |

This preserves the existing `/yoloe` latency for all callers that don't explicitly request segmentation.

### 3.3 Non-fatal design

The service starts and serves all existing endpoints even if:
- `mobile-sam` failed to install (pip install in Dockerfile uses `|| echo` fallback)
- `mobile_sam.pt` checkpoint is absent (wget uses `|| echo` fallback)
- `sam_inference.py` raises any unexpected error (wrapped in try/except in `get_sam()`)

`GET /health` reports `sam_loaded: false` when SAM is unavailable. All other endpoints are unaffected. Callers of `POST /segment` receive a `503` with a clear message.

---

## 4. New files

### 4.1 `edge/inference/sam_inference.py`

Core module. Key components:

**`SAMInference` class**
```python
class SAMInference:
    def load(self) -> bool           # loads MobileSAM predictor; returns False on any failure
    def segment_from_bboxes(        # main entry point
        image_np: np.ndarray,       # RGB HxWx3
        bboxes: list[list[float]]   # [[x1,y1,x2,y2]] pixel coords
    ) -> list[list[list[float]]]    # [[[x,y],...]] normalized 0-1 per bbox
```

**`_mask_to_polygon(mask, img_w, img_h, epsilon_ratio)`**
- Converts binary mask → largest OpenCV contour → Douglas-Peucker simplified polygon
- `epsilon_ratio=0.005` (0.5% of perimeter) gives good detail without excessive vertex count
- Output: `[[x, y], ...]` normalized to [0, 1]

**`get_sam_model()`**
- Global lazy loader
- Searches `SAM_MODEL_DIR` for known checkpoint filenames
- Returns `None` if unavailable (never raises)

### 4.2 Changes to existing files

**`yoloe_inference.py` — `Detection` class**
```python
# Before
class Detection:
    def __init__(self, label, confidence, bbox):
        self.bbox = bbox  # [x1,y1,x2,y2] pixels

# After — backward compatible (mask_polygon defaults to None)
class Detection:
    def __init__(self, label, confidence, bbox):
        self.bbox = bbox
        self.mask_polygon: list[list[float]] | None = None  # set by SAM

    def to_normalized(self, w, h) -> dict:
        d = {"label": ..., "confidence": ..., "bbox": [...normalized...]}
        if self.mask_polygon is not None:
            d["mask_polygon"] = self.mask_polygon  # already normalized
        return d
```

No existing callers are broken. `mask_polygon` is only present in the response when SAM has run.

**`inference_service.py`**
- `sam_instance = None` global + `get_sam()` lazy loader with try/except
- Lifespan pre-loads SAM alongside YOLOE and VLM (non-fatal path)
- `/yoloe` gets `segment: bool = Query(False)` parameter
- SAM block runs after VLM block; adds `sam_enriched: bool` to response
- New `POST /segment` endpoint
- `/health` adds `sam_loaded: bool`

**`edge/inference/Dockerfile`**
- New `sam-downloader` stage (between exporter and vlm-downloader): `wget mobile_sam.pt || echo non-fatal`
- Runtime stage: `pip install mobile-sam || echo non-fatal` (separate RUN, after core requirements)
- `COPY --from=sam-downloader /sam-checkpoint/ /models/sam/`
- `COPY sam_inference.py /app/sam_inference.py`

---

## 5. API reference

### `POST /yoloe?segment=true`

All existing parameters unchanged. New optional parameter:

| Param | Type | Default | Description |
|---|---|---|---|
| `segment` | bool | `false` | Run SAM after YOLOE; adds `mask_polygon` to each detection |

**Response additions when `segment=true`:**
```json
{
  "detections": [
    {
      "label": "vehicle",
      "confidence": 0.87,
      "bbox": [0.12, 0.23, 0.45, 0.67],
      "mask_polygon": [
        [0.13, 0.24], [0.22, 0.23], [0.38, 0.24],
        [0.44, 0.31], [0.44, 0.60], [0.35, 0.67],
        [0.14, 0.66], [0.12, 0.57]
      ]
    }
  ],
  "sam_enriched": true,
  "latency_ms": 312
}
```

`mask_polygon` — list of `[x, y]` pairs, normalized [0, 1] relative to image dimensions. GeoJSON-ready after homography projection.

When `segment=false` (default) or SAM unavailable: `mask_polygon` absent, `sam_enriched: false`.

### `POST /segment`

Standalone segmentation endpoint. Takes image + pre-computed bboxes.

**Query parameters:**
| Param | Type | Required | Description |
|---|---|---|---|
| `bboxes` | string (JSON) | Yes | JSON array of normalized [x1,y1,x2,y2] boxes |

**Example:**
```
POST /segment?bboxes=[[0.10,0.20,0.45,0.70],[0.50,0.10,0.90,0.80]]
Content-Type: multipart/form-data
Body: image=<file>
```

**Response:**
```json
{
  "polygons": [
    [[0.11, 0.21], [0.20, 0.20], [0.43, 0.22], [0.44, 0.68], [0.12, 0.69]],
    [[0.51, 0.11], [0.88, 0.12], [0.89, 0.79], [0.52, 0.78]]
  ],
  "count": 2,
  "latency_ms": 87
}
```

Returns `503` if `sam_loaded: false`. Returns `[]` for individual bboxes that fail (partial success).

### `GET /health`

New field added:
```json
{
  "status": "healthy",
  "yoloe_loaded": true,
  "vlm_loaded": true,
  "sam_loaded": true,
  "cached_models": 2
}
```

---

## 6. Environment variables

| Variable | Default | Description |
|---|---|---|
| `SAM_MODEL_DIR` | `/models/sam` | Directory containing SAM checkpoint |
| `SAM_MODEL_TYPE` | `vit_t` | `vit_t` = MobileSAM, `vit_b` = SAM ViT-B |
| `SAM_CHECKPOINT` | `mobile_sam.pt` | Checkpoint filename within `SAM_MODEL_DIR` |
| `SAM_POLY_EPSILON` | `0.005` | Douglas-Peucker tolerance (0.005 = 0.5% of perimeter) |

---

## 7. Eagle Eye integration points

### 7.1 Map polygon footprints
Eagle Eye's ingest worker receives `mask_polygon` in the IO 2.5 detection payload. It projects the polygon from camera-frame [0,1] coordinates to world coordinates via the camera's calibration homography matrix, producing a `GEOGRAPHY(POLYGON, 4326)` stored in `event_evidence.mask_polygon`.

This replaces the current bbox-projected rectangle on the map with the actual shape of the detected object.

### 7.2 Severity scoring
`event_evidence.mask_area_m2` (computed from the PostGIS polygon) feeds directly into:
- `infrastructure_impact` subscore — polygon intersected against road/building/utility layers
- `population_exposure` subscore — polygon intersected against census block population density
- `velocity` subscore — area delta between consecutive event states (e.g., wildfire growth rate)

### 7.3 Analyst Workbench click-to-segment
1. Analyst clicks on object in evidence frame
2. Frontend sends small auto-generated bbox centered on click → `POST /segment`
3. SAM returns mask polygon in <100ms
4. Analyst tags the segment with a label ("fire perimeter", "damaged structure", "suspect vehicle")
5. Saved as `evidence_region` record linked to `event_evidence`

### 7.4 Active Incident Dashboard (LEO Tier 3)
SAM runs on camera feeds within the incident geofence. Output: person-shaped object outlines in corridors and rooms visible to cameras. Displayed as a polygon overlay layer alongside the WiFi CSI density heatmap (§21.6). Shape + position only — no identification.

### 7.5 Active learning label quality
SAM polygon masks replace bounding-box annotations as pseudo-labels in the active learning loop. Polygon labels produce significantly better YOLOE fine-tuning data. The `evidence_region` records (analyst-verified SAM masks) become the highest-quality training annotations.

---

## 8. DB schema additions (Eagle Eye)

```sql
-- Alembic migration: add polygon footprint to event_evidence
ALTER TABLE event_evidence
    ADD COLUMN IF NOT EXISTS mask_polygon   geography(POLYGON, 4326),
    ADD COLUMN IF NOT EXISTS mask_area_m2   float,
    ADD COLUMN IF NOT EXISTS mask_source    text DEFAULT 'bbox';
    -- mask_source: 'bbox' | 'sam' | 'analyst'

-- Analyst-named segment regions (click-to-segment)
CREATE TABLE IF NOT EXISTS evidence_region (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    evidence_id uuid NOT NULL REFERENCES event_evidence(id),
    label       text NOT NULL,
    polygon     geography(POLYGON, 4326) NOT NULL,
    area_m2     float,
    source      text DEFAULT 'sam',     -- 'sam' | 'analyst_drawn'
    created_by  uuid REFERENCES users(id),
    created_at  timestamptz DEFAULT now()
);

CREATE INDEX ON evidence_region (evidence_id);
```

---

## 9. Build & test checklist

### Rebuild container
```bash
# From C:\Dev\intellioptics_2.5\install or edge\
docker compose -f docker-compose.prod.yml build edge-inference
docker compose -f docker-compose.prod.yml up -d edge-inference
```

### Verify SAM loaded
```bash
curl http://localhost:8001/health
# Expect: "sam_loaded": true
```

### Test standalone segment endpoint
```bash
curl -X POST "http://localhost:8001/segment?bboxes=[[0.1,0.1,0.6,0.8]]" \
  -F "image=@/path/to/test.jpg"
# Expect: {"polygons": [[...]], "count": 1, "latency_ms": ...}
```

### Test enriched YOLOE detection
```bash
curl -X POST "http://localhost:8001/yoloe?prompts=vehicle&segment=true" \
  -F "image=@/path/to/test.jpg"
# Expect: detections include "mask_polygon", "sam_enriched": true
```

### Verify existing endpoints unbroken
```bash
curl -X POST "http://localhost:8001/yoloe?prompts=vehicle" -F "image=@test.jpg"
# Expect: normal response, NO mask_polygon, "sam_enriched": false

curl http://localhost:8001/health
# Expect: yoloe_loaded + vlm_loaded still true
```

### SAM unavailable path (regression test)
```bash
# Rename checkpoint temporarily to simulate absence
mv /models/sam/mobile_sam.pt /models/sam/mobile_sam.pt.bak
curl http://localhost:8001/health  # sam_loaded: false
curl -X POST "http://localhost:8001/segment?bboxes=[[0.1,0.1,0.5,0.5]]" -F "image=@test.jpg"
# Expect: 503 with clear message
curl -X POST "http://localhost:8001/yoloe?prompts=vehicle" -F "image=@test.jpg"
# Expect: normal detection, sam_enriched: false — NOT a 500
```

---

## 10. Failure modes and mitigations

| Failure | Impact | Mitigation in place |
|---|---|---|
| `mobile-sam` pip install fails during Docker build | SAM disabled; all other endpoints work | `pip install mobile-sam \|\| echo` in Dockerfile — build does not fail |
| `mobile_sam.pt` wget fails during Docker build | SAM disabled; all other endpoints work | `wget ... \|\| echo` in Dockerfile |
| `SAMInference.load()` raises at startup | SAM disabled; service starts normally | try/except in `load()` returns `False` |
| `get_sam()` raises unexpectedly | SAM disabled; service starts normally | try/except wrapper in `get_sam()` |
| SAM latency too high on CPU (~200ms for large images) | `/yoloe?segment=true` callers see higher latency | Only opt-in callers affected; default `/yoloe` unaffected |
| `segment_from_bboxes()` fails for one bbox | That bbox gets `[]` polygon; others succeed | Per-bbox try/except with empty fallback |

---

## 11. Upgrade path

When a production deployment has GPU available:

1. Set `SAM_MODEL_TYPE=vit_b` in docker-compose env
2. Download `sam_vit_b_01ec64.pth` to `/models/sam/`
3. Restart `edge-inference` — no code changes

For SAM 2 (video-aware, tracks masks across frames):

1. Replace `mobile_sam` import with `sam2` package when Meta releases stable pip package
2. `SAMInference.load()` and `segment_from_bboxes()` adapt to SAM 2 predictor interface
3. SAM 2 enables per-frame mask tracking — pass masks across frames for consistent temporal segmentation

---

## 12. Standalone IO 2.5 use cases (outside Eagle Eye)

SAM is a force-multiplier for every vertical IntelliOptics 2.5 serves independently. The value proposition is the same in every case: bounding boxes tell you *that* something is there; SAM polygons tell you *exactly where* it is and *how much space it occupies*. That shift from approximate to precise unlocks a tier of spatial reasoning that was previously impossible.

### 12.1 IntelliPark — parking management

| Capability | Without SAM | With SAM |
|---|---|---|
| Space occupancy | Bbox intersects space rectangle → occupied | Vehicle polygon vs. space polygon → % overlap, straddle detection |
| Violation detection | Bbox near fire lane → alert | Vehicle mask in fire lane polygon → alert only when actually inside |
| Double-parking | Hard to distinguish from adjacent cars | Two distinct masks in one space → confirmed double-park |
| Capacity count | Bbox count (over-counts at edges) | Instance mask count — touching vehicles always separated |

Straddle detection alone eliminates most false "occupied" calls in tight lots where adjacent vehicles' bounding boxes bleed into each other.

### 12.2 Perimeter and zone security

**Precise zone triggering:** Bounding box proximity fires alerts before someone actually crosses a line. SAM polygon containment fires only when the person's body mass is inside the zone — eliminating the false positive rate that causes operators to disable alerts.

**Tailgating detection:** Two overlapping bounding boxes → single detection. Two SAM masks that are physically adjacent → confirmed two separate bodies → "one badge scan, two entries" alert.

**Loitering:** SAM mask centroid + area remain stable for N minutes within a defined zone → confirmed stationary presence. Bbox jitter makes this unreliable without masks.

**Equipment clearance zones:** Worker polygon within N pixels of machinery polygon → proximity alert. Only possible with per-object shapes.

### 12.3 Industrial and site safety

**PPE compliance — placement verification:**
- Current: "Hard hat detected in frame" — passes even if the hat is on a shelf
- With SAM: hard hat polygon overlaps head region polygon → hat is *on* the person's head
- Same logic applies to vests, gloves, safety glasses, harnesses

**Defect localization:**
- YOLOE detects "defect" → SAM segments exact defect polygon → `area_m2` calculated → pass if below threshold, fail if above
- Today this requires a human to eyeball the bbox crop and make a judgment call

**Restricted zone compliance:**
- Worker mask enters exclusion zone during active machine operation → immediate alert
- Bbox triggering fires when workers are near the zone; mask triggering fires only when they're in it

### 12.4 Camera health and obstruction detection

**Current:** Camera baseline mismatch score: 0.73 → alert sent, operator investigates.

**With SAM:** "Camera 3 is 61% obscured. Obstruction polygon identified. YOLOE classified it as: cardboard." The operator knows immediately what happened and how severe it is without watching the footage.

Segment the obstruction, compute its area as a fraction of the frame, classify it — automated triage instead of human investigation.

### 12.5 Retail and commercial

**Shelf compliance:** Segment each product → compare polygon positions to planogram → detect gaps (missing product), misplacements (wrong SKU position), wrong facing (product turned backward). Bounding box grids cannot do planogram alignment — they're too coarse to distinguish adjacent SKU positions.

**Queue measurement:** Person polygons in queue zone → total queue area → queue depth estimate without counting individuals. Alert when area exceeds threshold. No identity involved.

**Dwell analytics:** Segment customers → measure time spent in zone → per-zone dwell heatmap. Operational intelligence without any tracking or identification.

### 12.6 Forensic search — evidence export quality

The current BOLO/forensic export attaches a bbox crop to each match — a rectangle including background, adjacent objects, and surrounding context.

With SAM: the export attaches a clean object segment — only the matched vehicle, person, or object on a white background. For law enforcement, insurance, and legal use: a precise segment is materially better evidence than a noisy rectangle. Redaction is also more precise — mask-based face/plate redaction vs. rectangle redaction that over-redacts the surrounding area.

### 12.7 Active learning — faster model improvement

This is the most operationally significant standalone benefit.

Every detection your operators review teaches the system. Currently, they review a bbox — approve or reject — and the system saves a bounding box annotation. The next model fine-tune trains on rectangles.

With SAM: operator clicks approve → SAM generates the polygon mask automatically in the background → polygon annotation saved. The next fine-tune trains on pixel-level labels. For the same number of reviewed frames:
- Better spatial precision in training data
- Fewer epochs to convergence
- Higher final accuracy, especially on objects that are irregular in shape or partially occluded
- Custom detectors improve measurably faster

This compounds: better model → fewer false positives → less review burden → more time to label more data → even better model.

### 12.8 Natural language analysis (VLM) — description quality

**Before:** Moondream receives a bbox crop of a vehicle. The crop includes road, adjacent vehicles, wall, and parking lot markings.

**After:** Moondream receives a background-masked crop — only the vehicle, everything else black-filled.

Result: descriptions shift from scene-level (*"a truck near other vehicles in a parking area"*) to object-level (*"a dark blue flatbed truck with construction equipment in the bed, appears to have a roof-mounted light bar"*).

For forensic search, alert notifications, and investigation reports this is the difference between a usable description and noise.

### 12.9 The `POST /segment` endpoint as a platform API

Beyond the IO 2.5 detection pipeline, `POST /segment` is a general-purpose segmentation service. Any system that produces bounding boxes — another detector, a human annotation tool, a rule-based trigger, a third-party API — can send those boxes to IO 2.5 and receive pixel-precise masks back.

This positions IO 2.5 as the segmentation microservice for the broader 4Ward Motions product stack, not just a camera analysis tool.

---

*4Ward Motions Solutions, Inc. — IntelliOptics 2.5*
