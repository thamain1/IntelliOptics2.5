"""
Camera Inspection Worker - CPU-only, Raspberry Pi compatible

This worker performs automated camera health inspections on configurable intervals.
Runs traditional computer vision algorithms (no ML/GPU required).

Key Features:
- RTSP connection testing
- FPS measurement
- Image quality analysis (brightness, sharpness)
- View change detection (SSIM + ORB features)
- Alert generation and email notifications
- Configurable inspection intervals (1-4 hours typical)
"""
import asyncio
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import cv2
import httpx
import numpy as np
from dotenv import load_dotenv
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from skimage.metrics import structural_similarity as ssim

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
ALERT_FROM_EMAIL = os.getenv("ALERT_FROM_EMAIL", "alerts@intellioptics.com")
AZURE_BLOB_CONNECTION_STRING = os.getenv("AZURE_BLOB_CONNECTION_STRING")
AZURE_BLOB_CONTAINER = os.getenv("AZURE_BLOB_CONTAINER", "camera-baselines")


class CameraInspectionWorker:
    """
    Main worker class for camera health inspections.

    Performs periodic health checks on all cameras, including:
    - Connection status
    - Stream quality (FPS, resolution)
    - Image quality (brightness, sharpness)
    - Network metrics (latency)
    - View change detection (SSIM + ORB)
    """

    def __init__(self):
        self.api_url = API_BASE_URL
        self.client = httpx.AsyncClient(timeout=30.0)
        self.sendgrid_client = SendGridAPIClient(SENDGRID_API_KEY) if SENDGRID_API_KEY else None
        self.baseline_cache = {}  # Cache baseline images in memory

    async def get_inspection_config(self) -> Dict:
        """Get inspection configuration from API."""
        try:
            response = await self.client.get(f"{self.api_url}/inspection-config")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get inspection config: {e}")
            # Return default config
            return {
                "inspection_interval_minutes": 60,
                "offline_threshold_minutes": 5,
                "fps_drop_threshold_pct": 0.5,
                "latency_threshold_ms": 1000,
                "view_change_threshold": 0.7,
                "alert_emails": []
            }

    async def get_cameras(self) -> List[Dict]:
        """Get all cameras from API."""
        try:
            response = await self.client.get(f"{self.api_url}/hubs")
            response.raise_for_status()
            hubs = response.json()

            cameras = []
            for hub in hubs:
                if hub.get("cameras"):
                    cameras.extend(hub["cameras"])

            return cameras
        except Exception as e:
            logger.error(f"Failed to get cameras: {e}")
            return []

    def connect_to_rtsp(self, rtsp_url: str, timeout: int = 10) -> Optional[cv2.VideoCapture]:
        """
        Connect to RTSP stream with timeout.

        Args:
            rtsp_url: RTSP URL of the camera
            timeout: Connection timeout in seconds

        Returns:
            VideoCapture object if successful, None otherwise
        """
        try:
            cap = cv2.VideoCapture(rtsp_url)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce latency

            # Wait for connection
            start_time = time.time()
            while time.time() - start_time < timeout:
                if cap.isOpened():
                    # Try to read a frame to verify connection
                    ret, _ = cap.read()
                    if ret:
                        return cap
                time.sleep(0.5)

            cap.release()
            return None
        except Exception as e:
            logger.error(f"Failed to connect to RTSP {rtsp_url}: {e}")
            return None

    def measure_fps(self, cap: cv2.VideoCapture, num_frames: int = 30) -> float:
        """
        Measure actual FPS by capturing frames.

        Args:
            cap: OpenCV VideoCapture object
            num_frames: Number of frames to capture for measurement

        Returns:
            Measured FPS
        """
        try:
            start_time = time.time()
            frames_captured = 0

            for _ in range(num_frames):
                ret, _ = cap.read()
                if ret:
                    frames_captured += 1
                else:
                    break

            elapsed_time = time.time() - start_time
            return frames_captured / elapsed_time if elapsed_time > 0 else 0.0
        except Exception as e:
            logger.error(f"Failed to measure FPS: {e}")
            return 0.0

    def analyze_image_quality(self, frame: np.ndarray) -> Dict[str, float]:
        """
        Analyze image quality metrics.

        Args:
            frame: OpenCV frame (BGR format)

        Returns:
            Dictionary with brightness and sharpness scores
        """
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Calculate brightness (mean pixel value)
            brightness = np.mean(gray)

            # Calculate sharpness (Laplacian variance)
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            sharpness = laplacian.var()

            return {
                "avg_brightness": float(brightness),
                "sharpness_score": float(sharpness)
            }
        except Exception as e:
            logger.error(f"Failed to analyze image quality: {e}")
            return {"avg_brightness": 0.0, "sharpness_score": 0.0}

    def detect_view_change(
        self,
        current_frame: np.ndarray,
        baseline_frame: np.ndarray,
        ssim_threshold: float = 0.7
    ) -> Tuple[float, bool]:
        """
        Detect if camera view has changed using SSIM + ORB features.

        This uses CPU-only traditional computer vision algorithms:
        - SSIM: Structural similarity between images
        - ORB: Oriented FAST and Rotated BRIEF feature detector

        Args:
            current_frame: Current camera frame
            baseline_frame: Baseline frame to compare against
            ssim_threshold: SSIM threshold (0.7 default, lower = more different)

        Returns:
            Tuple of (similarity_score, view_changed)
        """
        try:
            # Resize frames to same size for comparison
            height, width = 480, 640
            current_resized = cv2.resize(current_frame, (width, height))
            baseline_resized = cv2.resize(baseline_frame, (width, height))

            # Convert to grayscale
            current_gray = cv2.cvtColor(current_resized, cv2.COLOR_BGR2GRAY)
            baseline_gray = cv2.cvtColor(baseline_resized, cv2.COLOR_BGR2GRAY)

            # Calculate SSIM (Structural Similarity Index)
            similarity_score = ssim(baseline_gray, current_gray)

            # If SSIM is very low, view definitely changed
            if similarity_score < ssim_threshold:
                logger.info(f"View change detected: SSIM={similarity_score:.3f} < {ssim_threshold}")
                return float(similarity_score), True

            # Use ORB features for additional validation
            orb = cv2.ORB_create()
            kp1, des1 = orb.detectAndCompute(baseline_gray, None)
            kp2, des2 = orb.detectAndCompute(current_gray, None)

            if des1 is not None and des2 is not None:
                # Match features using BFMatcher
                bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
                matches = bf.match(des1, des2)

                # Calculate match ratio
                match_ratio = len(matches) / max(len(kp1), len(kp2)) if kp1 and kp2 else 0

                # View changed if few features match
                if match_ratio < 0.3:
                    logger.info(f"View change detected: ORB match ratio={match_ratio:.3f} < 0.3")
                    return float(similarity_score), True

            return float(similarity_score), False

        except Exception as e:
            logger.error(f"Failed to detect view change: {e}")
            return 0.0, False

    async def get_baseline_image(self, camera_id: str, baseline_path: Optional[str]) -> Optional[np.ndarray]:
        """
        Get baseline image for view change detection.

        Args:
            camera_id: Camera ID
            baseline_path: Azure Blob path to baseline image

        Returns:
            Baseline frame as numpy array, or None if not available
        """
        if not baseline_path:
            return None

        # Check cache first
        if camera_id in self.baseline_cache:
            return self.baseline_cache[camera_id]

        # TODO: Download from Azure Blob Storage
        # For now, return None (baseline images not yet implemented)
        logger.warning(f"Baseline image download not implemented yet for camera {camera_id}")
        return None

    async def inspect_camera(self, camera: Dict, config: Dict) -> Dict:
        """
        Perform full health inspection on a single camera.

        Args:
            camera: Camera object from API
            config: Inspection configuration

        Returns:
            Health data dictionary
        """
        camera_id = camera["id"]
        camera_name = camera["name"]
        rtsp_url = camera["url"]

        logger.info(f"Inspecting camera: {camera_name} ({camera_id})")

        # Initialize health data
        health_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "status": "offline",
            "fps": 0.0,
            "expected_fps": 30.0,  # Default expected FPS
            "resolution": "N/A",
            "last_frame_at": None,
            "uptime_24h": 0.0,
            "latency_ms": 0,
            "view_similarity_score": None,
            "view_change_detected": False,
            "avg_brightness": None,
            "sharpness_score": None
        }

        # Measure connection latency
        connect_start = time.time()
        cap = self.connect_to_rtsp(rtsp_url, timeout=10)
        latency_ms = int((time.time() - connect_start) * 1000)
        health_data["latency_ms"] = latency_ms

        if not cap:
            logger.warning(f"Camera {camera_name} is offline (connection failed)")
            return health_data

        try:
            # Camera is connected
            health_data["status"] = "connected"

            # Measure FPS
            fps = self.measure_fps(cap, num_frames=30)
            health_data["fps"] = fps

            # Get resolution
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            health_data["resolution"] = f"{width}x{height}"

            # Capture current frame for analysis
            ret, frame = cap.read()
            if ret:
                health_data["last_frame_at"] = datetime.utcnow().isoformat()

                # Analyze image quality
                quality_metrics = self.analyze_image_quality(frame)
                health_data["avg_brightness"] = quality_metrics["avg_brightness"]
                health_data["sharpness_score"] = quality_metrics["sharpness_score"]

                # View change detection (if baseline exists)
                baseline_frame = await self.get_baseline_image(
                    camera_id,
                    camera.get("baseline_image_path")
                )
                if baseline_frame is not None:
                    similarity, view_changed = self.detect_view_change(
                        frame,
                        baseline_frame,
                        config["view_change_threshold"]
                    )
                    health_data["view_similarity_score"] = similarity
                    health_data["view_change_detected"] = view_changed

            # Check if degraded (low FPS, high latency)
            fps_threshold = health_data["expected_fps"] * config["fps_drop_threshold_pct"]
            if fps < fps_threshold or latency_ms > config["latency_threshold_ms"]:
                health_data["status"] = "degraded"

            # Calculate uptime (placeholder - would need historical data)
            health_data["uptime_24h"] = 95.0  # TODO: Calculate from historical health records

        except Exception as e:
            logger.error(f"Error inspecting camera {camera_name}: {e}")
            health_data["status"] = "offline"
        finally:
            cap.release()

        return health_data

    async def create_health_record(self, camera_id: str, health_data: Dict) -> bool:
        """
        POST health data to backend API.

        Args:
            camera_id: Camera ID
            health_data: Health metrics dictionary

        Returns:
            True if successful
        """
        try:
            response = await self.client.post(
                f"{self.api_url}/camera-inspection/cameras/{camera_id}/health",
                json=health_data
            )
            response.raise_for_status()
            logger.info(f"Health record created for camera {camera_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to create health record for camera {camera_id}: {e}")
            return False

    async def create_alert(
        self,
        camera_id: str,
        alert_type: str,
        severity: str,
        message: str
    ) -> bool:
        """
        Create alert for camera issue.

        Args:
            camera_id: Camera ID
            alert_type: offline, fps_drop, view_change, quality_degradation, network_issue
            severity: critical, warning, info
            message: Alert message

        Returns:
            True if successful
        """
        try:
            alert_data = {
                "camera_id": camera_id,
                "alert_type": alert_type,
                "severity": severity,
                "message": message,
                "created_at": datetime.utcnow().isoformat()
            }

            response = await self.client.post(
                f"{self.api_url}/camera-inspection/alerts",
                json=alert_data
            )
            response.raise_for_status()
            logger.info(f"Alert created: {alert_type} for camera {camera_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to create alert for camera {camera_id}: {e}")
            return False

    async def send_email_alert(
        self,
        to_emails: List[str],
        camera_name: str,
        alert_type: str,
        message: str
    ):
        """
        Send email notification via SendGrid.

        Args:
            to_emails: List of recipient email addresses
            camera_name: Camera name
            alert_type: Alert type
            message: Alert message
        """
        if not self.sendgrid_client or not to_emails:
            return

        try:
            subject = f"[IntelliOptics] Camera Alert: {camera_name}"

            html_content = f"""
            <html>
            <body>
                <h2>Camera Health Alert</h2>
                <p><strong>Camera:</strong> {camera_name}</p>
                <p><strong>Alert Type:</strong> {alert_type}</p>
                <p><strong>Message:</strong> {message}</p>
                <p><strong>Time:</strong> {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
                <hr>
                <p><em>This is an automated alert from IntelliOptics Camera Inspection System.</em></p>
            </body>
            </html>
            """

            for email in to_emails:
                mail = Mail(
                    from_email=ALERT_FROM_EMAIL,
                    to_emails=email,
                    subject=subject,
                    html_content=html_content
                )

                response = self.sendgrid_client.send(mail)
                logger.info(f"Email alert sent to {email}: {response.status_code}")

        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")

    async def check_alert_conditions(
        self,
        camera: Dict,
        health_data: Dict,
        config: Dict
    ):
        """
        Check if any alert conditions are met and create alerts.

        Args:
            camera: Camera object
            health_data: Health metrics
            config: Inspection configuration
        """
        camera_id = camera["id"]
        camera_name = camera["name"]
        alert_emails = config.get("alert_emails", [])

        # Check offline
        if health_data["status"] == "offline":
            await self.create_alert(
                camera_id,
                "offline",
                "critical",
                f"Camera {camera_name} is offline (connection failed)"
            )
            await self.send_email_alert(
                alert_emails,
                camera_name,
                "offline",
                "Camera connection failed"
            )

        # Check FPS drop
        fps_threshold = health_data["expected_fps"] * config["fps_drop_threshold_pct"]
        if health_data["fps"] > 0 and health_data["fps"] < fps_threshold:
            await self.create_alert(
                camera_id,
                "fps_drop",
                "warning",
                f"FPS dropped to {health_data['fps']:.1f} (expected {health_data['expected_fps']})"
            )
            await self.send_email_alert(
                alert_emails,
                camera_name,
                "fps_drop",
                f"FPS dropped to {health_data['fps']:.1f}"
            )

        # Check view change
        if health_data.get("view_change_detected"):
            await self.create_alert(
                camera_id,
                "view_change",
                "critical",
                f"Camera view has changed (similarity: {health_data.get('view_similarity_score', 0):.2f})"
            )
            await self.send_email_alert(
                alert_emails,
                camera_name,
                "view_change",
                "Camera view has been physically changed"
            )

        # Check network latency
        if health_data["latency_ms"] > config["latency_threshold_ms"]:
            await self.create_alert(
                camera_id,
                "network_issue",
                "warning",
                f"High latency: {health_data['latency_ms']}ms"
            )

    async def run_inspection_cycle(self):
        """
        Run a complete inspection cycle for all cameras.
        """
        logger.info("=== Starting inspection cycle ===")

        # Get configuration
        config = await self.get_inspection_config()
        logger.info(f"Inspection interval: {config['inspection_interval_minutes']} minutes")

        # Get all cameras
        cameras = await self.get_cameras()
        logger.info(f"Found {len(cameras)} cameras to inspect")

        if not cameras:
            logger.warning("No cameras found, skipping inspection")
            return

        # Create inspection run
        try:
            response = await self.client.post(f"{self.api_url}/camera-inspection/runs")
            response.raise_for_status()
            run_data = response.json()
            run_id = run_data["id"]
            logger.info(f"Created inspection run: {run_id}")
        except Exception as e:
            logger.error(f"Failed to create inspection run: {e}")
            run_id = None

        # Inspect each camera
        healthy_count = 0
        warning_count = 0
        failed_count = 0

        for camera in cameras:
            try:
                # Perform inspection
                health_data = await self.inspect_camera(camera, config)

                # Create health record
                await self.create_health_record(camera["id"], health_data)

                # Check alert conditions
                await self.check_alert_conditions(camera, health_data, config)

                # Update counts
                if health_data["status"] == "connected":
                    healthy_count += 1
                elif health_data["status"] == "degraded":
                    warning_count += 1
                else:
                    failed_count += 1

            except Exception as e:
                logger.error(f"Error inspecting camera {camera['name']}: {e}")
                failed_count += 1

        # Update inspection run
        if run_id:
            try:
                await self.client.put(
                    f"{self.api_url}/camera-inspection/runs/{run_id}",
                    params={
                        "total_cameras": len(cameras),
                        "cameras_inspected": len(cameras),
                        "cameras_healthy": healthy_count,
                        "cameras_warning": warning_count,
                        "cameras_failed": failed_count,
                        "status": "completed"
                    }
                )
                logger.info(f"Inspection run completed: {healthy_count} healthy, {warning_count} warning, {failed_count} failed")
            except Exception as e:
                logger.error(f"Failed to update inspection run: {e}")

        logger.info("=== Inspection cycle complete ===")

    async def run_forever(self):
        """
        Run inspection worker continuously.
        """
        logger.info("Camera Inspection Worker started")

        while True:
            try:
                # Get current config to check interval
                config = await self.get_inspection_config()
                interval_minutes = config["inspection_interval_minutes"]

                # Run inspection cycle
                await self.run_inspection_cycle()

                # Sleep until next cycle
                sleep_seconds = interval_minutes * 60
                logger.info(f"Sleeping for {interval_minutes} minutes until next inspection")
                await asyncio.sleep(sleep_seconds)

            except KeyboardInterrupt:
                logger.info("Received shutdown signal, stopping worker")
                break
            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}")
                # Sleep 5 minutes on error before retrying
                await asyncio.sleep(300)

        # Cleanup
        await self.client.aclose()
        logger.info("Camera Inspection Worker stopped")


async def main():
    """Main entry point."""
    worker = CameraInspectionWorker()
    await worker.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
