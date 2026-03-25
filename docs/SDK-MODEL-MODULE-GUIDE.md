# IntelliOptics SDK - Missing `model` Module Implementation Guide

**Target**: https://github.com/thamain1/IntelliOptics-SDK
**Issue**: SDK missing `model` module with type definitions
**Priority**: HIGH - Required for cloud integration functionality

---

## What Needs to Be Added

The SDK repository needs to include a `model` module (Python package) that contains **Pydantic model classes** representing the IntelliOptics API data structures.

### Required Imports (from edge-api code analysis)

The edge-api expects to import these classes from the `model` module:

```python
from model import (
    # Core Types
    Detector,                      # Detector configuration/metadata
    ImageQuery,                    # Image query request/response

    # Enums
    ImageQueryTypeEnum,            # Type of image query (BINARY, MULTICLASS, etc.)
    ModeEnum,                      # Detection mode
    ResultTypeEnum,                # Type of result returned

    # Result Types
    BinaryClassificationResult,    # Binary classification result
    MultiClassificationResult,     # Multi-class classification result
    CountingResult,                # Object counting result

    # Configuration Types
    CountModeConfiguration,        # Configuration for counting mode
    MultiClassModeConfiguration,   # Configuration for multi-class mode

    # Supporting Types
    ROI,                           # Region of Interest
    Label,                         # Label/class definition
    Source,                        # Source information
)
```

---

## Recommended SDK Repository Structure

```
IntelliOptics-SDK/
├── intellioptics/              # ✅ Already exists
│   ├── __init__.py
│   ├── client.py               # IntelliOptics class
│   └── ...
│
├── model/                      # ❌ ADD THIS DIRECTORY
│   ├── __init__.py            # Exports all model classes
│   ├── detector.py            # Detector class
│   ├── image_query.py         # ImageQuery class
│   ├── results.py             # Result classes (BinaryClassificationResult, etc.)
│   ├── enums.py               # Enum types (ModeEnum, ResultTypeEnum, etc.)
│   ├── configuration.py       # Configuration classes
│   └── types.py               # Supporting types (ROI, Label, Source)
│
├── pyproject.toml             # ⚠️ UPDATE THIS
├── README.md
└── tests/                     # ⚠️ ADD INTEGRATION TESTS
    └── test_imports.py
```

---

## Implementation Details

### 1. Create `model/__init__.py`

This file should export all the classes that edge-api needs to import:

```python
"""
IntelliOptics SDK Model Types

This module contains Pydantic models for the IntelliOptics API.
"""

from .detector import Detector
from .image_query import ImageQuery
from .enums import ImageQueryTypeEnum, ModeEnum, ResultTypeEnum
from .results import (
    BinaryClassificationResult,
    MultiClassificationResult,
    CountingResult,
)
from .configuration import (
    CountModeConfiguration,
    MultiClassModeConfiguration,
)
from .types import ROI, Label, Source

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

    # Configuration
    "CountModeConfiguration",
    "MultiClassModeConfiguration",

    # Supporting Types
    "ROI",
    "Label",
    "Source",
]
```

---

### 2. Create `model/enums.py`

Define the enum types:

```python
"""Enum types for IntelliOptics models."""

from enum import Enum


class ModeEnum(str, Enum):
    """Detection mode types."""
    BINARY = "BINARY"
    MULTICLASS = "MULTICLASS"
    COUNTING = "COUNTING"
    BOUNDING_BOX = "BOUNDING_BOX"
    TEXT = "TEXT"


class ResultTypeEnum(str, Enum):
    """Result type indicators."""
    BINARY_CLASSIFICATION = "BINARY_CLASSIFICATION"
    MULTI_CLASS_CLASSIFICATION = "MULTI_CLASS_CLASSIFICATION"
    COUNTING = "COUNTING"
    BOUNDING_BOX = "BOUNDING_BOX"
    TEXT = "TEXT"


class ImageQueryTypeEnum(str, Enum):
    """Image query type."""
    SYNC = "SYNC"
    ASYNC = "ASYNC"
```

---

### 3. Create `model/types.py`

Define supporting data types:

```python
"""Supporting type definitions."""

from typing import Optional
from pydantic import BaseModel, Field


class ROI(BaseModel):
    """Region of Interest in an image."""
    x: float = Field(..., description="X coordinate (top-left)")
    y: float = Field(..., description="Y coordinate (top-left)")
    width: float = Field(..., description="Width of ROI")
    height: float = Field(..., description="Height of ROI")
    confidence: Optional[float] = Field(None, description="Confidence score")


class Label(BaseModel):
    """Classification label."""
    id: str = Field(..., description="Label ID")
    name: str = Field(..., description="Label name")
    confidence: float = Field(..., description="Confidence score", ge=0.0, le=1.0)


class Source(BaseModel):
    """Source information for an image query."""
    source_id: Optional[str] = Field(None, description="Unique source identifier")
    source_type: Optional[str] = Field(None, description="Type of source (camera, upload, etc.)")
    metadata: Optional[dict] = Field(None, description="Additional source metadata")
```

---

### 4. Create `model/detector.py`

Define the Detector class:

```python
"""Detector model definition."""

from typing import Optional, List
from pydantic import BaseModel, Field
from .enums import ModeEnum


class Detector(BaseModel):
    """
    Detector configuration and metadata.

    Represents a detector in the IntelliOptics system.
    """
    id: str = Field(..., description="Unique detector ID", alias="detector_id")
    name: str = Field(..., description="Human-readable detector name")
    mode: ModeEnum = Field(..., description="Detection mode")
    confidence_threshold: float = Field(
        default=0.85,
        description="Confidence threshold for predictions",
        ge=0.0,
        le=1.0
    )
    class_names: Optional[List[str]] = Field(
        None,
        description="List of class names (for MULTICLASS mode)"
    )
    metadata: Optional[dict] = Field(
        None,
        description="Additional detector metadata"
    )

    class Config:
        populate_by_name = True  # Allow both 'id' and 'detector_id'
```

---

### 5. Create `model/results.py`

Define result classes:

```python
"""Result type definitions."""

from typing import Optional, List
from pydantic import BaseModel, Field
from .types import ROI, Label


class BinaryClassificationResult(BaseModel):
    """Result from binary classification."""
    label: str = Field(..., description="Predicted label (e.g., 'pass' or 'fail')")
    confidence: float = Field(..., description="Confidence score", ge=0.0, le=1.0)
    raw_confidence: Optional[float] = Field(
        None,
        description="Raw confidence before OODD adjustment"
    )
    is_out_of_domain: Optional[bool] = Field(
        None,
        description="Whether OODD detected out-of-domain image"
    )


class MultiClassificationResult(BaseModel):
    """Result from multi-class classification."""
    labels: List[Label] = Field(..., description="Predicted labels with confidence scores")
    top_label: str = Field(..., description="Highest confidence label")
    top_confidence: float = Field(..., description="Highest confidence score", ge=0.0, le=1.0)


class CountingResult(BaseModel):
    """Result from object counting."""
    count: int = Field(..., description="Number of objects detected", ge=0)
    confidence: float = Field(..., description="Confidence score", ge=0.0, le=1.0)
    rois: Optional[List[ROI]] = Field(None, description="Regions of interest for each detected object")
```

---

### 6. Create `model/configuration.py`

Define configuration classes:

```python
"""Configuration type definitions."""

from typing import Optional, List
from pydantic import BaseModel, Field


class CountModeConfiguration(BaseModel):
    """Configuration for counting mode detection."""
    min_count: Optional[int] = Field(None, description="Minimum count threshold", ge=0)
    max_count: Optional[int] = Field(None, description="Maximum count threshold", ge=0)
    count_threshold: Optional[float] = Field(
        None,
        description="Confidence threshold for counting",
        ge=0.0,
        le=1.0
    )


class MultiClassModeConfiguration(BaseModel):
    """Configuration for multi-class detection."""
    class_names: List[str] = Field(..., description="List of class names")
    top_k: Optional[int] = Field(
        None,
        description="Return top K predictions",
        ge=1
    )
    min_confidence: Optional[float] = Field(
        None,
        description="Minimum confidence for predictions",
        ge=0.0,
        le=1.0
    )
```

---

### 7. Create `model/image_query.py`

Define ImageQuery class:

```python
"""Image query model definition."""

from typing import Optional, Union
from datetime import datetime
from pydantic import BaseModel, Field
from .enums import ImageQueryTypeEnum, ResultTypeEnum
from .results import (
    BinaryClassificationResult,
    MultiClassificationResult,
    CountingResult,
)
from .types import Source


class ImageQuery(BaseModel):
    """
    Image query request/response.

    Represents an image query to the IntelliOptics API.
    """
    id: str = Field(..., description="Unique image query ID")
    detector_id: str = Field(..., description="Detector ID for this query")
    query_type: ImageQueryTypeEnum = Field(
        default=ImageQueryTypeEnum.SYNC,
        description="Query type (sync or async)"
    )
    result_type: Optional[ResultTypeEnum] = Field(
        None,
        description="Type of result returned"
    )
    result: Optional[Union[
        BinaryClassificationResult,
        MultiClassificationResult,
        CountingResult,
        dict
    ]] = Field(None, description="Query result")
    confidence: Optional[float] = Field(
        None,
        description="Overall confidence score",
        ge=0.0,
        le=1.0
    )
    source: Optional[Source] = Field(None, description="Source information")
    created_at: Optional[datetime] = Field(None, description="Query creation timestamp")
    metadata: Optional[dict] = Field(None, description="Additional metadata")
```

---

## Update SDK Package Configuration

### Update `pyproject.toml`

Add the `model` package to the package list:

```toml
[tool.poetry]
name = "intellioptics"
version = "0.2.1"  # Increment version
description = "IntelliOptics SDK for edge and cloud integration"
authors = ["Your Name <email@example.com>"]

[tool.poetry.packages]
packages = [
    { include = "intellioptics" },
    { include = "model" }  # ⭐ ADD THIS LINE
]

[tool.poetry.dependencies]
python = "^3.8"
httpx = ">=0.27"
pydantic = "^2.0"
typer = ">=0.12"
rich = ">=10.11.0"
# ... other dependencies

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
```

**OR** if using `setup.py`:

```python
from setuptools import setup, find_packages

setup(
    name="intellioptics",
    version="0.2.1",
    packages=find_packages(),  # This will automatically find both intellioptics/ and model/
    # OR explicitly list:
    # packages=["intellioptics", "model"],
    install_requires=[
        "httpx>=0.27",
        "pydantic>=2.0",
        "typer>=0.12",
        "rich>=10.11.0",
    ],
)
```

---

## Add Integration Tests

### Create `tests/test_imports.py`

```python
"""Test that all SDK modules import correctly."""

import pytest


def test_intellioptics_import():
    """Test that IntelliOptics client imports."""
    from intellioptics import IntelliOptics
    assert IntelliOptics is not None


def test_model_imports():
    """Test that all model types import successfully."""
    from model import (
        Detector,
        ImageQuery,
        ImageQueryTypeEnum,
        ModeEnum,
        ResultTypeEnum,
        BinaryClassificationResult,
        MultiClassificationResult,
        CountingResult,
        CountModeConfiguration,
        MultiClassModeConfiguration,
        ROI,
        Label,
        Source,
    )

    # Verify all imports are not None
    assert Detector is not None
    assert ImageQuery is not None
    assert ImageQueryTypeEnum is not None
    assert ModeEnum is not None
    assert ResultTypeEnum is not None
    assert BinaryClassificationResult is not None
    assert MultiClassificationResult is not None
    assert CountingResult is not None
    assert CountModeConfiguration is not None
    assert MultiClassModeConfiguration is not None
    assert ROI is not None
    assert Label is not None
    assert Source is not None


def test_detector_creation():
    """Test Detector model instantiation."""
    from model import Detector, ModeEnum

    detector = Detector(
        id="det_test_001",
        name="Test Detector",
        mode=ModeEnum.BINARY,
        confidence_threshold=0.85,
        class_names=["pass", "fail"]
    )

    assert detector.id == "det_test_001"
    assert detector.name == "Test Detector"
    assert detector.mode == ModeEnum.BINARY
    assert detector.confidence_threshold == 0.85


def test_image_query_creation():
    """Test ImageQuery model instantiation."""
    from model import ImageQuery, ImageQueryTypeEnum

    iq = ImageQuery(
        id="iq_test_001",
        detector_id="det_test_001",
        query_type=ImageQueryTypeEnum.SYNC
    )

    assert iq.id == "iq_test_001"
    assert iq.detector_id == "det_test_001"
    assert iq.query_type == ImageQueryTypeEnum.SYNC
```

---

## Verification Steps After Implementation

### 1. Build and Install Locally

```bash
cd IntelliOptics-SDK

# Build the package
python -m build
# OR
poetry build

# Install locally
pip install -e .
```

### 2. Test Imports

```bash
python -c "
from intellioptics import IntelliOptics
from model import Detector, ImageQuery
print('✅ All imports successful!')
print('Detector:', Detector)
print('ImageQuery:', ImageQuery)
"
```

### 3. Run Tests

```bash
pytest tests/test_imports.py -v
```

### 4. Test in Edge Deployment

After pushing to GitHub:

```bash
cd "C:\Dev\IntelliOptics 2.0\edge"

# Rebuild edge-api (will fetch updated SDK)
docker-compose build edge-api

# Restart services
docker-compose down && docker-compose up -d

# Verify SDK loaded successfully
docker-compose logs edge-api | grep -i "sdk"
# Should NOT see: "IntelliOptics SDK not available"
# Should NOT see: "IntelliOptics SDK model types not available"
```

### 5. Validate SDK Functionality

```bash
# Test import in container
docker exec intellioptics-edge-api python -c "
from intellioptics import IntelliOptics
from model import Detector, ImageQuery
print('✅ SDK fully functional!')
"
```

---

## Expected Outcome

After implementation, the SDK should:

1. ✅ Install successfully from GitHub
2. ✅ `from intellioptics import IntelliOptics` works
3. ✅ `from model import Detector, ImageQuery` works (currently fails)
4. ✅ All model types available for edge-api cloud integration
5. ✅ Edge-api can sync detector metadata from cloud
6. ✅ Edge-api can submit image queries to cloud API
7. ✅ No SDK warnings in edge-api logs

---

## Summary Checklist

- [ ] Create `model/` directory in SDK repository
- [ ] Add `model/__init__.py` with exports
- [ ] Add `model/enums.py` with enum types
- [ ] Add `model/types.py` with supporting types
- [ ] Add `model/detector.py` with Detector class
- [ ] Add `model/results.py` with result classes
- [ ] Add `model/configuration.py` with config classes
- [ ] Add `model/image_query.py` with ImageQuery class
- [ ] Update `pyproject.toml` to include `model` package
- [ ] Add `tests/test_imports.py` with integration tests
- [ ] Test locally before pushing
- [ ] Push to GitHub
- [ ] Increment version (0.2.0 → 0.2.1 or 0.3.0)
- [ ] Test in edge deployment

---

## Questions or Issues?

If any class structure or field is unclear, please reference:
- Pydantic documentation: https://docs.pydantic.dev/
- Edge-api usage in `C:\Dev\IntelliOptics 2.0\edge\edge-api\app\`
- IntelliOptics API documentation (if available)

The key principle: These are **Pydantic BaseModel classes** that represent the data structures used by the IntelliOptics API for communication between edge and cloud.
