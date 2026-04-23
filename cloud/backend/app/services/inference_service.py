import json
import logging
import uuid
import httpx
from typing import Dict, Any, List, Optional
from ..config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class InferenceService:
    @staticmethod
    async def run_inference(
        detector_id: str,
        image_bytes: bytes,
        detector_config: Any,
        primary_model_blob_path: Optional[str] = None,
        oodd_model_blob_path: Optional[str] = None,
        use_legacy: bool = False
    ) -> Dict[str, Any]:
        """
        Run real inference by calling the cloud worker.
        
        Args:
            detector_id: UUID of the detector
            image_bytes: Raw image data
            detector_config: Configuration object
            primary_model_blob_path: Path to model
            oodd_model_blob_path: Path to OODD model
            use_legacy: If True, sends raw bytes for high-performance global model inference
        """
        if not image_bytes:
            raise ValueError("No image data provided for inference")

        worker_url = settings.worker_url

        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                if use_legacy:
                    # High-performance mode: raw bytes to worker
                    logger.info(f"🚀 Sending legacy/fast inference request to {worker_url}")
                    response = await client.post(
                        worker_url,
                        content=image_bytes,
                        headers={'Content-Type': 'application/octet-stream'}
                    )
                else:
                    # Detector-aware mode: multipart with config
                    # ── Item 6: OODD Per-Detector Threshold ─────────────────
                    # Pass the per-detector calibrated threshold to the worker
                    # so run_oodd_inference() uses it instead of the hardcoded
                    # 0.444 default.
                    detector_config_payload = {
                        "detector_id": str(detector_id),
                        "mode": getattr(detector_config, 'mode', 'BINARY'),
                        "class_names": getattr(detector_config, 'class_names', []),
                        "confidence_threshold": getattr(detector_config, 'confidence_threshold', 0.85),
                        "per_class_thresholds": getattr(detector_config, 'per_class_thresholds', {}),
                        "model_input_config": getattr(detector_config, 'model_input_config', {}),
                        "model_output_config": getattr(detector_config, 'model_output_config', {}),
                        "detection_params": getattr(detector_config, 'detection_params', {}),
                        "primary_model_blob_path": primary_model_blob_path,
                        "oodd_model_blob_path": oodd_model_blob_path,
                        "oodd_calibrated_threshold": getattr(detector_config, 'oodd_calibrated_threshold', 0.444) or 0.444,
                        "candidate_model_path": getattr(detector_config, 'candidate_model_path', None),
                    }

                    files = {
                        'image': ('image.jpg', image_bytes, 'image/jpeg'),
                        'config': ('config.json', json.dumps(detector_config_payload), 'application/json')
                    }

                    logger.info(f"🚀 Sending detector-aware inference request to {worker_url}")
                    response = await client.post(worker_url, files=files)

                if response.status_code != 200:
                    logger.error(f"❌ Worker inference failed: {response.text}")
                    raise Exception(f"Worker returned status {response.status_code}: {response.text}")

                return response.json()

        except httpx.TimeoutException:
            logger.error("❌ Worker inference timeout")
            raise Exception("Worker inference timed out")
        except httpx.RequestError as e:
            logger.error(f"❌ Worker connection error: {str(e)}")
            raise Exception(f"Failed to connect to worker: {str(e)}")
        except Exception as e:
            logger.error(f"❌ Inference error: {str(e)}", exc_info=True)
            raise
