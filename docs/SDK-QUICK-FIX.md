# IntelliOptics SDK Quick Fix - Add `model` Module

**What's Missing**: The SDK is missing a `model` Python package
**Where**: https://github.com/thamain1/IntelliOptics-SDK
**Impact**: Cloud integration features disabled in edge deployment

---

## Quick Fix (5 Steps)

### 1️⃣ Create `model/` Directory

In your SDK repository root, create a new directory:

```
IntelliOptics-SDK/
├── intellioptics/     # Already exists ✅
├── model/            # ⭐ ADD THIS
└── pyproject.toml
```

### 2️⃣ Add Required Files

Create these 7 files in the `model/` directory:

```
model/
├── __init__.py          # Exports all classes
├── detector.py          # Detector class
├── image_query.py       # ImageQuery class
├── results.py           # Result classes
├── enums.py            # Enum types
├── configuration.py    # Config classes
└── types.py            # Supporting types (ROI, Label, Source)
```

### 3️⃣ Update Package Configuration

**If using `pyproject.toml`**:
```toml
[tool.poetry.packages]
packages = [
    { include = "intellioptics" },
    { include = "model" }  # ⭐ ADD THIS LINE
]
```

**If using `setup.py`**:
```python
packages=["intellioptics", "model"]  # Add "model"
```

### 4️⃣ Key Classes to Include

The `model` module must export these 13 classes/types:

```python
# model/__init__.py
from .detector import Detector
from .image_query import ImageQuery
from .enums import ImageQueryTypeEnum, ModeEnum, ResultTypeEnum
from .results import BinaryClassificationResult, MultiClassificationResult, CountingResult
from .configuration import CountModeConfiguration, MultiClassModeConfiguration
from .types import ROI, Label, Source

__all__ = [
    "Detector", "ImageQuery",
    "ImageQueryTypeEnum", "ModeEnum", "ResultTypeEnum",
    "BinaryClassificationResult", "MultiClassificationResult", "CountingResult",
    "CountModeConfiguration", "MultiClassModeConfiguration",
    "ROI", "Label", "Source"
]
```

### 5️⃣ Test Before Publishing

```bash
# Install locally
pip install -e .

# Test imports
python -c "
from model import Detector, ImageQuery
print('✅ SUCCESS!')
"
```

---

## Example: Minimal Detector Class

```python
# model/detector.py
from pydantic import BaseModel, Field
from .enums import ModeEnum

class Detector(BaseModel):
    """Detector configuration."""
    id: str = Field(..., alias="detector_id")
    name: str
    mode: ModeEnum
    confidence_threshold: float = 0.85

    class Config:
        populate_by_name = True
```

---

## Example: Minimal Enums

```python
# model/enums.py
from enum import Enum

class ModeEnum(str, Enum):
    BINARY = "BINARY"
    MULTICLASS = "MULTICLASS"
    COUNTING = "COUNTING"

class ResultTypeEnum(str, Enum):
    BINARY_CLASSIFICATION = "BINARY_CLASSIFICATION"
    MULTI_CLASS_CLASSIFICATION = "MULTI_CLASS_CLASSIFICATION"

class ImageQueryTypeEnum(str, Enum):
    SYNC = "SYNC"
    ASYNC = "ASYNC"
```

---

## Verification

After publishing to GitHub, this should work:

```bash
# Install from GitHub
pip install git+https://github.com/thamain1/IntelliOptics-SDK@main

# Test
python -c "
from intellioptics import IntelliOptics  # ✅ Already works
from model import Detector, ImageQuery   # ✅ Should work after fix
print('✅ SDK Complete!')
"
```

---

## Full Implementation Guide

See **SDK-MODEL-MODULE-GUIDE.md** for:
- Complete class implementations with all fields
- Pydantic model examples
- Full test suite
- Detailed verification steps

---

## Why This Matters

**Current State**:
```
Edge Deployment: ✅ Running
Cloud Integration: ❌ Disabled (SDK incomplete)
```

**After Fix**:
```
Edge Deployment: ✅ Running
Cloud Integration: ✅ Enabled (SDK complete)
```

The `model` module provides the **data types** (Pydantic models) that represent the IntelliOptics API structures used for communication between edge and cloud.
