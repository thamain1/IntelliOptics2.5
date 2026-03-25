"""
IntelliOptics Model Types - Top-Level Package (CORRECTED VERSION)

This is the CORRECTED version of model/__init__.py that only imports
types that actually exist in intellioptics.models.

Replace the current model/__init__.py in the SDK with this content.
"""

from intellioptics.models import (
    # Core Types
    Detector,
    ImageQuery,

    # Enums
    ImageQueryTypeEnum,
    ModeEnum,
    ResultTypeEnum,

    # Result Types
    BinaryClassificationResult,
    MultiClassificationResult,
    CountingResult,

    # Supporting Types
    ROI,
)

__all__ = [
    # Core
    "Detector",
    "ImageQuery",

    # Enums
    "ImageQueryTypeEnum",
    "ModeEnum",
    "ResultTypeEnum",

    # Results
    "BinaryClassificationResult",
    "MultiClassificationResult",
    "CountingResult",

    # Supporting Types
    "ROI",
]
