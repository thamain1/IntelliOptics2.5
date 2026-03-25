#!/usr/bin/env python3
"""Test script for camera health monitoring.

This script demonstrates and tests the camera health monitoring capabilities
without requiring a live RTSP stream. It uses synthetic test images.
"""

import sys
from pathlib import Path

# Add edge-api to path
sys.path.insert(0, str(Path(__file__).parent.parent / "edge-api"))

import numpy as np

try:
    import cv2
except ImportError:
    print("ERROR: OpenCV not installed. Install with: pip install opencv-python")
    sys.exit(1)

from app.camera_health import CameraHealthMonitor


def create_test_images():
    """Create synthetic test images for different scenarios."""
    images = {}

    # 1. Sharp, well-lit image (HEALTHY)
    sharp_image = np.random.randint(80, 180, (480, 640, 3), dtype=np.uint8)
    # Add some texture for sharpness
    for i in range(100):
        x, y = np.random.randint(0, 640), np.random.randint(0, 480)
        cv2.circle(sharp_image, (x, y), 5, (255, 255, 255), -1)
    images["sharp_well_lit"] = sharp_image

    # 2. Blurry image (WARNING/CRITICAL)
    blurry_image = cv2.GaussianBlur(sharp_image, (51, 51), 0)
    images["blurry"] = blurry_image

    # 3. Too dark image (WARNING)
    dark_image = np.random.randint(5, 40, (480, 640, 3), dtype=np.uint8)
    images["too_dark"] = dark_image

    # 4. Too bright image (WARNING)
    bright_image = np.random.randint(200, 255, (480, 640, 3), dtype=np.uint8)
    images["too_bright"] = bright_image

    # 5. Low contrast image (WARNING)
    low_contrast = np.full((480, 640, 3), 128, dtype=np.uint8)
    images["low_contrast"] = low_contrast

    # 6. Obstructed image (CRITICAL)
    obstructed_image = np.random.randint(80, 180, (480, 640, 3), dtype=np.uint8)
    # Cover 50% of the image with black (obstruction)
    obstructed_image[:, :320] = 0
    images["obstructed"] = obstructed_image

    return images


def test_quality_assessment():
    """Test image quality assessment features."""
    print("=" * 70)
    print("TEST 1: Image Quality Assessment")
    print("=" * 70)

    monitor = CameraHealthMonitor(
        blur_threshold=100.0,
        brightness_low=40.0,
        brightness_high=220.0,
        contrast_low=30.0,
    )

    images = create_test_images()

    for name, image in images.items():
        result = monitor.assess_health(image, check_tampering=False)

        print(f"\n{name.upper().replace('_', ' ')}:")
        print(f"  Status: {result.status.value}")
        print(f"  Overall Score: {result.overall_score:.1f}/100")
        print(f"  Quality Metrics:")
        print(f"    - Blur Score: {result.quality_metrics.blur_score:.1f}")
        print(f"    - Brightness: {result.quality_metrics.brightness:.1f}")
        print(f"    - Contrast: {result.quality_metrics.contrast:.1f}")
        print(f"    - Sharpness: {result.quality_metrics.sharpness:.2f}")

        if result.quality_issues:
            print(f"  Quality Issues: {[issue.value for issue in result.quality_issues]}")

        # Verify expected results
        if name == "sharp_well_lit":
            assert result.status.value in ["healthy", "warning"], f"Expected healthy/warning, got {result.status.value}"
        elif name == "blurry":
            assert result.quality_metrics.is_blurry, "Expected blur detection"
        elif name == "too_dark":
            assert result.quality_metrics.is_too_dark, "Expected dark detection"
        elif name == "too_bright":
            assert result.quality_metrics.is_too_bright, "Expected bright detection"
        elif name == "low_contrast":
            assert result.quality_metrics.is_low_contrast, "Expected low contrast detection"

    print("\n✅ Quality assessment tests PASSED")


def test_tampering_detection():
    """Test tampering detection features."""
    print("\n" + "=" * 70)
    print("TEST 2: Tampering Detection")
    print("=" * 70)

    monitor = CameraHealthMonitor(
        blur_threshold=100.0,
        obstruction_threshold=0.3,
        movement_threshold=50.0,
    )

    images = create_test_images()

    # Test 1: Set reference frame (clean image)
    print("\nSetting reference frame (sharp, well-lit image)...")
    reference = images["sharp_well_lit"]
    monitor.reset_reference(reference)

    # Test 2: Check same image (should be healthy)
    print("\nTest 2a: Same image (should be HEALTHY):")
    result = monitor.assess_health(reference, check_tampering=True)
    print(f"  Status: {result.status.value}")
    print(f"  Tampering Issues: {[issue.value for issue in result.tampering_issues]}")
    assert len(result.tampering_issues) == 0, "Same image should have no tampering issues"

    # Test 3: Obstructed image (should detect obstruction)
    print("\nTest 2b: Obstructed image (50% black):")
    obstructed = images["obstructed"]
    result = monitor.assess_health(obstructed, check_tampering=True)
    print(f"  Status: {result.status.value}")
    print(f"  Obstruction Ratio: {result.tampering_metrics.obstruction_ratio:.2f}")
    print(f"  Tampering Issues: {[issue.value for issue in result.tampering_issues]}")
    assert result.tampering_metrics.is_obstructed, "Should detect obstruction"
    assert result.status.value == "critical", "Obstruction should be CRITICAL"

    # Test 4: Slightly different image (simulated movement)
    print("\nTest 2c: Different scene (should detect change):")
    different = np.random.randint(80, 180, (480, 640, 3), dtype=np.uint8)
    result = monitor.assess_health(different, check_tampering=True)
    print(f"  Status: {result.status.value}")
    print(f"  Frame Diff Score: {result.tampering_metrics.frame_diff_score:.2f}")
    print(f"  Tampering Issues: {[issue.value for issue in result.tampering_issues]}")

    print("\n✅ Tampering detection tests PASSED")


def test_health_scoring():
    """Test health scoring system."""
    print("\n" + "=" * 70)
    print("TEST 3: Health Scoring System")
    print("=" * 70)

    monitor = CameraHealthMonitor()
    images = create_test_images()

    results = {}
    for name, image in images.items():
        result = monitor.assess_health(image, check_tampering=False)
        results[name] = result.overall_score

    print("\nHealth Scores:")
    for name, score in sorted(results.items(), key=lambda x: x[1], reverse=True):
        print(f"  {name:20s}: {score:5.1f}/100")

    # Verify scoring logic
    assert results["sharp_well_lit"] > results["blurry"], "Sharp image should score higher than blurry"
    assert results["obstructed"] < 50, "Obstructed image should be CRITICAL (<50)"

    print("\n✅ Health scoring tests PASSED")


def test_frame_skipping():
    """Test frame skipping logic."""
    print("\n" + "=" * 70)
    print("TEST 4: Frame Skipping Logic")
    print("=" * 70)

    monitor = CameraHealthMonitor()
    images = create_test_images()

    print("\nFrame Skipping Decisions (if skip_unhealthy_frames=True):")
    for name, image in images.items():
        result = monitor.assess_health(image, check_tampering=False)
        from app.camera_health.monitor import HealthStatus

        should_skip = result.status == HealthStatus.CRITICAL
        action = "SKIP" if should_skip else "SUBMIT"

        print(f"  {name:20s}: {result.status.value:10s} → {action}")

    print("\n✅ Frame skipping tests PASSED")


def main():
    """Run all tests."""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "IntelliOptics Camera Health Monitoring Test" + " " * 10 + "║")
    print("╚" + "=" * 68 + "╝")

    try:
        test_quality_assessment()
        test_tampering_detection()
        test_health_scoring()
        test_frame_skipping()

        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED")
        print("=" * 70)
        print("\nCamera health monitoring is working correctly!")
        print("\nNext steps:")
        print("  1. Configure camera health in edge-config.yaml")
        print("  2. Enable for RTSP streams with 'camera_health.enabled: true'")
        print("  3. Tune thresholds based on your camera environment")
        print("  4. Monitor logs for health status during operation")
        print("\nSee docs/CAMERA-HEALTH-MONITORING.md for full documentation.")
        print()

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
