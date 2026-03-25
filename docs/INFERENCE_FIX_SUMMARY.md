# Inference and Demo Page Fix Summary - Jan 15, 2026

## Executive Summary
Addressed multiple points of failure preventing inference from working on the YouTube Live Stream Demo page. Fixes spanned from frontend connectivity (Vite proxies) to backend database models and video capture logic.

## Technical Changes

### 1. Connectivity & Routing
*   **Vite Proxy Configuration:** Updated `cloud/frontend/vite.config.ts` to include proxies for `/demo-streams`, `/deployments`, `/detector-alerts`, and other missing endpoints. This fixed 404 errors when the frontend tried to reach these services.
*   **Dynamic Worker URL:** Integrated `WORKER_URL` into the backend settings (`config.py`). Updated `demo_session_manager.py` to use this setting rather than a hardcoded string, facilitating easier troubleshooting in local development.

### 2. Database Models & Schema
*   **SQLAlchemy Syntax Fix:** Corrected a critical error in `cloud/backend/app/models.py` where the `confidence` column was incorrectly defined as `Float = Column(Float)` in both `Query` and `Feedback` models. This was a direct blocker for saving inference results.
*   **Attribute Unification:** Standardized the use of `detector_metadata` across `models.py`, `schemas.py`, and the `detectors.py` router to ensure data persistence and API validation work reliably.

### 3. Background Processing & Capture Logic
*   **Isolated DB Sessions:** Refactored `process_demo_query` in `routers/demo_streams.py` to use a fresh `SessionLocal`. This prevents "session already closed" errors when processing inference results asynchronously.
*   **Robust JPEG Extraction:** Improved `YouTubeFrameGrabber` in `services/youtube_capture.py` to identify frames using both `\xff\xd8` (start) and `\xff\xd9` (end) markers. This prevents the worker from receiving partial or corrupted image data.
*   **Enhanced Stream Extraction:** Changed `yt-dlp` extraction format to `'best'` to ensure FFmpeg receives a reliable stream for all YouTube sources.

### 6. Elimination of Simulated Data (Real Inference Only)
*   **Refactored Inference Service:** Created a centralized `InferenceService` that handles communication with the cloud worker.
*   **Updated Demo Streams:** Replaced random data generation in `process_demo_query` with real worker-backed inference.
*   **Updated Image Queries:** Refactored `POST /queries` to perform real local inference instead of returning random "pass/fail" results.
*   **Async Threading:** Updated background tasks to correctly handle asynchronous worker calls.

## Root Cause Analysis of "Inference Not Working"
The failure was likely caused by a combination of:
1.  **Proxies:** Frontend could not start sessions due to 404s.
2.  **DB Errors:** Once started, the backend likely crashed trying to save results to the incorrectly defined `confidence` column.
3.  **Corrupt Frames:** Partial JPEG data being piped to the worker.

## Next Verification Steps
1.  Verify the `worker` container logs to ensure it is receiving and processing requests at `/infer`.
2.  Check the `backend` logs for `on_frame` callback successes.
3.  Ensure the `.env` file has a valid `MODEL_URL` and `AZURE_STORAGE_CONNECTION_STRING`.
