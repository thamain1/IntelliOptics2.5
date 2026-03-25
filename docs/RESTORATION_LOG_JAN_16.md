# IntelliOptics 2.0 Restoration & Stability Report
**Date:** January 16, 2026
**Status:** System Restored & Stable

## 1. Database & Connectivity Fixes
*   **Azure Migration:** Identified that `docker-compose.yml` had a hardcoded `POSTGRES_DSN` pointing to a local, non-persistent container. Switched the backend to correctly use the Azure PostgreSQL Flexible Server credentials from the `.env` file.
*   **Schema Alignment:** 
    *   Found a mismatch between the codebase (expecting UUIDs) and the existing Azure schema (using Text/String IDs). Updated all models, schemas, and routers to use `String(36)` IDs.
    *   Updated database lookups from `.get(id)` to `.filter(Model.id == id).first()` to ensure robust string matching.
*   **Missing Column Restoration:** Manually added missing columns to Azure tables via `ALTER TABLE` to support current features:
    *   `detectors`: Added `primary_model_blob_path`, `oodd_model_blob_path`, and `model_blob_path`.
    *   `demo_sessions`: Added `error_message` and `last_frame_at`.
    *   `detector_configs`: Added `primary_model_blob_path` and `oodd_model_blob_path`.

## 2. Model & Naming Conflicts
*   **Metadata Collision:** Resolved a critical crash caused by SQLAlchemy's reserved keyword `metadata`. Renamed internal model attributes to `detector_metadata_serialized` and `config_metadata` while maintaining mapping to the actual `metadata` column in the database.
*   **Pydantic Protection:** Configured `protected_namespaces = ()` in Pydantic schemas to prevent conflicts between API fields and internal SQLAlchemy properties.

## 3. Authentication & Access
*   **User Restoration:** Identified that the `users` table was empty after the rebuild. Successfully seeded the admin account:
    *   **User:** `jmorgan@4wardmotions.com`
    *   **Password:** `g@za8560EYAS`
*   **Hashing Compatibility:** Verified and aligned password hashing between `auth.py` and `seed_admin.py` to use `pbkdf2_sha256` for cross-platform stability.
*   **CORS Configuration:** Updated `main.py` to dynamically pull allowed origins from settings, explicitly allowing `http://localhost:3000` to resolve browser login blocks.

## 4. Inference & Demo Engine
*   **Real Local Inference:** Replaced random simulations in `queries.py` and `demo_streams.py`. The system now calls the local `worker` container via `InferenceService` for real-time ONNX processing.
*   **YouTube Capture Fixes:**
    *   Addressed `403 Forbidden` errors by implementing browser-mimicking `User-Agents` in both `yt-dlp` and `FFmpeg`.
    *   Forced IPv4 resolution in the stream extractor to prevent segment fetch failures.
    *   Added explicit logging for frame capture status (`📸 Captured X frames`) to the backend logs for visibility.

## 5. Router & API Logic
*   **Priority Routing:** Fixed a `404 Not Found` error for `/detectors/groups` by moving the static route above the dynamic `/{detector_id}` path in the router configuration.
*   **Sync Logic:** Implemented automatic path syncing so that uploading a model to a detector now correctly updates its associated inference configuration.

## Final Environment State
*   **Backend:** `http://localhost:8000` (FastAPI)
*   **Frontend:** `http://localhost:3000` (Vite/React)
*   **Worker:** Internal Docker network (ONNX Runtime)
*   **Persistence:** Azure PostgreSQL & Azure Blob Storage
