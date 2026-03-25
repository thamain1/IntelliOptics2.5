"""Video frame capture using streamlink + FFmpeg for multiple streaming sites."""
import logging
import subprocess
import time
from threading import Thread, Event
from typing import Callable, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Browser-mimicking User-Agent
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


class MockFrameGrabber:
    """Generates mock frames for testing the inference pipeline."""

    def __init__(self, fps: float = 0.5):
        self.fps = fps
        self.frame_interval = 1.0 / fps
        self._running = False
        self._stop_event = Event()
        self._thread: Optional[Thread] = None

    def start(self, on_frame: Callable[[bytes, int], None]):
        if self._running:
            logger.warning("Already running")
            return

        self._running = True
        self._stop_event.clear()

        def capture_loop():
            frames_captured = 0
            last_capture_time = 0

            colors = [
                (255, 100, 100), (100, 255, 100), (100, 100, 255),
                (255, 255, 100), (255, 100, 255), (100, 255, 255),
            ]

            logger.info(f"🎬 MockFrameGrabber started at {self.fps} fps")

            while self._running and not self._stop_event.is_set():
                current_time = time.time()
                if current_time - last_capture_time < self.frame_interval:
                    time.sleep(0.1)
                    continue

                last_capture_time = current_time
                frames_captured += 1

                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                frame[:] = colors[frames_captured % len(colors)]

                timestamp = time.strftime("%H:%M:%S")
                cv2.putText(frame, f"Mock Frame #{frames_captured}", (50, 100),
                           cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 0), 3)
                cv2.putText(frame, timestamp, (50, 200),
                           cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 0), 3)

                try:
                    _, jpeg_bytes = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    frame_bytes = jpeg_bytes.tobytes()
                    logger.info(f"📸 Mock frame {frames_captured} generated ({len(frame_bytes)} bytes)")
                    on_frame(frame_bytes, frames_captured)
                except Exception as e:
                    logger.error(f"Error encoding mock frame: {e}")

            logger.info("Mock capture loop finished")

        self._thread = Thread(target=capture_loop, daemon=True)
        self._thread.start()
        logger.info("✓ Mock capture thread started")

    def stop(self):
        if not self._running:
            return
        logger.info("Stopping mock capture...")
        self._running = False
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("✓ Mock capture stopped")


class YouTubeFrameGrabber:
    """Captures frames from streaming sites using streamlink + FFmpeg."""

    def __init__(self, youtube_url: str, fps: float = 0.5):
        self.stream_url = youtube_url
        self.fps = fps
        self.frame_interval = 1.0 / fps
        self._running = False
        self._stop_event = Event()
        self._thread: Optional[Thread] = None
        self._ffmpeg_process: Optional[subprocess.Popen] = None

    def _get_stream_url(self) -> Optional[str]:
        """Extract stream URL using streamlink (supports many sites including EarthCam, YouTube, etc.)."""
        try:
            cmd = [
                "streamlink",
                "--stream-url",
                self.stream_url,
                "best"
            ]
            logger.info(f"🔍 Extracting stream URL with streamlink...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0 and result.stdout.strip():
                url = result.stdout.strip()
                if url.startswith('http'):
                    logger.info(f"✓ Got stream URL: {url[:80]}...")
                    return url
                else:
                    logger.error(f"Invalid streamlink output: {url}")
                    return None
            else:
                logger.error(f"streamlink failed: {result.stderr}")
                return None
        except Exception as e:
            logger.error(f"Error extracting stream URL: {e}")
            return None

    def _extract_jpeg(self, buffer: bytes) -> Optional[bytes]:
        """Extract a complete JPEG from the buffer using markers."""
        start = buffer.find(b'\xff\xd8')
        if start == -1:
            return None

        end = buffer.find(b'\xff\xd9', start + 2)
        if end == -1:
            return None

        return buffer[start:end + 2]

    def start(self, on_frame: Callable[[bytes, int], None]):
        if self._running:
            logger.warning("Already running")
            return

        self._running = True
        self._stop_event.clear()

        def capture_loop():
            retry_count = 0

            while self._running and not self._stop_event.is_set():
                try:
                    # Get fresh stream URL
                    stream_url = self._get_stream_url()
                    if not stream_url:
                        retry_count += 1
                        wait_time = min(30, 5 * retry_count)
                        logger.warning(f"Failed to get stream URL, retrying in {wait_time}s...")
                        time.sleep(wait_time)
                        continue

                    # Start FFmpeg to extract JPEG frames
                    ffmpeg_cmd = [
                        "ffmpeg",
                        "-headers", f"User-Agent: {USER_AGENT}\r\n",
                        "-i", stream_url,
                        "-vf", f"fps={self.fps}",
                        "-f", "image2pipe",
                        "-vcodec", "mjpeg",
                        "-q:v", "5",
                        "-"
                    ]

                    logger.info(f"🎬 Starting FFmpeg pipeline at {self.fps} fps")
                    self._ffmpeg_process = subprocess.Popen(
                        ffmpeg_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        bufsize=10**7
                    )

                    retry_count = 0
                    frames_captured = 0
                    buffer = b''
                    last_frame_time = time.time()

                    while self._running and not self._stop_event.is_set():
                        chunk = self._ffmpeg_process.stdout.read(65536)
                        if not chunk:
                            logger.warning("FFmpeg stream ended")
                            break

                        buffer += chunk

                        while True:
                            jpeg_data = self._extract_jpeg(buffer)
                            if not jpeg_data:
                                break

                            end_pos = buffer.find(b'\xff\xd9') + 2
                            buffer = buffer[end_pos:]

                            current_time = time.time()
                            if current_time - last_frame_time < self.frame_interval:
                                continue

                            last_frame_time = current_time
                            frames_captured += 1

                            logger.info(f"📸 Frame {frames_captured} captured ({len(jpeg_data)} bytes)")
                            on_frame(jpeg_data, frames_captured)

                        if len(buffer) > 10**7:
                            buffer = buffer[-10**6:]

                    if self._ffmpeg_process:
                        self._ffmpeg_process.terminate()
                        self._ffmpeg_process.wait(timeout=5)
                        self._ffmpeg_process = None

                    if self._running:
                        retry_count += 1
                        wait_time = min(30, 3 * retry_count)
                        logger.info(f"Stream ended, restarting in {wait_time}s...")
                        time.sleep(wait_time)

                except Exception as e:
                    logger.error(f"Error in capture loop: {e}", exc_info=True)
                    if self._ffmpeg_process:
                        self._ffmpeg_process.terminate()
                        self._ffmpeg_process = None
                    retry_count += 1
                    time.sleep(5)

            logger.info("Capture loop finished")

        self._thread = Thread(target=capture_loop, daemon=True)
        self._thread.start()
        logger.info("✓ Capture thread started")

    def stop(self):
        if not self._running:
            return
        logger.info("Stopping capture...")
        self._running = False
        self._stop_event.set()
        if self._ffmpeg_process:
            self._ffmpeg_process.terminate()
            try:
                self._ffmpeg_process.wait(timeout=5)
            except:
                self._ffmpeg_process.kill()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("✓ Capture stopped")
