# IntelliOptics SDK - Add Missing Types (v0.2.2)

**Purpose**: Add 4 missing types to SDK that are currently implemented as fallbacks in edge-api
**Target Version**: 0.2.2
**Repository**: https://github.com/thamain1/IntelliOptics-SDK

---

## Instructions for Codex/AI Assistant

Execute the following steps to add the missing types to the IntelliOptics SDK:

---

## STEP 1: Add Types to `intellioptics/models.py`

Open the file `intellioptics/models.py` and **add the following code at the end of the file** (after all existing class definitions):

```python
# ============================================================================
# Additional Types for Edge Integration
# ============================================================================

class Source(str, Enum):
    """
    Source of a result.

    Indicates where a prediction or label came from.
    """
    ALGORITHM = "ALGORITHM"  # Result from ML model
    HUMAN = "HUMAN"          # Result from human reviewer
    UNKNOWN = "UNKNOWN"      # Source unknown


class Label(str, Enum):
    """
    Binary classification labels.

    Standard labels for binary classification detectors.
    """
    YES = "YES"
    NO = "NO"


class CountModeConfiguration(BaseModel):
    """
    Configuration for counting mode detectors.

    Defines thresholds and constraints for object counting detectors.
    """
    min_count: Optional[int] = Field(
        None,
        description="Minimum count threshold",
        ge=0
    )
    max_count: Optional[int] = Field(
        None,
        description="Maximum count threshold",
        ge=0
    )
    count_threshold: Optional[float] = Field(
        None,
        description="Confidence threshold for counting",
        ge=0.0,
        le=1.0
    )

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "min_count": 1,
                "max_count": 10,
                "count_threshold": 0.8
            }
        }


class MultiClassModeConfiguration(BaseModel):
    """
    Configuration for multi-class classification detectors.

    Defines class names and prediction constraints for multi-class detectors.
    """
    class_names: List[str] = Field(
        ...,
        description="List of class names",
        min_length=2
    )
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

    class Config:
        """Pydantic config."""
        json_schema_extra = {
            "example": {
                "class_names": ["cat", "dog", "bird"],
                "top_k": 3,
                "min_confidence": 0.5
            }
        }
```

**Important**:
- Make sure to add this code **after all existing classes** but **before any `__all__` definition** (if one exists)
- Verify the imports at the top of `models.py` include:
  ```python
  from enum import Enum
  from typing import List, Optional
  from pydantic import BaseModel, Field
  ```
- If any of these imports are missing, add them

---

## STEP 2: Update `model/__init__.py`

Replace the **entire content** of `model/__init__.py` with this updated version:

```python
"""
IntelliOptics Model Types - Top-Level Package

This package provides convenient top-level access to all IntelliOptics model types.
Re-exports all model types from intellioptics.models for backwards compatibility.

Usage:
    from model import Detector, ImageQuery, ModeEnum

This is equivalent to:
    from intellioptics.models import Detector, ImageQuery, ModeEnum
"""

from intellioptics.models import (
    # Core Types
    Detector,
    ImageQuery,

    # Enums
    ImageQueryTypeEnum,
    ModeEnum,
    ResultTypeEnum,
    Source,
    Label,

    # Result Types
    BinaryClassificationResult,
    MultiClassificationResult,
    CountingResult,

    # Configuration Types
    CountModeConfiguration,
    MultiClassModeConfiguration,

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

---

## STEP 3: Update Version in `pyproject.toml`

Change the version number from `0.2.1.3` to `0.2.2`:

```toml
[tool.poetry]
name = "intellioptics"
version = "0.2.2"  # ⭐ CHANGE THIS LINE
description = "IntelliOptics SDK for edge and cloud integration"
```

---

## STEP 4: Test Locally Before Publishing

Run these commands to verify the changes work:

### 4a. Install SDK Locally

```bash
cd IntelliOptics-SDK
pip install -e .
```

### 4b. Test All Imports

```bash
python -c "
# Test basic SDK imports
from intellioptics import IntelliOptics
print('✅ IntelliOptics client imports')

# Test model types from intellioptics.models
from intellioptics.models import (
    Detector, ImageQuery, ModeEnum, ResultTypeEnum, ROI,
    BinaryClassificationResult, MultiClassificationResult, CountingResult,
    Source, Label, CountModeConfiguration, MultiClassModeConfiguration
)
print('✅ All types from intellioptics.models')

# Test top-level model package
from model import (
    Detector, ImageQuery, ModeEnum, ResultTypeEnum, ROI,
    BinaryClassificationResult, MultiClassificationResult, CountingResult,
    Source, Label, CountModeConfiguration, MultiClassModeConfiguration
)
print('✅ All types from model package')

print('')
print('Testing new types...')
print('Source.ALGORITHM:', Source.ALGORITHM)
print('Label.YES:', Label.YES)
print('Label.NO:', Label.NO)

# Test Pydantic models
config = CountModeConfiguration(min_count=1, max_count=10)
print('CountModeConfiguration:', config)

multi_config = MultiClassModeConfiguration(class_names=['cat', 'dog'])
print('MultiClassModeConfiguration:', multi_config)

print('')
print('🎉 ALL TESTS PASSED - SDK v0.2.2 is ready!')
"
```

**Expected output:**
```
✅ IntelliOptics client imports
✅ All types from intellioptics.models
✅ All types from model package

Testing new types...
Source.ALGORITHM: Source.ALGORITHM
Label.YES: Label.YES
Label.NO: Label.NO
CountModeConfiguration: min_count=1 max_count=10 count_threshold=None
MultiClassModeConfiguration: class_names=['cat', 'dog'] top_k=None min_confidence=None

🎉 ALL TESTS PASSED - SDK v0.2.2 is ready!
```

### 4c. Test Import Equivalence

Verify both import styles work identically:

```bash
python -c "
from model import Source as S1, Label as L1
from intellioptics.models import Source as S2, Label as L2

assert S1 is S2, 'Source classes should be identical!'
assert L1 is L2, 'Label classes should be identical!'

print('✅ Both import paths reference the same classes')
"
```

---

## STEP 5: Commit and Push to GitHub

If all tests pass, commit and push:

```bash
git add intellioptics/models.py model/__init__.py pyproject.toml
git commit -m "Add missing types to SDK (v0.2.2)

- Added Source enum (ALGORITHM, HUMAN, UNKNOWN) to intellioptics.models
- Added Label enum (YES, NO) to intellioptics.models
- Added CountModeConfiguration Pydantic model
- Added MultiClassModeConfiguration Pydantic model
- Updated model/__init__.py to export new types
- Bumped version to 0.2.2

These types were previously implemented as fallbacks in edge-api.
Now they are part of the core SDK.
"

git push origin main
```

---

## STEP 6: Verify GitHub Installation

After pushing, verify the SDK installs correctly from GitHub:

```bash
# Uninstall local version
pip uninstall intellioptics -y

# Install from GitHub
pip install git+https://github.com/thamain1/IntelliOptics-SDK@main

# Test imports again
python -c "
from model import Source, Label, CountModeConfiguration, MultiClassModeConfiguration
print('✅ SDK v0.2.2 installs from GitHub successfully!')
print('Source:', Source)
print('Label:', Label)
print('CountModeConfiguration:', CountModeConfiguration)
print('MultiClassModeConfiguration:', MultiClassModeConfiguration)
"
```

---

## Summary of Changes

### Files Modified

1. **`intellioptics/models.py`** - Added 4 new types (Source, Label, CountModeConfiguration, MultiClassModeConfiguration)
2. **`model/__init__.py`** - Updated to import and export the 4 new types
3. **`pyproject.toml`** - Bumped version from 0.2.1.3 to 0.2.2

### Types Added

**Enums:**
- `Source(str, Enum)` - ALGORITHM, HUMAN, UNKNOWN
- `Label(str, Enum)` - YES, NO

**Pydantic Models:**
- `CountModeConfiguration(BaseModel)` - Configuration for counting detectors
- `MultiClassModeConfiguration(BaseModel)` - Configuration for multi-class detectors

### Expected Version

- **Before**: v0.2.1.3 (types only available via fallbacks)
- **After**: v0.2.2 (types included in SDK)

---

## Troubleshooting

### Issue: "ImportError: cannot import name 'Source'"

**Solution**: Make sure you added the code to `intellioptics/models.py` and that the imports at the top include `from enum import Enum`

### Issue: "NameError: name 'Optional' is not defined"

**Solution**: Add to imports at top of `intellioptics/models.py`:
```python
from typing import List, Optional
```

### Issue: "NameError: name 'Field' is not defined"

**Solution**: Add to imports at top of `intellioptics/models.py`:
```python
from pydantic import BaseModel, Field
```

### Issue: Tests pass locally but fail from GitHub

**Solution**:
1. Verify you committed all changes: `git status`
2. Verify you pushed to main: `git log origin/main -1`
3. Wait 30 seconds for GitHub to update, then try again

---

## Next Steps After Publishing

Once SDK v0.2.2 is published to GitHub, notify the edge-api team to:

1. Update edge-api to use SDK v0.2.2
2. Remove local fallback code from `app/core/utils.py`
3. Remove patching code from `app/escalation_queue/__init__.py`
4. Test that all imports work from SDK directly

The edge-api should then be able to import all types directly from the SDK without any local fallbacks.
