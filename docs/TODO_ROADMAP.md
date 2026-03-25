# IntelliOptics 2.0 - TODO / Roadmap

## Status Legend
- [ ] Not started
- [x] Completed
- [~] In progress

---

## Completed This Session (Jan 16-17, 2026)

- [x] Fix demo stream capture (switched from YouTube to EarthCam/streamlink)
- [x] Rename page to "Live Stream Demo" (removed YouTube designation)
- [x] Add live frame preview from server captures
- [x] Add local webcam/USB camera support for demos

---

## High Priority - Edge Device / Hub Registration

### Automatic Hub Registration
- [ ] **Implement automatic edge device registration ("call home")**
  - Edge device calls cloud API on startup to register itself
  - Cloud creates Hub record if device_id doesn't exist
  - Link edge device_id to hub record automatically
  - Return hub configuration to edge device

- [ ] **Implement hub heartbeat system**
  - Periodic heartbeat from edge to cloud (e.g., every 30-60 seconds)
  - Update `last_ping` and `status` on Hub record
  - Detect offline hubs (no heartbeat for X minutes)
  - Dashboard shows hub online/offline status in real-time

- [ ] **Add hub registration API endpoint**
  - `POST /hubs/register` - accepts device_id, friendly_name, metadata
  - Creates hub if new, updates if existing
  - Returns hub_id and any pending deployments/configs

- [ ] **Edge startup registration flow**
  - On edge-api startup, call cloud registration endpoint
  - Store assigned hub_id locally
  - Begin heartbeat loop after successful registration

---

## High Priority - Model Management & Reporting

### Metrics Collection Gaps
- [ ] **Add inference latency tracking**
  - Track processing time per query
  - Store in Query table or separate metrics table
  - Enable performance monitoring and SLA tracking

- [ ] **Implement model version tracking**
  - Track version history when models are updated
  - Link queries to specific model versions
  - Enable performance comparison across versions

- [ ] **Add data drift detection**
  - Baseline comparison for input distributions
  - Alert when inputs deviate from training data
  - Track confidence distribution changes over time

### Analytics Infrastructure
- [ ] **Build aggregate metrics rollups**
  - Daily/weekly accuracy rollups per detector
  - Scheduled jobs or materialized views
  - Pre-computed stats for fast dashboard loading

- [ ] **Add detailed accuracy breakdown**
  - False positive / false negative rates
  - Per-class performance (accuracy by label type)
  - Confusion matrix data per detector

- [ ] **Track operational metrics**
  - Confidence score distributions
  - Throughput metrics (queries per hour/day per detector)
  - Escalation rates over time

### Reporting UI
- [ ] **Create model management dashboard**
  - Visualize accuracy trends over time
  - Show performance comparisons across detectors
  - Display drift alerts and anomalies
  - Export reports for stakeholders

---

## High Priority - UI Improvements

### Sign In Page
- [ ] **Update sign in page to match application theme**
  - Estimated effort: 1-2 hours
  - Apply consistent styling/colors with rest of application
  - Add company logo to sign in page

### Footer
- [ ] **Add company branding to footer**
  - Estimated effort: 15-30 minutes
  - Add "4wardmotion Solutions, inc" to footer
  - Apply to all pages (likely in shared layout component)

### Navigation Menu
- [ ] **Clean up and better organize menu**
  - Estimated effort: 1-2 hours
  - Review current menu structure and groupings
  - Organize related items together (e.g., detector management, monitoring, demos)
  - Improve visual hierarchy and spacing
  - Consider collapsible sections for related features

### Deployment Manager
- [ ] **Fix detectors list not importing**
  - Bug: Deployment manager is not importing the detectors list
  - Investigate: API call, data parsing, or state management issue
  - Critical for deployment workflow

### Model Repository Page
- [ ] **Create model repository page with glossary and inventory**
  - List all available models in the system
  - Display model metadata (name, type, version, architecture)
  - Glossary of model types and their use cases
  - Show which detectors are using each model
  - Model upload/download capabilities (future)

### Detector Performance Analytics
- [ ] **Review/implement performance analytics per detector**
  - Display accuracy, precision, recall metrics per detector
  - Show detection counts, error rates over time
  - Visualize trends (charts/graphs)
  - Compare ground truth vs predictions

### Detector Management Page
- [ ] **Add delete button for detectors**
  - Estimated effort: 1-2 hours
  - Add trash icon to each detector row
  - Confirmation modal before delete
  - Call DELETE endpoint
  - Refresh list after deletion

- [ ] **Add sort/group by group functionality**
  - Estimated effort: 2-4 hours
  - Add dropdown or tabs for group filtering
  - Collapsible sections per group
  - group_name data already exists in backend

- [ ] **Address page length for large detector lists**
  - Pagination
  - Collapsible group accordions
  - Search/filter bar (can reuse from demo page)
  - Virtual scrolling (if 1000+ detectors)

### Escalation Page
- [ ] **Fix image not appearing in review modal**
  - Estimated effort: 1-2 hours
  - Bug: Image does not display in the escalation review modal
  - Investigate: signed URL generation, image fetch, or rendering issue
  - Critical for reviewer workflow

### Query History Page
- [ ] **Remove verified queries from default view**
  - Estimated effort: 1-2 hours
  - Hide queries once ground truth is submitted
  - Add toggle/filter to show all vs pending only
  - Keeps the list focused on items needing review

- [ ] **Group queries by detector**
  - Estimated effort: 2-3 hours
  - Collapsible sections per detector
  - Show detector name as group header
  - Count of pending vs verified per group

- [ ] **Address page length for large query lists**
  - Pagination
  - Filter by status (pending, verified, escalated)
  - Date range filter
  - Search by detector name

### Camera Health Monitoring Page
- [ ] **Rename "Camera Health Inspection" to "Camera Health Monitoring"**
  - Estimated effort: 30 min - 1 hour
  - Update page title, navigation, labels in frontend
  - Update backend route comments/docstrings if needed
  - Update any user-facing text referencing "inspection"

- [ ] **Verify camera health monitoring works end-to-end**
  - Estimated effort: 1-2 hours (testing only)
  - Code is implemented (backend + frontend complete)
  - Requires: cameras in DB, hubs configured, camera_inspection_worker running
  - Test: Dashboard loads, health records appear, alerts work
  - Note: May work already - needs production testing with real cameras

### Image Annotation Feature
- [ ] **Add ability to annotate images directly in UI**
  - Estimated effort: 2-5 days (using existing libraries)
  - **Fast path (1-2 days):**
    - Integrate library (react-image-annotate, annotorious, or similar)
    - Add backend endpoints to save/load annotations
    - New database table for annotation data (bboxes, labels, image refs)
  - **Full-featured (1-2 weeks):**
    - Multiple annotation types (bbox, polygon, keypoints)
    - Label management UI
    - Export to training formats (COCO, YOLO, Pascal VOC)
    - Annotation review/approval workflow
    - Integration with training pipeline

---

## Medium Priority - Demo Page Enhancements

### RTSP Support
- [ ] **Add RTSP stream support to demo page**
  - Estimated effort: Easy (streamlink/FFmpeg already support RTSP)
  - Allow `rtsp://` URLs in input validation
  - Test with common RTSP camera formats

### Counting Detector Display
- [ ] **Show counting results on detector config page**
  - Display count value from counting models
  - Show on test image results
  - Estimated effort: 1-2 hours

---

## Low Priority - Future Enhancements

### Model Support
- [ ] Investigate MCNN model support in worker
  - Check worker inference runtime (ONNX? PyTorch?)
  - May need worker modifications for non-YOLO architectures

### Edge Deployment
- [ ] Document edge deployment steps
  - Pre-configured Docker images
  - One-liner deployment command
  - Target: 10-30 minute deployment time

---

## Documentation Needed

- [ ] Complete deployment documentation
  - Cloud resource setup (Azure Blob, Database)
  - Environment configuration guide
  - Docker deployment steps
  - Edge device setup
  - Target: Enable 1-hour deployment for experienced users

---

## Notes

### Deployment Time Estimates (Clean Environment)
- **Full cloud + edge setup (new to stack):** 1-2 days
- **Full cloud + edge setup (experienced):** 2-4 hours
- **Edge only (cloud configured):** 10-30 minutes

### What's in the Repo
- All code, Dockerfiles, configs for build: YES
- External dependencies needed:
  - ML models (Azure Blob Storage)
  - Database content (detectors, users)
  - Secrets/credentials (.env file)
