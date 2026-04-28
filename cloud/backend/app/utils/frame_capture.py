"""Single-frame capture helper for RTSP and HTTP video URLs.

Used by:
- The "Test Connection" button on the Add Camera modal (preview the stream)
- The "Update Baseline" endpoint (store a reference frame for view-drift detection)

Uses OpenCV's VideoCapture which natively supports rtsp://, rtmp://,
http://*.m3u8, http://*.mp4, and any other format ffmpeg can decode.
"""
from __future__ import annotations

import logging
from typing import Optional

import cv2

logger = logging.getLogger(__name__)


def capture_single_frame(
    url: str,
    timeout_ms: int = 8000,
    jpeg_quality: int = 85,
) -> Optional[bytes]:
    """Open `url`, grab one frame, encode as JPEG, return the bytes.

    Returns None on any failure (cannot connect, no frames, decode error).
    Logs the failure cause for diagnostics. Never raises.
    """
    if not url:
        return None

    cap: Optional[cv2.VideoCapture] = None
    try:
        # FFMPEG backend supports the broadest set of protocols.
        # OpenCV reads OPENCV_FFMPEG_CAPTURE_OPTIONS for ffmpeg-specific tuning;
        # we set it via env in the worker compose so RTSP uses TCP transport.
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout_ms)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, timeout_ms)

        if not cap.isOpened():
            logger.warning("capture_single_frame: failed to open stream")
            return None

        # Many RTSP cameras need a few read attempts before delivering a
        # decodable keyframe — try up to 30 grabs (~1s at 30fps).
        for _ in range(30):
            ok, frame = cap.read()
            if ok and frame is not None and frame.size > 0:
                ok2, jpeg = cv2.imencode(
                    ".jpg",
                    frame,
                    [int(cv2.IMWRITE_JPEG_QUALITY), int(jpeg_quality)],
                )
                if ok2:
                    return bytes(jpeg)
                logger.warning("capture_single_frame: jpeg encode failed")
                return None

        logger.warning("capture_single_frame: no decodable frame after 30 attempts")
        return None

    except Exception as e:
        logger.error(f"capture_single_frame error: {e}", exc_info=True)
        return None
    finally:
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass
