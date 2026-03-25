# SDK Missing Types Analysis

**Date**: January 9, 2026
**SDK Version**: 0.2.1
**Issue**: `model` package imports fail due to missing types

---

## Problem Summary

The `model/__init__.py` that Codex created tries to import types from `intellioptics.models` that **don't actually exist** in the SDK:

```python
# THESE DON'T EXIST IN SDK:
from intellioptics.models import (
    CountModeConfiguration,      # ❌ NOT IN SDK
    MultiClassModeConfiguration,  # ❌ NOT IN SDK
    Label,                       # ❌ NOT IN SDK
    Source,                      # ❌ NOT IN SDK
)
```

**Error when importing:**
```
ImportError: cannot import name 'CountModeConfiguration' from 'intellioptics.models'
```

---

## What Actually Exists in SDK

**Types available in `intellioptics.models` (SDK v0.2.1):**

✅ **Core Types:**
- `Detector`
- `ImageQuery`

✅ **Enums:**
- `ImageQueryTypeEnum`
- `ModeEnum`
- `ResultTypeEnum`
- `ChannelEnum`
- `StatusEnum`
- `DetectorTypeEnum`
- `SnoozeTimeUnitEnum`
- `BlankEnum`

✅ **Result Types:**
- `BinaryClassificationResult`
- `MultiClassificationResult`
- `CountingResult`
- `BoundingBoxResult`
- `TextRecognitionResult`

✅ **Supporting Types:**
- `ROI`
- `Action`
- `ActionList`
- `Condition`
- `DetectorGroup`
- `FeedbackIn`
- `HTTPResponse`
- `PaginatedDetectorList`
- `PaginatedImageQueryList`
- `PaginatedRuleList`
- `PayloadTemplate`
- `QueryResult`
- `Rule`
- `UserIdentity`
- `WebhookAction`

❌ **Missing Types (used by edge-api but NOT in SDK):**
- `CountModeConfiguration`
- `MultiClassModeConfiguration`
- `Label`
- `Source`

---

## How Edge-API Uses Missing Types

### 1. `Source` Enum
**Usage in `app/core/utils.py:112`:**
```python
source = Source.ALGORITHM  # Results from edge model are always from algorithm
```
**Expected**: Enum with value `ALGORITHM`

### 2. `Label` Enum
**Usage in `app/core/utils.py:115`:**
```python
label = Label.NO if result_value else Label.YES
```
**Expected**: Enum with values `YES` and `NO`

### 3. `CountModeConfiguration` Class
**Usage in `app/core/utils.py:125`:**
```python
count_mode_configuration = CountModeConfiguration(**mode_configuration)
max_count = count_mode_configuration.max_count
```
**Expected**: Pydantic model with fields like `max_count`, `min_count`, `count_threshold`

### 4. `MultiClassModeConfiguration` Class
**Usage in `app/core/utils.py:142`:**
```python
multi_class_mode_configuration = MultiClassModeConfiguration(**mode_configuration)
multi_class_mode_configuration.class_names[result_value]
```
**Expected**: Pydantic model with field `class_names` (list of strings)

---

## Solution Options

### Option A: Add Missing Types to SDK (Recommended)

Update the SDK to include these missing types in `intellioptics/models.py`:

**File: `intellioptics/models.py`** (add to existing file)

```python
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class Source(str, Enum):
    """Source of a result."""
    ALGORITHM = "ALGORITHM"
    HUMAN = "HUMAN"
    UNKNOWN = "UNKNOWN"


class Label(str, Enum):
    """Binary classification labels."""
    YES = "YES"
    NO = "NO"


class CountModeConfiguration(BaseModel):
    """Configuration for counting mode detectors."""
    min_count: Optional[int] = Field(None, description="Minimum count threshold", ge=0)
    max_count: Optional[int] = Field(None, description="Maximum count threshold", ge=0)
    count_threshold: Optional[float] = Field(
        None,
        description="Confidence threshold for counting",
        ge=0.0,
        le=1.0
    )


class MultiClassModeConfiguration(BaseModel):
    """Configuration for multi-class detectors."""
    class_names: List[str] = Field(..., description="List of class names")
    top_k: Optional[int] = Field(None, description="Return top K predictions", ge=1)
    min_confidence: Optional[float] = Field(
        None,
        description="Minimum confidence for predictions",
        ge=0.0,
        le=1.0
    )
```

Then update `model/__init__.py` to import them:

**File: `model/__init__.py`** (replace current content)

```python
"""
IntelliOptics Model Types - Top-Level Package

Re-exports all model types from intellioptics.models for convenience.
"""

from intellioptics.models import (
    # Core Types
    Detector,
    ImageQuery,

    # Enums
    ImageQueryTypeEnum,
    ModeEnum,
    ResultTypeEnum,
    Source,               # ⭐ ADD THIS
    Label,                # ⭐ ADD THIS

    # Result Types
    BinaryClassificationResult,
    MultiClassificationResult,
    CountingResult,

    # Configuration Types
    CountModeConfiguration,         # ⭐ ADD THIS
    MultiClassModeConfiguration,    # ⭐ ADD THIS

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
    "Source",
    "Label",

    # Results
    "BinaryClassificationResult",
    "MultiClassificationResult",
    "CountingResult",

    # Configuration
    "CountModeConfiguration",
    "MultiClassModeConfiguration",

    # Supporting Types
    "ROI",
]
```

**Increment version to 0.2.2** in `pyproject.toml`:
```toml
version = "0.2.2"
```

---

### Option B: Create Local Fallbacks in Edge-API (Quick Fix)

Update `app/core/utils.py` to define these types locally when SDK doesn't have them:

```python
# IntelliOptics SDK model imports (optional - for cloud integration)
try:
    from model import (
        ROI, BinaryClassificationResult, CountingResult,
        ImageQuery, ImageQueryTypeEnum,
        ModeEnum, MultiClassificationResult,
        ResultTypeEnum,
    )
    # Try to import optional types
    try:
        from model import CountModeConfiguration, MultiClassModeConfiguration, Label, Source
    except ImportError:
        # Define fallbacks for missing types
        from enum import Enum
        from pydantic import BaseModel, Field
        from typing import List, Optional

        class Source(str, Enum):
            ALGORITHM = "ALGORITHM"
            HUMAN = "HUMAN"

        class Label(str, Enum):
            YES = "YES"
            NO = "NO"

        class CountModeConfiguration(BaseModel):
            min_count: Optional[int] = None
            max_count: Optional[int] = None
            count_threshold: Optional[float] = None

        class MultiClassModeConfiguration(BaseModel):
            class_names: List[str]
            top_k: Optional[int] = None
            min_confidence: Optional[float] = None

    MODEL_TYPES_AVAILABLE = True
except ImportError:
    # Full SDK not available - use all placeholders
    MODEL_TYPES_AVAILABLE = False
    # ... existing placeholder code ...
```

---

## Recommendation

**Use Option A** - Add the missing types to the SDK. This is the proper solution because:

1. ✅ These types are part of the IntelliOptics API domain model
2. ✅ They're used across multiple edge-api files
3. ✅ They provide type safety and validation (Pydantic)
4. ✅ Other SDK users will likely need them too
5. ✅ Keeps edge-api code clean

**Option B** is a temporary workaround if you can't update the SDK immediately.

---

## Next Steps

1. **Choose Option A or B**
2. **If Option A**: Give Codex the type definitions to add to SDK v0.2.2
3. **If Option B**: I'll update edge-api with local fallbacks right now

Which option would you like me to proceed with?
