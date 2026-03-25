#!/usr/bin/env python3
"""
Download and export YOLOv8 models for IntelliOptics Edge Inference

Usage:
    python download-models.py --detector-id det_test_001

Requirements:
    pip install ultralytics torch onnx
"""

import argparse
import os
from pathlib import Path


def download_yolo_model(detector_id: str, model_size: str = "n", base_path: str = "/opt/intellioptics/models"):
    """
    Download YOLOv8 model and export to ONNX format

    Args:
        detector_id: Detector identifier (e.g., det_test_001)
        model_size: YOLOv8 size: n (nano), s (small), m (medium), l (large), x (extra large)
        base_path: Base path for model storage
    """
    try:
        from ultralytics import YOLO
        print(f"Downloading YOLOv8{model_size}...")

        # Download YOLOv8 model
        model = YOLO(f'yolov8{model_size}.pt')

        # Export to ONNX
        print("Exporting to ONNX format...")
        onnx_path = model.export(format='onnx', imgsz=640)

        # Move to correct location
        primary_dir = Path(base_path) / detector_id / "primary" / "1"
        primary_dir.mkdir(parents=True, exist_ok=True)

        import shutil
        target_path = primary_dir / "model.buf"
        shutil.copy(onnx_path, target_path)

        print(f"✓ Primary model saved to: {target_path}")

        # For OODD, use the same model (in production, train a separate OODD model)
        oodd_dir = Path(base_path) / detector_id / "oodd" / "1"
        oodd_dir.mkdir(parents=True, exist_ok=True)
        oodd_target = oodd_dir / "model.buf"
        shutil.copy(onnx_path, oodd_target)

        print(f"✓ OODD model saved to: {oodd_target}")
        print(f"\nNOTE: Using same model for OODD. In production, train a separate OODD model.")

        return True

    except ImportError:
        print("ERROR: ultralytics not installed. Install with: pip install ultralytics torch onnx")
        return False
    except Exception as e:
        print(f"ERROR: Failed to download model: {e}")
        return False


def download_from_url(url: str, detector_id: str, model_type: str = "primary",
                      base_path: str = "/opt/intellioptics/models"):
    """
    Download ONNX model from URL

    Args:
        url: Direct URL to ONNX model file
        detector_id: Detector identifier
        model_type: "primary" or "oodd"
        base_path: Base path for model storage
    """
    import urllib.request

    target_dir = Path(base_path) / detector_id / model_type / "1"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / "model.buf"

    print(f"Downloading {model_type} model from {url}...")

    try:
        urllib.request.urlretrieve(url, target_path)
        print(f"✓ {model_type.capitalize()} model saved to: {target_path}")
        return True
    except Exception as e:
        print(f"ERROR: Failed to download from URL: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download YOLO models for IntelliOptics")
    parser.add_argument("--detector-id", default="det_test_001", help="Detector ID")
    parser.add_argument("--model-size", default="n", choices=["n", "s", "m", "l", "x"],
                       help="YOLOv8 model size (n=nano, s=small, m=medium, l=large, x=xlarge)")
    parser.add_argument("--from-url", help="Download from direct URL instead")
    parser.add_argument("--oodd-url", help="URL for OODD model (if different)")
    parser.add_argument("--base-path", default="/opt/intellioptics/models",
                       help="Base path for models")

    args = parser.parse_args()

    if args.from_url:
        # Download from URL
        success = download_from_url(args.from_url, args.detector_id, "primary", args.base_path)

        if args.oodd_url:
            download_from_url(args.oodd_url, args.detector_id, "oodd", args.base_path)
        else:
            # Use same model for OODD if no separate URL provided
            import shutil
            primary_path = Path(args.base_path) / args.detector_id / "primary" / "1" / "model.buf"
            oodd_dir = Path(args.base_path) / args.detector_id / "oodd" / "1"
            oodd_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy(primary_path, oodd_dir / "model.buf")
            print(f"✓ Copied primary model to OODD (same model)")
    else:
        # Download using ultralytics
        success = download_yolo_model(args.detector_id, args.model_size, args.base_path)

    if success:
        print("\n" + "="*60)
        print("✓ Model setup complete!")
        print("="*60)
        print(f"\nNext steps:")
        print(f"1. Configure detector in edge/config/edge-config.yaml")
        print(f"2. Start edge services: cd edge && docker-compose up -d")
        print(f"3. Test inference: curl -X POST http://localhost:30101/v1/image-queries?detector_id={args.detector_id} -F 'image=@test.jpg'")
    else:
        print("\n✗ Model setup failed. See errors above.")
        exit(1)
