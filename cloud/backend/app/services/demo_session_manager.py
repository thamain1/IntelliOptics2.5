"""Manager for active demo capture sessions."""
from __future__ import annotations

import uuid
import base64
import json
import logging
import requests
from typing import Dict, Optional
from datetime import datetime
from threading import Thread

from sqlalchemy.orm import Session as DBSession

from ..services.youtube_capture import YouTubeFrameGrabber, MockFrameGrabber
from ..services.inference_service import InferenceService
from ..utils.supabase_storage import upload_blob
from ..config import get_settings
from .. import models


logger = logging.getLogger(__name__)
settings = get_settings()


def _process_inference_local(query_id: str, result_id: str, image_bytes: bytes, detector_id: str):
    """Call cloud worker HTTP endpoint for immediate inference."""
    from ..database import SessionLocal

    db = SessionLocal()
    try:
        query = db.query(models.Query).filter(models.Query.id == query_id).first()
        result = db.query(models.DemoDetectionResult).filter(models.DemoDetectionResult.id == result_id).first()
        detector = db.query(models.Detector).filter(models.Detector.id == detector_id).first()

        if not query or not result or not detector:
            logger.error(f"Query {query_id}, result {result_id}, or detector {detector_id} not found")
            return

        try:
            # Get detector and config for model path and class names
            detector = db.query(models.Detector).filter(
                models.Detector.id == detector_id
            ).first()
            detector_config = db.query(models.DetectorConfig).filter(
                models.DetectorConfig.detector_id == detector_id
            ).first()

            # Use the actual model path from detector/config, fallback to default
            model_path = (
                (detector_config.primary_model_blob_path if detector_config else None) or
                (detector.primary_model_blob_path if detector else None) or
                f"{detector_id}/primary/model.onnx"
            )

            config_data = {
                "detector_id": detector_id,
                "primary_model_blob_path": model_path,
                "class_names": detector_config.class_names if detector_config else [],
                "confidence_threshold": detector_config.confidence_threshold if detector_config else 0.5,
                "detection_params": {
                    "min_score_threshold": 0.25,
                    "iou_threshold": 0.45,
                    "max_detections": 100
                },
                "mode": detector_config.mode if detector_config else "BOUNDING_BOX"
            }

            logger.info(f"🚀 [QUERY {query_id}] Sending to cloud worker: {settings.worker_url} (Size: {len(image_bytes)} bytes, classes: {config_data['class_names']})")

            # Send multipart form data with image and config
            import io
            files = {
                'image': ('frame.jpg', io.BytesIO(image_bytes), 'image/jpeg'),
                'config': ('config.json', io.BytesIO(json.dumps(config_data).encode()), 'application/json')
            }
            response = requests.post(
                settings.worker_url,
                files=files,
                timeout=30
            )

            logger.info(f"📥 [QUERY {query_id}] Worker Response Status: {response.status_code}")

            if response.status_code != 200:
                logger.error(f"❌ [QUERY {query_id}] Worker returned error: {response.text}")
                response.raise_for_status()

            # Parse inference result
            inference_result = response.json()
            detections = inference_result.get("detections", [])
            logger.info(f"🔍 [QUERY {query_id}] Detections found: {len(detections)}")

            # Determine label and confidence from detections
            if detections:
                best_detection = max(detections, key=lambda d: d.get("confidence", d.get("conf", 0)))
                label = best_detection.get("label", "detected")
                confidence = best_detection.get("confidence", best_detection.get("conf", 0.0))
            else:
                label = "no_detection"
                confidence = 0.0

            # Update query
            query.result_label = label
            query.confidence = confidence
            query.status = "DONE"

            # Update demo result
            result.result_label = label
            result.confidence = confidence
            result.status = "DONE"
            result.completed_at = datetime.utcnow()

            # Update session stats
            session = result.session
            if session and label != "no_detection" and len(detections) > 0:
                session.total_detections += len(detections)

            db.commit()

            # Create additional result records for other detections
            if len(detections) > 1:
                for detection in detections[1:]:
                    additional_result = models.DemoDetectionResult(
                        session_id=result.session_id,
                        query_id=query.id,
                        detector_id=result.detector_id,
                        frame_number=result.frame_number,
                        capture_method=result.capture_method,
                        result_label=detection.get("label"),
                        confidence=detection.get("confidence", detection.get("conf", 0.0)),
                        status="DONE",
                        completed_at=datetime.utcnow()
                    )
                    db.add(additional_result)
                db.commit()

        except requests.RequestException as e:
            logger.error(f"❌ [QUERY {query_id}] Worker inference failed: {e}")
            query.status = "ERROR"
            result.status = "ERROR"
            result.completed_at = datetime.utcnow()
            db.commit()

    except Exception as e:
        logger.error(f"Error processing inference for query {query_id}: {e}", exc_info=True)
    finally:
        db.close()


class DemoSessionManager:
    """Manages active video capture sessions."""

    def __init__(self):
        self._active_sessions: Dict[str, YouTubeFrameGrabber] = {}
        self._latest_frames: Dict[str, bytes] = {}  # session_id -> latest JPEG bytes
        self._session_prompts: Dict[str, str] = {}  # session_id -> current prompts (mutable)

    def update_prompts(self, session_id: str, prompts: str) -> bool:
        """Update prompts for an active session (takes effect on next frame)."""
        if session_id in self._active_sessions:
            self._session_prompts[session_id] = prompts
            logger.info(f"Updated prompts for session {session_id}: {prompts[:50]}")
            return True
        return False

    def get_prompts(self, session_id: str) -> Optional[str]:
        """Get current prompts for a session."""
        return self._session_prompts.get(session_id)

    def get_latest_frame(self, session_id: str) -> Optional[bytes]:
        """Get the latest captured frame for a session."""
        return self._latest_frames.get(session_id)

    def start_session(
        self,
        session_id: str,
        youtube_url: str,
        capture_mode: str,
        detector_ids: list[str],
        db: DBSession,
        polling_interval_ms: int = 2000,
        motion_threshold: float = 500.0,
        yoloworld_prompts: str = None,
    ) -> None:
        """
        Start a new capture session.

        Args:
            session_id: UUID of the demo session
            youtube_url: YouTube URL to capture
            capture_mode: 'motion' or 'polling'
            detector_ids: List of detector IDs to submit frames to
            db: Database session
            polling_interval_ms: Interval for polling mode
            motion_threshold: Threshold for motion detection mode
            yoloworld_prompts: Comma-separated prompts for YOLOWorld mode (optional)
        """
        if session_id in self._active_sessions:
            logger.warning(f"Session {session_id} already active")
            return

        # Store initial prompts so they can be updated later
        if yoloworld_prompts:
            self._session_prompts[session_id] = yoloworld_prompts

        logger.info(f"Starting capture session {session_id} in {capture_mode} mode")

        # Create callback for frame submission
        def on_frame_captured(image_bytes: bytes, frame_number: int):
            """Handle captured frame - submit to detectors or YOLOWorld."""
            logger.info(f"🎞️ Frame callback triggered for session {session_id}, frame {frame_number}, size {len(image_bytes)}")

            # Store latest frame for UI display
            self._latest_frames[session_id] = image_bytes
            try:
                # Get fresh DB session
                from ..database import SessionLocal
                db_local = SessionLocal()

                try:
                    # Get session from DB
                    session = db_local.query(models.DemoSession).filter(models.DemoSession.id == session_id).first()
                    if not session or session.status != 'active':
                        logger.info(f"Session {session_id} no longer active, skipping frame")
                        return

                    # Upload to blob storage
                    blob_name = f"demo-sessions/{session_id}/{uuid.uuid4()}.jpg"
                    blob_path = upload_blob(
                        settings.supabase_storage_bucket,
                        blob_name,
                        image_bytes,
                        "image/jpeg"
                    )

                    # Check if this is a YOLOWorld session (read live prompts)
                    current_prompts = self._session_prompts.get(session_id) or yoloworld_prompts
                    if current_prompts:
                        # YOLOWorld mode - use open-vocabulary detection
                        from ..services.yoloworld_inference import process_yoloworld_inference

                        # Create query (no specific detector for YOLOWorld)
                        query = models.Query(
                            detector_id=None,
                            image_blob_path=blob_path,
                            status="PENDING",
                            local_inference=True,
                            escalated=False,
                        )
                        db_local.add(query)
                        db_local.flush()

                        # Create detection result
                        result = models.DemoDetectionResult(
                            session_id=session_id,
                            query_id=query.id,
                            detector_id=None,
                            frame_number=frame_number,
                            capture_method="yoloworld",
                            status="PENDING"
                        )
                        db_local.add(result)
                        db_local.flush()

                        # Update session stats
                        session.total_frames_captured += 1
                        db_local.commit()

                        # Trigger YOLOWorld inference with current (possibly updated) prompts
                        thread = Thread(
                            target=process_yoloworld_inference,
                            args=(query.id, result.id, image_bytes, current_prompts),
                            daemon=True
                        )
                        thread.start()

                        logger.info(
                            f"🌍 Frame {frame_number} submitted to YOLOWorld for session {session_id} "
                            f"(prompts: {current_prompts[:50]}...)"
                        )

                    else:
                        # Regular detector mode
                        # Convert to base64 for query creation
                        base64_data = base64.b64encode(image_bytes).decode('utf-8')

                        # Submit to each detector using LOCAL INFERENCE (not Service Bus)
                        query_result_pairs = []
                        for detector_id in detector_ids:
                            detector_uuid = detector_id

                            # Create query with local_inference=True for demo
                            query = models.Query(
                                detector_id=detector_uuid,
                                image_blob_path=blob_path,
                                status="PENDING",
                                local_inference=True,  # Use local worker HTTP endpoint
                                escalated=False,
                            )
                            db_local.add(query)
                            db_local.flush()

                            # Create detection result
                            result = models.DemoDetectionResult(
                                session_id=session_id,
                                query_id=query.id,
                                detector_id=detector_uuid,
                                frame_number=frame_number,
                                capture_method=capture_mode,
                                status="PENDING"
                            )
                            db_local.add(result)
                            db_local.flush()

                            query_result_pairs.append((query.id, result.id, detector_uuid))

                        # Update session stats
                        session.total_frames_captured += 1
                        db_local.commit()

                        # Trigger local inference via worker HTTP endpoint
                        for query_id, result_id, detector_uuid in query_result_pairs:
                            thread = Thread(target=_process_inference_local, args=(query_id, result_id, image_bytes, detector_uuid), daemon=True)
                            thread.start()

                        logger.info(
                            f"Frame {frame_number} submitted to "
                            f"{len(detector_ids)} detectors for session {session_id} (local inference)"
                        )

                finally:
                    db_local.close()

            except Exception as e:
                logger.error(f"Error submitting frame for session {session_id}: {e}", exc_info=True)

        # Create frame grabber
        try:
            # Calculate FPS based on mode
            if capture_mode == 'polling':
                fps = 1000.0 / polling_interval_ms  # Convert ms to fps
            else:  # motion mode - for now just use 1 fps (we'll add motion detection later)
                fps = 1.0

            # Check if we should use mock mode for testing
            is_mock = youtube_url.lower().startswith(('mock://', 'test://'))

            if is_mock:
                logger.info(f"Creating MockFrameGrabber with {fps} fps (test mode)")
                grabber = MockFrameGrabber(fps=fps)
            else:
                logger.info(f"Creating YouTubeFrameGrabber with {fps} fps")
                grabber = YouTubeFrameGrabber(youtube_url=youtube_url, fps=fps)

            grabber.start(on_frame=on_frame_captured)

            self._active_sessions[session_id] = grabber
            logger.info(f"✓ Capture session {session_id} started successfully")

        except Exception as e:
            logger.error(f"✗ Failed to start capture session {session_id}: {e}", exc_info=True)
            # Update session status to error
            try:
                session = db.query(models.DemoSession).filter(models.DemoSession.id == session_id).first()
                if session:
                    session.status = 'error'
                    db.commit()
            except Exception:
                pass
            raise

    def stop_session(self, session_id: str) -> None:
        """
        Stop an active capture session.

        Args:
            session_id: UUID of the session to stop
        """
        capture = self._active_sessions.pop(session_id, None)
        self._latest_frames.pop(session_id, None)
        self._session_prompts.pop(session_id, None)
        if capture:
            logger.info(f"Stopping capture session {session_id}")
            capture.stop()
        else:
            logger.warning(f"Session {session_id} not found in active sessions")

    def is_session_active(self, session_id: str) -> bool:
        """Check if a session is actively capturing."""
        return session_id in self._active_sessions

    def stop_all(self) -> None:
        """Stop all active capture sessions."""
        logger.info(f"Stopping all {len(self._active_sessions)} active sessions")
        for session_id in list(self._active_sessions.keys()):
            self.stop_session(session_id)


# Global session manager instance
session_manager = DemoSessionManager()
