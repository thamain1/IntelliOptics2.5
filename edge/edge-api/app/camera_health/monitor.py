"""Camera health monitoring for image quality assessment and tampering detection."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np

try:
    import cv2  # type: ignore
except Exception:
    cv2 = None  # type: ignore[misc, assignment]

LOGGER = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Camera health status levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class QualityIssue(str, Enum):
    """Types of image quality issues."""
    BLUR = "blur"
    LOW_BRIGHTNESS = "low_brightness"
    HIGH_BRIGHTNESS = "high_brightness"
    LOW_CONTRAST = "low_contrast"
    OVEREXPOSURE = "overexposure"
    UNDEREXPOSURE = "underexposure"


class TamperingIssue(str, Enum):
    """Types of tampering issues."""
    OBSTRUCTION = "obstruction"
    CAMERA_MOVED = "camera_moved"
    FOCUS_CHANGED = "focus_changed"
    SIGNIFICANT_CHANGE = "significant_change"


@dataclass
class QualityMetrics:
    """Image quality metrics."""
    blur_score: float  # Laplacian variance (higher = sharper)
    brightness: float  # Mean pixel value (0-255)
    contrast: float  # Standard deviation of pixels
    sharpness: float  # Normalized blur score
    is_blurry: bool
    is_too_dark: bool
    is_too_bright: bool
    is_low_contrast: bool
    is_overexposed: bool
    is_underexposed: bool


@dataclass
class TamperingMetrics:
    """Tampering detection metrics."""
    obstruction_ratio: float  # Percentage of frame that's obstructed (0-1)
    movement_score: float  # Camera movement magnitude
    focus_change_score: float  # Focus/blur change from reference
    frame_diff_score: float  # Overall difference from reference (0-1)
    is_obstructed: bool
    has_moved: bool
    focus_changed: bool
    significant_change: bool


@dataclass
class CameraHealthResult:
    """Complete camera health assessment result."""
    status: HealthStatus
    quality_metrics: QualityMetrics
    tampering_metrics: Optional[TamperingMetrics]
    quality_issues: list[QualityIssue]
    tampering_issues: list[TamperingIssue]
    overall_score: float  # 0-100 health score


class CameraHealthMonitor:
    """Monitor for camera image quality and tampering detection.

    Features:
    - Blur detection using Laplacian variance
    - Brightness/exposure checks
    - Contrast analysis
    - Obstruction detection
    - Camera movement detection
    - Physical tampering indicators
    """

    def __init__(
        self,
        blur_threshold: float = 100.0,
        brightness_low: float = 40.0,
        brightness_high: float = 220.0,
        contrast_low: float = 30.0,
        overexposure_threshold: float = 250.0,
        underexposure_threshold: float = 20.0,
        obstruction_threshold: float = 0.3,
        movement_threshold: float = 50.0,
        focus_change_threshold: float = 0.3,
        frame_diff_threshold: float = 0.4,
    ) -> None:
        """Initialize camera health monitor with quality thresholds.

        Args:
            blur_threshold: Laplacian variance below this indicates blur
            brightness_low: Mean brightness below this is too dark
            brightness_high: Mean brightness above this is too bright
            contrast_low: Std dev below this indicates low contrast
            overexposure_threshold: Pixel brightness above this indicates overexposure
            underexposure_threshold: Pixel brightness below this indicates underexposure
            obstruction_threshold: Fraction of dark pixels indicating obstruction
            movement_threshold: Pixel shift magnitude indicating camera movement
            focus_change_threshold: Blur score change ratio indicating focus change
            frame_diff_threshold: Frame difference ratio indicating significant change
        """
        if cv2 is None:
            LOGGER.warning(
                "OpenCV is not available. Camera health monitoring will be disabled. "
                "Install opencv-python to enable health checks."
            )

        self.blur_threshold = blur_threshold
        self.brightness_low = brightness_low
        self.brightness_high = brightness_high
        self.contrast_low = contrast_low
        self.overexposure_threshold = overexposure_threshold
        self.underexposure_threshold = underexposure_threshold
        self.obstruction_threshold = obstruction_threshold
        self.movement_threshold = movement_threshold
        self.focus_change_threshold = focus_change_threshold
        self.frame_diff_threshold = frame_diff_threshold

        # Reference frame for tampering detection
        self._reference_frame: Optional[np.ndarray] = None
        self._reference_blur_score: Optional[float] = None
        self._reference_features: Optional[np.ndarray] = None

    def assess_health(
        self,
        frame: np.ndarray,
        check_tampering: bool = True,
    ) -> CameraHealthResult:
        """Assess camera health from a frame.

        Args:
            frame: OpenCV frame (BGR image)
            check_tampering: Whether to perform tampering detection

        Returns:
            Complete health assessment result
        """
        if cv2 is None:
            return self._create_unavailable_result()

        # Convert to grayscale for analysis
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Assess image quality
        quality_metrics = self._assess_quality(gray, frame)
        quality_issues = self._identify_quality_issues(quality_metrics)

        # Assess tampering if requested and reference exists
        tampering_metrics = None
        tampering_issues: list[TamperingIssue] = []

        if check_tampering:
            if self._reference_frame is None:
                # Initialize reference frame
                self._set_reference_frame(gray)
            else:
                tampering_metrics = self._assess_tampering(gray, frame)
                tampering_issues = self._identify_tampering_issues(tampering_metrics)

        # Calculate overall health status and score
        status, score = self._calculate_health_status(
            quality_issues,
            tampering_issues,
            quality_metrics,
        )

        return CameraHealthResult(
            status=status,
            quality_metrics=quality_metrics,
            tampering_metrics=tampering_metrics,
            quality_issues=quality_issues,
            tampering_issues=tampering_issues,
            overall_score=score,
        )

    def reset_reference(self, frame: Optional[np.ndarray] = None) -> None:
        """Reset the reference frame for tampering detection.

        Args:
            frame: Optional new reference frame (BGR). If None, clears reference.
        """
        if frame is None or cv2 is None:
            self._reference_frame = None
            self._reference_blur_score = None
            self._reference_features = None
        else:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            self._set_reference_frame(gray)

    def _set_reference_frame(self, gray: np.ndarray) -> None:
        """Set reference frame for tampering detection."""
        assert cv2 is not None

        self._reference_frame = gray.copy()
        self._reference_blur_score = self._calculate_blur_score(gray)

        # Extract features for movement detection (ORB keypoints)
        orb = cv2.ORB_create(nfeatures=500)
        keypoints, descriptors = orb.detectAndCompute(gray, None)
        self._reference_features = descriptors

    def _assess_quality(self, gray: np.ndarray, frame: np.ndarray) -> QualityMetrics:
        """Assess image quality metrics."""
        assert cv2 is not None

        # Blur detection using Laplacian variance
        blur_score = self._calculate_blur_score(gray)
        sharpness = min(blur_score / self.blur_threshold, 1.0)
        is_blurry = blur_score < self.blur_threshold

        # Brightness analysis
        brightness = float(np.mean(gray))
        is_too_dark = brightness < self.brightness_low
        is_too_bright = brightness > self.brightness_high

        # Contrast analysis
        contrast = float(np.std(gray))
        is_low_contrast = contrast < self.contrast_low

        # Exposure analysis
        overexposed_pixels = np.sum(gray > self.overexposure_threshold)
        underexposed_pixels = np.sum(gray < self.underexposure_threshold)
        total_pixels = gray.size

        is_overexposed = (overexposed_pixels / total_pixels) > 0.1  # >10% overexposed
        is_underexposed = (underexposed_pixels / total_pixels) > 0.3  # >30% underexposed

        return QualityMetrics(
            blur_score=blur_score,
            brightness=brightness,
            contrast=contrast,
            sharpness=sharpness,
            is_blurry=is_blurry,
            is_too_dark=is_too_dark,
            is_too_bright=is_too_bright,
            is_low_contrast=is_low_contrast,
            is_overexposed=is_overexposed,
            is_underexposed=is_underexposed,
        )

    def _assess_tampering(self, gray: np.ndarray, frame: np.ndarray) -> TamperingMetrics:
        """Assess tampering indicators."""
        assert cv2 is not None
        assert self._reference_frame is not None

        # Obstruction detection (sudden increase in dark pixels)
        dark_pixels = np.sum(gray < 30)
        obstruction_ratio = dark_pixels / gray.size
        is_obstructed = obstruction_ratio > self.obstruction_threshold

        # Camera movement detection using feature matching
        movement_score = self._detect_camera_movement(gray)
        has_moved = movement_score > self.movement_threshold

        # Focus change detection
        current_blur = self._calculate_blur_score(gray)
        if self._reference_blur_score and self._reference_blur_score > 0:
            focus_change_ratio = abs(current_blur - self._reference_blur_score) / self._reference_blur_score
        else:
            focus_change_ratio = 0.0
        focus_changed = focus_change_ratio > self.focus_change_threshold

        # Overall frame difference
        frame_diff_score = self._calculate_frame_difference(gray)
        significant_change = frame_diff_score > self.frame_diff_threshold

        return TamperingMetrics(
            obstruction_ratio=obstruction_ratio,
            movement_score=movement_score,
            focus_change_score=focus_change_ratio,
            frame_diff_score=frame_diff_score,
            is_obstructed=is_obstructed,
            has_moved=has_moved,
            focus_changed=focus_changed,
            significant_change=significant_change,
        )

    def _calculate_blur_score(self, gray: np.ndarray) -> float:
        """Calculate blur score using Laplacian variance."""
        assert cv2 is not None
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        return float(laplacian.var())

    def _detect_camera_movement(self, gray: np.ndarray) -> float:
        """Detect camera movement using feature matching."""
        assert cv2 is not None

        if self._reference_features is None or len(self._reference_features) == 0:
            return 0.0

        # Extract current frame features
        orb = cv2.ORB_create(nfeatures=500)
        keypoints, descriptors = orb.detectAndCompute(gray, None)

        if descriptors is None or len(descriptors) == 0:
            return 0.0

        # Match features
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        try:
            matches = bf.match(self._reference_features, descriptors)
        except cv2.error:
            return 0.0

        if len(matches) < 4:
            # Not enough matches, likely significant change
            return 100.0

        # Calculate average movement magnitude from matches
        movements = []
        for match in matches:
            # Get matched keypoint positions (we don't have them saved, so use match distance)
            movements.append(match.distance)

        return float(np.mean(movements)) if movements else 0.0

    def _calculate_frame_difference(self, gray: np.ndarray) -> float:
        """Calculate normalized frame difference from reference."""
        assert cv2 is not None
        assert self._reference_frame is not None

        # Resize if dimensions don't match
        if gray.shape != self._reference_frame.shape:
            gray = cv2.resize(gray, (self._reference_frame.shape[1], self._reference_frame.shape[0]))

        # Calculate absolute difference
        diff = cv2.absdiff(gray, self._reference_frame)

        # Normalize to 0-1 range
        return float(np.mean(diff)) / 255.0

    def _identify_quality_issues(self, metrics: QualityMetrics) -> list[QualityIssue]:
        """Identify specific quality issues from metrics."""
        issues: list[QualityIssue] = []

        if metrics.is_blurry:
            issues.append(QualityIssue.BLUR)
        if metrics.is_too_dark:
            issues.append(QualityIssue.LOW_BRIGHTNESS)
        if metrics.is_too_bright:
            issues.append(QualityIssue.HIGH_BRIGHTNESS)
        if metrics.is_low_contrast:
            issues.append(QualityIssue.LOW_CONTRAST)
        if metrics.is_overexposed:
            issues.append(QualityIssue.OVEREXPOSURE)
        if metrics.is_underexposed:
            issues.append(QualityIssue.UNDEREXPOSURE)

        return issues

    def _identify_tampering_issues(self, metrics: TamperingMetrics) -> list[TamperingIssue]:
        """Identify specific tampering issues from metrics."""
        issues: list[TamperingIssue] = []

        if metrics.is_obstructed:
            issues.append(TamperingIssue.OBSTRUCTION)
        if metrics.has_moved:
            issues.append(TamperingIssue.CAMERA_MOVED)
        if metrics.focus_changed:
            issues.append(TamperingIssue.FOCUS_CHANGED)
        if metrics.significant_change:
            issues.append(TamperingIssue.SIGNIFICANT_CHANGE)

        return issues

    def _calculate_health_status(
        self,
        quality_issues: list[QualityIssue],
        tampering_issues: list[TamperingIssue],
        quality_metrics: QualityMetrics,
    ) -> tuple[HealthStatus, float]:
        """Calculate overall health status and score.

        Returns:
            Tuple of (status, score) where score is 0-100
        """
        # Start with perfect score
        score = 100.0

        # Deduct for quality issues
        quality_deductions = {
            QualityIssue.BLUR: 20.0,
            QualityIssue.LOW_BRIGHTNESS: 15.0,
            QualityIssue.HIGH_BRIGHTNESS: 15.0,
            QualityIssue.LOW_CONTRAST: 10.0,
            QualityIssue.OVEREXPOSURE: 10.0,
            QualityIssue.UNDEREXPOSURE: 10.0,
        }

        for issue in quality_issues:
            score -= quality_deductions.get(issue, 5.0)

        # Deduct for tampering issues (more severe)
        tampering_deductions = {
            TamperingIssue.OBSTRUCTION: 50.0,
            TamperingIssue.CAMERA_MOVED: 30.0,
            TamperingIssue.FOCUS_CHANGED: 20.0,
            TamperingIssue.SIGNIFICANT_CHANGE: 15.0,
        }

        for issue in tampering_issues:
            score -= tampering_deductions.get(issue, 10.0)

        # Clamp score to 0-100
        score = max(0.0, min(100.0, score))

        # Determine status
        if TamperingIssue.OBSTRUCTION in tampering_issues:
            status = HealthStatus.CRITICAL
        elif score >= 80.0:
            status = HealthStatus.HEALTHY
        elif score >= 50.0:
            status = HealthStatus.WARNING
        else:
            status = HealthStatus.CRITICAL

        return status, score

    def _create_unavailable_result(self) -> CameraHealthResult:
        """Create result when OpenCV is unavailable."""
        return CameraHealthResult(
            status=HealthStatus.UNKNOWN,
            quality_metrics=QualityMetrics(
                blur_score=0.0,
                brightness=0.0,
                contrast=0.0,
                sharpness=0.0,
                is_blurry=False,
                is_too_dark=False,
                is_too_bright=False,
                is_low_contrast=False,
                is_overexposed=False,
                is_underexposed=False,
            ),
            tampering_metrics=None,
            quality_issues=[],
            tampering_issues=[],
            overall_score=0.0,
        )
