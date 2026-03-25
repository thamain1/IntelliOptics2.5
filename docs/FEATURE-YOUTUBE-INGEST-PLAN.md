# Feature Plan: YouTube Live Stream Ingestion

**Status**: Proposed / Planning
**Purpose**: Allow IntelliOptics 2.0 to use public YouTube Live streams as video sources for demos, training data collection, and remote monitoring without physical camera hardware.

---

## 1. Architecture Overview
Currently, the Edge Hub ingests video via **RTSP**. YouTube uses **HLS (HTTP Live Streaming)**. To bridge this, the Edge Hub will act as a "Stream Proxy," resolving the public YouTube URL into a direct video manifest (.m3u8) and processing it locally.

### Data Flow
1.  **Cloud UI**: User enters `https://youtube.com/live/...` into the Camera configuration.
2.  **Edge Hub**: Receives the URL and uses a "Resolver" to find the hidden HLS manifest.
3.  **Local AI**: Hub downloads the live segments and feeds them into the HRM/Detector pipeline just like a local camera.

---

## 2. Technical Requirements

### A. Edge Hub Component (The Resolver)
We will utilize `yt-dlp` (a lightweight, open-source library) on the Edge Hub to handle the YouTube handshake.
*   **Resolver Service**: A new Python class on the Hub that executes `yt-dlp --get-url` to extract the high-resolution `.m3u8` link.
*   **Watchdog Logic**: YouTube stream links expire every 4-6 hours. The Hub must monitor for "Stream EOF" and automatically re-run the resolver to refresh the link without user intervention.

### B. Backend Schema Updates
The `detectors` or `cameras` table requires two new fields:
*   **stream_type**: ENUM (`RTSP`, `YOUTUBE`, `TWITCH`).
*   **source_url**: String (The public URL or the RTSP string).

### C. Frontend UI Enhancements
*   **Source Toggle**: A switch on the "Add Camera" form to choose between "Local RTSP" and "Web Stream."
*   **Live Preview**: An update to the dashboard's "Live View" to support HLS playback (using `video.js` or `hls.js`) so the user can see the YouTube feed directly in the Centralized Web Page.

---

## 3. Implementation Phases

### Phase 1: Edge Resolver (Core)
*   Install `yt-dlp` in the Edge Hub Docker container.
*   Update the `video_ingest.py` service to support `cv2.VideoCapture()` from an HLS URL.
*   Implement segment-buffer logic to ensure the AI doesn't lag if the web stream jitters.

### Phase 2: Cloud Integration
*   Add `stream_type` to the FastAPI models and Pydantic schemas.
*   Expose the source type in the `GET /detectors/{id}/config` endpoint so the Hub knows which ingestion logic to use.

### Phase 3: Demo UI
*   Add a "Demo Mode" button in the Hub settings.
*   Pre-load a "Library" of known 24/7 YouTube streams (e.g., NYC Times Square, Retail Store Cams) for instant one-click demos.

---

## 4. Economic & Performance Impact
*   **Azure Cost**: Zero. Since the Edge Hub downloads the stream directly from YouTube, no video data passes through your Azure Backend until a "Theft" event is escalated.
*   **Edge Load**: Slightly higher CPU usage due to HTTPS overhead, but negligible compared to the GPU inference load.
*   **Dependency**: Requires the Edge Hub to have outbound internet access (standard for IntelliOptics 2.0).

---

## 5. Use Cases
1.  **Sales Demos**: Walk into a meeting and run live theft detection on a public London street cam in 30 seconds.
2.  **Synthetic Training**: Collect high-diversity behavioral data from global retail streams to train the HRM without installing physical cameras.
3.  **Failover Monitoring**: Use a YouTube stream as a secondary "Off-site" view for high-security facilities.
