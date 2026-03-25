# Debugging Plan: Demo Stream Detections

**Objective**: Identify why the Demo Stream is not producing detections despite the Worker and Database being healthy.

**Hypothesis**: The recent update to the `Detector` schema (metadata/data points) may have broken the `_process_inference_local` function in the `DemoSessionManager`, or the Worker is returning a response format that the backend no longer expects.

**Planned Actions**:

1.  **Modify `cloud/backend/app/services/demo_session_manager.py`**:
    *   **Location**: Inside the `_process_inference_local` function.
    *   **Change 1 (Pre-Request)**: Log the `WORKER_URL` and the size of the `image_bytes` being sent.
    *   **Change 2 (Post-Request)**: Log the HTTP Status Code and the raw Response Body (first 500 characters) returned by the Worker.
    *   **Change 3 (Parsing)**: Log the specific keys found in the `inference_result` JSON dictionary to verify if `"detections"` exists.

2.  **Restart Service**:
    *   Run `docker restart intellioptics-cloud-backend` to apply the logging changes.

3.  **Verify**:
    *   Start a new Demo Session.
    *   Run `docker logs -f intellioptics-cloud-backend` to inspect the new diagnostic logs.

**No logic changes will be made to the database schema or inference engine during this step.**
