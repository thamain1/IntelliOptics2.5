"""YOLOWorld and YOLOE open-vocabulary detection inference service."""

import logging
import requests
from datetime import datetime

from ..database import SessionLocal
from .. import models
from ..config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Worker endpoints (edge inference service, separate from cloud worker)
YOLOWORLD_WORKER_URL = settings.yoloworld_worker_url
YOLOE_WORKER_URL = settings.yoloe_worker_url


def process_yoloworld_inference(query_id: str, result_id: str, image_bytes: bytes, prompts: str):
    """
    Process YOLOWorld inference with custom text prompts.

    Args:
        query_id: The query record ID
        result_id: The demo detection result ID
        image_bytes: Raw image bytes (JPEG)
        prompts: Comma-separated list of things to detect (e.g., "person, car, fire")
    """
    db = SessionLocal()
    try:
        query = db.query(models.Query).filter(models.Query.id == query_id).first()
        result = db.query(models.DemoDetectionResult).filter(models.DemoDetectionResult.id == result_id).first()

        if not query or not result:
            logger.error(f"Query {query_id} or result {result_id} not found")
            return

        try:
            # Parse and clean prompts
            prompt_list = [p.strip() for p in prompts.split(',') if p.strip()]
            logger.info(f"🌍 [YOLOWorld] Processing with prompts: {prompt_list}")

            # Call YOLOWorld inference endpoint
            response = requests.post(
                YOLOWORLD_WORKER_URL,
                files={'image': ('frame.jpg', image_bytes, 'image/jpeg')},
                params={'prompts': ','.join(prompt_list)},  # Query param as expected by worker
                timeout=180  # YOLOWorld may take longer due to CLIP encoding
            )

            logger.info(f"📥 [YOLOWorld] Worker Response Status: {response.status_code}")

            if response.status_code != 200:
                logger.error(f"❌ [YOLOWorld] Worker returned error: {response.text}")
                response.raise_for_status()

            # Parse inference result
            inference_result = response.json()
            detections = inference_result.get("detections", [])
            logger.info(f"🔍 [YOLOWorld] Detections found: {len(detections)}")

            # Determine label and confidence from detections
            if detections:
                # Get highest confidence detection
                best_detection = max(detections, key=lambda d: d.get("confidence", d.get("conf", 0)))
                label = best_detection.get("label", best_detection.get("class", "detected"))
                confidence = best_detection.get("confidence", best_detection.get("conf", 0.0))

                # Log all detections
                for det in detections:
                    det_label = det.get("label", det.get("class", "unknown"))
                    det_conf = det.get("confidence", det.get("conf", 0.0))
                    logger.info(f"  🎯 {det_label}: {det_conf:.2%}")
            else:
                label = "no_detection"
                confidence = 0.0

            # Store all detections as JSON on the query for LiveBboxOverlay
            query.detections_json = detections
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

            # Create additional result records for other detections in the same frame
            if len(detections) > 1:
                for detection in detections[1:]:
                    additional_result = models.DemoDetectionResult(
                        session_id=result.session_id,
                        query_id=query.id,
                        detector_id=None,  # YOLOWorld mode
                        frame_number=result.frame_number,
                        capture_method="yoloworld",
                        result_label=detection.get("label", detection.get("class")),
                        confidence=detection.get("confidence", detection.get("conf", 0.0)),
                        status="DONE",
                        completed_at=datetime.utcnow()
                    )
                    db.add(additional_result)
                db.commit()

        except requests.RequestException as e:
            logger.error(f"❌ [YOLOWorld] Worker inference failed: {e}")
            query.status = "ERROR"
            result.status = "ERROR"
            result.completed_at = datetime.utcnow()
            db.commit()

    except Exception as e:
        logger.error(f"Error processing YOLOWorld inference for query {query_id}: {e}", exc_info=True)
    finally:
        db.close()


def process_yoloe_inference(query_id: str, result_id: str, image_bytes: bytes, prompts: str, conf: float = 0.25):
    """
    Process YOLOE open-vocabulary inference with dynamic text prompts.

    Similar to process_yoloworld_inference but uses the YOLOE endpoint which supports
    per-request dynamic prompts without needing to re-parameterize the model.

    Args:
        query_id: The query record ID
        result_id: The demo detection result ID
        image_bytes: Raw image bytes (JPEG)
        prompts: Comma-separated list of things to detect
        conf: Confidence threshold (0-1)
    """
    db = SessionLocal()
    try:
        query = db.query(models.Query).filter(models.Query.id == query_id).first()
        result = db.query(models.DemoDetectionResult).filter(models.DemoDetectionResult.id == result_id).first()

        if not query or not result:
            logger.error(f"Query {query_id} or result {result_id} not found")
            return

        try:
            prompt_list = [p.strip() for p in prompts.split(',') if p.strip()]
            logger.info(f"[YOLOE] Processing with prompts: {prompt_list}")

            response = requests.post(
                YOLOE_WORKER_URL,
                files={'image': ('frame.jpg', image_bytes, 'image/jpeg')},
                params={'prompts': ','.join(prompt_list), 'conf': str(conf)},
                timeout=180,
            )

            logger.info(f"[YOLOE] Worker Response Status: {response.status_code}")

            if response.status_code != 200:
                logger.error(f"[YOLOE] Worker returned error: {response.text}")
                response.raise_for_status()

            inference_result = response.json()
            detections = inference_result.get("detections", [])
            logger.info(f"[YOLOE] Detections found: {len(detections)}")

            if detections:
                best_detection = max(detections, key=lambda d: d.get("confidence", 0))
                label = best_detection.get("label", "detected")
                confidence = best_detection.get("confidence", 0.0)
            else:
                label = "no_detection"
                confidence = 0.0

            # Store all detections as JSON on the query for LiveBboxOverlay
            query.detections_json = detections
            query.result_label = label
            query.confidence = confidence
            query.status = "DONE"

            result.result_label = label
            result.confidence = confidence
            result.status = "DONE"
            result.completed_at = datetime.utcnow()

            session = result.session
            if session and label != "no_detection" and len(detections) > 0:
                session.total_detections += len(detections)

            db.commit()

            # Create additional result records for other detections in the same frame
            if len(detections) > 1:
                for detection in detections[1:]:
                    additional_result = models.DemoDetectionResult(
                        session_id=result.session_id,
                        query_id=query.id,
                        detector_id=None,
                        frame_number=result.frame_number,
                        capture_method="yoloe",
                        result_label=detection.get("label", "unknown"),
                        confidence=detection.get("confidence", 0.0),
                        status="DONE",
                        completed_at=datetime.utcnow(),
                    )
                    db.add(additional_result)
                db.commit()

        except requests.RequestException as e:
            logger.error(f"[YOLOE] Worker inference failed: {e}")
            query.status = "ERROR"
            result.status = "ERROR"
            result.completed_at = datetime.utcnow()
            db.commit()

    except Exception as e:
        logger.error(f"Error processing YOLOE inference for query {query_id}: {e}", exc_info=True)
    finally:
        db.close()
