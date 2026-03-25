"""Video capture and motion detection service using yt-dlp and OpenCV."""
from __future__ import annotations

import io
import logging
import time
import base64
from typing import Optional, Callable
from threading import Thread, Event

import cv2
import numpy as np
import yt_dlp


logger = logging.getLogger(__name__)


class VideoCapture:
    """Handles video capture from YouTube streams with motion detection."""

    def __init__(
        self,
        youtube_url: str,
        motion_threshold: float = 500.0,
        min_motion_area: int = 500,
        fps: int = 2,
    ):
        """
        Initialize video capture.

        Args:
            youtube_url: YouTube video/stream URL
            motion_threshold: Threshold for motion detection (default: 500)
            min_motion_area: Minimum contour area to consider as motion (default: 500)
            fps: Frames per second to capture (default: 2)
        """
        self.youtube_url = youtube_url
        self.motion_threshold = motion_threshold
        self.min_motion_area = min_motion_area
        self.fps = fps
        self.frame_interval = 1.0 / fps

        self.stream_url: Optional[str] = None
        self.cap: Optional[cv2.VideoCapture] = None
        self.bg_subtractor: Optional[cv2.BackgroundSubtractorMOG2] = None

        self._running = False
        self._stop_event = Event()
        self._capture_thread: Optional[Thread] = None

    def _get_stream_url(self) -> str:
        """Extract direct stream URL from YouTube using yt-dlp."""
        logger.info(f"📺 Extracting stream URL from: {self.youtube_url}")

        ydl_opts = {
            'format': 'best[height<=720]',  # Get 720p or lower for performance
            'quiet': False,  # Enable output for debugging
            'no_warnings': False,
            'extract_flat': False,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logger.info("Calling yt-dlp extract_info...")
                info = ydl.extract_info(self.youtube_url, download=False)
                stream_url = info['url']
                logger.info(f"✓ Stream URL extracted successfully: {stream_url[:100]}...")
                return stream_url
        except Exception as e:
            logger.error(f"✗ Failed to extract stream URL: {e}", exc_info=True)
            raise

    def start(self, on_motion: Callable[[bytes, dict], None]) -> None:
        """
        Start capturing video frames with motion detection.

        Args:
            on_motion: Callback function called when motion is detected.
                       Receives (image_bytes, metadata_dict) as arguments.
        """
        if self._running:
            logger.warning("Capture already running")
            return

        self._running = True
        self._stop_event.clear()

        def capture_loop():
            try:
                # Get stream URL
                self.stream_url = self._get_stream_url()

                # Open video capture
                logger.info("Opening video stream...")
                self.cap = cv2.VideoCapture(self.stream_url)

                if not self.cap.isOpened():
                    logger.error("Failed to open video stream")
                    return

                # Initialize MOG2 background subtractor
                self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
                    history=500,
                    varThreshold=16,
                    detectShadows=False
                )

                logger.info("Video capture started successfully")
                frame_count = 0
                last_capture_time = time.time()

                while self._running and not self._stop_event.is_set():
                    # Control frame rate
                    current_time = time.time()
                    if current_time - last_capture_time < self.frame_interval:
                        time.sleep(0.1)
                        continue

                    last_capture_time = current_time

                    # Read frame
                    ret, frame = self.cap.read()
                    if not ret:
                        logger.warning("Failed to read frame, stream may have ended")
                        time.sleep(1)
                        continue

                    frame_count += 1

                    # Resize frame for processing (faster)
                    frame_resized = cv2.resize(frame, (640, 360))

                    # Apply background subtraction
                    fg_mask = self.bg_subtractor.apply(frame_resized)

                    # Threshold and find contours
                    _, thresh = cv2.threshold(fg_mask, 244, 255, cv2.THRESH_BINARY)
                    contours, _ = cv2.findContours(
                        thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                    )

                    # Check for motion
                    motion_detected = False
                    total_motion_area = 0

                    for contour in contours:
                        area = cv2.contourArea(contour)
                        if area > self.min_motion_area:
                            total_motion_area += area
                            motion_detected = True

                    if motion_detected and total_motion_area > self.motion_threshold:
                        logger.info(
                            f"Motion detected! Area: {total_motion_area:.0f}, Frame: {frame_count}"
                        )

                        # Encode frame as JPEG
                        _, buffer = cv2.imencode('.jpg', frame_resized, [cv2.IMWRITE_JPEG_QUALITY, 85])
                        image_bytes = buffer.tobytes()

                        # Call callback with frame data
                        metadata = {
                            'frame_number': frame_count,
                            'motion_area': total_motion_area,
                            'timestamp': current_time,
                        }

                        try:
                            on_motion(image_bytes, metadata)
                        except Exception as e:
                            logger.error(f"Error in motion callback: {e}")

            except Exception as e:
                logger.error(f"Error in capture loop: {e}", exc_info=True)
            finally:
                self._cleanup()

        self._capture_thread = Thread(target=capture_loop, daemon=True)
        self._capture_thread.start()
        logger.info("Capture thread started")

    def stop(self) -> None:
        """Stop capturing video frames."""
        if not self._running:
            return

        logger.info("Stopping video capture...")
        self._running = False
        self._stop_event.set()

        if self._capture_thread:
            self._capture_thread.join(timeout=5)

        self._cleanup()
        logger.info("Video capture stopped")

    def _cleanup(self) -> None:
        """Clean up resources."""
        if self.cap:
            self.cap.release()
            self.cap = None

        self.bg_subtractor = None
        self._running = False

    def __del__(self):
        """Cleanup on deletion."""
        self.stop()


class PollingCapture:
    """Handles video capture from YouTube streams with fixed interval polling."""

    def __init__(self, youtube_url: str, polling_interval_ms: int = 2000):
        """
        Initialize polling capture.

        Args:
            youtube_url: YouTube video/stream URL
            polling_interval_ms: Interval between captures in milliseconds
        """
        self.youtube_url = youtube_url
        self.polling_interval_ms = polling_interval_ms
        self.frame_interval = polling_interval_ms / 1000.0

        self.stream_url: Optional[str] = None
        self.cap: Optional[cv2.VideoCapture] = None

        self._running = False
        self._stop_event = Event()
        self._capture_thread: Optional[Thread] = None

    def _get_stream_url(self) -> str:
        """Extract direct stream URL from YouTube using yt-dlp."""
        logger.info(f"📺 Extracting stream URL from: {self.youtube_url}")

        ydl_opts = {
            'format': 'best[height<=720]',
            'quiet': False,
            'no_warnings': False,
            'extract_flat': False,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logger.info("Calling yt-dlp extract_info...")
                info = ydl.extract_info(self.youtube_url, download=False)
                stream_url = info['url']
                logger.info(f"✓ Stream URL extracted successfully: {stream_url[:100]}...")
                return stream_url
        except Exception as e:
            logger.error(f"✗ Failed to extract stream URL: {e}", exc_info=True)
            raise

    def start(self, on_frame: Callable[[bytes, dict], None]) -> None:
        """
        Start capturing video frames at fixed intervals.

        Args:
            on_frame: Callback function called for each captured frame.
                      Receives (image_bytes, metadata_dict) as arguments.
        """
        if self._running:
            logger.warning("Capture already running")
            return

        self._running = True
        self._stop_event.clear()

        def capture_loop():
            try:
                # Get stream URL
                self.stream_url = self._get_stream_url()

                # Open video capture
                logger.info("Opening video stream...")
                self.cap = cv2.VideoCapture(self.stream_url)

                if not self.cap.isOpened():
                    logger.error("Failed to open video stream")
                    return

                logger.info(f"Polling capture started (interval: {self.polling_interval_ms}ms)")
                frame_count = 0
                last_capture_time = time.time()

                while self._running and not self._stop_event.is_set():
                    current_time = time.time()
                    if current_time - last_capture_time < self.frame_interval:
                        time.sleep(0.1)
                        continue

                    last_capture_time = current_time

                    # Read frame
                    ret, frame = self.cap.read()
                    if not ret:
                        logger.warning("Failed to read frame")
                        time.sleep(1)
                        continue

                    frame_count += 1

                    # Resize frame
                    frame_resized = cv2.resize(frame, (640, 360))

                    # Encode frame as JPEG
                    _, buffer = cv2.imencode('.jpg', frame_resized, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    image_bytes = buffer.tobytes()

                    # Call callback
                    metadata = {
                        'frame_number': frame_count,
                        'timestamp': current_time,
                    }

                    try:
                        on_frame(image_bytes, metadata)
                    except Exception as e:
                        logger.error(f"Error in frame callback: {e}")

            except Exception as e:
                logger.error(f"Error in capture loop: {e}", exc_info=True)
            finally:
                self._cleanup()

        self._capture_thread = Thread(target=capture_loop, daemon=True)
        self._capture_thread.start()
        logger.info("Capture thread started")

    def stop(self) -> None:
        """Stop capturing video frames."""
        if not self._running:
            return

        logger.info("Stopping polling capture...")
        self._running = False
        self._stop_event.set()

        if self._capture_thread:
            self._capture_thread.join(timeout=5)

        self._cleanup()
        logger.info("Polling capture stopped")

    def _cleanup(self) -> None:
        """Clean up resources."""
        if self.cap:
            self.cap.release()
            self.cap = None

        self._running = False

    def __del__(self):
        """Cleanup on deletion."""
        self.stop()
