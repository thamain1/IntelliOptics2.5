#!/usr/bin/env python3
"""
IntelliOptics 2.0 - YOLO-World v2 ONNX Export Utility

One-time script that exports yolov8s-worldv2.pt to ONNX with a comprehensive
fixed vocabulary (~300 classes). Run during Docker build (exporter stage) or
on a dev machine.

Usage:
    python export_onnx.py --output /export/models/
    python export_onnx.py --model yolov8s-worldv2.pt --output ./models/

Requirements (exporter stage only — NOT needed at runtime):
    pip install ultralytics>=8.3.0 "clip @ git+https://github.com/openai/CLIP.git"
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Comprehensive vocabulary (~300 classes)
# Organized by category for readability. Order matters — index = class ID
# in the exported ONNX model.
# ---------------------------------------------------------------------------

VOCABULARY = [
    # ── COCO 80 (standard) ──────────────────────────────────────────────
    "person", "bicycle", "car", "motorcycle", "airplane",
    "bus", "train", "truck", "boat", "traffic light",
    "fire hydrant", "stop sign", "parking meter", "bench", "bird",
    "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe", "backpack",
    "umbrella", "handbag", "tie", "suitcase", "frisbee",
    "skis", "snowboard", "sports ball", "kite", "baseball bat",
    "baseball glove", "skateboard", "surfboard", "tennis racket", "bottle",
    "wine glass", "cup", "fork", "knife", "spoon",
    "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut",
    "cake", "chair", "couch", "potted plant", "bed",
    "dining table", "toilet", "tv", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven",
    "toaster", "sink", "refrigerator", "book", "clock",
    "vase", "scissors", "teddy bear", "hair drier", "toothbrush",

    # ── Vehicles (extended) ─────────────────────────────────────────────
    "sedan", "SUV", "van", "minivan", "pickup truck",
    "sports car", "convertible", "station wagon", "limousine", "taxi",
    "police car", "ambulance", "fire truck", "tow truck", "dump truck",
    "cement mixer", "tanker truck", "delivery truck", "box truck",
    "golf cart", "ATV", "snowmobile", "RV", "trailer",
    "semi truck", "scooter", "moped", "electric scooter",

    # ── License plates ──────────────────────────────────────────────────
    "license plate", "number plate",

    # ── Security / Law enforcement ──────────────────────────────────────
    "weapon", "gun", "rifle", "pistol", "shotgun",
    "knife", "machete", "baton", "taser", "pepper spray",
    "handcuffs", "badge", "body armor", "bulletproof vest",
    "uniform", "mask", "balaclava", "ski mask",
    "security camera", "surveillance camera", "metal detector",
    "walkie talkie", "flashlight",

    # ── Safety / PPE ────────────────────────────────────────────────────
    "hard hat", "safety vest", "safety glasses", "goggles",
    "gloves", "work gloves", "rubber gloves",
    "steel toe boots", "safety boots",
    "face shield", "respirator", "gas mask", "dust mask",
    "ear protection", "earmuffs", "ear plugs",
    "safety harness", "fall protection",
    "fire extinguisher", "first aid kit", "AED",
    "caution tape", "warning sign", "safety cone",

    # ── Industrial / Construction ───────────────────────────────────────
    "forklift", "crane", "excavator", "bulldozer", "backhoe",
    "pallet", "pallet jack", "barrel", "drum", "container",
    "shipping container", "dumpster",
    "scaffold", "scaffolding", "ladder", "step ladder",
    "wheelbarrow", "generator", "compressor",
    "welding machine", "welding torch", "power tool",
    "drill", "saw", "grinder", "jackhammer",
    "pipe", "cable", "wire", "hose",
    "toolbox", "wrench", "hammer", "screwdriver",

    # ── Fire / Hazards ──────────────────────────────────────────────────
    "fire", "smoke", "flame", "explosion",
    "spill", "leak", "puddle",
    "sparks", "debris", "rubble",
    "hazmat suit", "chemical container",
    "warning light", "emergency light",

    # ── Parking / Traffic ───────────────────────────────────────────────
    "parking space", "parking lot", "parking garage",
    "parking meter", "ticket machine",
    "barrier", "gate", "boom gate", "turnstile",
    "cone", "traffic cone", "bollard",
    "speed bump", "curb", "median",
    "crosswalk", "pedestrian crossing",
    "road sign", "street sign", "speed limit sign",
    "traffic signal", "arrow sign",

    # ── Retail / Commercial ─────────────────────────────────────────────
    "shopping cart", "basket", "bag", "plastic bag",
    "cash register", "POS terminal", "card reader",
    "shelf", "display", "mannequin",
    "sign", "banner", "poster",
    "receipt", "price tag", "barcode",
    "vending machine", "ATM",

    # ── Animals (beyond COCO) ───────────────────────────────────────────
    "raccoon", "deer", "coyote", "fox", "wolf",
    "rat", "mouse", "squirrel", "rabbit",
    "snake", "lizard", "turtle",
    "hawk", "eagle", "owl", "crow", "pigeon",
    "fish", "duck", "goose",

    # ── Clothing / Accessories ──────────────────────────────────────────
    "jacket", "coat", "hoodie", "sweater",
    "shirt", "t-shirt", "polo shirt",
    "pants", "jeans", "shorts",
    "dress", "skirt", "suit",
    "shoes", "boots", "sneakers", "sandals",
    "hat", "cap", "beanie", "helmet",
    "sunglasses", "glasses", "watch",
    "belt", "wallet", "purse",
    "scarf", "glove", "mitten",

    # ── Electronics ─────────────────────────────────────────────────────
    "phone", "smartphone", "tablet",
    "camera", "video camera", "DSLR",
    "monitor", "screen", "display screen",
    "printer", "scanner", "copier",
    "drone", "robot",
    "speaker", "headphones", "earbuds",
    "charger", "power bank", "cable",
    "USB drive", "hard drive",

    # ── Furniture / Indoor ──────────────────────────────────────────────
    "desk", "table", "counter",
    "cabinet", "locker", "drawer",
    "door", "window", "gate",
    "staircase", "elevator", "escalator",
    "trash can", "recycling bin",
    "whiteboard", "bulletin board",
    "projector", "screen",

    # ── Food / Beverage ─────────────────────────────────────────────────
    "water bottle", "coffee cup", "mug",
    "plate", "tray", "napkin",
    "food container", "lunch box",
    "cooler", "thermos",

    # ── Medical ─────────────────────────────────────────────────────────
    "wheelchair", "stretcher", "gurney",
    "crutch", "walker", "cane",
    "medical bag", "oxygen tank",
    "stethoscope", "syringe",

    # ── Misc ────────────────────────────────────────────────────────────
    "flag", "badge", "ID card",
    "keys", "key card", "lanyard",
    "rope", "chain", "padlock",
    "tent", "tarp", "canopy",
    "shopping bag", "cardboard box", "package",
    "envelope", "clipboard", "binder",
    "pen", "pencil", "marker",
    "cigarette", "lighter",
    "umbrella", "stroller", "wagon",
    "fire alarm", "smoke detector", "sprinkler",
]


def deduplicate_vocabulary(vocab: list[str]) -> list[str]:
    """Remove duplicates while preserving order."""
    seen = set()
    unique = []
    for item in vocab:
        lower = item.lower()
        if lower not in seen:
            seen.add(lower)
            unique.append(item)
    return unique


def export(model_name: str, output_dir: str) -> None:
    """Export YOLO-World v2 to ONNX with fixed vocabulary."""
    import torch

    # Patch torch.load for PyTorch 2.6+ compatibility
    original_torch_load = torch.load

    def patched_torch_load(*args, **kwargs):
        kwargs["weights_only"] = False
        return original_torch_load(*args, **kwargs)

    torch.load = patched_torch_load

    try:
        from ultralytics import YOLO
    except Exception as e:
        logger.error(f"Failed to import ultralytics: {e}")
        logger.error("Install with: pip install ultralytics>=8.3.0")
        sys.exit(1)

    vocab = deduplicate_vocabulary(VOCABULARY)
    logger.info(f"Vocabulary: {len(vocab)} classes")

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Load model
    logger.info(f"Loading {model_name}...")
    model = YOLO(model_name)

    # Set comprehensive vocabulary (bakes CLIP embeddings into the model)
    logger.info("Setting vocabulary (computing CLIP embeddings)...")
    model.set_classes(vocab)

    # Export to ONNX
    onnx_path = out_path / "yolov8s-worldv2.onnx"
    logger.info(f"Exporting ONNX to {onnx_path}...")
    model.export(
        format="onnx",
        imgsz=640,
        simplify=True,
        opset=17,
    )

    # Ultralytics exports to same dir as the .pt file — move it
    # The export creates a file like yolov8s-worldv2.onnx next to the .pt
    exported = Path(model_name).with_suffix(".onnx")
    if exported.exists() and str(exported) != str(onnx_path):
        import shutil
        shutil.move(str(exported), str(onnx_path))
        logger.info(f"Moved {exported} -> {onnx_path}")

    # Save vocabulary index
    vocab_path = out_path / "vocabulary.json"
    with open(vocab_path, "w") as f:
        json.dump(vocab, f, indent=2)
    logger.info(f"Saved vocabulary ({len(vocab)} classes) to {vocab_path}")

    # Verify
    file_size_mb = onnx_path.stat().st_size / (1024 * 1024)
    logger.info(f"Export complete: {onnx_path} ({file_size_mb:.1f} MB)")
    logger.info(f"Vocabulary: {vocab_path}")

    # Restore torch.load
    torch.load = original_torch_load


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export YOLO-World v2 to ONNX")
    parser.add_argument(
        "--model", default="yolov8s-worldv2.pt",
        help="Path to YOLO-World v2 .pt model file",
    )
    parser.add_argument(
        "--output", default="/export/models/",
        help="Output directory for ONNX model + vocabulary.json",
    )
    args = parser.parse_args()
    export(args.model, args.output)
