"""
IntelliOptics 2.0 - Vehicle Identification Pipeline
License plate OCR + color + type/make, spatially matched using YOLOE + VLM.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class VehicleRecord:
    """Identified vehicle with plate, color, and type info."""

    plate_text: Optional[str] = None
    vehicle_color: Optional[str] = None
    vehicle_type: Optional[str] = None
    vehicle_make_model: Optional[str] = None
    confidence: float = 0.0
    bbox: list[float] = field(default_factory=list)  # [x1, y1, x2, y2] normalized
    plate_bbox: Optional[list[float]] = None
    latency_ms: float = 0.0


class VehicleIdentifier:
    """Vehicle identification pipeline using YOLOE + VLM.

    Pipeline:
    1. YOLOE detect vehicles and license plates
    2. VLM OCR on plate crops
    3. VLM query vehicle color and type
    4. Spatial overlap matching (plate inside vehicle = belongs to it)
    """

    def __init__(self, yoloe, vlm):
        from .yoloe_inference import YOLOEInference
        from .vlm_inference import MoondreamVLM

        self.yoloe: YOLOEInference = yoloe
        self.vlm: MoondreamVLM = vlm

    def identify(self, image: np.ndarray) -> list[VehicleRecord]:
        """Run the full vehicle identification pipeline on a single frame.

        Args:
            image: Input image as numpy array (RGB).

        Returns:
            List of VehicleRecord objects with plate, color, type matched.
        """
        start = time.perf_counter()
        h, w = image.shape[:2]

        # 1. YOLOE detect vehicles and plates
        vehicle_prompts = ["vehicle", "car", "truck", "van", "suv", "license plate"]
        detections = self.yoloe.detect(image, vehicle_prompts, conf=0.2)

        # Separate vehicles from plates
        vehicles = []
        plates = []
        for det in detections:
            if det.label == "license plate":
                plates.append(det)
            else:
                vehicles.append(det)

        logger.info(f"Found {len(vehicles)} vehicles, {len(plates)} plates")

        # 2. OCR each plate
        plate_texts: dict[int, str] = {}
        for i, plate in enumerate(plates):
            x1, y1, x2, y2 = [int(c) for c in plate.bbox]
            # Clamp to image bounds
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            if x2 - x1 > 5 and y2 - y1 > 5:
                plate_crop = image[y1:y2, x1:x2]
                text = self.vlm.ocr(plate_crop)
                plate_texts[i] = text.strip().upper() if text else None

        # 3. Query vehicle color and type for each vehicle
        records: list[VehicleRecord] = []
        for veh in vehicles:
            vx1, vy1, vx2, vy2 = [int(c) for c in veh.bbox]
            vx1, vy1 = max(0, vx1), max(0, vy1)
            vx2, vy2 = min(w, vx2), min(h, vy2)

            # Crop vehicle
            if vx2 - vx1 < 20 or vy2 - vy1 < 20:
                continue

            vehicle_crop = image[vy1:vy2, vx1:vx2]

            # VLM queries
            color_result = self.vlm.query(vehicle_crop, "What color is this vehicle? Reply with just the color.")
            type_result = self.vlm.query(
                vehicle_crop,
                "What type of vehicle is this? Include make and model if visible. Reply briefly.",
            )

            color = color_result.answer.strip() if color_result.answer else None
            vtype = type_result.answer.strip() if type_result.answer else None

            # 4. Spatial matching: find plate whose center is inside this vehicle bbox
            matched_plate_text = None
            matched_plate_bbox = None
            for pi, plate in enumerate(plates):
                px_center = (plate.bbox[0] + plate.bbox[2]) / 2
                py_center = (plate.bbox[1] + plate.bbox[3]) / 2
                if veh.bbox[0] <= px_center <= veh.bbox[2] and veh.bbox[1] <= py_center <= veh.bbox[3]:
                    matched_plate_text = plate_texts.get(pi)
                    matched_plate_bbox = [c / (w if idx % 2 == 0 else h) for idx, c in enumerate(plate.bbox)]
                    break

            # Parse type and make/model
            vehicle_type = veh.label  # car, truck, van, etc.
            make_model = vtype

            records.append(
                VehicleRecord(
                    plate_text=matched_plate_text,
                    vehicle_color=color,
                    vehicle_type=vehicle_type,
                    vehicle_make_model=make_model,
                    confidence=veh.confidence,
                    bbox=[c / (w if idx % 2 == 0 else h) for idx, c in enumerate(veh.bbox)],
                    plate_bbox=matched_plate_bbox,
                )
            )

        elapsed_ms = (time.perf_counter() - start) * 1000
        for r in records:
            r.latency_ms = elapsed_ms

        logger.info(f"Vehicle ID pipeline: {len(records)} vehicles identified in {elapsed_ms:.0f}ms")
        return records

    def plate_ocr(self, image: np.ndarray) -> str:
        """Run plate-only OCR on a cropped plate image."""
        return self.vlm.ocr(image)
