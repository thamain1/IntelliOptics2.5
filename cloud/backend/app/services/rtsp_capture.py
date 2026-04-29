"""Generic frame grabber for RTSP, RTMP, HLS, MJPEG, and direct video URLs.

Distinct from `YouTubeFrameGrabber`, which uses streamlink to resolve a stream URL
from a streaming site (YouTube, Twitch, EarthCam) before ffmpeg consumes it. For
direct-protocol URLs (RTSP, RTMP, HLS, MJPEG, plain mp4/webm), streamlink is the
wrong abstraction — ffmpeg can read these formats natively. This grabber pipes
the URL straight into ffmpeg with appropriate flags per protocol.
"""
from __future__ import annotations

import logging
import subprocess
import time
from threading import Thread, Event
from typing import Callable, Optional

logger = logging.getLogger(__name__)


def is_direct_stream_url(url: str) -> bool:
    """True if ffmpeg can consume this URL directly without streamlink resolution.

    Catches: rtsp://, rtmp://, plus http(s) URLs ending in common streaming
    extensions or containing MJPEG markers. Returns False for streaming-site
    URLs (YouTube, Twitch, EarthCam) which need streamlink to extract a playable
    stream URL first.
    """
    if not url:
        return False
    u = url.strip().lower()
    if u.startswith(("rtsp://", "rtmp://", "rtsps://", "rtmps://")):
        return True
    if u.startswith(("http://", "https://")):
        if "youtube.com" in u or "youtu.be" in u:
            return False
        if "twitch.tv" in u or "earthcam.com" in u:
            return False
        # Direct media or HLS playlist
        if any(u.split("?", 1)[0].endswith(ext) for ext in (".m3u8", ".mp4", ".webm", ".mov", ".mkv")):
            return True
        # MJPEG-style endpoints
        if "mjpg" in u or "mjpeg" in u or "snapshot.cgi" in u or "video.cgi" in u:
            return True
    return False


class RtspFrameGrabber:
    """Captures frames from a direct-protocol stream (RTSP, RTMP, HLS, MJPEG, mp4).

    Uses ffmpeg directly for protocol decoding. Same interface as
    `YouTubeFrameGrabber`: `start(on_frame=...)` and `stop()`.
    """

    def __init__(self, url: str, fps: float = 0.5):
        self.url = url
        self.fps = fps
        self.frame_interval = 1.0 / fps
        self._running = False
        self._stop_event = Event()
        self._thread: Optional[Thread] = None
        self._ffmpeg_process: Optional[subprocess.Popen] = None

    def _build_ffmpeg_cmd(self) -> list[str]:
        """Build the ffmpeg command tuned for the URL's protocol."""
        url_lower = self.url.lower()
        cmd = ["ffmpeg"]

        # RTSP-specific: prefer TCP transport (more reliable than UDP through
        # NAT/firewall). Note: -reconnect* flags are HTTP-only in ffmpeg 7.x
        # and cause a fatal "Option not found" error on RTSP inputs.
        if url_lower.startswith(("rtsp://", "rtsps://")):
            cmd += [
                "-rtsp_transport", "tcp",
                "-timeout", "10000000",   # 10s socket timeout (microseconds)
            ]
        elif url_lower.startswith(("http://", "https://")):
            cmd += [
                "-reconnect", "1",
                "-reconnect_streamed", "1",
                "-reconnect_delay_max", "5",
            ]

        cmd += [
            "-i", self.url,
            "-vf", f"fps={self.fps}",
            "-f", "image2pipe",
            "-vcodec", "mjpeg",
            "-q:v", "5",
            "-",
        ]
        return cmd

    @staticmethod
    def _extract_jpeg(buffer: bytes) -> Optional[bytes]:
        start = buffer.find(b"\xff\xd8")
        if start == -1:
            return None
        end = buffer.find(b"\xff\xd9", start + 2)
        if end == -1:
            return None
        return buffer[start:end + 2]

    def start(self, on_frame: Callable[[bytes, int], None]):
        if self._running:
            logger.warning("RtspFrameGrabber already running")
            return

        self._running = True
        self._stop_event.clear()

        def capture_loop():
            retry_count = 0

            while self._running and not self._stop_event.is_set():
                try:
                    cmd = self._build_ffmpeg_cmd()
                    safe_cmd = " ".join(c if "@" not in c else "<url-with-credentials>" for c in cmd)
                    logger.info(f"🎬 Starting RTSP/direct-stream capture at {self.fps} fps :: {safe_cmd}")

                    self._ffmpeg_process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL,
                        bufsize=10**7,
                    )

                    retry_count = 0
                    frames_captured = 0
                    buffer = b""
                    last_frame_time = time.time()

                    while self._running and not self._stop_event.is_set():
                        chunk = self._ffmpeg_process.stdout.read(65536)
                        if not chunk:
                            logger.warning("ffmpeg stream ended (no data)")
                            break

                        buffer += chunk

                        while True:
                            jpeg_data = self._extract_jpeg(buffer)
                            if not jpeg_data:
                                break

                            end_pos = buffer.find(b"\xff\xd9") + 2
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
                        try:
                            self._ffmpeg_process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            self._ffmpeg_process.kill()
                        self._ffmpeg_process = None

                    if self._running:
                        retry_count += 1
                        wait_time = min(30, 3 * retry_count)
                        logger.info(f"Stream ended, retrying in {wait_time}s (attempt {retry_count})")
                        time.sleep(wait_time)

                except Exception as e:
                    logger.error(f"Error in RTSP capture loop: {e}", exc_info=True)
                    if self._ffmpeg_process:
                        try:
                            self._ffmpeg_process.terminate()
                        except Exception:
                            pass
                        self._ffmpeg_process = None
                    retry_count += 1
                    time.sleep(5)

            logger.info("RTSP capture loop finished")

        self._thread = Thread(target=capture_loop, daemon=True)
        self._thread.start()
        logger.info("✓ RTSP capture thread started")

    def stop(self):
        if not self._running:
            return
        logger.info("Stopping RTSP capture…")
        self._running = False
        self._stop_event.set()
        if self._ffmpeg_process:
            self._ffmpeg_process.terminate()
            try:
                self._ffmpeg_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._ffmpeg_process.kill()
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("✓ RTSP capture stopped")
