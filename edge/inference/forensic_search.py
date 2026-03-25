"""
IntelliOptics 2.0 - Video Forensic Search (BOLO)
Search recorded DVR footage with natural language queries.
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import AsyncGenerator, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ForensicSearchJob:
    """A search job configuration."""

    id: str = ""
    query_text: str = ""
    source_url: str = ""
    source_type: str = "video_file"  # dvr, rtsp_recording, video_file
    camera_ids: list[str] = field(default_factory=list)
    time_range_start: Optional[str] = None
    time_range_end: Optional[str] = None
    frame_interval_sec: float = 1.0  # Extract frames at this interval
    confidence_threshold: float = 0.3
    status: str = "PENDING"
    progress_pct: float = 0.0
    total_frames: int = 0
    frames_scanned: int = 0
    matches_found: int = 0


@dataclass
class SearchResult:
    """A single search match."""

    id: str = ""
    job_id: str = ""
    timestamp_sec: float = 0.0
    camera_id: Optional[str] = None
    confidence: float = 0.0
    bbox: list[float] = field(default_factory=list)  # [x1, y1, x2, y2] normalized
    label: str = ""
    description: str = ""  # VLM description of what was found
    frame_data: Optional[bytes] = None  # JPEG encoded frame


class ForensicSearchEngine:
    """BOLO video forensic search engine.

    Pipeline:
    1. Extract frames from video source at configurable intervals
    2. Batch YOLOE scan with prompts derived from natural language query
    3. VLM confirmation on candidate frames (YOLOE hit)
    4. Yield timestamped results
    """

    def __init__(self, yoloe, vlm):
        from yoloe_inference import YOLOEInference
        from vlm_inference import MoondreamVLM

        self.yoloe: YOLOEInference = yoloe
        self.vlm: MoondreamVLM = vlm
        self._active_jobs: dict[str, ForensicSearchJob] = {}
        self._cancel_flags: dict[str, bool] = {}

    def _parse_prompts(self, query_text: str) -> list[str]:
        """Extract YOLOE prompts from natural language query.

        Simple keyword extraction — pulls nouns and descriptive phrases.
        E.g., "man with red backpack near lot C" → ["person", "man", "backpack"]
        """
        # Core detection terms — always useful
        prompts = []

        # Common object mappings
        query_lower = query_text.lower()
        keyword_map = {
            "person": ["person", "man", "woman", "girl", "boy", "child", "people", "someone"],
            "vehicle": ["car", "truck", "van", "vehicle", "suv", "bus"],
            "backpack": ["backpack", "bag", "suitcase", "luggage"],
            "bicycle": ["bicycle", "bike", "cyclist"],
            "dog": ["dog"],
            "cat": ["cat"],
        }

        for prompt, keywords in keyword_map.items():
            for kw in keywords:
                if kw in query_lower:
                    prompts.append(prompt)
                    break

        # Also add raw nouns from query as prompts
        words = query_text.split()
        skip_words = {
            "the", "a", "an", "is", "was", "in", "on", "at", "near",
            "with", "wearing", "around", "about", "from", "to", "and",
            "or", "of", "lot", "area", "zone", "between",
        }
        for word in words:
            cleaned = word.strip(".,!?").lower()
            if cleaned not in skip_words and len(cleaned) > 2 and cleaned not in prompts:
                prompts.append(cleaned)

        if not prompts:
            prompts = ["person", "vehicle"]

        return list(set(prompts))[:10]  # Cap at 10 prompts

    async def search(self, job: ForensicSearchJob) -> AsyncGenerator[SearchResult, None]:
        """Run forensic search on a video source.

        Yields SearchResult objects as matches are found.
        """
        job.id = job.id or str(uuid.uuid4())
        job.status = "RUNNING"
        self._active_jobs[job.id] = job
        self._cancel_flags[job.id] = False

        prompts = self._parse_prompts(job.query_text)
        logger.info(f"BOLO search '{job.query_text}' → prompts: {prompts}")

        cap = cv2.VideoCapture(job.source_url)
        if not cap.isOpened():
            job.status = "ERROR"
            logger.error(f"Cannot open video source: {job.source_url}")
            return

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        frame_skip = max(1, int(fps * job.frame_interval_sec))
        job.total_frames = total_frames // frame_skip if total_frames > 0 else 0

        frame_idx = 0
        try:
            while cap.isOpened():
                if self._cancel_flags.get(job.id, False):
                    job.status = "CANCELLED"
                    break

                ret, frame = cap.read()
                if not ret:
                    break

                frame_idx += 1
                if frame_idx % frame_skip != 0:
                    continue

                job.frames_scanned += 1
                timestamp_sec = frame_idx / fps

                # Update progress
                if job.total_frames > 0:
                    job.progress_pct = (job.frames_scanned / job.total_frames) * 100

                # Stage 1: YOLOE fast scan
                detections = self.yoloe.detect(frame, prompts, conf=job.confidence_threshold)

                if detections:
                    h, w = frame.shape[:2]

                    # Stage 2: VLM description — ask what it sees
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    vlm_result = self.vlm.query(
                        rgb_frame,
                        f"Describe what you see in this image related to: '{job.query_text}'. "
                        f"Include details about people, clothing, objects, colors, and actions. "
                        f"If nothing relevant is visible, say 'no match'.",
                    )

                    description = vlm_result.answer.strip()
                    is_match = "no match" not in description.lower()

                    if is_match:
                        best_det = max(detections, key=lambda d: d.confidence)

                        # Draw bounding boxes on the frame
                        annotated = frame.copy()
                        for det in detections:
                            x1, y1, x2, y2 = [int(c) for c in det.bbox]
                            color = (0, 255, 0)  # green
                            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                            label_text = f"{det.label} {det.confidence:.0%}"
                            font_scale = 0.6
                            thickness = 2
                            (tw, th), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
                            cv2.rectangle(annotated, (x1, y1 - th - 8), (x1 + tw + 4, y1), color, -1)
                            cv2.putText(annotated, label_text, (x1 + 2, y1 - 4),
                                        cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 0), thickness)

                        # Encode annotated frame as JPEG
                        _, jpeg_buf = cv2.imencode(".jpg", annotated)
                        frame_bytes = jpeg_buf.tobytes()

                        result = SearchResult(
                            id=str(uuid.uuid4()),
                            job_id=job.id,
                            timestamp_sec=timestamp_sec,
                            confidence=best_det.confidence,
                            bbox=best_det.to_normalized(w, h)["bbox"],
                            label=best_det.label,
                            description=description,
                            frame_data=frame_bytes,
                        )

                        job.matches_found += 1
                        logger.info(f"Match at {timestamp_sec:.1f}s: {best_det.label} ({best_det.confidence:.0%}) — {description[:100]}")
                        yield result

                # Yield control to event loop periodically
                if job.frames_scanned % 10 == 0:
                    await asyncio.sleep(0)

        finally:
            cap.release()
            if job.status == "RUNNING":
                job.status = "COMPLETED"
            self._cancel_flags.pop(job.id, None)

        logger.info(
            f"BOLO search complete: {job.frames_scanned} frames scanned, "
            f"{job.matches_found} matches in {job.id}"
        )

    def stop(self, job_id: str) -> bool:
        """Cancel a running search job."""
        if job_id in self._cancel_flags:
            self._cancel_flags[job_id] = True
            return True
        return False

    def get_job(self, job_id: str) -> Optional[ForensicSearchJob]:
        """Get a search job by ID."""
        return self._active_jobs.get(job_id)
